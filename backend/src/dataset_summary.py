"""WearCare Mate 백엔드 - 발표용 "별도 데이터셋" 요약 집계 (/dashboard 전용).

걸음 수(사용자별 Fitbit 활동)와 별개로, 발표 화면에 **데이터셋 단위 집계**를 보여주기 위한
읽기 전용 Athena 집계입니다. 세 가지를 각각 독립적으로 조회합니다.

    - sleepDatasetSummary     : 수면 데이터셋 평균 수면 시간·집계 기록 수
    - heartRateDatasetSummary : 심박 데이터셋 전체/양수 행 수(+ 평균값, 라벨은 보수적으로)
    - psychologyDatasetSummary: 심리상담 CSV 파일별 데이터 행 수(COUNT 만)

설계 원칙:
    - 각 집계는 **독립적으로** 실행되고, 하나가 실패해도 나머지와 걸음 수·AI 가이드에 영향을 주지 않는다.
      실패/빈 결과는 status 로 구분하고, 집계 누락을 실제 0 으로 표시하지 않는다(값은 None).
    - 집계값은 **실제 Athena 쿼리 결과**에서 가져온다. 코드에 숫자를 하드코딩하지 않는다.
    - 심리상담: COUNT(*) 만 조회한다. 상담 원문·개인별 점수·ID 는 쿼리/로그/응답에 넣지 않는다.
    - AWS 클라이언트는 밖에서 주입(client_factory)받고, boto3 는 athena_repository 를 통해서만 쓴다.
    - /ai-guide 재조회에는 이 집계를 쓰지 않는다(ai_service 가 호출하지 않음). /dashboard 에서만.

status 값:
    - "ok"      : 집계 성공(값 있음)
    - "empty"   : 쿼리는 성공했으나 대상 행이 없음(값 None)
    - "error"   : 조회 실패(값 None). 사유는 로그로만 남기고 응답에는 넣지 않는다.
"""

import logging
import os
import re
import time

from src.athena_repository import (
    DEFAULT_REGION,
    AthenaConfig,
    _dig,
    create_athena_client,
)
from src.data_source import DataSourceUnavailableError

logger = logging.getLogger(__name__)

SOURCE_LABEL = "별도 데이터셋"

# 집계 활성 스위치. REAL /dashboard 에서만 켠다. 기본 꺼짐(기존 동작·테스트 영향 없음).
ENV_ENABLE = "ENABLE_DATASET_SUMMARY"

# 데이터셋 집계는 오하이오(us-east-2) 리전에 있다. 활동 테이블과 리전이 다를 수 있어 별도 환경변수로 둔다.
ENV_REGION = "DATASET_SUMMARY_REGION"
ENV_DATABASE = "DATASET_SUMMARY_DATABASE"
ENV_WORKGROUP = "DATASET_SUMMARY_WORKGROUP"
ENV_OUTPUT = "DATASET_SUMMARY_OUTPUT_LOCATION"
ENV_TIMEOUT = "DATASET_SUMMARY_TIMEOUT_SECONDS"

DEFAULT_DATABASE = "wearcare_mate_db"
DEFAULT_WORKGROUP = "primary"
DEFAULT_TIMEOUT_SECONDS = 25.0

# 테이블·S3 경로 (요청 명세의 고정 값). 사용자 입력을 받지 않으므로 쿼리에 상수로 들어간다.
SLEEP_TABLE = "wearable_sleep_table_fixed"
SLEEP_PATH = ("s3://wearcare-mate-bucket-2026/raw-data/sleep_quality/"
              "wearable_tech_sleep_quality_fixed.csv")
HEART_TABLE = "heart_rate_table"
PSYCHOLOGY_TABLE = "psychology_csv_check"
PSYCHOLOGY_INTEGRATED_PATH = ("s3://wearcare-mate-bucket-2026/raw-data/psychology/"
                              "psychology_integrated_dataset.csv")
PSYCHOLOGY_VALIDATION_PATH = ("s3://wearcare-mate-bucket-2026/raw-data/psychology/"
                             "psychology_validation_dataset.csv")

