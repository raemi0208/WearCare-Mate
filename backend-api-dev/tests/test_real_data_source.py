"""DATA_SOURCE=real (Athena REAL 모드) 통합 테스트.

lambda_handler → data_source → real_health_data → athena_repository → mappers → health_service
전체 흐름을 가짜 Athena 클라이언트로 검증합니다.

AWS 호출 차단:
    - 모든 테스트에서 src.athena_repository.create_athena_client 를 가짜로 바꿉니다.
      기본 가짜는 호출되면 UnexpectedAwsClientCreation(BaseException)을 던집니다.
      BaseException 은 lambda_handler 의 500 처리(except Exception)에 잡히지 않으므로,
      실수로 클라이언트 생성이 일어나면 테스트가 즉시 실패합니다.
    - 가짜 클라이언트가 필요한 테스트만 FakeAthenaClient 를 돌려주게 설정합니다.
    - 쿼리 상태는 즉시 SUCCEEDED/FAILED 를 돌려주므로 실제로 기다리지 않습니다.
      (타임아웃은 test_athena_repository.py 에서 가짜 시계로 검증)

환경변수 격리:
    - 테스트마다 os.environ 을 patch.dict 로 감싸고, 관련 변수(DATA_SOURCE,
      ENABLE_REAL_DATA_TESTING, ATHENA_*)를 모두 지운 뒤 필요한 값만 설정합니다.

테스트 데이터는 모두 가상의 값입니다.
"""

import json
import os
import sys
import unittest
from unittest import mock

# src 패키지를 import 할 수 있도록 backend 폴더를 모듈 검색 경로에 추가합니다.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.athena_repository import (  # noqa: E402
    AthenaQueryValidationError,
    create_athena_client as REAL_CREATE_ATHENA_CLIENT,
)
from src.data_source import (  # noqa: E402
    DataSourceConfigError,
    DataSourceNotFoundError,
    DataSourceRequestError,
    DataSourceUnavailableError,
)
from src.lambda_function import lambda_handler  # noqa: E402
from src.mock_data import build_health_data_mock  # noqa: E402
from src.real_health_data import (  # noqa: E402
    DASHBOARD_USER_ID_ENV,
    ENABLE_REAL_DATA_TESTING_ENV,
    build_real_health_data,
    is_real_data_testing_enabled,
)
from tests.test_athena_repository import (  # noqa: E402
    FakeAthenaClient,
    data_row,
    header_row,
    results_page,
)

USER_ID = "1000000001"
OTHER_USER_ID = "1000000002"
SECRET = "secret-aws-detail-1234"
LOGGER_NAME = "src.lambda_function"
PATCH_CLIENT_FACTORY = "src.athena_repository.create_athena_client"
HEALTH_PATH = f"/users/{USER_ID}/health-data"

_MANAGED_ENV_PREFIXES = ("ATHENA_",)
_MANAGED_ENV_NAMES = ("DATA_SOURCE", ENABLE_REAL_DATA_TESTING_ENV, DASHBOARD_USER_ID_ENV)


class UnexpectedAwsClientCreation(BaseException):
    """허용하지 않은 AWS 클라이언트 생성 시도. (Exception 이 아니므로 500 처리에 잡히지 않음)"""


def _block_client_creation(*args, **kwargs):
    raise UnexpectedAwsClientCreation("테스트에서 허용하지 않은 Athena 클라이언트 생성 시도")


def make_event(method, path, query="__default__"):
    event = {"requestContext": {"http": {"method": method, "path": path}}}
    if query != "__default__":
        event["queryStringParameters"] = query
    return event


def success_pages(*rows):
    """헤더 + 주어진 데이터 행으로 결과 1페이지를 만든다."""
    return [results_page([header_row(), *rows])]


