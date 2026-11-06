"""WearCare Mate 백엔드 - 데이터 소스 선택 모듈.

환경변수 DATA_SOURCE 값에 따라 health-data 응답을 만들 함수(빌더)를 고릅니다.

    DATA_SOURCE 값          동작
    ----------------------  ------------------------------------------------
    (설정 안 함)             mock  → 기존 MOCK 빌더 사용 (기본값)
    "mock"                  mock  → 기존 MOCK 빌더 사용
    "real"                  real_health_data.build_real_health_data 사용 (Athena 조회)
                            단, ENABLE_REAL_DATA_TESTING=true 가 함께 설정되지 않으면
                            빌더 호출 시 DataSourceUnavailableError (503)
                            (임시 개발 장치. 실패해도 MOCK 데이터로 대체하지 않음)
    그 외 값 / 빈 문자열     DataSourceConfigError 발생 (MOCK 으로 조용히 바꾸지 않음)

    값의 앞뒤 공백과 대소문자는 무시합니다. 예) " MOCK " → "mock"

설계 원칙:
    - 이 모듈은 데이터 소스를 "선택"만 합니다. Athena 조회 코드는
      real_health_data.py / athena_repository.py 에 있으며, real 일 때만 불러옵니다.
    - mock_data 를 직접 import 하지 않고, 호출하는 쪽에서 MOCK 빌더를 넘겨받습니다.
      이렇게 하면 이 모듈이 MOCK 구현에 묶이지 않고 테스트에서 바꿔 끼우기도 쉽습니다.
    - 환경변수는 import 시점이 아니라 "호출할 때마다" 읽습니다.
      테스트에서 환경변수를 바꿔도 다른 테스트에 영향이 남지 않게 하기 위함입니다.
"""

import os

# 환경변수 이름과 허용 값
DATA_SOURCE_ENV = "DATA_SOURCE"
DATA_SOURCE_MOCK = "mock"
DATA_SOURCE_REAL = "real"
DEFAULT_DATA_SOURCE = DATA_SOURCE_MOCK
VALID_DATA_SOURCES = (DATA_SOURCE_MOCK, DATA_SOURCE_REAL)


class DataSourceUnavailableError(Exception):
    """데이터 소스를 사용할 수 없을 때 발생하는 예외.

    예) DATA_SOURCE=real 이지만 ENABLE_REAL_DATA_TESTING 이 꺼져 있음,
        AWS 조회 실패, 쿼리 실패/취소, 타임아웃
    lambda_function 은 이 예외만 HTTP 503 으로 바꾸고,
    외부 응답에는 고정 문구만 내보낸다. (이 예외의 메시지는 노출하지 않음)
    """


class DataSourceRequestError(Exception):
    """데이터 소스가 사용자 요청 값을 받아들일 수 없을 때 발생하는 예외.

    예) 숫자가 아닌 userId, 잘못된 날짜 형식, from 이 to 보다 늦은 날짜 범위
    lambda_function 은 이 예외만 HTTP 400 으로 바꾼다.

    ⚠️ ValueError 를 상속하지 않는다. 일반적인 ValueError(데이터 처리 버그 등)는
       기존처럼 500 으로 처리되어야 하기 때문이다.
    ⚠️ 메시지는 응답에 그대로 쓰이므로, 사용자 입력값이나 건강 데이터를 넣지 않는다.
    """


class DataSourceNotFoundError(Exception):
    """요청한 대상의 데이터를 이 데이터 소스에서 제공할 수 없을 때 발생하는 예외.

    예) REAL 모드에서 DASHBOARD_USER_ID 와 다른 사용자 ID 를 요청한 경우
    lambda_function 은 이 예외만 HTTP 404 로 바꾼다.
    (403 이 아니라 404 로 응답해, 어떤 사용자 ID 가 존재하는지 알 수 없게 한다)

    ⚠️ 메시지는 응답에 쓰이므로 사용자 ID 를 넣지 않는다.
    """


class DataSourceConfigError(Exception):
    """DATA_SOURCE 환경변수 값이 잘못되었을 때 발생하는 예외.

    서버 설정 오류이므로 MOCK 으로 조용히 대체하지 않는다.
    lambda_function 에서는 예상하지 못한 예외와 같이 HTTP 500 으로 처리되고,
    로그에는 예외 타입 이름(DataSourceConfigError)이 남는다.
    """


def get_data_source_name():
    """현재 설정된 데이터 소스 이름을 돌려준다.

    - 환경변수가 없으면 기본값 "mock".
    - 값은 앞뒤 공백을 제거하고 소문자로 바꿔 비교한다.
    - 허용되지 않은 값이나 빈 문자열이면 DataSourceConfigError.

    Returns:
        str: "mock" 또는 "real".

    Raises:
        DataSourceConfigError: 허용되지 않은 값일 때.
    """
    raw_value = os.environ.get(DATA_SOURCE_ENV)
    if raw_value is None:
        return DEFAULT_DATA_SOURCE

    value = raw_value.strip().lower()
    if value not in VALID_DATA_SOURCES:
        # 잘못된 설정값 자체는 메시지에 넣지 않는다(설정 실수로 비밀값이 들어갈 수 있음).
        raise DataSourceConfigError(
            f"{DATA_SOURCE_ENV} 값이 올바르지 않습니다. "
            f"허용 값: {', '.join(VALID_DATA_SOURCES)}"
        )
    return value


