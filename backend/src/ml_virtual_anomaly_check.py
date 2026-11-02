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


def lambda_handler(event, context):
    # 공개 API 로 노출되는 일을 막는다. API Gateway 이벤트면 AI/ML 을 호출하지 않는다.
    if _is_api_gateway_event(event):
        return {"statusCode": 403, "test": TEST_NAME, "verdict": "REFUSED",
                "note": "콘솔 전용 도구입니다. API Gateway 에 연결하지 마세요."}
    return run_check()
