"""Console-only integration probe; do not attach this handler to API Gateway.

실제 Athena 데이터로 백엔드 → AI/ML 경로를 날짜별로 검증하는 콘솔 전용 도구입니다.
AWS 런타임 서비스 핸들러(`src.lambda_function.lambda_handler`)와 별개이며, 공개 HTTP 경로에 연결하지 마세요.

콘솔 이벤트:
    {"target_date": "2016-04-10"}  또는  {"target_date": "2016-04-12"}
    - 허용 날짜는 ALLOWED_TARGET_DATES 두 개뿐입니다. 그 외 날짜·형식은 ML 호출 전에 거절합니다.
    - 사용자는 기존 테스트 사용자(real_health_data.get_allowed_user_id, 보통 DASHBOARD_USER_ID)만 씁니다.
    - API Gateway 형식 이벤트는 ML 호출 전에 거절(REFUSED)합니다.
    - target_date 를 주지 않으면 기본값 2016-04-10.

기존 로직 재사용 (변환 로직을 복제하지 않음):
    - Athena 조회·매핑: real_health_data.build_real_health_data (활동 4개 컬럼 + 비활동 포함)
    - 날짜별 걸음 수: dashboard_service.collect_daily_steps
    - 날짜별 기록 시간 합계: ml_adapter.collect_daily_tracked_minutes
      (mappers 가 very/fairly/lightly/sedentary 네 값이 모두 유효할 때만 activity.trackedMinutes 를 만든다)
    - 요청 생성: ml_adapter.build_detection_request (최상위 notify=false, metrics.tracked_minutes 포함)
    - 응답 검증·요약: ml_client.invoke_detection, ml_adapter.summarize_detection

4월 12일 처리:
    - 일반 API(ai_service._load_result)는 2016-04-12 를 "기준일 선택"에서 제외한다
      (build_detection_request(excluded_dates=("2016-04-12",)) 그리고 ML_TARGET_DATE=2016-04-12 거부).
      제외는 조회나 과거 이력이 아니라 "기준일 선택" 단계에만 적용된다. Athena 조회는 날짜 필터 없이
      사용자의 모든 행을 읽으므로 04-12 행도 items 에 들어온다.
    - 이 콘솔 검증은 excluded_dates 를 비워 **4월 12일을 명시적으로 기준일로 조회**할 수 있게 한다.
      일반 API 의 04-12 제외 동작은 바꾸지 않는다(이 파일은 콘솔 전용 핸들러일 뿐).

기대 비교값 (결과 비교용, 요청 값은 Athena 에서 읽은 값으로 구성):
    - 2016-04-10: 기록 시간 962분 · 걸음 10,057 → 기록 시간 ≥ 800 → 걸음 수 판정 대상(normal 이어도 됨)
    - 2016-04-12: 기록 시간 41분 · 걸음 224 → 기록 시간 < 800 → 걸음 수(ACTIVITY_DROP) 판정 제외
"""

from datetime import date

from src.dashboard_service import collect_daily_steps
from src.ml_adapter import (
    STEP_ANOMALY_TYPE,
    MLRequestError,
    TargetNotEligibleError,
    build_detection_request,
    collect_daily_tracked_minutes,
    summarize_detection,
)
from src.ml_client import MLClient, MLConfig, create_lambda_client
from src.real_health_data import build_real_health_data, get_allowed_user_id

TEST_NAME = "athena-real-data-boundary-check"

# 콘솔에서만 허용하는 기준일. (데모·통합 기준일은 2016-04-11 이전이지만, 04-12 는 부분 수집 방어 검증용)
ALLOWED_TARGET_DATES = ("2016-04-10", "2016-04-12")

# 기록 시간 800분 미만이면 AI/ML 이 걸음 수(ACTIVITY_DROP) 판정을 건너뛴다 (명세 11번).
MIN_TRACKED_MINUTES = 800

# 결과 비교용 기대값 (요청 값 자체는 Athena 조회 결과로 구성한다)
EXPECTED = {
    "2016-04-10": {"trackedMinutes": 962, "steps": 10057},
    "2016-04-12": {"trackedMinutes": 41, "steps": 224},
}


def _is_api_gateway_event(event):
    return isinstance(event, dict) and any(
        key in event for key in ("requestContext", "routeKey", "rawPath", "httpMethod")
    )


def _base(**fields):
    body = {
        "test": TEST_NAME,
        "inputKind": "athena-real",
        "note": ("실제 Athena 데이터로 날짜별 백엔드→AI/ML 경로를 검증합니다. 콘솔 전용. "
                 "요청 값은 Athena 조회 결과로 구성하고, 기대 비교값(962/10057, 41/224)은 참고용입니다."),
    }
    body.update(fields)
    return body


def _daily_from_items(items):
    """items(real_health_data 응답의 items)에서 날짜별 걸음 수·기록 시간 합계를 만든다. (기존 함수 재사용)"""
    daily_steps = collect_daily_steps(items)
    daily_tracked = collect_daily_tracked_minutes(items)
    return daily_steps, daily_tracked


