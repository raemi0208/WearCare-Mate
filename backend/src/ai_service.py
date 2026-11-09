"""Real AI routes for the private integration-test Lambda.

Enabling these routes on a public API requires authentication separately.
ML_TARGET_DATE deliberately pins the dataset day; never interpret old data as today.
"""

import os
from datetime import date

from src.dashboard_data import build_real_dashboard, fetch_dashboard_activity_items
from src.dashboard_service import (
    build_steps_summary_card, build_steps_timeseries, collect_daily_steps,
    compute_weekly_steps,
)
from src.data_source import DataSourceUnavailableError
from src.ml_adapter import (
    TargetNotEligibleError, build_detection_request, collect_daily_tracked_minutes,
    step_anomaly_dates, summarize_detection,
)
from src.ml_client import MLClient, MLConfig, create_lambda_client
from src.real_health_data import get_allowed_user_id, is_real_data_testing_enabled


def _load_result(environ=None, athena_client_factory=None, ml_client_factory=None):
    env = os.environ if environ is None else environ
    # Check all switches before reading data or constructing an AWS client.
    if (env.get("DATA_SOURCE", "").strip().lower() != "real"
            or not is_real_data_testing_enabled(env)):
        raise DataSourceUnavailableError("실제 AI 테스트가 활성화되어 있지 않습니다.")
    raw_day = env.get("ML_TARGET_DATE", "")
    try:
        target = date.fromisoformat(raw_day)
        if target.isoformat() != raw_day or raw_day == "2016-04-12":
            raise ValueError
    except (TypeError, ValueError):
        raise DataSourceUnavailableError("검증할 데이터 기준일을 설정해야 합니다.") from None

    user_id = get_allowed_user_id(env)
    config = MLConfig.from_env(env)
    items = fetch_dashboard_activity_items(client_factory=athena_client_factory, environ=env)
    try:
        request = build_detection_request(
            user_id, target, collect_daily_steps(items), excluded_dates=("2016-04-12",),
            daily_tracked_minutes=collect_daily_tracked_minutes(items),
            # /dashboard·/ai-guide 조회·재조회 경로는 SNS 발송 안 함 → notify=False 고정 (v0.5).
            # 같은 요청을 재시도해도 notify=False 가 유지된다. 발송 허용 일일 평가 경로는 별도 작업.
            notify=False,
        )
    except TargetNotEligibleError:
        raise DataSourceUnavailableError("기준일에 판정 가능한 걸음 수가 없습니다.") from None
    factory = ml_client_factory or create_lambda_client
    result = MLClient(factory(config), config).invoke_detection(request)
    return items, result, env


def guide_for_frontend(result):
    """Preserve frontend's model/updatedAt/headline/text/actions fields.

    guide.lines 는 lines 로 그대로 전달한다(줄별 표시용). alertSent 는 AI/ML 의 SNS 발송 여부
    (true/false/null), alertReason 은 발송/미발송 사유(v0.5, 없으면 null)를 표시·로그용으로 넘긴다.
    백엔드는 SNS 를 직접 발송하지 않는다. guide 가 null 이어도 alertSent·alertReason 은 보존한다.
    """
    guide = result["guide"]
    summary = summarize_detection(result)
    common = {
        "status": summary["guideState"], "analysisStatus": result["status"],
        "referenceDate": result["date"],
        "updatedAt": guide["generated_at"] if guide else "생성된 가이드 없음",
        "warnings": list(guide["warnings"]) if guide else [],
        "alertSent": summary["alertSent"],
        "alertReason": summary["alertReason"],
    }
    if guide:
        lines = guide["lines"]
        return dict(common, model="Amazon Bedrock · " + guide["model_id"],
                    headline=lines[0], text=guide["text"], actions=lines[1:2],
                    lines=list(lines))
    if result["status"] == "normal":
        headline = "선택한 날짜의 활동량에서 이상 감소가 감지되지 않았어요."
        text = "걸음 수 기준 판정이며, 다른 건강 지표의 정상 여부를 의미하지 않아요."
    elif result["status"] == "insufficient_data":
        headline = "활동량을 판정할 과거 기록이 부족해요."
        text = "데이터 부족 상태이며 정상 판정이나 AI 가이드 생성 결과가 아니에요."
    else:
        headline = "활동량 이상이 감지됐지만 가이드를 생성하지 못했어요."
        text = "이상 탐지 결과는 확인됐어요. 가이드 생성은 다시 시도해 주세요."
    return dict(common, model="활동량 분석 · 생성형 가이드 없음",
                headline=headline, text=text, actions=[])


def anomalies_for_frontend(result):
    severity = {"low": "warn", "medium": "warn", "high": "danger"}
    titles = {"ACTIVITY_DROP": "평소 대비 걸음 수 감소"}
    return [{
        "id": f"{result['date']}-{index}",
        "severity": severity[item["severity"]],
        "title": titles.get(item["type"], "지표 이상 감지"),
        "time": result["date"],
        # 걸음 수 단위는 AI/ML v0.4(origin/ai-ml @ 1956156a)와 같은 "걸음"으로 통일한다.
        # (카드·차트·예시 데이터의 "보" 단위는 별도 범위)
        "desc": (f"기준일 걸음 수 {item['value']:,.0f}걸음 · "
                 f"과거 기록 평균 {item['baseline_mean']:,.0f}걸음")
                 if item["type"] == "ACTIVITY_DROP" else "AI/ML 지표 판정 결과입니다.",
    } for index, item in enumerate(result["anomalies"])]


def build_ai_guide(environ=None, athena_client_factory=None, ml_client_factory=None):
    _, result, _ = _load_result(environ, athena_client_factory, ml_client_factory)
    return guide_for_frontend(result)


def build_ai_dashboard(environ=None, athena_client_factory=None, ml_client_factory=None,
                       summary_client_factory=None):
    items, result, env = _load_result(environ, athena_client_factory, ml_client_factory)
    # Keep dashboard statistics in the target day's week, excluding later records.
    items = [item for item in items if item["date"] <= result["date"]]
    # 데이터셋 요약 집계는 build_real_dashboard 안에서 ENABLE_DATASET_SUMMARY=true 일 때만 수행된다.
    # /ai-guide(build_ai_guide)는 build_real_dashboard 를 호출하지 않으므로 집계가 실행되지 않는다.
    body = build_real_dashboard(environ=env, activity_items=items,
                                summary_client_factory=summary_client_factory)
    stats = compute_weekly_steps(items)
    card = build_steps_summary_card(stats)
    body["summaryStats"] = [card] if card else []
    body["timeseries"]["steps"] = build_steps_timeseries(
        stats, anomaly_dates=step_anomaly_dates([result])
    )
    body["anomalies"] = anomalies_for_frontend(result)
    body["aiGuide"] = guide_for_frontend(result)
    # No devices, persisted guide history, or SNS records have been connected.
    body["devices"] = []
    body["guideHistory"] = []
    body["notifications"] = []
    body["analysis"] = {
        "referenceDate": result["date"], "status": result["status"],
        "overallSeverity": result["overall_severity"],
        "evaluatedDates": [result["date"]],
        "note": "선택한 날짜의 걸음 수만 판정했습니다. 다른 날짜는 판정하지 않았습니다.",
    }
    return body
