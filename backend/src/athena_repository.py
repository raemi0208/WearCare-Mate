"""WearCare Mate 백엔드 - Amazon Athena Fitbit 활동 데이터 조회 모듈.

Athena 테이블에서 특정 사용자의 Fitbit 활동 데이터를 조회해,
mappers.map_fitbit_activity_rows() 에 그대로 넘길 수 있는 "문자열 dict 목록"으로 돌려줍니다.

    rows = repository.fetch_activity_rows("1000000001", "2099-01-01", "2099-01-31")
    # [{"id": "1000000001", "activitydate": "2099-01-01", "totalsteps": "1234",
    #   "calories": "1000", "veryactiveminutes": None, "fairlyactiveminutes": None,
    #   "lightlyactiveminutes": None, "sedentaryminutes": None}, ...]

⚠️ 현재 상태:
    - 이 모듈은 아직 API(data_source.py)에 연결되어 있지 않습니다.
    - 단위 테스트는 가짜 클라이언트만 사용하며 AWS 에 접속하지 않습니다.

설계 원칙:
    - AWS 클라이언트는 밖에서 주입받습니다. (테스트에서는 가짜 클라이언트 사용)
    - boto3 는 create_athena_client() 안에서만 import 합니다.
      그래서 boto3 가 없는 로컬 환경에서도 이 모듈을 import 하고 테스트할 수 있습니다.
    - 액세스 키 등 자격 증명은 코드에 두지 않습니다. (Lambda 실행 역할 등 기본 자격 증명 체인 사용)
    - DB·테이블 이름은 환경변수(설정값)로 관리합니다.

SQL Injection 방지 (이중 방어):
    1) 사용자 입력(userId, from, to)은 SQL 문자열에 넣지 않고 ExecutionParameters 로만 전달합니다.
       Athena 공식 문서 규칙에 따라 `?` 는 따옴표 없이 쓰고, 문자열 값은 작은따옴표로 감쌉니다.
       (Athena 는 파라미터 값을 SQL 식으로 해석하므로, 값의 형식 검증이 반드시 함께 필요합니다.)
    2) 사용자 입력은 쿼리 전에 엄격히 검증합니다.
       - userId: 숫자 1~20자
       - 날짜: 실제로 존재하는 YYYY-MM-DD
       검증을 통과한 값에는 작은따옴표가 들어갈 수 없습니다.
    DB·테이블 이름은 `?` 로 넣을 수 없는 자리이므로, 설정값을 식별자 형식으로 검증한 뒤
    큰따옴표로 감싸 SQL 에 넣습니다. (사용자 입력이 아니라 서버 설정값)

오류 구분:
    - AthenaQueryValidationError : 잘못된 사용자 입력 (쿼리를 실행하지 않음)
    - DataSourceConfigError      : 잘못되거나 누락된 서버 설정, boto3 미설치
    - DataSourceUnavailableError : AWS 호출 실패, 쿼리 실패/취소, 타임아웃, 응답 형식 이상
    예외 메시지에는 사용자 ID, SQL, 설정값, AWS 오류 원문을 넣지 않습니다.
"""

import math
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime

from src.data_source import DataSourceConfigError, DataSourceUnavailableError

# ---------------------------------------------------------------------------
# 기본값과 환경변수 이름
# ---------------------------------------------------------------------------
DEFAULT_REGION = "us-east-2"
DEFAULT_WORKGROUP = "primary"
DEFAULT_QUERY_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_ROWS = 1000
MAX_ROWS_UPPER_LIMIT = 10000

ENV_REGION = "ATHENA_REGION"
ENV_DATABASE = "ATHENA_DATABASE"
ENV_TABLE = "ATHENA_TABLE"
ENV_WORKGROUP = "ATHENA_WORKGROUP"
ENV_OUTPUT_LOCATION = "ATHENA_OUTPUT_LOCATION"
ENV_QUERY_TIMEOUT = "ATHENA_QUERY_TIMEOUT_SECONDS"
ENV_MAX_ROWS = "ATHENA_MAX_ROWS"

