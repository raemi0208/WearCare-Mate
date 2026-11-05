"""Console-only probe: virtual anomaly input -> real AI/ML Lambda -> backend screen conversion.

콘솔 전용 검증 도구입니다. API Gateway 라우트에 연결하지 마세요.

- 입력은 고정된 **가상 값**입니다. Athena, 실제 사용자 데이터, 2016-04-12 데이터를 쓰지 않습니다.
- AI/ML 요청은 실제 AI/ML 인터페이스(origin/ai-ml 4732493c, AI_ML/lambda_handler.py)를 따릅니다.
  요청에 history_steps 가 있으면 AI/ML Lambda 는 Athena 를 조회하지 않고 그 값을 기준선으로 씁니다.
- 응답 검증과 화면용 변환은 기존 함수를 그대로 씁니다. (변환 로직을 복제하지 않음)
    MLClient.invoke_detection  -> unwrap + validate_detection_result
    summarize_detection        -> guide 상태 구분
    ai_service.guide_for_frontend / anomalies_for_frontend -> 화면용 변환
- 호출 실패, 이상 미판정, 가이드 없음은 verdict=FAIL 로 돌려줍니다. 예시 가이드로 대체하지 않습니다.

환경변수: ML_FUNCTION_NAME (필수), ML_REGION (기본 ap-northeast-2), ML_TIMEOUT_SECONDS (기본 15)
"""

from src.ai_service import anomalies_for_frontend, guide_for_frontend
from src.ml_adapter import STEP_ANOMALY_TYPE, summarize_detection
from src.ml_client import MLClient, MLConfig, MLErrorResponse, create_lambda_client

TEST_NAME = "virtual-anomaly-ml-guide-check"
INPUT_KIND = "virtual"  # 가상 입력. Athena 실제 데이터 아님.

# 이전에 AI/ML 단독으로 검증한 가상 입력 (필드 이름과 형식은 AI/ML lambda_handler 기준)
VIRTUAL_REQUEST = {
    "user_id": "test-user",
    "date": "2026-10-30",
    "metrics": {"steps": 1000},
    "history_steps": [10000, 10500, 9800, 10200, 10100, 9900],
}

# ---------------------------------------------------------------------------
# 기록 시간(tracked_minutes) 경계 검증용 가상 입력 (AI/ML v0.4)
# ---------------------------------------------------------------------------
# 사용자·날짜·걸음 수·과거 기록은 VIRTUAL_REQUEST 와 동일하게 두고 metrics.tracked_minutes 만 바꾼다.
# 800 분 미만이면 걸음 수 판정을 건너뛴다는 규칙은 AI/ML 쪽 책임이다. 백엔드는 값을 그대로 전달한다.
#   - 799 분: 기록 시간 기준 미달 → 걸음 수(ACTIVITY_DROP) 판정을 건너뛰는 것이 기대 결과.
#   - 800 분: 기준 통과 → 걸음 수 판정 대상이 되는 것이 기대 결과.
#     (가이드 생성·SNS 발송은 경계 테스트의 필수 통과 조건이 아니다.)
# ⚠️ 실제 "판정 제외 시 응답 형식"과 alert_sent 위치는 담당자 v0.4 명세·실제 응답으로 확정해야 한다.
TRACKED_MINUTES_BELOW = 799
TRACKED_MINUTES_AT = 800

TRACKED_MINUTES_CASES = (
    {
        "name": "below_threshold_799",
        "trackedMinutes": TRACKED_MINUTES_BELOW,
        "expectation": "stepJudgmentSkipped",  # 걸음 수 판정 건너뜀 (기대)
        "note": "기록 시간 799분(<800)이라 걸음 수 판정을 건너뛰는 것이 기대 결과. 판정 제외 응답 형식은 v0.4 확정 필요.",
    },
    {
        "name": "at_threshold_800",
        "trackedMinutes": TRACKED_MINUTES_AT,
        "expectation": "stepJudged",  # 걸음 수 판정 대상 (기대). 가이드/SNS 는 필수 아님
        "note": "기록 시간 800분(=기준)이라 걸음 수 판정 대상이 되는 것이 기대 결과. 가이드 생성·SNS 발송은 필수 통과 조건 아님.",
    },
)


def build_tracked_minutes_request(tracked_minutes):
    """VIRTUAL_REQUEST 와 user_id·date·steps·history_steps 는 같고 metrics.tracked_minutes 만 더한 요청."""
    request = dict(VIRTUAL_REQUEST)
    request["metrics"] = dict(VIRTUAL_REQUEST["metrics"], tracked_minutes=tracked_minutes)
    return request


def _is_api_gateway_event(event):
    return isinstance(event, dict) and any(
        key in event for key in ("requestContext", "routeKey", "rawPath", "httpMethod")
    )


def _base(**fields):
    body = {
        "test": TEST_NAME,
        "inputKind": INPUT_KIND,
        "note": "가상 입력 기반 검증입니다. Athena 실제 데이터와 공개 API 경로는 포함하지 않습니다.",
        "request": VIRTUAL_REQUEST,
    }
    body.update(fields)
    return body


def _failure(status_code, stage, error, ml_invoked):
    fields = {"verdict": "FAIL", "stage": stage, "mlInvoked": ml_invoked,
              "errorType": type(error).__name__}
    if isinstance(error, MLErrorResponse):
        fields.update(mlStatusCode=error.status_code, mlErrorCode=error.error_code)
    return dict(statusCode=status_code, **_base(**fields))