class RealModeTestCase(unittest.TestCase):
    """환경변수 격리 + AWS 클라이언트 생성 차단을 제공하는 기본 클래스."""

    def setUp(self):
        env_patcher = mock.patch.dict(os.environ)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        for name in list(os.environ):
            if name in _MANAGED_ENV_NAMES or name.startswith(_MANAGED_ENV_PREFIXES):
                del os.environ[name]

        # 기본: 클라이언트 생성 차단
        self.client_factory = mock.Mock(side_effect=_block_client_creation)
        factory_patcher = mock.patch(PATCH_CLIENT_FACTORY, self.client_factory)
        factory_patcher.start()
        self.addCleanup(factory_patcher.stop)

    def enable_real(self, switch="true", database="test_db", table="test_table",
                    allowed_user_id=USER_ID):
        """DATA_SOURCE=real + 스위치 + 허용 사용자 + Athena 필수 설정을 이 테스트 안에서만 설정한다."""
        os.environ["DATA_SOURCE"] = "real"
        if allowed_user_id is not None:
            os.environ[DASHBOARD_USER_ID_ENV] = allowed_user_id
        if switch is not None:
            os.environ[ENABLE_REAL_DATA_TESTING_ENV] = switch
        if database is not None:
            os.environ["ATHENA_DATABASE"] = database
        if table is not None:
            os.environ["ATHENA_TABLE"] = table

    def use_fake_client(self, client):
        """이 테스트에서만 가짜 Athena 클라이언트 생성을 허용한다."""
        self.client_factory.side_effect = None
        self.client_factory.return_value = client
        return client

    def call(self, path=HEALTH_PATH, query="__default__", method="GET"):
        return lambda_handler(make_event(method, path, query), None)

    def body_of(self, response):
        return json.loads(response["body"])

    def assert_error(self, response, status, error):
        self.assertEqual(response["statusCode"], status)
        self.assertEqual(response["headers"]["Content-Type"], "application/json")
        body = self.body_of(response)
        self.assertEqual(set(body.keys()), {"error", "message"})
        self.assertEqual(body["error"], error)
        return body


# ---------------------------------------------------------------------------
# 실제 데이터 테스트 스위치
# ---------------------------------------------------------------------------
class RealDataTestingSwitchTest(RealModeTestCase):

    def test_real_without_switch_returns_503(self):
        """DATA_SOURCE=real 만 설정하면 기존처럼 503 이고 클라이언트를 만들지 않는다."""
        self.enable_real(switch=None)
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            response = self.call()
        self.assert_error(response, 503, "unavailable")
        self.client_factory.assert_not_called()

    def test_switch_values_other_than_true_are_disabled(self):
        """'true' 가 아닌 값은 모두 비활성화로 본다(안전한 쪽으로 처리)."""
        for value in ("false", "0", "1", "yes", "on", "", "  ", "truee"):
            self.enable_real(switch=value)
            with self.assertLogs(LOGGER_NAME, level="ERROR"):
                response = self.call()
            self.assertEqual(response["statusCode"], 503, repr(value))
        self.client_factory.assert_not_called()

    def test_switch_ignores_case_and_whitespace(self):
        self.enable_real(switch="  TRUE ")
        self.use_fake_client(FakeAthenaClient())
        self.assertEqual(self.call()["statusCode"], 200)

    def test_switch_without_real_keeps_mock(self):
        """스위치만 켜고 DATA_SOURCE 가 mock/미설정이면 기존 MOCK 응답 그대로."""
        os.environ[ENABLE_REAL_DATA_TESTING_ENV] = "true"
        for data_source in (None, "mock"):
            if data_source is not None:
                os.environ["DATA_SOURCE"] = data_source
            response = self.call(query={"from": "2099-01-01"})
            self.assertEqual(response["statusCode"], 200)
            self.assertEqual(
                self.body_of(response), build_health_data_mock(USER_ID, {"from": "2099-01-01"})
            )
        self.client_factory.assert_not_called()

    def test_is_enabled_reads_given_environ(self):
        self.assertTrue(is_real_data_testing_enabled({ENABLE_REAL_DATA_TESTING_ENV: "true"}))
        self.assertFalse(is_real_data_testing_enabled({}))
        self.assertFalse(is_real_data_testing_enabled({ENABLE_REAL_DATA_TESTING_ENV: None}))


