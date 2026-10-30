"""WearCare Mate 백엔드 - AWS Lambda 진입점(핸들러).

이 모듈은 Amazon API Gateway(HTTP API, payload format 2.0)에서 들어온
요청을 처리하는 Lambda 핸들러를 정의합니다.

지금 단계에서는 외부 서비스(Timestream, SNS, Bedrock 등)에 연결하지 않고,
표준 라이브러리만으로 기본 라우팅과 응답 형식만 구현합니다.
"""

import json
import logging

from src.data_source import DataSourceUnavailableError, select_health_data_builder
from src.mock_data import (
    build_anomalies_mock,
    build_guides_mock,
    build_health_data_mock,
)

# 서비스 이름을 한 곳에서 관리하기 위한 상수입니다.
SERVICE_NAME = "WearCare Mate Backend"

# 예상하지 못한 예외가 발생했을 때 클라이언트에 돌려줄 고정 응답 본문입니다.
# ⚠️ 예외 메시지, 스택 트레이스, 사용자 ID 등은 절대 포함하지 않습니다.
#    (내부 구현이나 민감한 데이터가 응답으로 새어 나가지 않게 하기 위함)
INTERNAL_ERROR_BODY = {
    "error": "internal_error",
    "message": "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
}

# 데이터 소스를 사용할 수 없을 때(DataSourceUnavailableError) 돌려줄 고정 응답 본문입니다.
# api-spec.md 1.4절의 503 `unavailable` 을 따릅니다.
# ⚠️ 어떤 데이터 소스인지, 왜 사용할 수 없는지 같은 내부 정보는 포함하지 않습니다.
UNAVAILABLE_BODY = {
    "error": "unavailable",
    "message": "일시적으로 데이터를 조회할 수 없습니다. 잠시 후 다시 시도해 주세요.",
}

# 모듈 로거. Lambda 에서는 CloudWatch Logs 로 전달됩니다.
logger = logging.getLogger(__name__)


def _build_response(status_code, body):
    """API Gateway(HTTP API)가 이해하는 형식의 응답 객체를 만듭니다.

    Lambda가 반환하는 dict는 아래 세 가지 키를 가져야 합니다.
    - statusCode: HTTP 상태 코드(예: 200, 404)
    - headers: 응답 헤더(여기서는 JSON임을 알립니다)
    - body: 실제 응답 본문(문자열이어야 하므로 json.dumps로 직렬화)

    Args:
        status_code (int): 반환할 HTTP 상태 코드.
        body (dict): 응답 본문으로 쓸 파이썬 딕셔너리.

    Returns:
        dict: API Gateway 형식의 응답.
    """
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        # ensure_ascii=False 로 한글이 깨지지 않게 그대로 출력합니다.
        "body": json.dumps(body, ensure_ascii=False),
    }


def _extract_route(event):
    """이벤트에서 HTTP 메서드와 경로(path)를 꺼냅니다.

    API Gateway HTTP API payload format 2.0 이벤트는
    event["requestContext"]["http"] 안에 method 와 path 가 들어 있습니다.

    형식이 올바르지 않으면(필수 키가 없거나 타입이 다르면) ValueError 를 던져
    호출하는 쪽에서 400 응답을 만들 수 있게 합니다.

    Args:
        event (dict): Lambda 가 전달받은 이벤트.

    Returns:
        tuple[str, str]: (HTTP 메서드, 경로) 예: ("GET", "/health")

    Raises:
        ValueError: 이벤트 형식이 기대와 다를 때.
    """
    if not isinstance(event, dict):
        raise ValueError("이벤트는 dict 형식이어야 합니다.")

    request_context = event.get("requestContext")
    if not isinstance(request_context, dict):
        raise ValueError("requestContext 가 없거나 형식이 올바르지 않습니다.")

    http = request_context.get("http")
    if not isinstance(http, dict):
        raise ValueError("requestContext.http 가 없거나 형식이 올바르지 않습니다.")

    method = http.get("method")
    path = http.get("path")
    if not isinstance(method, str) or not isinstance(path, str):
        raise ValueError("http.method 또는 http.path 가 없거나 문자열이 아닙니다.")

    return method, path


