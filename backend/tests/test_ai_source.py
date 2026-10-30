"""AI_SOURCE (AI 데이터 소스 선택) 테스트.

- AI_SOURCE 는 DATA_SOURCE 와 독립이다. 기본값은 mock.
- AI_SOURCE=real 은 아직 API 에 연결하지 않았으므로 /dashboard, /ai-guide 는 503 이다.
  (예시 데이터로 조용히 대체하지 않는다)
- AWS 에 접속하지 않는다. 환경변수와 Athena 클라이언트 생성은 DashboardTestCase 가 격리·차단한다.
"""

import os
import sys
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.dashboard_mock_data import build_ai_guide_mock, build_dashboard_mock  # noqa: E402
from src.data_source import (  # noqa: E402
    DataSourceConfigError,
    DataSourceUnavailableError,
    ensure_ai_source_is_mock,
    get_ai_source_name,
)
from src.mock_data import build_anomalies_mock, build_guides_mock  # noqa: E402
from tests.test_dashboard import LOGGER_NAME, DashboardTestCase  # noqa: E402


class GetAiSourceNameTest(unittest.TestCase):

    def test_default_is_mock(self):
        self.assertEqual(get_ai_source_name({}), "mock")

    def test_values_ignore_case_and_whitespace(self):
        self.assertEqual(get_ai_source_name({"AI_SOURCE": " MOCK "}), "mock")
        self.assertEqual(get_ai_source_name({"AI_SOURCE": "Real"}), "real")

    def test_invalid_values_raise_config_error_without_echo(self):
        for value in ("bedrock", "", "  ", "secret-like-value"):
            with self.assertRaises(DataSourceConfigError, msg=value) as context:
                get_ai_source_name({"AI_SOURCE": value})
            if value.strip():
                self.assertNotIn(value, str(context.exception))

    def test_independent_from_data_source(self):
        self.assertEqual(get_ai_source_name({"DATA_SOURCE": "real"}), "mock")

    def test_ensure_mock(self):
        ensure_ai_source_is_mock({})
        ensure_ai_source_is_mock({"AI_SOURCE": "mock"})
        with self.assertRaises(DataSourceUnavailableError):
            ensure_ai_source_is_mock({"AI_SOURCE": "real"})
        with self.assertRaises(DataSourceConfigError):
            ensure_ai_source_is_mock({"AI_SOURCE": "x"})


class AiSourceEndpointTest(DashboardTestCase):

    def test_mock_or_unset_keeps_existing_responses(self):
        for value in (None, "mock"):
            if value is not None:
                os.environ["AI_SOURCE"] = value
            self.assertEqual(self.body_of(self.call("/dashboard")), build_dashboard_mock())
            self.assertEqual(self.body_of(self.call("/ai-guide")), build_ai_guide_mock())

    def test_real_returns_503_without_mock_fallback(self):
        os.environ["AI_SOURCE"] = "real"
        for path in ("/dashboard", "/ai-guide"):
            with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
                response = self.call(path)
            self.assertEqual(response["statusCode"], 503, path)
            body = self.body_of(response)
            self.assertEqual(set(body.keys()), {"error", "message"})
            self.assertEqual(body["error"], "unavailable")
            self.assertNotIn("예시", response["body"])
            self.assertIn("DataSourceUnavailableError", "\n".join(captured.output))
        self.client_factory.assert_not_called()

    def test_real_ai_with_real_data_source_still_503(self):
        """DATA_SOURCE REAL 조건이 모두 있어도 AI_SOURCE=real 은 아직 연결 전이므로 503."""
        os.environ.update({
            "AI_SOURCE": "real", "DATA_SOURCE": "real", "ENABLE_REAL_DATA_TESTING": "true",
            "DASHBOARD_USER_ID": "1000000001",
            "ATHENA_DATABASE": "test_db", "ATHENA_TABLE": "test_table",
            "ML_FUNCTION_NAME": "wearcare-ml",
        })
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            response = self.call("/dashboard")
        self.assertEqual(response["statusCode"], 503)
        self.client_factory.assert_not_called()

    def test_invalid_ai_source_returns_500(self):
        os.environ["AI_SOURCE"] = "bedrock"
        for path in ("/dashboard", "/ai-guide"):
            with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
                response = self.call(path)
            self.assertEqual(response["statusCode"], 500, path)
            self.assertIn("DataSourceConfigError", "\n".join(captured.output))

    def test_other_endpoints_are_not_affected(self):
        """기존 /health 와 /users/{userId}/anomalies·guides(MOCK) 는 AI_SOURCE 의 영향을 받지 않는다."""
        for value in ("real", "bedrock"):
            os.environ["AI_SOURCE"] = value
            self.assertEqual(self.call("/health")["statusCode"], 200)
            self.assertEqual(self.body_of(self.call("/users/u-1001/anomalies")),
                             build_anomalies_mock("u-1001", {}))
            self.assertEqual(self.body_of(self.call("/users/u-1001/guides")),
                             build_guides_mock("u-1001", {}))


if __name__ == "__main__":
    unittest.main()