# ---------------------------------------------------------------------------
# 정상 조회
# ---------------------------------------------------------------------------
class RealModeSuccessTest(RealModeTestCase):

    def test_full_flow_returns_health_data_response(self):
        """Athena 조회 → 매핑 → 응답 조립. MOCK 표시 필드는 없어야 한다."""
        self.enable_real()
        client = self.use_fake_client(FakeAthenaClient(pages=success_pages(
            data_row(USER_ID, "2099-01-01", "1234", "1000", "5"),
            data_row(USER_ID, "2099-01-02", "2345", "1100", None),
        )))
        response = self.call(query={"from": "2099-01-01", "to": "2099-01-31"})

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(self.body_of(response), {
            "userId": USER_ID,
            "range": {"from": "2099-01-01", "to": "2099-01-31"},
            "items": [
                {"date": "2099-01-01",
                 "activity": {"totalSteps": 1234, "calories": 1000, "veryActiveMinutes": 5}},
                {"date": "2099-01-02", "activity": {"totalSteps": 2345, "calories": 1100}},
            ],
        })
        # 클라이언트는 us-east-2 로 한 번만 만들고, 사용자 입력은 파라미터로만 전달한다.
        self.client_factory.assert_called_once_with("us-east-2")
        start = client.calls_of("start")[0]
        self.assertEqual(start["QueryExecutionContext"], {"Database": "test_db"})
        self.assertEqual(start["WorkGroup"], "primary")
        self.assertEqual(start["ExecutionParameters"],
                         ["'1000000001'", "'2099-01-01'", "'2099-01-31'"])
        self.assertNotIn(USER_ID, start["QueryString"])

    def test_zero_rows_returns_200_with_empty_items(self):
        self.enable_real()
        self.use_fake_client(FakeAthenaClient(pages=success_pages()))
        response = self.call()
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(self.body_of(response),
                         {"userId": USER_ID, "range": {"from": None, "to": None}, "items": []})

    def test_same_from_and_to_is_allowed(self):
        self.enable_real()
        self.use_fake_client(FakeAthenaClient(pages=success_pages(
            data_row(USER_ID, "2099-01-01", "1", "1", "1"),
        )))
        response = self.call(query={"from": "2099-01-01", "to": "2099-01-01"})
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(len(self.body_of(response)["items"]), 1)

    def test_rows_of_other_users_are_not_exposed(self):
        """조회 결과에 다른 사용자 행이 섞여도 응답에는 요청 사용자 행만 포함된다."""
        self.enable_real()
        self.use_fake_client(FakeAthenaClient(pages=success_pages(
            data_row(USER_ID, "2099-01-01", "1", "1", "1"),
            data_row(OTHER_USER_ID, "2099-01-01", "999", "999", "999"),
        )))
        body_text = self.call()["body"]
        self.assertNotIn(OTHER_USER_ID, body_text)
        self.assertEqual(len(json.loads(body_text)["items"]), 1)

    def test_other_query_parameters_are_ignored(self):
        """from/to 외의 쿼리(metric 등)는 조회에 영향을 주지 않는다."""
        self.enable_real()
        client = self.use_fake_client(FakeAthenaClient())
        response = self.call(query={"metric": "sleep", "interval": "day"})
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(client.calls_of("start")[0]["ExecutionParameters"], ["'1000000001'"])


