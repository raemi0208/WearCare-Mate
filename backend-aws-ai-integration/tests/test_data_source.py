"""data_source 모듈과 health-data 데이터 소스 전환 동작에 대한 단위 테스트.

외부 패키지 없이 파이썬 표준 라이브러리 unittest 만 사용합니다.
AWS 에 접속하지 않으며, 실제 건강 데이터를 사용하지 않습니다.

환경변수 격리:
    모든 테스트는 mock.patch.dict(os.environ) 안에서 실행됩니다.
    테스트 중 DATA_SOURCE 를 바꿔도 테스트가 끝나면 원래 값으로 되돌아가고,
    되돌아갔는지도 테스트마다 확인합니다.

실행 방법(backend 폴더 기준):
    python -m unittest discover -s tests -v
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

from src.data_source import (  # noqa: E402
    DATA_SOURCE_ENV,
    DataSourceConfigError,
    DataSourceUnavailableError,
    get_data_source_name,
    select_health_data_builder,
)
from src.lambda_function import lambda_handler  # noqa: E402
from src.mock_data import build_health_data_mock  # noqa: E402

LOGGER_NAME = "src.lambda_function"
USER_ID = "u-1001"


def make_event(method, path, query="__default__"):
    """테스트용 API Gateway HTTP API(payload 2.0) 이벤트를 만듭니다."""
    event = {"requestContext": {"http": {"method": method, "path": path}}}
    if query != "__default__":
        event["queryStringParameters"] = query
    return event


# 테스트마다 지우는 환경변수 (개발 PC 설정이 테스트 결과에 영향을 주지 않도록)
# - DATA_SOURCE: 데이터 소스 선택
# - ENABLE_REAL_DATA_TESTING, DASHBOARD_USER_ID: REAL 조회 진입 조건
# - ATHENA_*: Athena 조회 설정
# - AI_SOURCE, ML_*: AI 데이터 소스와 AI/ML 호출 설정
_ISOLATED_ENV_NAMES = (DATA_SOURCE_ENV, "ENABLE_REAL_DATA_TESTING", "DASHBOARD_USER_ID", "AI_SOURCE")
_ISOLATED_ENV_PREFIXES = ("ATHENA_", "ML_")


def _is_isolated_env(name):
    return name in _ISOLATED_ENV_NAMES or name.startswith(_ISOLATED_ENV_PREFIXES)


def _snapshot_isolated_env():
    return {name: value for name, value in os.environ.items() if _is_isolated_env(name)}


class EnvIsolatedTestCase(unittest.TestCase):
    """데이터 소스 관련 환경변수를 테스트마다 격리하는 기본 클래스.

    - setUp 에서 os.environ 전체를 patch.dict 로 감싸고, 관련 환경변수
      (DATA_SOURCE, ENABLE_REAL_DATA_TESTING, DASHBOARD_USER_ID, ATHENA_*)를 모두 지운다.
      (개발자 PC 에 이 값들이 설정되어 있어도 테스트 결과가 바뀌지 않게 함)
    - 테스트가 끝나면 patch.dict 가 원래 환경변수로 복원한다.
    - 복원 후 관련 환경변수가 테스트 전과 같은지도 확인한다.
    """

    def setUp(self):
        original = _snapshot_isolated_env()
        # cleanup 은 등록 역순으로 실행된다 → 이 확인이 patch 복원 '이후'에 실행됨
        self.addCleanup(self._assert_env_restored, original)

        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in list(os.environ):
            if _is_isolated_env(name):
                del os.environ[name]

    def _assert_env_restored(self, original):
        self.assertEqual(_snapshot_isolated_env(), original)

    def set_data_source(self, value):
        """현재 테스트 안에서만 DATA_SOURCE 를 설정한다."""
        os.environ[DATA_SOURCE_ENV] = value


class GetDataSourceNameTest(EnvIsolatedTestCase):
    """환경변수 값 해석."""

    def test_default_is_mock_when_unset(self):
        """환경변수가 없으면 mock 이어야 한다."""
        self.assertEqual(get_data_source_name(), "mock")

    def test_mock_value(self):
        self.set_data_source("mock")
        self.assertEqual(get_data_source_name(), "mock")

    def test_real_value(self):
        self.set_data_source("real")
        self.assertEqual(get_data_source_name(), "real")

    def test_case_and_whitespace_are_ignored(self):
        """대소문자와 앞뒤 공백은 무시해야 한다."""
        self.set_data_source("  MOCK ")
        self.assertEqual(get_data_source_name(), "mock")
        self.set_data_source("Real")
        self.assertEqual(get_data_source_name(), "real")

    def test_invalid_value_raises_config_error(self):
        """허용되지 않은 값은 mock 으로 바꾸지 않고 설정 오류여야 한다."""
        for value in ("athena", "timestream", "mocks", "prod"):
            self.set_data_source(value)
            with self.assertRaises(DataSourceConfigError, msg=value):
                get_data_source_name()

    def test_empty_value_raises_config_error(self):
        """빈 문자열/공백만 있는 값도 설정 오류여야 한다(미설정과 구분)."""
        for value in ("", "   "):
            self.set_data_source(value)
            with self.assertRaises(DataSourceConfigError):
                get_data_source_name()

    def test_config_error_message_does_not_echo_value(self):
        """설정 오류 메시지에 잘못 입력된 값 자체를 넣지 않아야 한다."""
        self.set_data_source("secret-like-value")
        with self.assertRaises(DataSourceConfigError) as context:
            get_data_source_name()
        self.assertNotIn("secret-like-value", str(context.exception))

    def test_env_is_read_at_call_time(self):
        """환경변수는 호출할 때마다 읽어야 한다(같은 테스트 안에서 값 변경 반영)."""
        self.assertEqual(get_data_source_name(), "mock")
        self.set_data_source("real")
        self.assertEqual(get_data_source_name(), "real")
        os.environ.pop(DATA_SOURCE_ENV)
        self.assertEqual(get_data_source_name(), "mock")


class SelectHealthDataBuilderTest(EnvIsolatedTestCase):
    """빌더 선택."""

    def test_mock_returns_given_mock_builder(self):
        """mock(기본값)이면 넘겨받은 MOCK 빌더를 그대로 돌려줘야 한다."""
        sentinel = mock.Mock()
        self.assertIs(select_health_data_builder(sentinel), sentinel)
        self.set_data_source("mock")
        self.assertIs(select_health_data_builder(sentinel), sentinel)

    def test_real_does_not_fall_back_to_mock(self):
        """real 이면 MOCK 빌더가 아닌 함수를 돌려주고, MOCK 빌더는 호출되지 않아야 한다."""
        self.set_data_source("real")
        sentinel = mock.Mock()
        builder = select_health_data_builder(sentinel)
        self.assertIsNot(builder, sentinel)
        with self.assertRaises(DataSourceUnavailableError):
            builder(USER_ID, {})
        sentinel.assert_not_called()

    def test_real_selection_itself_does_not_raise(self):
        """real 에서 예외는 빌더 '호출' 시점에 나야 한다(선택 시점에는 안 남)."""
        self.set_data_source("real")
        builder = select_health_data_builder(mock.Mock())
        self.assertTrue(callable(builder))

    def test_invalid_value_raises_on_selection(self):
        """잘못된 값이면 빌더를 고를 때 설정 오류가 나야 한다."""
        self.set_data_source("athena")
        with self.assertRaises(DataSourceConfigError):
            select_health_data_builder(mock.Mock())


class HealthDataEndpointDataSourceTest(EnvIsolatedTestCase):
    """lambda_handler 를 통한 health-data 데이터 소스 전환."""

    def call(self, path, query="__default__"):
        return lambda_handler(make_event("GET", path, query), None)

    def test_unset_returns_existing_mock_response(self):
        """미설정이면 기존 MOCK 응답과 완전히 같아야 한다."""
        response = self.call(f"/users/{USER_ID}/health-data")
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            json.loads(response["body"]), build_health_data_mock(USER_ID, {})
        )

    def test_mock_returns_existing_mock_response(self):
        """DATA_SOURCE=mock 이면 기존 MOCK 응답과 같아야 한다(쿼리 echo 포함)."""
        self.set_data_source("mock")
        query = {"from": "2099-01-01", "to": "2099-01-02"}
        response = self.call(f"/users/{USER_ID}/health-data", query)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            json.loads(response["body"]), build_health_data_mock(USER_ID, query)
        )

    def test_real_returns_503_without_internal_details(self):
        """real 이면 503 과 고정 문구만 돌려주고, 내부 정보는 노출하지 않아야 한다."""
        self.set_data_source("real")
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            response = self.call(f"/users/{USER_ID}/health-data")
        self.assertEqual(response["statusCode"], 503)
        self.assertEqual(response["headers"]["Content-Type"], "application/json")
        body = json.loads(response["body"])
        self.assertEqual(set(body.keys()), {"error", "message"})
        self.assertEqual(body["error"], "unavailable")
        for leaked in (USER_ID, "real", "DATA_SOURCE", "DataSourceUnavailableError",
                       "미구현", "구현되지", "Traceback", "mock"):
            self.assertNotIn(leaked, response["body"])

    def test_real_logs_only_exception_type(self):
        """real 의 503 로그에는 예외 타입만 남고 사용자 ID 는 남지 않아야 한다."""
        self.set_data_source("real")
        with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
            self.call(f"/users/{USER_ID}/health-data")
        log_text = "\n".join(captured.output)
        self.assertIn("DataSourceUnavailableError", log_text)
        self.assertNotIn(USER_ID, log_text)

    def test_real_still_validates_request_first(self):
        """real 이어도 빈 userId 와 잘못된 쿼리는 503 이 아니라 400 이어야 한다."""
        self.set_data_source("real")
        self.assertEqual(self.call("/users//health-data")["statusCode"], 400)
        self.assertEqual(
            self.call(f"/users/{USER_ID}/health-data", ["not", "a", "dict"])["statusCode"],
            400,
        )

    def test_invalid_value_returns_500(self):
        """잘못된 DATA_SOURCE 는 MOCK 으로 대체되지 않고 500 이어야 한다."""
        self.set_data_source("athena")
        with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
            response = self.call(f"/users/{USER_ID}/health-data")
        self.assertEqual(response["statusCode"], 500)
        body = json.loads(response["body"])
        self.assertEqual(body["error"], "internal_error")
        self.assertNotIn("mock", body)
        self.assertNotIn("athena", response["body"])
        # 운영자가 원인을 알 수 있도록 로그에는 설정 오류 타입이 남아야 한다.
        self.assertIn("DataSourceConfigError", "\n".join(captured.output))


class OtherEndpointsUnaffectedTest(EnvIsolatedTestCase):
    """DATA_SOURCE 설정과 관계없이 다른 API 는 기존 동작을 유지해야 한다."""

    def assert_others_unchanged(self):
        health = lambda_handler(make_event("GET", "/health"), None)
        self.assertEqual(health["statusCode"], 200)
        self.assertEqual(json.loads(health["body"])["status"], "ok")

        for resource in ("anomalies", "guides"):
            response = lambda_handler(make_event("GET", f"/users/{USER_ID}/{resource}"), None)
            self.assertEqual(response["statusCode"], 200, resource)
            self.assertIs(json.loads(response["body"])["mock"], True, resource)

        self.assertEqual(lambda_handler(make_event("GET", "/unknown"), None)["statusCode"], 404)
        self.assertEqual(
            lambda_handler(make_event("POST", f"/users/{USER_ID}/health-data"), None)["statusCode"],
            404,
        )
        self.assertEqual(lambda_handler({"foo": "bar"}, None)["statusCode"], 400)

    def test_with_real(self):
        self.set_data_source("real")
        self.assert_others_unchanged()

    def test_with_invalid_value(self):
        """잘못된 값이어도 health-data 외 API 는 영향을 받지 않아야 한다."""
        self.set_data_source("athena")
        self.assert_others_unchanged()


if __name__ == "__main__":
    unittest.main()
