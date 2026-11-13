"""WearCare Mate 백엔드 - health-data 실제 데이터(REAL) 빌더.

DATA_SOURCE=real 일 때 data_source.select_health_data_builder() 가 돌려주는 빌더입니다.
MOCK 빌더와 같은 (user_id, query) -> dict 형태입니다.

처리 순서:
    1) 실제 데이터 테스트 스위치 확인       꺼져 있으면 DataSourceUnavailableError (503)
    2) 사용자 입력 검증 (AWS 호출 전)        잘못되면 DataSourceRequestError (400)
       - userId: 숫자 1~20자
       - from/to: 실제로 존재하는 YYYY-MM-DD, from <= to
    2-1) 접근 대상 확인 (AWS 호출 전)
       - DASHBOARD_USER_ID 가 없거나 형식 오류 → DataSourceConfigError (500)
       - 요청 userId 가 DASHBOARD_USER_ID 와 다름 → DataSourceNotFoundError (404)
    3) Athena 설정 읽기                     잘못되면 DataSourceConfigError (500)
    4) Athena 클라이언트 생성                boto3 미설치 등 → DataSourceConfigError (500)
    5) Athena 조회                          AWS 실패/타임아웃 → DataSourceUnavailableError (503)
    6) mappers.map_fitbit_activity_rows()  → health_service.build_health_data_response()
       조회 결과가 0행이면 200 + 빈 items

⚠️ ENABLE_REAL_DATA_TESTING 스위치 (임시 개발 장치):
    - DATA_SOURCE=real 과 ENABLE_REAL_DATA_TESTING=true 가 모두 설정되어야 실제 조회를 한다.
    - 기본값은 비활성화이다. DATA_SOURCE=real 만 설정하면 기존처럼 503 을 돌려준다.
      (기존 테스트가 기대하는 "real 단독 = 503" 동작을 유지하기 위한 장치이기도 하다)
    - 개발 및 통합 테스트 전용이며, 인증·인가를 대체하지 않는다.
    - 배포 환경에서는 활성화하지 않는 것을 원칙으로 한다.
    - 인증·인가가 구현되면 이 스위치는 제거하거나 재검토한다.

보안:
    - 실패 시 MOCK 데이터로 대체하지 않는다.
    - 예외 메시지에 사용자 입력값이나 건강 데이터를 넣지 않는다.
    - 응답은 health_service 가 다시 한 번 사용자 ID 로 거르므로,
      다른 사용자의 행이 섞여 들어와도 응답에는 포함되지 않는다.
"""

import os

# create_athena_client 는 "모듈 속성"으로 호출한다.
# (테스트에서 src.athena_repository.create_athena_client 를 패치할 수 있게 하기 위함)
from src import athena_repository
from src.athena_repository import (
    AthenaActivityRepository,
    AthenaConfig,
    AthenaQueryValidationError,
    validate_optional_date,
    validate_user_id,
)
from src.data_source import (
    DataSourceConfigError,
    DataSourceNotFoundError,
    DataSourceRequestError,
    DataSourceUnavailableError,
)
from src.health_service import build_health_data_response
from src.mappers import map_fitbit_activity_rows

# 실제 데이터 테스트 스위치 (임시 개발 장치 — 모듈 설명 참고)
ENABLE_REAL_DATA_TESTING_ENV = "ENABLE_REAL_DATA_TESTING"
_ENABLED_VALUE = "true"

# 개발용 데모 조회 대상 사용자 ID (임시 개발 장치)
# ⚠️ 인증·인가를 대신하지 않는다. REAL 모드에서 조회 대상을 이 사용자 1명으로 제한할 뿐이다.
DASHBOARD_USER_ID_ENV = "DASHBOARD_USER_ID"


def is_real_data_testing_enabled(environ=None):
    """ENABLE_REAL_DATA_TESTING 이 "true" 인지 확인한다.

    앞뒤 공백과 대소문자는 무시한다. 그 외의 값("1", "yes", "", 미설정 등)은
    모두 비활성화로 본다. 안전을 위해 애매한 값은 꺼진 쪽으로 처리한다.
    """
    env = os.environ if environ is None else environ
    value = env.get(ENABLE_REAL_DATA_TESTING_ENV)
    return isinstance(value, str) and value.strip().lower() == _ENABLED_VALUE


def _validate_request(user_id, date_from, date_to):
    """AWS 를 호출하기 전에 사용자 입력을 검증한다.

    Athena 모듈의 검증 오류(AthenaQueryValidationError)만 DataSourceRequestError(400)로 바꾼다.
    다른 ValueError 는 바꾸지 않는다(기존처럼 500).
    """
    try:
        validate_user_id(user_id)
        validate_optional_date(date_from, "from")
        validate_optional_date(date_to, "to")
    except AthenaQueryValidationError as error:
        # 검증 메시지는 고정 문구이며 사용자 입력값을 포함하지 않는다.
        raise DataSourceRequestError(str(error)) from None

    # 검증된 YYYY-MM-DD 문자열은 문자열 비교로 날짜 순서를 비교할 수 있다.
    if date_from is not None and date_to is not None and date_from > date_to:
        raise DataSourceRequestError("from 은 to 보다 늦을 수 없습니다.")