# ---------------------------------------------------------------------------
# 400: 잘못된 요청 (AWS 호출 없음)
# ---------------------------------------------------------------------------
class RealModeBadRequestTest(RealModeTestCase):

    def test_invalid_user_ids_return_400_without_aws_call(self):
        self.enable_real()
        bad_ids = ["u-1001", "1'%20OR%20'1'='1", "1' OR '1'='1", "123abc", "1" * 21, "１２３"]
        for user_id in bad_ids:
            response = self.call(path=f"/users/{user_id}/health-data")
            body = self.assert_error(response, 400, "bad_request")
            self.assertNotIn(user_id, response["body"])
            self.assertTrue(body["message"])
        self.client_factory.assert_not_called()

    def test_invalid_dates_return_400_and_are_not_ignored(self):
        self.enable_real()
        bad_dates = ["", "2099-1-1", "2099-02-30", "1/2/2099", "20990101",
                     "2099-01-01' OR '1'='1", "2099-01-01,2099-01-02"]
        for value in bad_dates:
            for key in ("from", "to"):
                response = self.call(query={key: value})
                self.assert_error(response, 400, "bad_request")
                if value:
                    self.assertNotIn(value, response["body"])
        self.client_factory.assert_not_called()

    def test_non_string_date_returns_400(self):
        self.enable_real()
        response = self.call(query={"from": 20990101})
        self.assert_error(response, 400, "bad_request")
        self.client_factory.assert_not_called()

    def test_from_after_to_returns_400(self):
        self.enable_real()
        response = self.call(query={"from": "2099-01-02", "to": "2099-01-01"})
        self.assert_error(response, 400, "bad_request")
        self.client_factory.assert_not_called()

    def test_existing_request_validation_still_400(self):
        """빈 userId, 쿼리 형식 오류는 기존 핸들러 검증으로 400."""
        self.enable_real()
        self.assert_error(self.call(path="/users//health-data"), 400, "bad_request")
        self.assert_error(self.call(query=["not", "a", "dict"]), 400, "bad_request")
        self.client_factory.assert_not_called()

    def test_input_validation_runs_before_config_check(self):
        """잘못된 입력은 Athena 설정이 없어도 500 이 아니라 400 이어야 한다."""
        self.enable_real(database=None, table=None)
        response = self.call(path="/users/u-1001/health-data")
        self.assert_error(response, 400, "bad_request")
        self.client_factory.assert_not_called()

    def test_validation_error_from_repository_becomes_400(self):
        """조회 단계에서 AthenaQueryValidationError 가 나도 400 으로 처리한다(방어 경로)."""
        self.enable_real()
        self.use_fake_client(FakeAthenaClient())
        with mock.patch(
            "src.real_health_data.AthenaActivityRepository.fetch_activity_rows",
            side_effect=AthenaQueryValidationError("검증 실패"),
        ):
            response = self.call()
        self.assert_error(response, 400, "bad_request")


# ---------------------------------------------------------------------------
# 500: 설정 오류 / 일반 예외
# ---------------------------------------------------------------------------
class RealModeConfigErrorTest(RealModeTestCase):

    def test_missing_athena_settings_return_500(self):
        for missing_env in ("ATHENA_DATABASE", "ATHENA_TABLE"):
            # 반복마다 필수 설정을 모두 넣은 뒤, 확인할 항목 하나만 지운다.
            self.enable_real()
            del os.environ[missing_env]
            with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
                response = self.call()
            self.assert_error(response, 500, "internal_error")
            self.assertIn("DataSourceConfigError", "\n".join(captured.output), missing_env)
        self.client_factory.assert_not_called()

    def test_invalid_athena_settings_return_500(self):
        cases = [("ATHENA_TABLE", "bad-table;"), ("ATHENA_DATABASE", "Bad DB"),
                 ("ATHENA_REGION", "nowhere"), ("ATHENA_MAX_ROWS", "abc")]
        for name, value in cases:
            self.enable_real()
            os.environ[name] = value
            with self.assertLogs(LOGGER_NAME, level="ERROR"):
                response = self.call()
            self.assert_error(response, 500, "internal_error")
            self.assertNotIn(value, response["body"])
            del os.environ[name]
        self.client_factory.assert_not_called()

    def test_missing_boto3_returns_500(self):
        """실제 클라이언트 생성 함수를 쓰되 boto3 import 를 막아 설정 오류(500)를 확인한다."""
        self.enable_real()
        with mock.patch(PATCH_CLIENT_FACTORY, REAL_CREATE_ATHENA_CLIENT), \
                mock.patch.dict(sys.modules, {"boto3": None}):
            with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
                response = self.call()
        self.assert_error(response, 500, "internal_error")
        self.assertIn("DataSourceConfigError", "\n".join(captured.output))

    def test_generic_value_error_is_still_500(self):
        """AthenaQueryValidationError 가 아닌 일반 ValueError 는 400 이 아니라 500."""
        self.enable_real()
        self.use_fake_client(FakeAthenaClient(pages=success_pages(
            data_row(USER_ID, "2099-01-01", "1", "1", "1"),
        )))
        with mock.patch("src.real_health_data.map_fitbit_activity_rows",
                        side_effect=ValueError(SECRET)):
            with self.assertLogs(LOGGER_NAME, level="ERROR"):
                response = self.call()
        self.assert_error(response, 500, "internal_error")
        self.assertNotIn(SECRET, response["body"])