def _extract_query(event):
    """이벤트에서 쿼리 파라미터 딕셔너리를 꺼낸다.

    API Gateway HTTP API(payload 2.0)는 쿼리 파라미터를
    event["queryStringParameters"] 에 넣어 보낸다.
    - 쿼리가 하나도 없으면 이 키가 없거나 None 일 수 있다 → 빈 dict 로 처리.
    - 값이 있는데 dict 가 아니면(형식 오류) ValueError 를 던져 400 으로 처리한다.

    Args:
        event (dict): Lambda 가 전달받은 이벤트.

    Returns:
        dict: 쿼리 파라미터 딕셔너리 (없으면 빈 dict).

    Raises:
        ValueError: queryStringParameters 가 dict/None 이 아닐 때.
    """
    query = event.get("queryStringParameters")
    if query is None:
        # 쿼리가 없는 정상 상황 → 빈 dict 로 통일해서 다루기 쉽게 한다.
        return {}
    if not isinstance(query, dict):
        raise ValueError("queryStringParameters 는 객체(dict) 형식이어야 합니다.")
    return query


def _match_user_resource_route(method, path, resource):
    """경로가 GET /users/{userId}/{resource} 패턴인지 확인하고 userId 를 돌려준다.

    여러 리소스(health-data, anomalies 등)가 같은 경로 구조를 공유하므로,
    resource 이름만 바꿔 재사용할 수 있도록 일반화한 공용 헬퍼이다.

    경로를 '/' 기준으로 분해해서 ["users", <userId>, <resource>] 형태인지 본다.
    주의: 빈 userId(예: /users//anomalies)도 걸러내기 위해,
          split 결과에서 빈 문자열이 사라지지 않도록 strip 으로 양끝 '/' 만 제거한다.

    Args:
        method (str): HTTP 메서드. (GET 만 매칭)
        path (str): 요청 경로.
        resource (str): 세 번째 세그먼트에 와야 하는 리소스 이름.
                        예: "health-data", "anomalies"

    Returns:
        str | None: 패턴이 맞으면 userId 문자열(빈 문자열일 수도 있음), 아니면 None.
    """
    if method != "GET":
        return None

    # 양끝의 '/' 만 떼어낸다. 가운데 빈 세그먼트는 유지해야 빈 userId 를 잡을 수 있다.
    # 예) "/users//anomalies" -> "users//anomalies" -> ["users", "", "anomalies"]
    segments = path.strip("/").split("/")
    if len(segments) == 3 and segments[0] == "users" and segments[2] == resource:
        return segments[1]  # userId (빈 문자열일 수 있음)
    return None


def _handle_user_resource(event, user_id, mock_builder):
    """/users/{userId}/{resource} 형태 MOCK 라우트의 공통 처리 로직.

    health-data 와 anomalies 가 동일한 검증 절차(빈 userId 검사, 쿼리 형식 검사)를
    공유하므로, 중복을 줄이기 위해 하나로 묶었다.

    처리 순서:
    1) userId 가 빈 문자열이면 400 (경로에 userId 가 빠진 경우)
    2) 쿼리 파라미터 추출. dict 가 아니면 400
    3) 전달받은 mock_builder(user_id, query) 로 가상 응답을 만들어 200 반환

    참고: 인증·인가는 아직 구현되지 않았다. userId 가 있다고 해서 해당 사용자
          데이터 접근 권한이 확인된 것은 아니다(실제 연동 전 반드시 추가 필요).

    Args:
        event (dict): Lambda 이벤트.
        user_id (str): 경로에서 추출한 사용자 식별자.
        mock_builder (callable): (user_id, query) 를 받아 응답 dict 를 만드는 함수.

    Returns:
        dict: API Gateway 형식의 응답 객체.
    """
    # 1) 빈 userId (예: /users//anomalies) → 400
    if user_id == "":
        return _build_response(
            400,
            {"error": "bad_request", "message": "userId 경로 값이 비어 있습니다."},
        )
    # 2) 쿼리 파라미터 추출. 형식이 잘못되면 400
    try:
        query = _extract_query(event)
    except ValueError as error:
        return _build_response(400, {"error": "bad_request", "message": str(error)})
    # 3) 가상(MOCK) 응답 생성 후 200 반환
    return _build_response(200, mock_builder(user_id, query))