# 조회할 컬럼 (Athena 테이블의 실제 컬럼명, 모두 string 타입)
# 활동 시간 네 컬럼(very/fairly/lightly/sedentary)은 AI/ML v0.4 의 tracked_minutes 합산 근거값이다.
ACTIVITY_COLUMNS = (
    "id", "activitydate", "totalsteps", "calories",
    "veryactiveminutes", "fairlyactiveminutes", "lightlyactiveminutes", "sedentaryminutes",
)

# GetQueryResults 한 번에 받을 수 있는 최대 행 수 (Athena API 제한)
_RESULTS_PAGE_LIMIT = 1000

# 쿼리 상태 확인 간격: 0.2초에서 시작해 2배씩, 최대 1초
_POLL_INITIAL_DELAY = 0.2
_POLL_MAX_DELAY = 1.0

_STATE_SUCCEEDED = "SUCCEEDED"
_FAILED_STATES = ("FAILED", "CANCELLED")

# ---------------------------------------------------------------------------
# 형식 검증 패턴
# re.fullmatch 를 사용하므로 문자열 전체가 패턴과 일치해야 한다.
# [0-9] 는 ASCII 숫자만 허용한다. (\d 는 다른 문자권의 숫자도 허용하므로 사용하지 않음)
# ---------------------------------------------------------------------------
_USER_ID_PATTERN = re.compile(r"[0-9]{1,20}")
_IDENTIFIER_PATTERN = re.compile(r"[a-z0-9_]{1,128}")  # Glue DB/테이블 이름
_WORKGROUP_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,128}")
_REGION_PATTERN = re.compile(r"[a-z]{2}(-[a-z]+)+-[0-9]")
# strptime 은 전각 숫자(２０９９)도 허용하므로, ASCII 형식을 먼저 정규식으로 확인한다.
_ISO_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class AthenaQueryValidationError(ValueError):
    """사용자 입력(userId, from, to)이 허용 형식이 아닐 때 발생하는 예외.

    서버 설정 오류나 AWS 장애가 아니라 "요청이 잘못된" 경우이다.
    이 예외가 발생하면 Athena 쿼리는 실행되지 않는다.
    (API 연결 단계에서 HTTP 400 으로 변환할 예정)
    """


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AthenaConfig:
    """Athena 조회 설정. 생성할 때 모든 값의 형식을 검증한다.

    Attributes:
        database: Glue 데이터베이스 이름 (예: wearcare_mate_db)
        table: 테이블 이름 (예: fitbit_activity_table)
        region: AWS 리전 (기본 us-east-2)
        workgroup: Athena 워크그룹 (기본 primary)
        output_location: 쿼리 결과 S3 위치. 워크그룹에 결과 위치가 설정되어 있으면 None.
        query_timeout_seconds: 쿼리 완료를 기다리는 최대 시간 (기본 20초)
        max_rows: 한 번에 돌려줄 최대 행 수 (기본 1000)

    Raises:
        DataSourceConfigError: 값이 없거나 형식이 잘못되었을 때.
            메시지에는 어떤 항목이 잘못되었는지만 쓰고, 입력값 자체는 넣지 않는다.
    """

    database: str
    table: str
    region: str = DEFAULT_REGION
    workgroup: str = DEFAULT_WORKGROUP
    output_location: str = None
    query_timeout_seconds: float = DEFAULT_QUERY_TIMEOUT_SECONDS
    max_rows: int = DEFAULT_MAX_ROWS

    def __post_init__(self):
        _require_match(self.database, _IDENTIFIER_PATTERN, ENV_DATABASE)
        _require_match(self.table, _IDENTIFIER_PATTERN, ENV_TABLE)
        _require_match(self.region, _REGION_PATTERN, ENV_REGION)
        _require_match(self.workgroup, _WORKGROUP_PATTERN, ENV_WORKGROUP)

        if self.output_location is not None:
            location = self.output_location
            if (
                not isinstance(location, str)
                or not location.startswith("s3://")
                or len(location) <= len("s3://")
                or any(ch.isspace() for ch in location)
            ):
                raise DataSourceConfigError(f"{ENV_OUTPUT_LOCATION} 형식이 올바르지 않습니다.")

        timeout = self.query_timeout_seconds
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise DataSourceConfigError(f"{ENV_QUERY_TIMEOUT} 값이 올바르지 않습니다.")

        max_rows = self.max_rows
        if (
            isinstance(max_rows, bool)
            or not isinstance(max_rows, int)
            or not 1 <= max_rows <= MAX_ROWS_UPPER_LIMIT
        ):
            raise DataSourceConfigError(f"{ENV_MAX_ROWS} 값이 올바르지 않습니다.")

    @classmethod
    def from_env(cls, environ=None):
        """환경변수에서 설정을 읽는다.

        Args:
            environ (Mapping | None): 읽을 환경변수. None 이면 os.environ.
                테스트에서는 dict 를 넘겨 실제 환경변수를 건드리지 않는다.

        Returns:
            AthenaConfig

        Raises:
            DataSourceConfigError: 필수값(ATHENA_DATABASE, ATHENA_TABLE)이 없거나
                값의 형식이 잘못되었을 때.
        """
        env = os.environ if environ is None else environ

        database = _read_required(env, ENV_DATABASE)
        table = _read_required(env, ENV_TABLE)
        region = _read_optional(env, ENV_REGION) or DEFAULT_REGION
        workgroup = _read_optional(env, ENV_WORKGROUP) or DEFAULT_WORKGROUP
        output_location = _read_optional(env, ENV_OUTPUT_LOCATION)

        timeout_text = _read_optional(env, ENV_QUERY_TIMEOUT)
        if timeout_text is None:
            timeout = DEFAULT_QUERY_TIMEOUT_SECONDS
        else:
            try:
                timeout = float(timeout_text)
            except ValueError:
                raise DataSourceConfigError(
                    f"{ENV_QUERY_TIMEOUT} 값이 올바르지 않습니다."
                ) from None

        max_rows_text = _read_optional(env, ENV_MAX_ROWS)
        if max_rows_text is None:
            max_rows = DEFAULT_MAX_ROWS
        else:
            try:
                max_rows = int(max_rows_text)
            except ValueError:
                raise DataSourceConfigError(f"{ENV_MAX_ROWS} 값이 올바르지 않습니다.") from None

        return cls(
            database=database,
            table=table,
            region=region,
            workgroup=workgroup,
            output_location=output_location,
            query_timeout_seconds=timeout,
            max_rows=max_rows,
        )