# ---------------------------------------------------------------------------
# 503: AWS 조회 실패 (MOCK 대체 없음)
# ---------------------------------------------------------------------------
class RealModeUnavailableTest(RealModeTestCase):

    def assert_unavailable_without_leak(self, response):
        self.assert_error(response, 503, "unavailable")
        for leaked in (USER_ID, SECRET, "mock", "MOCK", "Athena", "Traceback"):
            self.assertNotIn(leaked, response["body"])

    def test_query_failed_or_cancelled_returns_503(self):
        for state in ("FAILED", "CANCELLED"):
            self.enable_real()
            self.use_fake_client(FakeAthenaClient(states=[state]))
            with self.assertLogs(LOGGER_NAME, level="ERROR"):
                response = self.call()
            self.assert_unavailable_without_leak(response)

    def test_client_errors_return_503(self):
        for attribute in ("start_error", "status_error", "results_error"):
            self.enable_real()
            client = FakeAthenaClient()
            setattr(client, attribute, RuntimeError(SECRET))
            self.use_fake_client(client)
            with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
                response = self.call()
            self.assert_unavailable_without_leak(response)
            log_text = "\n".join(captured.output)
            self.assertNotIn(SECRET, log_text)
            self.assertNotIn(USER_ID, log_text)

    def test_logs_contain_no_health_data(self):
        """오류 로그에 사용자 ID 나 건강 수치가 남지 않는다."""
        self.enable_real()
        client = FakeAthenaClient(pages=success_pages(
            data_row(USER_ID, "2099-01-01", "98765", "4321", "5"),
        ))
        client.results_error = RuntimeError("rows: 98765 steps")
        self.use_fake_client(client)
        with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
            self.call()
        log_text = "\n".join(captured.output)
        self.assertIn("DataSourceUnavailableError", log_text)
        for leaked in (USER_ID, "98765", "4321"):
            self.assertNotIn(leaked, log_text)


# ---------------------------------------------------------------------------
# 접근 제한: DASHBOARD_USER_ID 와 같은 사용자만 조회 (인증·인가 대체 아님)
# ---------------------------------------------------------------------------
class RealModeAccessRestrictionTest(RealModeTestCase):

    def test_other_user_returns_404_without_aws_call(self):
        """허용되지 않은 사용자는 404 이고, Athena 클라이언트를 만들지 않는다."""
        self.enable_real()
        response = self.call(path=f"/users/{OTHER_USER_ID}/health-data")
        self.assert_error(response, 404, "not_found")
        self.assertNotIn(OTHER_USER_ID, response["body"])
        self.assertNotIn(USER_ID, response["body"])
        self.client_factory.assert_not_called()

    def test_only_exact_user_id_is_allowed(self):
        """앞자리 0 등 표기가 다른 ID 는 같은 사용자로 보지 않는다."""
        self.enable_real(allowed_user_id="0000000123")
        for user_id in ("123", "00000000123", "0000000124"):
            response = self.call(path=f"/users/{user_id}/health-data")
            self.assertEqual(response["statusCode"], 404, user_id)
        self.client_factory.assert_not_called()

    def test_access_check_runs_before_athena_config(self):
        """Athena 설정이 없어도, 허용되지 않은 사용자는 500 이 아니라 404."""
        self.enable_real(database=None, table=None)
        response = self.call(path=f"/users/{OTHER_USER_ID}/health-data")
        self.assert_error(response, 404, "not_found")
        self.client_factory.assert_not_called()

    def test_allowed_user_with_surrounding_spaces_in_setting(self):
        """설정값의 앞뒤 공백은 무시한다."""
        self.enable_real(allowed_user_id=f"  {USER_ID} ")
        self.use_fake_client(FakeAthenaClient())
        self.assertEqual(self.call()["statusCode"], 200)

    def test_missing_or_invalid_allowed_user_returns_500(self):
        """DASHBOARD_USER_ID 가 없거나 형식이 잘못되면 설정 오류(500)이고 값을 노출하지 않는다."""
        for value in (None, "", "   ", "u-1001", "1' OR '1'='1", "1" * 21):
            self.enable_real(allowed_user_id=value)
            if value is None:
                os.environ.pop(DASHBOARD_USER_ID_ENV, None)
            with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
                response = self.call()
            self.assert_error(response, 500, "internal_error")
            self.assertIn("DataSourceConfigError", "\n".join(captured.output))
            if value and value.strip():
                self.assertNotIn(value, response["body"])
        self.client_factory.assert_not_called()

    def test_without_switch_allowed_user_is_not_enough(self):
        """DASHBOARD_USER_ID 만으로는 REAL 조회가 열리지 않는다(스위치 필요)."""
        self.enable_real(switch=None)
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            response = self.call()
        self.assert_error(response, 503, "unavailable")
        self.client_factory.assert_not_called()

    def test_not_found_is_not_value_error(self):
        self.assertFalse(issubclass(DataSourceNotFoundError, ValueError))