_STATE_SUCCEEDED = "SUCCEEDED"
_FAILED_STATES = ("FAILED", "CANCELLED")
_POLL_INITIAL_DELAY = 0.2
_POLL_MAX_DELAY = 1.0
_RESULTS_PAGE_LIMIT = 10

# S3 경로 형식 방어 검증(상수이지만, 주입 오염을 막기 위해 작은따옴표/공백을 금지한다).
_S3_PATH_PATTERN = re.compile(r"s3://[A-Za-z0-9._/\-]+")


def is_enabled(environ=None):
    env = os.environ if environ is None else environ
    return str(env.get(ENV_ENABLE, "")).strip().lower() == "true"


def _summary_config(environ=None):
    """집계용 Athena 설정. 활동 테이블과 별개 리전/DB 를 쓸 수 있다.

    AthenaConfig 는 table 이 필수라서 임의로 HEART_TABLE 을 넣는다(집계 SQL 은 테이블을 직접 지정).
    """
    env = os.environ if environ is None else environ
    region = (str(env.get(ENV_REGION, "")).strip() or DEFAULT_REGION)
    database = (str(env.get(ENV_DATABASE, "")).strip() or DEFAULT_DATABASE)
    workgroup = (str(env.get(ENV_WORKGROUP, "")).strip() or DEFAULT_WORKGROUP)
    output = str(env.get(ENV_OUTPUT, "")).strip() or None
    timeout_text = str(env.get(ENV_TIMEOUT, "")).strip()
    try:
        timeout = float(timeout_text) if timeout_text else DEFAULT_TIMEOUT_SECONDS
    except ValueError:
        timeout = DEFAULT_TIMEOUT_SECONDS
    return AthenaConfig(
        database=database,
        table=HEART_TABLE,  # placeholder; 집계 SQL 이 테이블을 직접 FROM 에 쓴다
        region=region,
        workgroup=workgroup,
        output_location=output,
        query_timeout_seconds=timeout,
        max_rows=10,
    )


def _check_s3_path(path):
    if not isinstance(path, str) or _S3_PATH_PATTERN.fullmatch(path) is None:
        raise DataSourceUnavailableError("데이터셋 경로 형식이 올바르지 않습니다.")
    return path


def _run_query_rows(client, config, sql, max_results=_RESULTS_PAGE_LIMIT):
    """고정 집계 SQL 을 실행(시작→폴링→결과)하고 (columns, data_rows) 를 돌려준다.

    사용자 입력이 없는 고정 집계 쿼리 전용(파라미터 없음). 단일 행/다중 행 조회가
    공통으로 쓰는 실행·폴링·파싱 로직이다. (기존 _run_scalar_query 의 본문을 추출한 것)

    여러 결과 페이지가 있으면 NextToken 으로 이어서 읽어 모든 데이터 행을 모은다.

    Returns:
        tuple[list[str], list[list[str|None]]]:
            columns: 소문자 컬럼명 목록 (결과 행이 하나도 없으면 빈 목록)
            data_rows: 헤더를 제외한 데이터 행들(각 행은 셀 문자열/None 의 리스트)
    """
    request = {
        "QueryString": sql,
        "QueryExecutionContext": {"Database": config.database},
        "WorkGroup": config.workgroup,
    }
    if config.output_location is not None:
        request["ResultConfiguration"] = {"OutputLocation": config.output_location}

    response = client.start_query_execution(**request)
    qid = _dig(response, "QueryExecutionId")
    if not isinstance(qid, str) or not qid:
        raise DataSourceUnavailableError("집계 쿼리 시작 응답 형식이 올바르지 않습니다.")

    deadline = time.monotonic() + config.query_timeout_seconds
    delay = _POLL_INITIAL_DELAY
    while True:
        status = client.get_query_execution(QueryExecutionId=qid)
        state = _dig(status, "QueryExecution", "Status", "State")
        if state == _STATE_SUCCEEDED:
            break
        if state in _FAILED_STATES:
            raise DataSourceUnavailableError("집계 쿼리가 완료되지 않았습니다.")
        now = time.monotonic()
        if now >= deadline:
            try:
                client.stop_query_execution(QueryExecutionId=qid)
            except Exception:  # noqa: BLE001 - 중지는 최선 노력
                pass
            raise DataSourceUnavailableError("집계 쿼리 시간이 초과되었습니다.")
        time.sleep(max(0.0, min(delay, deadline - now)))
        delay = min(delay * 2, _POLL_MAX_DELAY)

    columns = []
    data_rows = []
    next_token = None
    header_dropped = False
    while True:
        kwargs = {"QueryExecutionId": qid, "MaxResults": max_results}
        if next_token:
            kwargs["NextToken"] = next_token
        results = client.get_query_results(**kwargs)
        rows = _dig(results, "ResultSet", "Rows")
        if not isinstance(rows, list):
            rows = []
        if not columns:
            column_info = _dig(results, "ResultSet", "ResultSetMetadata", "ColumnInfo")
            if not isinstance(column_info, list) or not column_info:
                # 결과 행도 없고 컬럼 정보도 없으면 빈 결과로 본다.
                if not rows:
                    return [], []
                raise DataSourceUnavailableError("집계 결과에 컬럼 정보가 없습니다.")
            columns = [str(_dig(info, "Name")).lower() for info in column_info]

        page_rows = [
            [_dig(cell, "VarCharValue") for cell in (_dig(row, "Data") or [])]
            for row in rows
        ]
        # 첫 페이지의 첫 행이 헤더(컬럼명과 동일)면 한 번만 건너뛴다.
        if not header_dropped:
            header_dropped = True
            if page_rows and page_rows[0] == columns:
                page_rows = page_rows[1:]
        data_rows.extend(page_rows)

        next_token = _dig(results, "NextToken")
        if not next_token:
            break

    return columns, data_rows