def get_allowed_user_id(environ=None):
    """REAL 모드에서 조회를 허용할 개발용 데모 사용자 ID(DASHBOARD_USER_ID)를 읽는다.

    ⚠️ 이 값은 개발·통합 테스트에서 조회 대상을 1명으로 제한하는 장치이며,
       인증·인가를 대신하지 않는다.

    Raises:
        DataSourceConfigError: 값이 없거나 숫자 1~20자 형식이 아닐 때 (500).
            메시지에는 설정값 자체를 넣지 않는다.
    """
    env = os.environ if environ is None else environ
    raw_value = env.get(DASHBOARD_USER_ID_ENV)
    value = raw_value.strip() if isinstance(raw_value, str) else ""
    if not value:
        raise DataSourceConfigError(f"{DASHBOARD_USER_ID_ENV} 값이 설정되지 않았습니다.")
    try:
        return validate_user_id(value)
    except AthenaQueryValidationError:
        raise DataSourceConfigError(f"{DASHBOARD_USER_ID_ENV} 형식이 올바르지 않습니다.") from None


def build_real_health_data(user_id, query, client_factory=None, environ=None):
    """Athena 에서 활동 데이터를 조회해 health-data 응답 본문을 만든다.

    Args:
        user_id (str): 경로의 사용자 ID.
        query (dict): 쿼리 파라미터. from/to 를 사용한다.
        client_factory (callable | None): region 을 받아 Athena 클라이언트를 돌려주는 함수.
            None 이면 athena_repository.create_athena_client 를 사용한다.
            테스트에서는 가짜 클라이언트를 돌려주는 함수를 넣는다.
        environ (Mapping | None): 읽을 환경변수. None 이면 os.environ.

    Returns:
        dict: {"userId": ..., "range": {"from": ..., "to": ...}, "items": [...]}

    Raises:
        DataSourceUnavailableError: 스위치가 꺼져 있거나 AWS 조회가 실패했을 때 (503)
        DataSourceRequestError: 사용자 입력이 잘못되었을 때 (400)
        DataSourceNotFoundError: DASHBOARD_USER_ID 와 다른 사용자를 요청했을 때 (404)
        DataSourceConfigError: DASHBOARD_USER_ID/Athena 설정이 잘못되었거나 boto3 가 없을 때 (500)
    """
    env = os.environ if environ is None else environ

    # 1) 스위치가 꺼져 있으면 실제 조회 경로로 들어가지 않는다.
    if not is_real_data_testing_enabled(env):
        raise DataSourceUnavailableError("실제 데이터 조회가 활성화되어 있지 않습니다.")

    # 2) 사용자 입력 검증 (AWS 호출 전)
    date_from = query.get("from")
    date_to = query.get("to")
    _validate_request(user_id, date_from, date_to)

    # 2-1) 접근 대상 확인: 개발용 데모 사용자와 같은 ID 만 조회한다.
    #      Athena 설정을 읽거나 클라이언트를 만들기 전에 확인한다.
    #      다른 ID 는 404 (어떤 ID 가 존재하는지 알 수 없게 함). 정확히 같은 문자열만 허용.
    if user_id != get_allowed_user_id(env):
        raise DataSourceNotFoundError("요청한 데이터를 찾을 수 없습니다.")

    # 3) 설정 → 4) 클라이언트 → 5) 조회 → 6) 매핑
    mapped_rows, _config = fetch_mapped_activity_rows(
        user_id, date_from, date_to, client_factory=client_factory, environ=env
    )
    # 7) 응답 조립
    return build_health_data_response(mapped_rows, user_id, date_from, date_to)


def fetch_mapped_activity_rows(user_id, date_from=None, date_to=None,
                               client_factory=None, environ=None):
    """Athena 설정 → 클라이언트 생성 → 조회 → Fitbit 매핑을 수행한다.

    ⚠️ 이 함수는 스위치 확인, 입력 검증, 접근 대상(DASHBOARD_USER_ID) 확인을 하지 않는다.
       반드시 그 확인을 마친 뒤에 호출해야 한다.
       (build_real_health_data, dashboard_data.build_real_dashboard 에서 사용)

    Returns:
        tuple[list[dict], AthenaConfig]: (매핑된 행 목록, 사용한 설정)

    Raises:
        DataSourceConfigError: Athena 설정 오류, boto3 미설치 (500)
        DataSourceUnavailableError: AWS 조회 실패/타임아웃 (503)
        DataSourceRequestError: 조회 단계의 입력 검증 오류 (400)
    """
    env = os.environ if environ is None else environ
    config = AthenaConfig.from_env(env)
    factory = client_factory if client_factory is not None else athena_repository.create_athena_client
    client = factory(config.region)

    # 입력은 호출 전에 검증했지만, 검증 오류가 나면 같은 방식(400)으로 처리한다.
    repository = AthenaActivityRepository(client, config)
    try:
        rows = repository.fetch_activity_rows(user_id, date_from, date_to)
    except AthenaQueryValidationError as error:
        raise DataSourceRequestError(str(error)) from None

    return map_fitbit_activity_rows(rows), config