def run_real_data_check(target_date, lambda_client_factory=None, environ=None):
    """허용된 한 날짜만 실제 Athena 데이터로 조회해 ML 을 한 번 호출하고 결과를 돌려준다.

    - 허용 날짜(ALLOWED_TARGET_DATES) 외/형식 오류는 ML 호출 전에 거절(REJECTED, 400).
    - 요청 최상위에 notify=false, metrics.tracked_minutes(Athena 합계)를 넣는다.
    - 4월 12일도 이 콘솔 경로에서는 기준일로 쓸 수 있다(excluded_dates 비움).
    """
    base = {"targetDate": target_date, **_base()}

    # 허용 날짜·형식 검증 (AWS/ML 호출 전)
    if not (isinstance(target_date, str) and target_date in ALLOWED_TARGET_DATES):
        return dict(statusCode=400, verdict="REJECTED", mlInvoked=False,
                    supported=list(ALLOWED_TARGET_DATES), **base)
    try:
        target = date.fromisoformat(target_date)
    except (TypeError, ValueError):
        return dict(statusCode=400, verdict="REJECTED", mlInvoked=False,
                    supported=list(ALLOWED_TARGET_DATES), **base)

    env = environ
    user_id = get_allowed_user_id(env)  # 기존 테스트 사용자만

    # Athena 조회·매핑 (기존 로직). 날짜 필터 없이 사용자 전체 행을 읽는다.
    health = build_real_health_data(user_id, {}, environ=env)
    items = health.get("items", [])
    daily_steps, daily_tracked = _daily_from_items(items)

    # 요청 생성: 이 콘솔 경로는 excluded_dates 를 비워 04-12 도 기준일로 허용한다.
    try:
        request = build_detection_request(
            user_id, target, daily_steps,
            daily_tracked_minutes=daily_tracked,
            notify=False,  # 실제 ML 요청 최상위 notify=false (SNS 미발송)
        )
    except TargetNotEligibleError as error:
        return dict(statusCode=422, verdict="FAIL", stage="build_request",
                    reason=error.reason, mlInvoked=False, **base)
    except MLRequestError as error:
        return dict(statusCode=400, verdict="FAIL", stage="build_request",
                    errorType=type(error).__name__, mlInvoked=False, **base)

    sent_steps = request["metrics"].get("steps")
    sent_tracked = request["metrics"].get("tracked_minutes")
    expected = EXPECTED.get(target_date, {})

    # 모듈 속성으로 참조해 테스트에서 패치 가능하게 한다. (기본 create_lambda_client)
    factory = lambda_client_factory if lambda_client_factory is not None else create_lambda_client
    try:
        config = MLConfig.from_env(env)
        client = MLClient(factory(config), config)
    except Exception as error:  # noqa: BLE001 - 설정 오류도 실패로 보고(ML 미호출)
        return dict(statusCode=500, verdict="FAIL", stage="config",
                    mlInvoked=False, errorType=type(error).__name__,
                    sentSteps=sent_steps, sentTrackedMinutes=sent_tracked, **base)

    # ML 을 정확히 한 번 호출한다.
    try:
        result = client.invoke_detection(dict(request))
    except Exception as error:  # noqa: BLE001 - 호출·검증 실패는 FAIL (대체 응답 없음)
        return dict(statusCode=502, verdict="FAIL", stage="invoke_or_validate",
                    mlInvoked=True, errorType=type(error).__name__,
                    sentSteps=sent_steps, sentTrackedMinutes=sent_tracked, **base)

    summary = summarize_detection(result)
    step_judged = any(a["type"] == STEP_ANOMALY_TYPE for a in result["anomalies"])
    below_threshold = isinstance(sent_tracked, int) and sent_tracked < MIN_TRACKED_MINUTES
    # 41분 케이스: 걸음 수 판정 제외 근거 = 기록 시간<800 이면서 ACTIVITY_DROP 없음
    step_judgment_skipped = below_threshold and not step_judged

    return dict(
        statusCode=200,
        verdict="OK",
        mlInvoked=True,
        request={
            "user_id": request["user_id"], "date": request["date"],
            "metrics": request["metrics"], "notify": request["notify"],
        },
        sentSteps=sent_steps,
        sentTrackedMinutes=sent_tracked,
        expected=expected,
        matchesExpectedSteps=(sent_steps == expected.get("steps")),
        matchesExpectedTrackedMinutes=(sent_tracked == expected.get("trackedMinutes")),
        trackedMinutesBelowThreshold=below_threshold,
        ml={
            "status": result["status"],
            "overallSeverity": result["overall_severity"],
            "stepAnomalyDetected": step_judged,
            "anomalyTypes": [a["type"] for a in result["anomalies"]],
        },
        # 41분 케이스에서 걸음 수 판정이 제외됐는지 응답으로 확인할 근거
        stepJudgmentSkipped=step_judgment_skipped,
        alertSent=summary["alertSent"],
        alertReason=summary["alertReason"],
        **base,
    )


def lambda_handler(event, context):
    # API Gateway 형식 이벤트는 ML 호출 전에 거절한다. 콘솔 전용 도구.
    if _is_api_gateway_event(event):
        return {"statusCode": 403, "test": TEST_NAME, "verdict": "REFUSED",
                "note": "콘솔 전용 도구입니다. API Gateway 에 연결하지 마세요."}
    target_date = event.get("target_date", "2016-04-10") if isinstance(event, dict) else "2016-04-10"
    return run_real_data_check(target_date)