# ---------------------------------------------------------------------------
# 다른 API 영향 없음
# ---------------------------------------------------------------------------
class RealModeOtherEndpointsTest(RealModeTestCase):

    def test_other_endpoints_unchanged(self):
        self.enable_real()
        self.assertEqual(self.call(path="/health")["statusCode"], 200)
        for resource in ("anomalies", "guides"):
            response = self.call(path=f"/users/{USER_ID}/{resource}")
            self.assertEqual(response["statusCode"], 200)
            self.assertIs(self.body_of(response)["mock"], True)
        self.assertEqual(self.call(path="/unknown")["statusCode"], 404)
        self.assertEqual(self.call(method="POST")["statusCode"], 404)
        self.client_factory.assert_not_called()


# ---------------------------------------------------------------------------
# build_real_health_data 직접 호출 (의존성 주입)
# ---------------------------------------------------------------------------
class BuildRealHealthDataInjectionTest(unittest.TestCase):
    """environ 과 client_factory 를 직접 넘겨 os.environ 과 패치 없이 동작을 확인한다."""

    ENV = {
        ENABLE_REAL_DATA_TESTING_ENV: "true",
        DASHBOARD_USER_ID_ENV: USER_ID,
        "ATHENA_DATABASE": "test_db",
        "ATHENA_TABLE": "test_table",
    }

    def test_injected_factory_and_environ(self):
        client = FakeAthenaClient(pages=success_pages(
            data_row(USER_ID, "2099-01-01", "10", "20", None),
        ))
        factory = mock.Mock(return_value=client)
        body = build_real_health_data(USER_ID, {}, client_factory=factory, environ=self.ENV)
        factory.assert_called_once_with("us-east-2")
        self.assertEqual(body["items"], [
            {"date": "2099-01-01", "activity": {"totalSteps": 10, "calories": 20}},
        ])

    def test_switch_off_raises_unavailable_without_factory_call(self):
        factory = mock.Mock()
        with self.assertRaises(DataSourceUnavailableError):
            build_real_health_data(USER_ID, {}, client_factory=factory, environ={})
        factory.assert_not_called()

    def test_error_types(self):
        """입력 오류 / 설정 오류가 서로 다른 예외 타입으로 구분된다."""
        factory = mock.Mock()
        with self.assertRaises(DataSourceRequestError):
            build_real_health_data("u-1001", {}, client_factory=factory, environ=self.ENV)
        with self.assertRaises(DataSourceConfigError):
            build_real_health_data(
                USER_ID, {}, client_factory=factory,
                # 허용 사용자는 설정하고 Athena 설정만 빠뜨려, Athena 설정 오류를 확인한다.
                environ={ENABLE_REAL_DATA_TESTING_ENV: "true", DASHBOARD_USER_ID_ENV: USER_ID},
            )
        factory.assert_not_called()

    def test_request_error_is_not_value_error(self):
        """DataSourceRequestError 는 ValueError 가 아니다(일반 ValueError 는 500 유지)."""
        self.assertFalse(issubclass(DataSourceRequestError, ValueError))


if __name__ == "__main__":
    unittest.main()