def _run_scalar_query(client, config, sql):
    """단일 행 집계 SQL 을 실행하고 (컬럼명 -> 문자열 값) dict 를 돌려준다.

    사용자 입력이 없는 고정 집계 쿼리 전용(파라미터 없음). 결과 행이 없으면 빈 dict.
    """
    columns, data_rows = _run_query_rows(client, config, sql)
    if not columns or not data_rows:
        return {}
    first = data_rows[0]
    return {columns[i]: (first[i] if i < len(first) else None) for i in range(len(columns))}


def _run_multi_row_query(client, config, sql, max_results=_RESULTS_PAGE_LIMIT):
    """다중 행 집계 SQL 을 실행하고 [ {컬럼명: 값}, ... ] 목록을 돌려준다.

    단일 행 헬퍼(_run_scalar_query)를 억지로 쓰지 않고, 공통 실행·폴링·파싱(_run_query_rows)을
    재사용해 날짜별 시계열 같은 여러 행 결과를 그대로 반환한다. 결과 행이 없으면 빈 목록.
    """
    columns, data_rows = _run_query_rows(client, config, sql, max_results=max_results)
    if not columns:
        return []
    return [
        {columns[i]: (row[i] if i < len(row) else None) for i in range(len(columns))}
        for row in data_rows
    ]


def _to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _to_float(value):
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result


# ---------------------------------------------------------------------------
# 개별 집계 (각자 자신의 쿼리 SQL 과 결과 해석을 가진다)
# ---------------------------------------------------------------------------
_SLEEP_BUCKETS = (
    ("0 이상 4 미만", 0, 4, False),
    ("4 이상 6 미만", 4, 6, False),
    ("6 이상 8 미만", 6, 8, False),
    ("8 이상 10 미만", 8, 10, False),
    ("10 이상 24 이하", 10, 24, True),
)


def _sleep_bucket_case(index, lower, upper, inclusive_upper):
    value = "TRY_CAST(sleep_duration_hours AS double)"
    upper_operator = "<=" if inclusive_upper else "<"
    return (
        f"SUM(CASE WHEN {value} >= {lower} "
        f"AND {value} {upper_operator} {upper} "
        f"THEN 1 ELSE 0 END) AS bucket_{index}"
    )


