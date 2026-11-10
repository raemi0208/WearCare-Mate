"""WearCare Mate 백엔드 - 웹 발표용 가상 이상 시연(POST /demo/anomaly).

콘솔 전용 도구(ml_virtual_anomaly_check.py)와 달리, 이 모듈은 공개 API 라우트
(POST /demo/anomaly)에 연결해 발표 화면에서 "가상 이상 입력 → 실제 AI/ML → 화면 변환"을
한 번에 보여 주기 위한 것입니다.

핵심 원칙:
    1) 기능 스위치: ENABLE_DEMO_ANOMALY=true 일 때만 동작한다(기본 비활성).
       꺼져 있으면 라우트가 없는 것처럼 404 를 돌려준다(존재를 드러내지 않음).
    2) 입력값은 서버 고정 시나리오에서 선택한다. 임의의 사용자 지표는 받지 않는다.
       - user_id: test-user
       - date: 2026-11-14
       - metrics: steps=1000, tracked_minutes=800
       - history_steps: [10000, 10500, 9800, 10200, 10100, 9900]
       - notify: false (분석 호출에서는 SNS 발송 금지, 발송은 저장된 결과에서 별도 처리)
    3) 변환은 기존 함수를 그대로 쓴다(복제하지 않음).
       MLClient.invoke_detection -> unwrap + validate_detection_result
       ai_service.guide_for_frontend / anomalies_for_frontend -> 화면용 변환
    4) 실패(설정 오류, 호출 실패, 응답 검증 실패)는 그대로 오류로 돌려준다.
       예시 가이드로 대체하지 않는다.

응답(성공):
    {
      "inputKind": "virtual",
      "referenceDate": "2026-11-14",
      "analysisStatus": "...",
      "overallSeverity": "...",
      "aiGuide": {...},        # guide_for_frontend 결과
      "anomalies": [...],      # anomalies_for_frontend 결과
      "request": {...},        # 서버가 보낸 고정 입력(걸음 수 등은 가상 값)
    }

보안·범위:
    - 발표용 임시 장치다. 인증·인가를 대신하지 않는다.
    - 실제 사용자 데이터·Athena 를 쓰지 않는다. 고정 가상 입력만 보낸다.
    - history_steps 를 요청에 포함하므로 AI/ML Lambda 는 Athena 를 조회하지 않고 그 값을
      기준선으로 쓴다(명세 history_steps 규칙). 그래서 build_detection_request() 대신
      이 모듈에서 요청을 직접 조립한다(build_detection_request 는 history_steps 를 보내지 않음).
    - 분석 호출은 notify=False 고정. 발송 시연은 history_service 에서 저장 결과를 사용한다.
"""

import os

from src.ai_service import anomalies_for_frontend, guide_for_frontend
from src.ml_client import MLClient, MLConfig, MLErrorResponse, create_lambda_client

INPUT_KIND = "virtual"  # 가상 입력. Athena 실제 데이터 아님.

# 기능 스위치 (기본 비활성)
ENABLE_DEMO_ANOMALY_ENV = "ENABLE_DEMO_ANOMALY"
_ENABLED_VALUE = "true"

# 서버에서 고정하는 가상 요청. 클라이언트가 바꾸지 못한다.
# 필드 이름·형식은 AI/ML lambda_handler 기준(ml_virtual_anomaly_check.VIRTUAL_REQUEST 와 동일 값).
DEMO_REQUEST = {
    "user_id": "test-user",
    "date": "2026-11-14",
    "metrics": {"steps": 1000, "tracked_minutes": 800},
    "history_steps": [10000, 10500, 9800, 10200, 10100, 9900],
    "notify": False,
}


def is_demo_anomaly_enabled(environ=None):
    """ENABLE_DEMO_ANOMALY 가 "true" 인지 확인한다(기본 비활성).

    앞뒤 공백·대소문자는 무시한다. 그 외 값("1", "yes", "", 미설정 등)은 모두 비활성으로 본다.
    애매한 값은 안전하게 꺼진 쪽으로 처리한다. (real_health_data.is_real_data_testing_enabled 와 같은 규칙)
    """
    env = os.environ if environ is None else environ
    value = env.get(ENABLE_DEMO_ANOMALY_ENV)
    return isinstance(value, str) and value.strip().lower() == _ENABLED_VALUE


SCENARIOS = {
    "steps": ("걸음 수 감소", {}),
    "sleep": ("수면 부족", {"sleep_hours": 3.0}),
    "restless": ("수면 중 움직임 증가", {"movement_during_sleep": 6.0}),
    "hrv": ("HRV 감소", {"heart_rate_variability": 15.0}),
    "stress": ("스트레스 증가", {"stress_level": 10.0}),
    "multi": ("다중 지표", {"sleep_hours": 3.0, "heart_rate_variability": 15.0, "stress_level": 10.0}),
}


