"""athena_repository 모듈에 대한 단위 테스트.

외부 패키지 없이 파이썬 표준 라이브러리 unittest 만 사용합니다.
- AWS 에 접속하지 않습니다. Athena 클라이언트는 가짜(FakeAthenaClient)를 주입합니다.
- 실제로 기다리지 않습니다. 대기/시계 함수도 가짜(FakeClock)를 주입합니다.
- boto3 가 설치되지 않은 환경에서도 실행됩니다.
- 테스트 데이터는 모두 가상의 값입니다.

실행 방법(backend 폴더 기준):
    python -m unittest discover -s tests -v
"""

import importlib.util
import os
import sys
import unittest
from unittest import mock

# src 패키지를 import 할 수 있도록 backend 폴더를 모듈 검색 경로에 추가합니다.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.athena_repository import (  # noqa: E402
    DEFAULT_MAX_ROWS,
    DEFAULT_QUERY_TIMEOUT_SECONDS,
    DEFAULT_REGION,
    DEFAULT_WORKGROUP,
    AthenaActivityRepository,
    AthenaConfig,
    AthenaQueryValidationError,
    _quote_string_parameter,
    build_activity_query,
    create_athena_client,
)
from src.data_source import DataSourceConfigError, DataSourceUnavailableError  # noqa: E402
from src.health_service import build_health_data_response  # noqa: E402
from src.mappers import map_fitbit_activity_rows  # noqa: E402

USER_ID = "1000000001"
COLUMNS = ["id", "activitydate", "totalsteps", "calories", "veryactiveminutes"]
SECRET = "secret-aws-detail-1234"


# ---------------------------------------------------------------------------
# 테스트 도우미
# ---------------------------------------------------------------------------
def make_config(**overrides):
    values = {"database": "test_db", "table": "test_table"}
    values.update(overrides)
    return AthenaConfig(**values)


def header_row():
    return {"Data": [{"VarCharValue": name} for name in COLUMNS]}


def data_row(*values):
    """값 목록으로 결과 행을 만든다. None 은 VarCharValue 가 없는 칸(NULL)이 된다."""
    return {"Data": [{} if value is None else {"VarCharValue": value} for value in values]}


def results_page(rows, next_token=None):
    page = {
        "ResultSet": {
            "Rows": rows,
            "ResultSetMetadata": {
                "ColumnInfo": [{"Name": name, "Type": "varchar"} for name in COLUMNS]
            },
        }
    }
    if next_token is not None:
        page["NextToken"] = next_token
    return page