def _sleep_summary(client, config):
    path = _check_s3_path(SLEEP_PATH)
    bucket_expressions = ", ".join(
        _sleep_bucket_case(index, lower, upper, inclusive)
        for index, (_, lower, upper, inclusive)
        in enumerate(_SLEEP_BUCKETS)
    )

    sql = (
        "SELECT COUNT(*) AS record_count, "
        "AVG(TRY_CAST(sleep_duration_hours AS double)) AS average_hours, "
        "MIN(TRY_CAST(sleep_duration_hours AS double)) AS minimum_hours, "
        "MAX(TRY_CAST(sleep_duration_hours AS double)) AS maximum_hours, "
        f"{bucket_expressions} "
        f'FROM "{config.database}"."{SLEEP_TABLE}" '
        f"WHERE \"$path\" = '{path}' "
        "AND TRY_CAST(sleep_duration_hours AS double) BETWEEN 0 AND 24"
    )

    row = _run_scalar_query(client, config, sql)
    count = _to_int(row.get("record_count"))

    if count is None or count < 0:
        raise DataSourceUnavailableError(
            "수면 집계 결과가 올바르지 않습니다."
        )

    if count == 0:
        return {
            "status": "empty",
            "sourceLabel": SOURCE_LABEL,
            "averageHours": None,
            "recordCount": 0,
            "minimumHours": None,
            "maximumHours": None,
            "distribution": [],
        }

    average = _to_float(row.get("average_hours"))
    minimum = _to_float(row.get("minimum_hours"))
    maximum = _to_float(row.get("maximum_hours"))

    if (
        average is None
        or minimum is None
        or maximum is None
        or not (0 <= minimum <= average <= maximum <= 24)
    ):
        raise DataSourceUnavailableError(
            "수면 요약 통계가 올바르지 않습니다."
        )

    distribution = []
    bucket_total = 0

    for index, (label, lower, upper, inclusive) in enumerate(
        _SLEEP_BUCKETS
    ):
        bucket_count = _to_int(row.get(f"bucket_{index}"))

        if bucket_count is None or bucket_count < 0:
            raise DataSourceUnavailableError(
                "수면 분포 구간 집계 결과가 올바르지 않습니다."
            )

        distribution.append({
            "label": label,
            "lowerHours": lower,
            "upperHours": upper,
            "upperInclusive": inclusive,
            "count": bucket_count,
        })
        bucket_total += bucket_count

    if bucket_total != count:
        raise DataSourceUnavailableError(
            "수면 분포 구간 합계가 전체 건수와 일치하지 않습니다."
        )

    return {
        "status": "ok",
        "sourceLabel": SOURCE_LABEL,
        "averageHours": round(average, 2),
        "recordCount": count,
        "minimumHours": round(minimum, 2),
        "maximumHours": round(maximum, 2),
        "distribution": distribution,
    }

# 확인된 날짜 형식: YYYY-MM-DD
HEART_DATE_EXPR = (
    "TRY_CAST(TRIM(CAST(measure_datetime AS VARCHAR)) AS DATE)"
)