def run_check(lambda_client_factory=create_lambda_client, environ=None):
    """가상 입력으로 실제 AI/ML 을 호출하고 백엔드 변환까지 확인한 결과를 돌려준다."""
    try:
        config = MLConfig.from_env(environ)
        client = MLClient(lambda_client_factory(config), config)
    except Exception as error:  # noqa: BLE001 - 설정 오류도 실패로 보고
        return _failure(500, "config", error, ml_invoked=False)

    try:
        result = client.invoke_detection(dict(VIRTUAL_REQUEST))
    except Exception as error:  # noqa: BLE001 - 호출·응답 검증 실패는 FAIL (대체 응답 없음)
        return _failure(502, "invoke_or_validate", error, ml_invoked=True)

    summary = summarize_detection(result)
    screen_guide = guide_for_frontend(result)
    screen_anomalies = anomalies_for_frontend(result)
    guide = result["guide"]
    warnings = list(guide["warnings"]) if guide else []

    checks = {
        "mlResponseValid": True,
        "statusIsAnomaly": result["status"] == "anomaly",
        "stepAnomalyDetected": any(a["type"] == STEP_ANOMALY_TYPE for a in result["anomalies"]),
        "guideGenerated": summary["guideState"] == "generated",
        "screenGuideGenerated": screen_guide.get("status") == "generated",
        "screenGuideHasActions": bool(screen_guide.get("actions")),
    }
    if not all(checks.values()):
        verdict = "FAIL"
    elif warnings:
        verdict = "PASS_WITH_WARNINGS"  # 명세 8번: warnings 가 있어도 표시는 가능
    else:
        verdict = "PASS"

    return dict(statusCode=200 if verdict != "FAIL" else 422, **_base(
        verdict=verdict,
        mlInvoked=True,
        checks=checks,
        ml={
            "status": result["status"],
            "overallSeverity": result["overall_severity"],
            "anomalies": [
                {"type": a["type"], "severity": a["severity"], "value": a["value"],
                 "baselineMean": a.get("baseline_mean"), "zScore": a["z_score"],
                 "dropPct": a.get("drop_pct")}
                for a in result["anomalies"]
            ],
            "guideGenerated": guide is not None,
            "guideModelId": guide["model_id"] if guide else None,
            "guideWarnings": warnings,
            "modelVersion": result["model_version"],
        },
        screen={"aiGuide": screen_guide, "anomalies": screen_anomalies},
    ))


BOUNDARY_TEST_NAME = "tracked-minutes-boundary-check"


def _boundary_base(**fields):
    body = {
        "test": BOUNDARY_TEST_NAME,
        "inputKind": INPUT_KIND,
        "note": ("기록 시간(tracked_minutes) 경계 검증입니다. 800분 미만 걸음 수 판정 제외는 AI/ML 규칙이며, "
                 "백엔드는 799/800 값을 그대로 전달만 합니다. 판정 제외 시 응답 형식과 alert_sent 위치는 "
                 "담당자 v0.4 명세·실제 응답으로 확정해야 합니다."),
    }
    body.update(fields)
    return body


def _observe_case(case, client):
    """경계 입력 1건을 보내고, 걸음 수 판정 여부를 관찰해 기록한다. (가이드/SNS 를 통과 조건으로 삼지 않음)"""
    request = build_tracked_minutes_request(case["trackedMinutes"])
    observed = {
        "name": case["name"],
        "trackedMinutes": case["trackedMinutes"],
        "expectation": case["expectation"],
        "request": request,
        "note": case["note"],
    }
    try:
        result = client.invoke_detection(dict(request))
    except Exception as error:  # noqa: BLE001 - 호출·검증 실패는 관찰 실패로 기록 (대체 응답 없음)
        observed.update(invoked=True, observeError=type(error).__name__)
        if isinstance(error, MLErrorResponse):
            observed.update(mlStatusCode=error.status_code, mlErrorCode=error.error_code)
        return observed

    summary = summarize_detection(result)
    step_judged = any(a["type"] == STEP_ANOMALY_TYPE for a in result["anomalies"])
    # 기대: 799 → 건너뜀(판정 안 함), 800 → 판정 대상(이 가상 입력은 급감이라 ACTIVITY_DROP 기대)
    expected_step_judged = case["expectation"] == "stepJudged"
    observed.update(
        invoked=True,
        mlStatus=result["status"],
        overallSeverity=result["overall_severity"],
        stepAnomalyJudged=step_judged,
        guideState=summary["guideState"],
        # 관찰값이 기대와 맞는지. 실제 v0.4 응답을 받기 전까지는 참고용 비교다.
        matchesExpectation=(step_judged == expected_step_judged),
    )
    return observed


def run_tracked_minutes_boundary_check(lambda_client_factory=create_lambda_client, environ=None):
    """799/800 두 입력을 보내 걸음 수 판정 경계를 관찰한다. (실제 판정은 AI/ML 책임)

    가이드 생성·SNS 발송을 통과 조건으로 삼지 않는다. 걸음 수 판정 여부만 관찰해 기대와 비교한다.
    실제 v0.4 응답을 받기 전에는 로컬 관찰 결과로만 본다.
    """
    try:
        config = MLConfig.from_env(environ)
        client = MLClient(lambda_client_factory(config), config)
    except Exception as error:  # noqa: BLE001
        return dict(statusCode=500, **_boundary_base(
            stage="config", errorType=type(error).__name__, mlInvoked=False))

    cases = [_observe_case(case, client) for case in TRACKED_MINUTES_CASES]
    return dict(statusCode=200, **_boundary_base(mlInvoked=True, cases=cases))


def lambda_handler(event, context):
    # 공개 API 로 노출되는 일을 막는다. API Gateway 이벤트면 AI/ML 을 호출하지 않는다.
    if _is_api_gateway_event(event):
        return {"statusCode": 403, "test": TEST_NAME, "verdict": "REFUSED",
                "note": "콘솔 전용 도구입니다. API Gateway 에 연결하지 마세요."}
    return run_check()