def build_demo_request(scenario="steps"):
    """서버가 보낼 고정 가상 요청의 복사본을 만든다. (DEMO_REQUEST 원본 보호)

    중첩된 metrics·history_steps 까지 새 객체로 복사해, 호출하는 쪽이 바꿔도 원본이 변하지 않게 한다.
    """
    if scenario not in SCENARIOS:
        raise ValueError("지원하지 않는 시나리오입니다.")
    metrics = dict(DEMO_REQUEST["metrics"])
    if scenario != "steps":
        metrics["steps"] = 10000
    metrics.update(SCENARIOS[scenario][1])
    return {
        "user_id": DEMO_REQUEST["user_id"], "date": DEMO_REQUEST["date"],
        "metrics": metrics, "history_steps": list(DEMO_REQUEST["history_steps"]),
        "notify": False,
    }



def run_demo_anomaly(lambda_client_factory=None, environ=None, scenario="steps"):
    """고정 가상 입력으로 실제 AI/ML 을 호출하고 화면용 변환까지 수행한다.

    Args:
        lambda_client_factory (callable | None): MLConfig 를 받아 Lambda 클라이언트를 돌려주는 함수.
            None 이면 ml_client.create_lambda_client 를 쓴다. 테스트에서는 가짜 클라이언트를 넣는다.
        environ (Mapping | None): 읽을 환경변수. None 이면 os.environ.

    Returns:
        dict: {"statusCode": int, ...}. 성공이면 200 과 aiGuide/anomalies/inputKind 를 담고,
              실패면 5xx 와 오류 정보를 담는다. (예시 가이드로 대체하지 않는다)

    참고:
        - 기능 스위치가 꺼져 있으면 이 함수를 호출하지 않는다(라우터가 404 처리). 방어적으로
          여기서도 확인해, 직접 호출돼도 활성화 없이는 AI/ML 을 부르지 않는다.
    """
    env = os.environ if environ is None else environ

    # 0) 기능 스위치 확인(방어적). 꺼져 있으면 AI/ML 을 호출하지 않는다.
    if not is_demo_anomaly_enabled(env):
        return {
            "statusCode": 404,
            "inputKind": INPUT_KIND,
            "error": "not_found",
            "message": "요청하신 기능을 사용할 수 없습니다.",
        }

    if scenario not in SCENARIOS:
        return {"statusCode": 400, "error": "invalid_scenario"}
    request = build_demo_request(scenario)

    # 1) 설정 → 클라이언트 생성
    factory = lambda_client_factory or create_lambda_client
    try:
        config = MLConfig.from_env(env)
        client = MLClient(factory(config), config)
    except Exception as error:  # noqa: BLE001 - 설정·boto3 오류도 실패로 보고 (ML 미호출)
        return _failure(503, "config", error)

    # 2) 호출 + 응답 검증 (실패 시 예시 가이드로 대체하지 않음)
    try:
        result = client.invoke_detection(request)
    except Exception as error:  # noqa: BLE001 - 호출·응답 검증 실패는 503 계열
        return _failure(502, "invoke_or_validate", error)

    # 3) 기존 변환 함수 재사용
    screen_guide = guide_for_frontend(result)
    screen_anomalies = anomalies_for_frontend(result)

    return {
        "statusCode": 200,
        "inputKind": INPUT_KIND,
        "referenceDate": result["date"],
        "scenario": scenario, "scenarioLabel": SCENARIOS[scenario][0],
        "analysisStatus": result["status"],
        "overallSeverity": result["overall_severity"],
        "aiGuide": screen_guide,
        "anomalies": screen_anomalies,
        # 발표용으로 서버가 보낸 고정 입력을 함께 돌려준다(가상 값임을 명시).
        "request": request,
    }


def _failure(status_code, stage, error):
    """실패 응답을 만든다. 예외 메시지 원문·민감 정보는 넣지 않는다(타입 이름만)."""
    body = {
        "statusCode": status_code,
        "inputKind": INPUT_KIND,
        "error": "unavailable",
        "stage": stage,
        "errorType": type(error).__name__,
        "message": "가상 이상 시연을 완료하지 못했습니다.",
    }
    if isinstance(error, MLErrorResponse):
        # AI/ML 오류 코드/상태는 참고용으로만 담는다(원문 메시지는 넣지 않음).
        body["mlStatusCode"] = error.status_code
        body["mlErrorCode"] = error.error_code
    return body