def select_health_data_builder(mock_builder):
    """DATA_SOURCE 설정에 맞는 health-data 빌더를 돌려준다.

    빌더는 (user_id, query) 를 받아 응답 본문 dict 를 돌려주는 함수다.
    - mock(기본값): 넘겨받은 MOCK 빌더
    - real: real_health_data.build_real_health_data
      ENABLE_REAL_DATA_TESTING=true 가 아니면 호출 시 503 이 된다. (임시 개발 장치)
    "real" 의 오류는 빌더를 고르는 시점이 아니라 "호출하는 시점"에 난다.
    그래서 빈 userId(400)나 잘못된 쿼리(400) 같은 요청 검증은 기존처럼 먼저 이루어진다.

    Args:
        mock_builder (callable): DATA_SOURCE=mock 일 때 사용할 MOCK 빌더.

    Returns:
        callable: (user_id, query) -> dict

    Raises:
        DataSourceConfigError: DATA_SOURCE 값이 잘못되었을 때.
    """
    if get_data_source_name() == DATA_SOURCE_MOCK:
        return mock_builder

    # real 일 때만 불러온다. (순환 import 방지 + MOCK 모드에서는 Athena 코드를 불러오지 않음)
    from src.real_health_data import build_real_health_data

    return build_real_health_data


def select_dashboard_builder(mock_builder):
    """DATA_SOURCE 설정에 맞는 /dashboard 빌더를 돌려준다. 빌더는 인자 없이 호출한다.

    - mock(기본값): 넘겨받은 MOCK 빌더
    - real: dashboard_data.build_real_dashboard (걸음 수만 Athena 실제 데이터)
      ENABLE_REAL_DATA_TESTING=true 와 DASHBOARD_USER_ID 가 없으면 호출 시 503/500.
      실패해도 MOCK 으로 대체하지 않는다.

    Raises:
        DataSourceConfigError: DATA_SOURCE 값이 잘못되었을 때.
    """
    if get_data_source_name() == DATA_SOURCE_MOCK:
        return mock_builder

    # real 일 때만 불러온다. (순환 import 방지 + MOCK 모드에서는 Athena 코드를 불러오지 않음)
    from src.dashboard_data import build_real_dashboard

    return build_real_dashboard


# ---------------------------------------------------------------------------
# AI 데이터 소스 (AI_SOURCE) — DATA_SOURCE 와 독립
# ---------------------------------------------------------------------------
# /dashboard 의 anomalies·aiGuide·timeseries[].anomaly 와 /ai-guide 의 출처를 정한다.
#   (설정 안 함) / "mock" → 기존 예시 데이터 (기본값)
#   "real"              → lambda_function에서 ai_service.py의 실제 AI 경로 선택
#                          (실패를 MOCK으로 대체하지 않는다)
#   그 외 값 / 빈 문자열  → DataSourceConfigError (500)
# 실제 연결 시에도 기존 REAL 진입 조건(ENABLE_REAL_DATA_TESTING, DASHBOARD_USER_ID)을 함께 요구한다.
# /users/{userId}/anomalies, /users/{userId}/guides (기존 MOCK API) 에는 영향이 없다.
AI_SOURCE_ENV = "AI_SOURCE"
AI_SOURCE_MOCK = "mock"
AI_SOURCE_REAL = "real"
DEFAULT_AI_SOURCE = AI_SOURCE_MOCK
VALID_AI_SOURCES = (AI_SOURCE_MOCK, AI_SOURCE_REAL)


def get_ai_source_name(environ=None):
    """현재 설정된 AI 데이터 소스 이름("mock" 또는 "real")을 돌려준다.

    값의 앞뒤 공백과 대소문자는 무시한다. 허용되지 않은 값이나 빈 문자열이면 DataSourceConfigError.
    """
    env = os.environ if environ is None else environ
    raw_value = env.get(AI_SOURCE_ENV)
    if raw_value is None:
        return DEFAULT_AI_SOURCE

    value = raw_value.strip().lower() if isinstance(raw_value, str) else ""
    if value not in VALID_AI_SOURCES:
        # 잘못된 설정값 자체는 메시지에 넣지 않는다.
        raise DataSourceConfigError(
            f"{AI_SOURCE_ENV} 값이 올바르지 않습니다. 허용 값: {', '.join(VALID_AI_SOURCES)}"
        )
    return value


def ensure_ai_source_is_mock(environ=None):
    """예시 전용 분기에 실제 AI 설정이 들어오지 않았는지 확인한다.

    - mock(기본값): 통과
    - real: 예시 전용 분기에서는 DataSourceUnavailableError (503).
      운영자가 실제 AI 결과를 기대하고 real 을 설정했는데 예시 데이터가 나가는 일을 막는다.
    - 잘못된 값: DataSourceConfigError (500)
    """
    if get_ai_source_name(environ) == AI_SOURCE_REAL:
        raise DataSourceUnavailableError("실제 AI 설정에서 예시 응답을 사용할 수 없습니다.")