def _require_match(value, pattern, name):
    """설정값이 패턴과 정확히 일치하는지 확인한다. 아니면 DataSourceConfigError."""
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise DataSourceConfigError(f"{name} 값이 없거나 형식이 올바르지 않습니다.")


def _read_optional(env, name):
    """환경변수를 읽어 앞뒤 공백을 제거한다. 없거나 빈 값이면 None."""
    value = env.get(name)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _read_required(env, name):
    """필수 환경변수를 읽는다. 없거나 빈 값이면 DataSourceConfigError."""
    value = _read_optional(env, name)
    if value is None:
        raise DataSourceConfigError(f"{name} 값이 설정되지 않았습니다.")
    return value


# ---------------------------------------------------------------------------
# 사용자 입력 검증과 쿼리 생성
# ---------------------------------------------------------------------------
def validate_user_id(user_id):
    """userId 가 숫자 문자열(1~20자)인지 확인하고 그대로 돌려준다.

    Raises:
        AthenaQueryValidationError: 문자열이 아니거나 형식이 맞지 않을 때.
    """
    if not isinstance(user_id, str) or _USER_ID_PATTERN.fullmatch(user_id) is None:
        raise AthenaQueryValidationError("userId 는 숫자 1~20자여야 합니다.")
    return user_id