def _heart_rate_summary(client, config):
    summary_sql = (
        "SELECT COUNT(*) AS total_rows, "
        "COUNT(TRY_CAST(heart_rate AS double)) AS numeric_rows, "
        "SUM(CASE WHEN TRY_CAST(heart_rate AS double) = 0 "
        "THEN 1 ELSE 0 END) AS zero_rows, "
        "SUM(CASE WHEN TRY_CAST(heart_rate AS double) > 0 "
        "THEN 1 ELSE 0 END) AS positive_rows, "
        "AVG(TRY_CAST(heart_rate AS double)) AS avg_all, "
        "AVG(CASE WHEN TRY_CAST(heart_rate AS double) > 0 "
        "THEN TRY_CAST(heart_rate AS double) END) AS avg_positive, "
        f"SUM(CASE WHEN {HEART_DATE_EXPR} IS NULL "
        "THEN 1 ELSE 0 END) AS invalid_date_rows "
        f'FROM "{config.database}"."{HEART_TABLE}"'
    )

    row = _run_scalar_query(client, config, summary_sql)
    total = _to_int(row.get("total_rows"))

    if total is None or total < 0:
        raise DataSourceUnavailableError(
            "심박 전체 집계 건수가 올바르지 않습니다."
        )

    if total == 0:
        return {
            "status": "empty",
            "sourceLabel": SOURCE_LABEL,
            "totalRows": 0,
            "numericRows": 0,
            "zeroRows": 0,
            "positiveRows": 0,
            "averageValue": None,
            "averageBasis": None,
            "unit": None,
            "unitBasis": "unconfirmed",
            "dailySeries": [],
            "invalidDateRows": 0,
        }

    numeric = _to_int(row.get("numeric_rows"))
    zero = _to_int(row.get("zero_rows"))
    positive = _to_int(row.get("positive_rows"))
    invalid_dates = _to_int(row.get("invalid_date_rows"))

    for value in (numeric, zero, positive, invalid_dates):
        if value is None or value < 0 or value > total:
            raise DataSourceUnavailableError(
                "심박 집계 건수가 올바르지 않습니다."
            )

    if zero + positive > numeric:
        raise DataSourceUnavailableError(
            "심박 집계 건수 사이의 관계가 올바르지 않습니다."
        )

    avg_all = _to_float(row.get("avg_all"))
    avg_positive = _to_float(row.get("avg_positive"))

    if numeric > 0 and (
        avg_all is None
        or not (-float("inf") < avg_all < float("inf"))
    ):
        raise DataSourceUnavailableError(
            "심박 전체 평균이 올바르지 않습니다."
        )

    if positive > 0 and (
        avg_positive is None
        or not (0 < avg_positive < float("inf"))
    ):
        raise DataSourceUnavailableError(
            "심박 양수 평균이 올바르지 않습니다."
        )

    # 기존 전체 대표 평균 정책을 유지한다.
    # 0값과 양수값이 함께 있으면 양수 평균, 그 외에는 전체 평균.
    if zero > 0 and positive > 0:
        average_value = round(avg_positive, 1)
        average_basis = "positive"
    else:
        average_value = (
            round(avg_all, 1) if avg_all is not None else None
        )
        average_basis = "all"

    # 날짜별 평균은 항상 heart_rate > 0인 행만 포함한다.
    # 날짜가 유효하지만 양수값이 없으면 평균은 None이다.
    daily_sql = (
        f"SELECT {HEART_DATE_EXPR} AS day, "
        "AVG(CASE WHEN TRY_CAST(heart_rate AS double) > 0 "
        "THEN TRY_CAST(heart_rate AS double) END) AS avg_positive, "
        "SUM(CASE WHEN TRY_CAST(heart_rate AS double) > 0 "
        "THEN 1 ELSE 0 END) AS included_rows "
        f'FROM "{config.database}"."{HEART_TABLE}" '
        f"WHERE {HEART_DATE_EXPR} IS NOT NULL "
        f"GROUP BY {HEART_DATE_EXPR} "
        f"ORDER BY {HEART_DATE_EXPR} ASC"
    )

    daily_rows = _run_multi_row_query(client, config, daily_sql)
    daily_series = []
    included_total = 0
    seen_dates = set()

    # 지역 import이므로 파일 상단 import를 추가할 필요가 없다.
    from datetime import date

    for daily_row in daily_rows:
        raw_day = daily_row.get("day")

        try:
            day = date.fromisoformat(str(raw_day).strip()).isoformat()
        except (TypeError, ValueError):
            raise DataSourceUnavailableError(
                "심박 날짜별 집계의 날짜가 올바르지 않습니다."
            )

        if day in seen_dates:
            raise DataSourceUnavailableError(
                "심박 날짜별 집계에 중복 날짜가 있습니다."
            )
        seen_dates.add(day)

        included = _to_int(daily_row.get("included_rows"))
        if included is None or included < 0 or included > positive:
            raise DataSourceUnavailableError(
                "심박 날짜별 포함 건수가 올바르지 않습니다."
            )

        if included == 0:
            average_day = None
        else:
            average_day = _to_float(daily_row.get("avg_positive"))
            if average_day is None or not (
                0 < average_day < float("inf")
            ):
                raise DataSourceUnavailableError(
                    "심박 날짜별 평균이 올바르지 않습니다."
                )
            average_day = round(average_day, 1)

        daily_series.append({
            "date": day,
            "averageValue": average_day,
            "includedRows": included,
        })
        included_total += included

    if included_total > positive:
        raise DataSourceUnavailableError(
            "심박 날짜별 포함 건수 합계가 올바르지 않습니다."
        )

    if invalid_dates == 0 and included_total != positive:
        raise DataSourceUnavailableError(
            "심박 날짜별 집계에서 양수 기록이 누락됐습니다."
        )

    if total > invalid_dates and not daily_series:
        raise DataSourceUnavailableError(
            "유효 날짜가 있지만 심박 날짜별 집계가 없습니다."
        )

    daily_series.sort(key=lambda item: item["date"])

    return {
        "status": "ok",
        "sourceLabel": SOURCE_LABEL,
        "totalRows": total,
        "numericRows": numeric,
        "zeroRows": zero,
        "positiveRows": positive,
        "averageValue": average_value,
        "averageBasis": average_basis,
        "unit": None,
        "unitBasis": "unconfirmed",
        "dailySeries": daily_series,
        "invalidDateRows": invalid_dates,
    }

