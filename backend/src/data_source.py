"""WearCare Mate 백엔드 - 데이터 소스 선택 모듈.

환경변수 DATA_SOURCE 값에 따라 health-data 응답을 만들 함수(빌더)를 고릅니다.

    DATA_SOURCE 값          동작
    ----------------------  ------------------------------------------------
    (설정 안 함)             mock  → 기존 MOCK 빌더 사용 (기본값)
    "mock"                  mock  → 기존 MOCK 빌더 사용
    "real"                  실제 데이터 소스 → 아직 미구현.
                            빌더를 호출하면 DataSourceUnavailableError 발생
                            (MOCK 데이터로 대체하지 않음)
    그 외 값 / 빈 문자열     DataSourceConfigError 발생 (MOCK 으로 조용히 바꾸지 않음)

    값의 앞뒤 공백과 대소문자는 무시합니다. 예) " MOCK " → "mock"

설계 원칙:
    - 이 모듈은 Athena/Timestream 등 특정 저장소 코드를 담지 않습니다.
      (저장소 종류가 아직 확정되지 않았기 때문)
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

    현재는 DATA_SOURCE=real 이지만 실제 데이터 조회가 아직 구현되지 않은 경우에 쓴다.
    lambda_function 은 이 예외만 HTTP 503 으로 바꾸고,
    외부 응답에는 고정 문구만 내보낸다. (이 예외의 메시지는 노출하지 않음)
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


def _real_health_data_not_implemented(user_id, query):
    """실제 데이터 소스용 빌더 자리. 아직 구현되지 않았음을 알리는 예외를 던진다.

    MOCK 빌더와 같은 (user_id, query) 형태를 가지므로, 나중에 실제 조회 함수로
    이 함수만 바꾸면 된다.
    """
    raise DataSourceUnavailableError("실제 데이터 소스가 아직 구현되지 않았습니다.")


def select_health_data_builder(mock_builder):
    """DATA_SOURCE 설정에 맞는 health-data 빌더를 돌려준다.

    빌더는 (user_id, query) 를 받아 응답 본문 dict 를 돌려주는 함수다.
    "real" 일 때는 빌더를 고르는 시점이 아니라 "호출하는 시점"에 예외가 난다.
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
    return _real_health_data_not_implemented