def validate_optional_date(value, name):
    """날짜가 없으면(None) None, 있으면 실제로 존재하는 YYYY-MM-DD 인지 확인한다.

    빈 문자열("")은 "없음"이 아니라 잘못된 값으로 본다. (?from= 처럼 값 없이 보낸 경우)

    Raises:
        AthenaQueryValidationError: 형식이 맞지 않거나 존재하지 않는 날짜일 때.
    """
    if value is None:
        return None
    if isinstance(value, str) and _ISO_DATE_PATTERN.fullmatch(value) is not None:
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            pass
    raise AthenaQueryValidationError(f"{name} 는 YYYY-MM-DD 형식의 유효한 날짜여야 합니다.")


def _quote_string_parameter(value):
    """ExecutionParameters 용 문자열 값을 만든다.

    Athena 공식 문서: 실행 파라미터가 문자열로 처리되려면 작은따옴표로 감싸야 한다.
    값은 이미 검증되어 작은따옴표가 들어갈 수 없지만, 방어적으로 SQL 규칙대로
    작은따옴표를 두 번 써서(') → ('') 이스케이프한다.
    """
    return "'" + value.replace("'", "''") + "'"


def build_activity_query(config, user_id, date_from=None, date_to=None):
    """조회 SQL 과 ExecutionParameters 를 만든다.

    - 사용자 입력은 SQL 문자열에 들어가지 않고 `?` 위치의 파라미터로만 전달된다.
    - from/to 가 있을 때만 날짜 조건을 붙인다. (조건 문구는 고정 문자열)
    - 날짜는 YYYY-MM-DD 문자열이므로 문자열 비교로 범위를 정확히 거를 수 있다.

    Args:
        config (AthenaConfig): 검증된 설정.
        user_id (str): 사용자 ID.
        date_from (str | None): 시작일(포함).
        date_to (str | None): 종료일(포함).

    Returns:
        tuple[str, list[str]]: (SQL, ExecutionParameters)

    Raises:
        AthenaQueryValidationError: 사용자 입력이 잘못되었을 때.
    """
    user_id = validate_user_id(user_id)
    date_from = validate_optional_date(date_from, "from")
    date_to = validate_optional_date(date_to, "to")

    conditions = ["id = ?"]
    # Glue id is BIGINT. Send a numeric SQL parameter, not a quoted VARCHAR.
    # Validation above allows ASCII digits only; int also normalizes leading zeros.
    parameters = [str(int(user_id))]
    if date_from is not None:
        conditions.append("activitydate >= ?")
        parameters.append(_quote_string_parameter(date_from))
    if date_to is not None:
        conditions.append("activitydate <= ?")
        parameters.append(_quote_string_parameter(date_to))

    # database/table/max_rows 는 AthenaConfig 에서 형식이 검증된 서버 설정값이다.
    sql = (
        f"SELECT {', '.join(ACTIVITY_COLUMNS)}\n"
        f'FROM "{config.database}"."{config.table}"\n'
        f"WHERE {' AND '.join(conditions)}\n"
        "ORDER BY activitydate\n"
        f"LIMIT {int(config.max_rows)}"
    )
    return sql, parameters