def _psychology_summary(client, config):
    """심리상담 CSV 파일별 COUNT(*) 만 조회한다. 원문·점수·ID 는 조회하지 않는다."""
    integrated_path = _check_s3_path(PSYCHOLOGY_INTEGRATED_PATH)
    validation_path = _check_s3_path(PSYCHOLOGY_VALIDATION_PATH)

    def count_for(path):
        sql = (
            "SELECT COUNT(*) AS cnt "
            f'FROM "{config.database}"."{PSYCHOLOGY_TABLE}" '
            f"WHERE \"$path\" = '{path}'"
        )
        return _to_int(_run_scalar_query(client, config, sql).get("cnt"))

    integrated = count_for(integrated_path)
    validation = count_for(validation_path)
    files = []
    if integrated is not None:
        files.append({"id": "integrated", "label": "통합 데이터셋", "rowCount": integrated})
    if validation is not None:
        files.append({"id": "validation", "label": "검증 데이터셋", "rowCount": validation})
    if not files:
        return {"status": "empty", "sourceLabel": SOURCE_LABEL, "unit": "데이터 행 수", "files": []}
    return {"status": "ok", "sourceLabel": SOURCE_LABEL, "unit": "데이터 행 수", "files": files}


def _error_payload(kind):
    """조회 실패 시의 공통 payload. 집계 누락을 0 으로 표시하지 않기 위해 값은 None."""
    base = {"status": "error", "sourceLabel": SOURCE_LABEL}
    if kind == "sleep":
        base.update(averageHours=None, recordCount=None)
    elif kind == "heart":
        base.update(totalRows=None, numericRows=None, zeroRows=None, positiveRows=None,
                    averageValue=None, averageBasis=None, unit=None)
    elif kind == "psychology":
        base.update(unit="데이터 행 수", files=[])
    return base


_BUILDERS = (
    ("sleepDatasetSummary", "sleep", _sleep_summary),
    ("heartRateDatasetSummary", "heart", _heart_rate_summary),
    ("psychologyDatasetSummary", "psychology", _psychology_summary),
)


def build_dataset_summaries(client_factory=None, environ=None):
    """세 데이터셋 요약을 각각 독립적으로 집계해 dict 로 돌려준다.

    - 하나의 집계가 실패해도 나머지는 그대로 반환한다(개별 격리).
    - 설정(config)·클라이언트 생성 단계가 실패하면 세 필드 모두 error 로 채운다.
    - 반환 키: sleepDatasetSummary, heartRateDatasetSummary, psychologyDatasetSummary

    Returns:
        dict: 위 세 키를 가진 dict. 각 값은 status 를 포함한다.
    """
    try:
        config = _summary_config(environ)
        factory = client_factory or create_athena_client
        client = factory(config.region)
    except Exception as error:  # noqa: BLE001 - 설정/클라이언트 실패도 세 필드 error 로
        logger.error("dataset summary setup failed: %s", type(error).__name__)
        return {key: _error_payload(kind) for key, kind, _ in _BUILDERS}

    summaries = {}
    for key, kind, builder in _BUILDERS:
        try:
            summaries[key] = builder(client, config)
        except Exception as error:  # noqa: BLE001 - 개별 집계 실패는 그 필드만 error
            logger.error("dataset summary %s failed: %s", kind, type(error).__name__)
            summaries[key] = _error_payload(kind)
    return summaries