class FakeClock:
    """가짜 시계. sleep 을 호출하면 실제로 기다리지 않고 시간만 앞으로 간다."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeAthenaClient:
    """boto3 Athena 클라이언트를 흉내 내는 가짜 객체. 호출 내용을 기록한다."""

    def __init__(self, states=("SUCCEEDED",), pages=None, start_response=None):
        self.states = list(states)
        self.pages = list(pages) if pages is not None else [results_page([header_row()])]
        # 빈 dict({})도 "잘못된 응답" 테스트에 써야 하므로 `or` 가 아니라 None 으로 비교한다.
        self.start_response = (
            {"QueryExecutionId": "qid-1"} if start_response is None else start_response
        )
        self.calls = []
        self.start_error = None
        self.status_error = None
        self.results_error = None
        self.stop_error = None

    def start_query_execution(self, **kwargs):
        self.calls.append(("start", kwargs))
        if self.start_error:
            raise self.start_error
        return self.start_response

    def get_query_execution(self, **kwargs):
        self.calls.append(("status", kwargs))
        if self.status_error:
            raise self.status_error
        # 준비된 상태를 차례로 돌려주고, 마지막 상태는 계속 유지한다.
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return {"QueryExecution": {"Status": {"State": state}}}

    def get_query_results(self, **kwargs):
        self.calls.append(("results", kwargs))
        if self.results_error:
            raise self.results_error
        return self.pages.pop(0)

    def stop_query_execution(self, **kwargs):
        self.calls.append(("stop", kwargs))
        if self.stop_error:
            raise self.stop_error
        return {}

    def calls_of(self, name):
        return [kwargs for call_name, kwargs in self.calls if call_name == name]


def make_repository(client, clock=None, **config_overrides):
    clock = clock or FakeClock()
    return AthenaActivityRepository(
        client, make_config(**config_overrides), sleep=clock.sleep, clock=clock.clock
    )


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
class AthenaConfigTest(unittest.TestCase):

    def test_defaults(self):
        """기본값: us-east-2, primary, 20초, 1000행."""
        config = make_config()
        self.assertEqual(config.region, "us-east-2")
        self.assertEqual(config.workgroup, "primary")
        self.assertEqual(config.query_timeout_seconds, 20.0)
        self.assertEqual(config.max_rows, 1000)
        self.assertIsNone(config.output_location)
        self.assertEqual(
            (DEFAULT_REGION, DEFAULT_WORKGROUP, DEFAULT_QUERY_TIMEOUT_SECONDS, DEFAULT_MAX_ROWS),
            ("us-east-2", "primary", 20.0, 1000),
        )

    def test_from_env_with_required_values_only(self):
        config = AthenaConfig.from_env(
            {"ATHENA_DATABASE": "wearcare_mate_db", "ATHENA_TABLE": "fitbit_activity_table"}
        )
        self.assertEqual(config.database, "wearcare_mate_db")
        self.assertEqual(config.table, "fitbit_activity_table")
        self.assertEqual(config.region, "us-east-2")
        self.assertEqual(config.workgroup, "primary")

    def test_from_env_with_all_values(self):
        config = AthenaConfig.from_env({
            "ATHENA_DATABASE": " test_db ",
            "ATHENA_TABLE": "test_table",
            "ATHENA_REGION": "us-west-2",
            "ATHENA_WORKGROUP": "wg-01",
            "ATHENA_OUTPUT_LOCATION": "s3://example-bucket/results/",
            "ATHENA_QUERY_TIMEOUT_SECONDS": "5.5",
            "ATHENA_MAX_ROWS": "50",
        })
        self.assertEqual(config.database, "test_db")
        self.assertEqual(config.region, "us-west-2")
        self.assertEqual(config.workgroup, "wg-01")
        self.assertEqual(config.output_location, "s3://example-bucket/results/")
        self.assertEqual(config.query_timeout_seconds, 5.5)
        self.assertEqual(config.max_rows, 50)

    def test_from_env_reads_os_environ_by_default(self):
        """environ 을 넘기지 않으면 os.environ 을 읽는다. (테스트 안에서만 격리해 설정)"""
        with mock.patch.dict(
            os.environ, {"ATHENA_DATABASE": "env_db", "ATHENA_TABLE": "env_table"}
        ):
            config = AthenaConfig.from_env()
        self.assertEqual((config.database, config.table), ("env_db", "env_table"))

    def test_from_env_with_dict_ignores_os_environ(self):
        """dict 를 넘기면 os.environ 의 값과 관계없이 dict 만 읽는다."""
        with mock.patch.dict(os.environ, {"ATHENA_DATABASE": "BAD NAME"}):
            config = AthenaConfig.from_env({"ATHENA_DATABASE": "ok_db", "ATHENA_TABLE": "t"})
        self.assertEqual(config.database, "ok_db")

    def test_missing_required_values(self):
        for env in ({}, {"ATHENA_DATABASE": "db"}, {"ATHENA_TABLE": "t"},
                    {"ATHENA_DATABASE": "  ", "ATHENA_TABLE": "t"}):
            with self.assertRaises(DataSourceConfigError, msg=env):
                AthenaConfig.from_env(env)

    def test_invalid_identifiers(self):
        """DB/테이블 이름은 소문자·숫자·밑줄만 허용하고, 메시지에 값을 넣지 않는다."""
        bad_names = ['db"; DROP TABLE x; --', "Upper", "with-dash", "has space",
                     "a.b", "", "x" * 129, None, 123]
        for name in bad_names:
            for field in ("database", "table"):
                with self.assertRaises(DataSourceConfigError) as context:
                    make_config(**{field: name})
                if isinstance(name, str) and name:
                    self.assertNotIn(name, str(context.exception))

    def test_invalid_other_settings(self):
        invalid = [
            {"region": "us east 2"}, {"region": "US-EAST-2"},
            {"workgroup": "wg;drop"},
            {"output_location": "https://bucket/"}, {"output_location": "s3://"},
            {"output_location": "s3://bucket/a b"},
            {"query_timeout_seconds": 0}, {"query_timeout_seconds": -1},
            {"query_timeout_seconds": float("inf")}, {"query_timeout_seconds": True},
            {"max_rows": 0}, {"max_rows": 10001}, {"max_rows": 1.5}, {"max_rows": True},
        ]
        for overrides in invalid:
            with self.assertRaises(DataSourceConfigError, msg=overrides):
                make_config(**overrides)

    def test_invalid_numbers_in_env(self):
        base = {"ATHENA_DATABASE": "db", "ATHENA_TABLE": "t"}
        for extra in ({"ATHENA_QUERY_TIMEOUT_SECONDS": "abc"}, {"ATHENA_MAX_ROWS": "1.5"},
                      {"ATHENA_MAX_ROWS": "many"}):
            with self.assertRaises(DataSourceConfigError, msg=extra):
                AthenaConfig.from_env({**base, **extra})

    def test_repository_requires_config_object(self):
        with self.assertRaises(DataSourceConfigError):
            AthenaActivityRepository(FakeAthenaClient(), {"database": "db"})


# ---------------------------------------------------------------------------
# 사용자 입력 검증과 쿼리 생성
# ---------------------------------------------------------------------------
class QueryValidationTest(unittest.TestCase):

    def test_valid_user_ids(self):
        for user_id in ("1", USER_ID, "0000000123", "9" * 20):
            build_activity_query(make_config(), user_id)

    def test_invalid_user_ids(self):
        """숫자 1~20자가 아니면 검증 오류. 설정 오류나 AWS 장애로 취급하지 않는다."""
        bad_ids = ["", "u-1001", "1' OR '1'='1", "123;", "12 3", " 123", "123\n",
                   "１２３", "1" * 21, "-1", "1.0", None, 123, ["1"]]
        for user_id in bad_ids:
            with self.assertRaises(AthenaQueryValidationError, msg=repr(user_id)) as context:
                build_activity_query(make_config(), user_id)
            self.assertNotIsInstance(context.exception, DataSourceConfigError)
            self.assertNotIsInstance(context.exception, DataSourceUnavailableError)

    def test_valid_dates(self):
        build_activity_query(make_config(), USER_ID, "2099-01-01", "2099-12-31")
        build_activity_query(make_config(), USER_ID, "2096-02-29")  # 윤년

    def test_invalid_dates(self):
        bad_dates = ["", "2099-1-02", "2099-02-30", "2099-13-01", "1/2/2099", "20990101",
                     "２０９９-01-01", "2099-01-01' OR '1'='1", "2099-01-01 ", 20990101]
        for value in bad_dates:
            for field in ("date_from", "date_to"):
                with self.assertRaises(AthenaQueryValidationError, msg=(field, value)):
                    build_activity_query(make_config(), USER_ID, **{field: value})

    def test_validation_message_does_not_echo_input(self):
        with self.assertRaises(AthenaQueryValidationError) as context:
            build_activity_query(make_config(), "1' OR '1'='1")
        self.assertNotIn("OR", str(context.exception))


class BuildQueryTest(unittest.TestCase):

    def test_user_input_is_not_in_sql(self):
        """사용자 입력은 SQL 문자열이 아니라 ExecutionParameters 로만 전달된다."""
        sql, params = build_activity_query(make_config(), USER_ID, "2099-01-01", "2099-01-31")
        for value in (USER_ID, "2099-01-01", "2099-01-31"):
            self.assertNotIn(value, sql)
        self.assertEqual(sql.count("?"), len(params))

    def test_string_parameters_follow_athena_quoting_rule(self):
        """공식 문서 규칙: 문자열 값은 작은따옴표로 감싸고, ? 는 따옴표 안에 두지 않는다."""
        sql, params = build_activity_query(make_config(), USER_ID, "2099-01-01", "2099-01-31")
        self.assertEqual(params, ["'1000000001'", "'2099-01-01'", "'2099-01-31'"])
        self.assertNotIn("'?'", sql)
        self.assertNotIn('"?"', sql)

    def test_date_conditions_are_optional(self):
        cases = [
            ((None, None), ["id = ?"], 1),
            (("2099-01-01", None), ["id = ?", "activitydate >= ?"], 2),
            ((None, "2099-01-31"), ["id = ?", "activitydate <= ?"], 2),
            (("2099-01-01", "2099-01-31"),
             ["id = ?", "activitydate >= ?", "activitydate <= ?"], 3),
        ]
        for (date_from, date_to), expected_conditions, expected_count in cases:
            sql, params = build_activity_query(make_config(), USER_ID, date_from, date_to)
            self.assertIn("WHERE " + " AND ".join(expected_conditions), sql)
            self.assertEqual(len(params), expected_count)

    def test_sql_shape(self):
        sql, _ = build_activity_query(make_config(max_rows=50), USER_ID)
        self.assertTrue(
            sql.startswith("SELECT id, activitydate, totalsteps, calories, veryactiveminutes\n")
        )
        self.assertIn('FROM "test_db"."test_table"', sql)
        self.assertIn("ORDER BY activitydate", sql)
        self.assertTrue(sql.endswith("LIMIT 50"))

    def test_quote_helper_escapes_single_quotes(self):
        """방어 코드: 혹시 작은따옴표가 들어와도 SQL 규칙대로 두 번 써서 이스케이프한다."""
        self.assertEqual(_quote_string_parameter("a'b"), "'a''b'")


# ---------------------------------------------------------------------------
# 쿼리 실행과 상태 확인
# ---------------------------------------------------------------------------
class QueryExecutionTest(unittest.TestCase):

    def test_start_request(self):
        client = FakeAthenaClient()
        make_repository(client).fetch_activity_rows(USER_ID, "2099-01-01")
        request = client.calls_of("start")[0]
        self.assertEqual(request["QueryExecutionContext"], {"Database": "test_db"})
        self.assertEqual(request["WorkGroup"], "primary")
        self.assertEqual(request["ExecutionParameters"], ["'1000000001'", "'2099-01-01'"])
        self.assertNotIn(USER_ID, request["QueryString"])
        self.assertNotIn("ResultConfiguration", request)

    def test_output_location_is_sent_when_configured(self):
        client = FakeAthenaClient()
        make_repository(client, output_location="s3://example-bucket/results/") \
            .fetch_activity_rows(USER_ID)
        request = client.calls_of("start")[0]
        self.assertEqual(
            request["ResultConfiguration"], {"OutputLocation": "s3://example-bucket/results/"}
        )

    def test_invalid_input_makes_no_aws_call(self):
        """사용자 입력이 잘못되면 Athena 를 전혀 호출하지 않는다."""
        client = FakeAthenaClient()
        repository = make_repository(client)
        with self.assertRaises(AthenaQueryValidationError):
            repository.fetch_activity_rows("1' OR '1'='1")
        with self.assertRaises(AthenaQueryValidationError):
            repository.fetch_activity_rows(USER_ID, date_to="bad")
        self.assertEqual(client.calls, [])

    def test_polls_until_succeeded_with_backoff(self):
        client = FakeAthenaClient(states=["QUEUED", "RUNNING", "RUNNING", "SUCCEEDED"])
        clock = FakeClock()
        make_repository(client, clock).fetch_activity_rows(USER_ID)
        self.assertEqual(len(client.calls_of("status")), 4)
        self.assertEqual(clock.sleeps, [0.2, 0.4, 0.8])
        self.assertEqual(client.calls_of("stop"), [])

    def test_backoff_is_capped_at_one_second(self):
        client = FakeAthenaClient(states=["RUNNING"] * 6 + ["SUCCEEDED"])
        clock = FakeClock()
        make_repository(client, clock).fetch_activity_rows(USER_ID)
        self.assertEqual(clock.sleeps, [0.2, 0.4, 0.8, 1.0, 1.0, 1.0])

    def test_failed_and_cancelled_raise_unavailable(self):
        for state in ("FAILED", "CANCELLED"):
            client = FakeAthenaClient(states=[state])
            with self.assertRaises(DataSourceUnavailableError, msg=state):
                make_repository(client).fetch_activity_rows(USER_ID)
            self.assertEqual(client.calls_of("results"), [])
            self.assertEqual(client.calls_of("stop"), [])

    def test_timeout_stops_query(self):
        """시간이 초과되면 쿼리 중지를 요청하고 DataSourceUnavailableError 를 낸다."""
        client = FakeAthenaClient(states=["RUNNING"])
        clock = FakeClock()
        with self.assertRaises(DataSourceUnavailableError):
            make_repository(client, clock, query_timeout_seconds=3).fetch_activity_rows(USER_ID)
        self.assertEqual(client.calls_of("stop"), [{"QueryExecutionId": "qid-1"}])
        self.assertEqual(client.calls_of("results"), [])
        # 기다린 시간이 타임아웃을 넘지 않아야 한다.
        self.assertLessEqual(sum(clock.sleeps), 3 + 1e-9)

    def test_timeout_still_raised_when_stop_fails(self):
        client = FakeAthenaClient(states=["RUNNING"])
        client.stop_error = RuntimeError(SECRET)
        with self.assertRaises(DataSourceUnavailableError):
            make_repository(client, query_timeout_seconds=1).fetch_activity_rows(USER_ID)
        self.assertEqual(len(client.calls_of("stop")), 1)

    def test_client_errors_become_unavailable_without_details(self):
        """AWS 호출 오류는 DataSourceUnavailableError 로 감싸고 원문을 메시지에 넣지 않는다."""
        for attribute in ("start_error", "status_error", "results_error"):
            client = FakeAthenaClient()
            setattr(client, attribute, RuntimeError(SECRET))
            with self.assertRaises(DataSourceUnavailableError, msg=attribute) as context:
                make_repository(client).fetch_activity_rows(USER_ID)
            self.assertNotIn(SECRET, str(context.exception))
            self.assertNotIn(USER_ID, str(context.exception))

    def test_malformed_responses_become_unavailable(self):
        cases = [
            FakeAthenaClient(start_response={}),
            FakeAthenaClient(start_response={"QueryExecutionId": ""}),
            FakeAthenaClient(pages=[{"ResultSet": {"Rows": [header_row()]}}]),  # 컬럼 정보 없음
            FakeAthenaClient(pages=[{"ResultSet": {
                "Rows": "bad",
                "ResultSetMetadata": {"ColumnInfo": [{"Name": "id"}]},
            }}]),
        ]
        for client in cases:
            with self.assertRaises(DataSourceUnavailableError):
                make_repository(client).fetch_activity_rows(USER_ID)


# ---------------------------------------------------------------------------
# 결과 읽기 (헤더, NULL, 페이지네이션, 최대 행 수)
# ---------------------------------------------------------------------------
class ResultReadingTest(unittest.TestCase):

    def test_header_skipped_and_values_are_strings(self):
        client = FakeAthenaClient(pages=[results_page([
            header_row(),
            data_row(USER_ID, "2099-01-01", "1234", "1000", "5"),
        ])])
        rows = make_repository(client).fetch_activity_rows(USER_ID)
        self.assertEqual(rows, [{
            "id": USER_ID, "activitydate": "2099-01-01", "totalsteps": "1234",
            "calories": "1000", "veryactiveminutes": "5",
        }])

    def test_null_values_become_none(self):
        client = FakeAthenaClient(pages=[results_page([
            header_row(),
            data_row(USER_ID, "2099-01-01", None, "1000", None),
        ])])
        row = make_repository(client).fetch_activity_rows(USER_ID)[0]
        self.assertIsNone(row["totalsteps"])
        self.assertIsNone(row["veryactiveminutes"])

    def test_short_row_is_padded_with_none(self):
        client = FakeAthenaClient(pages=[results_page([
            header_row(), {"Data": [{"VarCharValue": USER_ID}, {"VarCharValue": "2099-01-01"}]},
        ])])
        row = make_repository(client).fetch_activity_rows(USER_ID)[0]
        self.assertIsNone(row["calories"])
        self.assertEqual(len(row), len(COLUMNS))

    def test_zero_rows_with_header_only(self):
        """결과가 0행이면(헤더만 있음) 빈 목록을 돌려준다."""
        client = FakeAthenaClient(pages=[results_page([header_row()])])
        self.assertEqual(make_repository(client).fetch_activity_rows(USER_ID), [])
        self.assertEqual(len(client.calls_of("results")), 1)

    def test_zero_rows_without_header(self):
        client = FakeAthenaClient(pages=[results_page([])])
        self.assertEqual(make_repository(client).fetch_activity_rows(USER_ID), [])

    def test_pagination_follows_next_token(self):
        """NextToken 으로 다음 페이지를 읽고, 두 번째 페이지의 첫 행은 헤더로 보지 않는다."""
        client = FakeAthenaClient(pages=[
            results_page([header_row(), data_row(USER_ID, "2099-01-01", "1", "1", "1")],
                         next_token="token-2"),
            results_page([data_row(USER_ID, "2099-01-02", "2", "2", "2")],
                         next_token="token-3"),
            results_page([data_row(USER_ID, "2099-01-03", "3", "3", "3")]),
        ])
        rows = make_repository(client).fetch_activity_rows(USER_ID)
        self.assertEqual([row["activitydate"] for row in rows],
                         ["2099-01-01", "2099-01-02", "2099-01-03"])
        requests = client.calls_of("results")
        self.assertEqual(len(requests), 3)
        self.assertNotIn("NextToken", requests[0])
        self.assertEqual(requests[1]["NextToken"], "token-2")
        self.assertEqual(requests[2]["NextToken"], "token-3")

    def test_page_size_respects_api_limit(self):
        """한 번에 요청하는 행 수는 Athena 제한(1000)을 넘지 않는다."""
        client = FakeAthenaClient()
        make_repository(client).fetch_activity_rows(USER_ID)
        self.assertEqual(client.calls_of("results")[0]["MaxResults"], 1000)

    def test_max_rows_stops_without_extra_page_request(self):
        """최대 행 수에 도달하면 NextToken 이 있어도 다음 페이지를 요청하지 않는다."""
        client = FakeAthenaClient(pages=[
            results_page([header_row(),
                          data_row(USER_ID, "2099-01-01", "1", "1", "1"),
                          data_row(USER_ID, "2099-01-02", "2", "2", "2")],
                         next_token="token-2"),
            results_page([data_row(USER_ID, "2099-01-03", "3", "3", "3"),
                          data_row(USER_ID, "2099-01-04", "4", "4", "4")],
                         next_token="token-3"),
            results_page([data_row(USER_ID, "2099-01-05", "5", "5", "5")]),
        ])
        rows = make_repository(client, max_rows=3).fetch_activity_rows(USER_ID)
        self.assertEqual(len(rows), 3)
        requests = client.calls_of("results")
        self.assertEqual(len(requests), 2)
        # 첫 페이지: 헤더 1 + 최대 3행, 두 번째 페이지: 남은 1행만 요청
        self.assertEqual([request["MaxResults"] for request in requests], [4, 1])

    def test_max_rows_reached_exactly_at_page_end(self):
        client = FakeAthenaClient(pages=[
            results_page([header_row(),
                          data_row(USER_ID, "2099-01-01", "1", "1", "1"),
                          data_row(USER_ID, "2099-01-02", "2", "2", "2")],
                         next_token="token-2"),
            results_page([data_row(USER_ID, "2099-01-03", "3", "3", "3")]),
        ])
        rows = make_repository(client, max_rows=2).fetch_activity_rows(USER_ID)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(client.calls_of("results")), 1)


# ---------------------------------------------------------------------------
# mappers / health_service 연결
# ---------------------------------------------------------------------------
class PipelineIntegrationTest(unittest.TestCase):

    def test_athena_rows_flow_into_health_data_response(self):
        """Athena 문자열 결과 → 매퍼 → 응답 조립이 끝까지 이어져야 한다."""
        client = FakeAthenaClient(pages=[results_page([
            header_row(),
            data_row(USER_ID, "2099-01-01", "1234", "1000", "5"),
            data_row(USER_ID, "2099-01-02", "2345", "1100", None),
        ])])
        rows = make_repository(client).fetch_activity_rows(USER_ID, "2099-01-01", "2099-01-31")
        response = build_health_data_response(
            map_fitbit_activity_rows(rows), USER_ID, "2099-01-01", "2099-01-31"
        )
        self.assertEqual(response, {
            "userId": USER_ID,
            "range": {"from": "2099-01-01", "to": "2099-01-31"},
            "items": [
                {"date": "2099-01-01",
                 "activity": {"totalSteps": 1234, "calories": 1000, "veryActiveMinutes": 5}},
                {"date": "2099-01-02", "activity": {"totalSteps": 2345, "calories": 1100}},
            ],
        })


# ---------------------------------------------------------------------------
# 클라이언트 생성과 boto3 없는 환경
# ---------------------------------------------------------------------------
class ClientFactoryTest(unittest.TestCase):

    def test_missing_boto3_raises_config_error(self):
        """boto3 를 import 할 수 없으면 설정 오류. (sys.modules 에 None 을 넣어 강제로 재현)"""
        with mock.patch.dict(sys.modules, {"boto3": None}):
            with self.assertRaises(DataSourceConfigError):
                create_athena_client("us-east-2")

    def test_invalid_region_raises_config_error_before_import(self):
        with self.assertRaises(DataSourceConfigError):
            create_athena_client("not a region")

    def test_factory_uses_us_east_2_by_default(self):
        """boto3 가 있는 것처럼 가짜 모듈을 넣어, 기본 리전과 타임아웃 설정을 확인한다."""
        fake_boto3 = mock.Mock()
        fake_botocore_config = mock.Mock()
        modules = {
            "boto3": fake_boto3,
            "botocore": mock.Mock(),
            "botocore.config": fake_botocore_config,
        }
        with mock.patch.dict(sys.modules, modules):
            client = create_athena_client()
        self.assertIs(client, fake_boto3.client.return_value)
        args, kwargs = fake_boto3.client.call_args
        self.assertEqual(args, ("athena",))
        self.assertEqual(kwargs["region_name"], "us-east-2")
        config_kwargs = fake_botocore_config.Config.call_args.kwargs
        self.assertEqual(config_kwargs["connect_timeout"], 3)
        self.assertEqual(config_kwargs["read_timeout"], 10)

    def test_module_imports_without_boto3(self):
        """boto3 가 없어도 모듈 자체는 import 되어야 한다(별도 이름으로 새로 불러와 확인)."""
        path = os.path.join(BACKEND_DIR, "src", "athena_repository.py")
        spec = importlib.util.spec_from_file_location("athena_repository_isolated", path)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"boto3": None, "botocore": None}):
            spec.loader.exec_module(module)
        self.assertTrue(hasattr(module, "AthenaActivityRepository"))


if __name__ == "__main__":
    unittest.main()