# ---------------------------------------------------------------------------
# 조회 실행
# ---------------------------------------------------------------------------
class AthenaActivityRepository:
    """Athena 에서 Fitbit 활동 데이터를 조회한다.

    Args:
        client: boto3 Athena 클라이언트 또는 같은 메서드를 가진 가짜 객체.
            사용 메서드: start_query_execution, get_query_execution,
                         get_query_results, stop_query_execution
        config (AthenaConfig): 조회 설정.
        sleep (callable): 대기 함수. 테스트에서는 실제로 기다리지 않는 함수를 넣는다.
        clock (callable): 현재 시각(초)을 돌려주는 함수. 타임아웃 계산에 쓴다.
    """

    def __init__(self, client, config, sleep=time.sleep, clock=time.monotonic):
        if not isinstance(config, AthenaConfig):
            raise DataSourceConfigError("Athena 설정이 올바르지 않습니다.")
        self._client = client
        self._config = config
        self._sleep = sleep
        self._clock = clock

    def fetch_activity_rows(self, user_id, date_from=None, date_to=None):
        """사용자·기간 조건으로 활동 데이터를 조회한다.

        처리 순서: 입력 검증 → 쿼리 시작 → 완료 대기 → 결과 페이지 읽기

        Returns:
            list[dict]: 컬럼명(소문자) → 문자열 값(NULL 이면 None) 딕셔너리 목록.
                        결과가 없으면 빈 리스트. 최대 config.max_rows 개.

        Raises:
            AthenaQueryValidationError: 사용자 입력이 잘못되었을 때 (쿼리 실행 안 함)
            DataSourceUnavailableError: AWS 호출 실패, 쿼리 실패/취소, 타임아웃
        """
        sql, parameters = build_activity_query(self._config, user_id, date_from, date_to)
        query_execution_id = self._start_query(sql, parameters)
        self._wait_for_completion(query_execution_id)
        return self._read_results(query_execution_id)

    def _start_query(self, sql, parameters):
        request = {
            "QueryString": sql,
            "QueryExecutionContext": {"Database": self._config.database},
            "WorkGroup": self._config.workgroup,
            "ExecutionParameters": parameters,
        }
        if self._config.output_location is not None:
            request["ResultConfiguration"] = {
                "OutputLocation": self._config.output_location
            }

        try:
            response = self._client.start_query_execution(**request)
        except Exception as error:  # noqa: BLE001 - AWS SDK/네트워크 오류를 모두 503 으로 감쌈
            raise DataSourceUnavailableError("Athena 쿼리를 시작하지 못했습니다.") from error

        query_execution_id = _dig(response, "QueryExecutionId")
        if not isinstance(query_execution_id, str) or not query_execution_id:
            raise DataSourceUnavailableError("Athena 쿼리 시작 응답 형식이 올바르지 않습니다.")
        return query_execution_id

    def _wait_for_completion(self, query_execution_id):
        """쿼리가 끝날 때까지 상태를 확인한다. 시간이 초과되면 쿼리 중지를 요청한다."""
        deadline = self._clock() + self._config.query_timeout_seconds
        delay = _POLL_INITIAL_DELAY

        while True:
            try:
                response = self._client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
            except Exception as error:  # noqa: BLE001
                raise DataSourceUnavailableError("Athena 쿼리 상태를 확인하지 못했습니다.") from error

            state = _dig(response, "QueryExecution", "Status", "State")
            if state == _STATE_SUCCEEDED:
                return
            if state in _FAILED_STATES:
                # 실패 사유(StateChangeReason)에는 SQL 이나 사용자 ID 가 들어 있을 수 있으므로 쓰지 않는다.
                raise DataSourceUnavailableError("Athena 쿼리가 완료되지 않았습니다.")

            # QUEUED / RUNNING / 알 수 없는 상태 → 타임아웃 전까지 계속 기다린다.
            now = self._clock()
            if now >= deadline:
                self._stop_query(query_execution_id)
                raise DataSourceUnavailableError("Athena 쿼리 시간이 초과되었습니다.")

            self._sleep(max(0.0, min(delay, deadline - now)))
            delay = min(delay * 2, _POLL_MAX_DELAY)

    def _stop_query(self, query_execution_id):
        """타임아웃된 쿼리의 중지를 요청한다. 실패해도 타임아웃 오류를 우선한다."""
        try:
            self._client.stop_query_execution(QueryExecutionId=query_execution_id)
        except Exception:  # noqa: BLE001 - 중지 요청은 최선 노력. 원래 오류(타임아웃)를 유지한다.
            pass

    def _read_results(self, query_execution_id):
        """결과를 페이지 단위로 읽어 dict 목록으로 만든다.

        - 첫 페이지의 첫 행이 컬럼 이름과 같으면 헤더 행으로 보고 제외한다.
          (Athena SELECT 결과는 첫 페이지 첫 행에 컬럼 이름이 들어 있음)
        - VarCharValue 가 없는 칸은 NULL 이므로 None 으로 둔다.
        - max_rows 에 도달하면 다음 페이지를 요청하지 않는다.
        """
        max_rows = self._config.max_rows
        rows = []
        columns = None
        next_token = None
        is_first_page = True

        while True:
            remaining = max_rows - len(rows)
            # 첫 페이지는 헤더 행 1개를 더 받는다.
            page_size = min(_RESULTS_PAGE_LIMIT, remaining + (1 if is_first_page else 0))
            request = {"QueryExecutionId": query_execution_id, "MaxResults": page_size}
            if next_token is not None:
                request["NextToken"] = next_token

            try:
                response = self._client.get_query_results(**request)
            except Exception as error:  # noqa: BLE001
                raise DataSourceUnavailableError("Athena 쿼리 결과를 읽지 못했습니다.") from error

            if columns is None:
                columns = _extract_columns(response)

            page_rows = _dig(response, "ResultSet", "Rows")
            if page_rows is None:
                page_rows = []
            if not isinstance(page_rows, list):
                raise DataSourceUnavailableError("Athena 결과 형식이 올바르지 않습니다.")

            for index, raw_row in enumerate(page_rows):
                values = _extract_values(raw_row, len(columns))
                if is_first_page and index == 0 and values == list(columns):
                    continue  # 헤더 행
                rows.append(dict(zip(columns, values)))
                if len(rows) >= max_rows:
                    return rows

            is_first_page = False
            next_token = response.get("NextToken") if isinstance(response, dict) else None
            if not next_token:
                return rows