def _route_request(event):
    """요청을 경로/메서드에 맞는 처리로 연결한다. (기존 lambda_handler 본문)

    400/404 같은 "예상된 오류"는 예외를 던지지 않고 응답 객체를 return 한다.
    그래서 lambda_handler 의 예외 처리(500)에 걸리지 않고 그대로 전달된다.

    처리 흐름:
    1) 이벤트에서 메서드/경로를 꺼낸다. 실패하면 400.
    2) GET /health 면 200 과 상태 JSON 을 반환한다.
    3) GET /users/{userId}/health-data 면 가상(MOCK) 건강 데이터를 반환한다.
    4) GET /users/{userId}/anomalies 면 가상(MOCK) 이상탐지 결과를 반환한다.
    5) GET /users/{userId}/guides 면 가상(MOCK) 건강 행동 가이드를 반환한다.
    6) 그 외 경로/메서드는 404 를 반환한다.

    Args:
        event (dict): API Gateway 가 전달한 요청 정보.

    Returns:
        dict: API Gateway 형식의 응답 객체.
    """
    # 1) 이벤트 형식 검증 및 라우팅 정보 추출
    try:
        method, path = _extract_route(event)
    except ValueError as error:
        return _build_response(400, {"error": "bad_request", "message": str(error)})

    # 2) 정상 경로: GET /health
    if method == "GET" and path == "/health":
        return _build_response(200, {"status": "ok", "service": SERVICE_NAME})

    # 3) GET /users/{userId}/health-data
    #    DATA_SOURCE 설정으로 빌더를 고른다. 기본값(mock)이면 기존 MOCK 빌더를 쓴다.
    #    ⚠️ 실제 데이터 소스(real)는 아직 미구현이며, 선택하면 503 이 된다.
    user_id = _match_user_resource_route(method, path, "health-data")
    if user_id is not None:
        builder = select_health_data_builder(build_health_data_mock)
        return _handle_user_resource(event, user_id, builder)

    # 4) GET /users/{userId}/anomalies (개발/테스트 전용 MOCK)
    #    ⚠️ 실제 AI/ML(SageMaker) 결과가 아니라 가상 데이터를 돌려준다.
    user_id = _match_user_resource_route(method, path, "anomalies")
    if user_id is not None:
        return _handle_user_resource(event, user_id, build_anomalies_mock)

    # 5) GET /users/{userId}/guides (개발/테스트 전용 MOCK)
    #    ⚠️ 실제 생성형 AI(Bedrock)가 만든 가이드가 아니라 가상 문구를 돌려준다.
    user_id = _match_user_resource_route(method, path, "guides")
    if user_id is not None:
        return _handle_user_resource(event, user_id, build_guides_mock)

    # 6) 그 외 지원하지 않는 경로/메서드
    return _build_response(
        404,
        {
            "error": "not_found",
            "message": f"지원하지 않는 요청입니다: {method} {path}",
        },
    )


def lambda_handler(event, context):
    """AWS Lambda 가 호출하는 진입 함수.

    실제 라우팅은 _route_request() 가 담당하고, 이 함수는 그 바깥을 감싸
    "예상하지 못한 예외"만 HTTP 500 응답으로 바꾼다.

    오류 처리 범위:
        - 400/404 등 예상된 오류는 _route_request() 가 응답으로 return 하므로
          여기서 바뀌지 않는다.
        - DataSourceUnavailableError 만 503 으로 바꾼다.
          (예: DATA_SOURCE=real 이지만 실제 데이터 조회가 아직 미구현)
        - 그 외 Exception 계열의 처리되지 않은 예외는 500 으로 바꾼다.
          DATA_SOURCE 설정 오류(DataSourceConfigError)도 여기에 해당한다.
          (예: MOCK/데이터 처리 중 버그, JSON 직렬화 실패)
        - KeyboardInterrupt, SystemExit 같은 BaseException 은 잡지 않는다.
          런타임 종료 신호까지 삼키지 않기 위함이다.

    보안:
        - 응답 본문은 고정 문구(INTERNAL_ERROR_BODY)만 사용한다.
          예외 메시지, 스택 트레이스, 사용자 ID 는 응답에 넣지 않는다.
        - 로그에는 예외 타입 이름만 남긴다. 예외 메시지에는 사용자 ID 나
          건강 수치가 섞여 있을 수 있으므로 기록하지 않는다.

    Args:
        event (dict): API Gateway 가 전달한 요청 정보.
        context: Lambda 실행 환경 정보(이번 구현에서는 사용하지 않음).

    Returns:
        dict: API Gateway 형식의 응답 객체.
    """
    try:
        return _route_request(event)
    except DataSourceUnavailableError as error:
        # 데이터 소스를 사용할 수 없는 경우만 503 으로 바꾼다. (내부 정보 비노출)
        logger.error("Data source unavailable: %s", type(error).__name__)
        return _build_response(503, dict(UNAVAILABLE_BODY))
    except Exception as error:  # noqa: BLE001 - 최종 안전망으로 의도적으로 넓게 잡음
        logger.error("Unhandled exception in lambda_handler: %s", type(error).__name__)
        # 매 요청마다 새 dict 를 넘겨 상수가 변경되지 않도록 한다.
        return _build_response(500, dict(INTERNAL_ERROR_BODY))