def _dig(data, *keys):
    """중첩 dict 에서 안전하게 값을 꺼낸다. 중간에 dict 가 아니거나 키가 없으면 None."""
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _extract_columns(response):
    """결과 메타데이터에서 컬럼 이름 목록을 꺼낸다."""
    column_info = _dig(response, "ResultSet", "ResultSetMetadata", "ColumnInfo")
    if not isinstance(column_info, list) or not column_info:
        raise DataSourceUnavailableError("Athena 결과에 컬럼 정보가 없습니다.")
    columns = []
    for info in column_info:
        name = _dig(info, "Name")
        if not isinstance(name, str) or not name:
            raise DataSourceUnavailableError("Athena 결과의 컬럼 정보가 올바르지 않습니다.")
        columns.append(name.lower())
    return columns


def _extract_values(raw_row, column_count):
    """결과 행 1개를 컬럼 수에 맞춘 값 목록으로 만든다. NULL 은 None."""
    data = _dig(raw_row, "Data")
    if not isinstance(data, list):
        raise DataSourceUnavailableError("Athena 결과 행 형식이 올바르지 않습니다.")
    values = [_dig(cell, "VarCharValue") for cell in data[:column_count]]
    # 뒤쪽 칸이 생략된 경우 None 으로 채운다.
    values.extend([None] * (column_count - len(values)))
    return values


# ---------------------------------------------------------------------------
# 클라이언트 생성
# ---------------------------------------------------------------------------
def create_athena_client(region=DEFAULT_REGION):
    """boto3 Athena 클라이언트를 만든다. (이 함수를 호출할 때만 boto3 를 import)

    - 자격 증명은 boto3 기본 체인(Lambda 실행 역할 등)을 사용한다. 코드에 키를 넣지 않는다.
    - 연결/읽기 타임아웃과 재시도 횟수를 제한해, 네트워크 문제로 Lambda 가 오래 멈추지 않게 한다.

    Raises:
        DataSourceConfigError: 리전 형식이 잘못되었거나 boto3 가 설치되지 않았을 때.
    """
    _require_match(region, _REGION_PATTERN, ENV_REGION)
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        raise DataSourceConfigError("boto3 가 설치되어 있지 않습니다.") from None

    client_config = Config(
        connect_timeout=3,
        read_timeout=10,
        retries={"max_attempts": 2, "mode": "standard"},
    )
    return boto3.client("athena", region_name=region, config=client_config)
