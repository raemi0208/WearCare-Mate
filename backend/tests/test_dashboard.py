"""GET /dashboard, GET /ai-guide (MOCK) 테스트.

- 응답이 프론트엔드 API.md 의 JSON 스키마(필드 이름·타입)를 따르는지 검사합니다.
- 예시 데이터가 실제 분석 결과로 오인되지 않도록 표시되어 있는지 검사합니다.
- AWS 에 접속하지 않습니다. Athena 클라이언트 생성은 테스트마다 차단합니다.
- 데이터 소스 관련 환경변수는 테스트마다 격리합니다.
"""

import json
import os
import sys
import unittest
from unittest import mock

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.dashboard_mock_data import build_ai_guide_mock, build_dashboard_mock  # noqa: E402
from src.lambda_function import lambda_handler  # noqa: E402
from src.mock_data import (  # noqa: E402
    build_anomalies_mock,
    build_guides_mock,
    build_health_data_mock,
)

LOGGER_NAME = "src.lambda_function"
PATCH_CLIENT_FACTORY = "src.athena_repository.create_athena_client"

# API.md 기준 스키마
DASHBOARD_KEYS = {"user", "summaryStats", "timeseries", "sleepStages",
                  "anomalies", "aiGuide", "notifications"}
# 발표용 "별도 데이터셋" 요약은 선택 키(MOCK 은 항상 포함, REAL 은 스위치 켜짐 시 포함).
DATASET_SUMMARY_KEYS = {"sleepDatasetSummary", "heartRateDatasetSummary",
                        "psychologyDatasetSummary"}
AI_GUIDE_KEYS = {"model", "updatedAt", "headline", "text", "actions"}
SEVERITIES = {"danger", "warn", "ok"}
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

# AI_SOURCE, ML_* 도 격리한다. (개발 PC 에 AI_SOURCE=real 이 있어도 MOCK 테스트가 안정적이도록)
_ISOLATED_ENV_NAMES = ("DATA_SOURCE", "ENABLE_REAL_DATA_TESTING", "DASHBOARD_USER_ID", "AI_SOURCE")
_ISOLATED_ENV_PREFIXES = ("ATHENA_", "ML_")


class UnexpectedAwsClientCreation(BaseException):
    """허용하지 않은 AWS 클라이언트 생성 시도. (500 처리에 잡히지 않음)"""


def _block_client_creation(*args, **kwargs):
    raise UnexpectedAwsClientCreation("테스트에서 허용하지 않은 Athena 클라이언트 생성 시도")


def make_event(method, path, query="__default__"):
    event = {"requestContext": {"http": {"method": method, "path": path}}}
    if query != "__default__":
        event["queryStringParameters"] = query
    return event


def is_number(value):
    """bool 은 int 의 하위 타입이므로 숫자로 보지 않는다."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class SchemaAssertions:
    """API.md 필드 표를 그대로 옮긴 스키마 검사 도우미."""

    def assert_strings(self, obj, keys, where):
        for key in keys:
            self.assertIsInstance(obj.get(key), str, f"{where}.{key}")

    def assert_ai_guide_schema(self, guide, where="aiGuide"):
        self.assertIsInstance(guide, dict, where)
        self.assertEqual(set(guide.keys()), AI_GUIDE_KEYS, where)
        self.assert_strings(guide, ("model", "updatedAt", "headline", "text"), where)
        self.assertIsInstance(guide["actions"], list, f"{where}.actions")
        for action in guide["actions"]:
            self.assertIsInstance(action, str, f"{where}.actions[]")

    def assert_dashboard_schema(self, body):
        # 필수 키는 모두 있어야 하고, 추가로 허용되는 것은 선택적 데이터셋 요약 키뿐이다.
        keys = set(body.keys())
        self.assertTrue(DASHBOARD_KEYS <= keys, DASHBOARD_KEYS - keys)
        self.assertTrue(keys <= (DASHBOARD_KEYS | DATASET_SUMMARY_KEYS),
                        keys - (DASHBOARD_KEYS | DATASET_SUMMARY_KEYS))

        user = body["user"]
        self.assertEqual(set(user.keys()), {"name", "meta", "initial"})
        self.assert_strings(user, ("name", "meta", "initial"), "user")

        self.assertIsInstance(body["summaryStats"], list)
        for stat in body["summaryStats"]:
            self.assertEqual(set(stat.keys()),
                             {"id", "icon", "label", "value", "unit", "delta", "deltaLabel"})
            self.assert_strings(stat, ("id", "icon", "label", "value", "unit", "deltaLabel"),
                                "summaryStats[]")
            self.assertTrue(is_number(stat["delta"]), "summaryStats[].delta")

        timeseries = body["timeseries"]
        self.assertEqual(set(timeseries.keys()), {"sleep", "heartRate", "steps"})
        for name, points in timeseries.items():
            self.assertIsInstance(points, list, name)
            for point in points:
                self.assertEqual(set(point.keys()), {"label", "value", "anomaly"}, name)
                self.assertIsInstance(point["label"], str, name)
                self.assertTrue(is_number(point["value"]), f"timeseries.{name}[].value")
                self.assertIsInstance(point["anomaly"], bool, name)

        stages = body["sleepStages"]
        self.assertEqual(set(stages.keys()), {"totalLabel", "segments"})
        self.assertIsInstance(stages["totalLabel"], str)
        self.assertIsInstance(stages["segments"], list)
        for segment in stages["segments"]:
            self.assertTrue({"id", "label", "pct"} <= set(segment.keys()))
            self.assertTrue(set(segment.keys()) <= {"id", "label", "pct", "color"})
            self.assert_strings(segment, ("id", "label"), "segments[]")
            self.assertTrue(is_number(segment["pct"]))
            if "color" in segment:
                self.assertIsInstance(segment["color"], str)

        self.assertIsInstance(body["anomalies"], list)
        for anomaly in body["anomalies"]:
            self.assertEqual(set(anomaly.keys()), {"id", "severity", "title", "time", "desc"})
            self.assert_strings(anomaly, ("id", "severity", "title", "time", "desc"), "anomalies[]")
            self.assertIn(anomaly["severity"], SEVERITIES)

        self.assert_ai_guide_schema(body["aiGuide"])

        self.assertIsInstance(body["notifications"], list)
        for item in body["notifications"]:
            self.assertEqual(set(item.keys()), {"id", "icon", "title", "time"})
            self.assert_strings(item, ("id", "icon", "title", "time"), "notifications[]")


class DashboardTestCase(SchemaAssertions, unittest.TestCase):
    """환경변수 격리 + AWS 클라이언트 생성 차단."""

    def setUp(self):
        original = self._snapshot_env()
        self.addCleanup(lambda: self.assertEqual(self._snapshot_env(), original))

        env_patcher = mock.patch.dict(os.environ)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        for name in list(os.environ):
            if self._is_isolated(name):
                del os.environ[name]

        self.client_factory = mock.Mock(side_effect=_block_client_creation)
        factory_patcher = mock.patch(PATCH_CLIENT_FACTORY, self.client_factory)
        factory_patcher.start()
        self.addCleanup(factory_patcher.stop)

    @staticmethod
    def _is_isolated(name):
        return name in _ISOLATED_ENV_NAMES or name.startswith(_ISOLATED_ENV_PREFIXES)

    def _snapshot_env(self):
        return {k: v for k, v in os.environ.items() if self._is_isolated(k)}

    def call(self, path, method="GET", query="__default__"):
        return lambda_handler(make_event(method, path, query), None)

    def body_of(self, response):
        return json.loads(response["body"])


# ---------------------------------------------------------------------------
# GET /dashboard
# ---------------------------------------------------------------------------
class DashboardSchemaTest(DashboardTestCase):

    def test_returns_200_json(self):
        response = self.call("/dashboard")
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["headers"]["Content-Type"], "application/json")

    def test_follows_api_md_schema(self):
        self.assert_dashboard_schema(self.body_of(self.call("/dashboard")))

    def test_no_fields_outside_api_md(self):
        """API.md 에 없는 필드(mock, _note, meta 등)는 넣지 않는다."""
        body = self.body_of(self.call("/dashboard"))
        for key in ("mock", "_note", "meta", "requestedRange"):
            self.assertNotIn(key, body)

    def test_mock_follows_api_md_rules(self):
        """MOCK 은 API.md 의 권장·규칙(카드 4개, 7일 월~일, pct 합계 100)을 따른다."""
        body = self.body_of(self.call("/dashboard"))
        self.assertEqual([stat["id"] for stat in body["summaryStats"]],
                         ["sleep", "hr", "steps", "score"])
        for name, points in body["timeseries"].items():
            self.assertEqual([point["label"] for point in points], WEEKDAYS, name)
        self.assertEqual(sum(segment["pct"] for segment in body["sleepStages"]["segments"]), 100)

    def test_summary_value_is_string_and_timeseries_value_is_number(self):
        body = self.body_of(self.call("/dashboard"))
        steps_card = next(stat for stat in body["summaryStats"] if stat["id"] == "steps")
        self.assertEqual(steps_card["value"], "7,929")
        self.assertIsInstance(body["timeseries"]["steps"][0]["value"], int)

    def test_each_call_returns_fresh_data(self):
        """반환된 dict 를 바꿔도 다음 응답에 영향이 없다."""
        first = build_dashboard_mock()
        first["user"]["name"] = "changed"
        first["timeseries"]["steps"].clear()
        second = build_dashboard_mock()
        self.assertEqual(second["user"]["name"], "예시 사용자")
        self.assertEqual(len(second["timeseries"]["steps"]), 7)


class DashboardMockMarkerTest(DashboardTestCase):
    """예시 데이터가 실제 분석 결과로 오인되지 않도록 표시되어 있는지."""

    def setUp(self):
        super().setUp()
        self.body = self.body_of(self.call("/dashboard"))

    def test_user_is_marked_as_example(self):
        self.assertIn("예시", self.body["user"]["name"])
        self.assertIn("실제 사용자 아님", self.body["user"]["meta"])

    def test_summary_stats_are_marked(self):
        for stat in self.body["summaryStats"]:
            self.assertEqual(stat["deltaLabel"], "예시 데이터", stat["id"])

    def test_anomalies_are_marked(self):
        for anomaly in self.body["anomalies"]:
            self.assertTrue(anomaly["title"].startswith("[예시]"), anomaly["id"])
            self.assertIn("AI 분석 결과가 아닌 예시 데이터", anomaly["desc"])
            self.assertIn("예시", anomaly["time"])

    def test_notifications_are_marked(self):
        for item in self.body["notifications"]:
            self.assertTrue(item["title"].startswith("[예시]"), item["id"])

    def test_sleep_stages_total_is_marked(self):
        self.assertIn("예시", self.body["sleepStages"]["totalLabel"])

    def test_ai_guide_is_marked_and_not_attributed_to_bedrock(self):
        guide = self.body["aiGuide"]
        self.assertIn("MOCK", guide["model"])
        self.assertIn("실제 AI 생성 아님", guide["model"])
        self.assertNotIn("Bedrock", guide["model"])
        self.assertNotIn("Claude", guide["model"])
        self.assertTrue(guide["headline"].startswith("[예시]"))
        self.assertIn("예시", guide["updatedAt"])

    def test_ai_guide_has_medical_disclaimer(self):
        text = self.body["aiGuide"]["text"]
        self.assertIn("진단", text)
        self.assertIn("치료", text)
        self.assertIn("대체하지 않습니다", text)


class DashboardDataSourceTest(DashboardTestCase):

    def test_mock_and_unset_return_mock_dashboard(self):
        expected = build_dashboard_mock()
        self.assertEqual(self.body_of(self.call("/dashboard")), expected)
        os.environ["DATA_SOURCE"] = "mock"
        self.assertEqual(self.body_of(self.call("/dashboard")), expected)

    def test_real_returns_503_without_mock_fallback(self):
        """REAL 대시보드는 아직 미구현 → 503. 예시 데이터로 대체하지 않는다."""
        os.environ["DATA_SOURCE"] = "real"
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            response = self.call("/dashboard")
        self.assertEqual(response["statusCode"], 503)
        body = self.body_of(response)
        self.assertEqual(set(body.keys()), {"error", "message"})
        self.assertEqual(body["error"], "unavailable")
        self.assertNotIn("예시", response["body"])
        self.client_factory.assert_not_called()

    def test_real_with_switch_and_user_uses_athena_path(self):
        """스위치·DASHBOARD_USER_ID·Athena 설정이 모두 있으면 REAL 경로(Athena 조회)로 진입한다.

        (2단계에서 REAL 대시보드를 연결하면서 "아직 503" 이던 기대를 바꾼 테스트.
         스위치가 없으면 503 인 조건은 test_real_returns_503_without_mock_fallback 에서 유지한다.
         상세 동작은 tests/test_dashboard_real.py 에서 검증한다.)
        """
        os.environ.update({
            "DATA_SOURCE": "real", "ENABLE_REAL_DATA_TESTING": "true",
            "DASHBOARD_USER_ID": "1000000001",
            "ATHENA_DATABASE": "test_db", "ATHENA_TABLE": "test_table",
        })
        fake_client = mock.Mock()
        fake_client.start_query_execution.return_value = {"QueryExecutionId": "qid-1"}
        fake_client.get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
        }
        fake_client.get_query_results.return_value = {"ResultSet": {
            "Rows": [],
            "ResultSetMetadata": {"ColumnInfo": [{"Name": "id"}]},
        }}
        self.client_factory.side_effect = None
        self.client_factory.return_value = fake_client

        response = self.call("/dashboard")
        self.assertEqual(response["statusCode"], 200)
        self.client_factory.assert_called_once_with("us-east-2")
        # 실제 데이터가 없으므로 수면·심박을 임의로 만들지 않는다.
        body = self.body_of(response)
        self.assertEqual(body["timeseries"]["sleep"], [])
        self.assertEqual(body["timeseries"]["heartRate"], [])

    def test_invalid_data_source_returns_500(self):
        os.environ["DATA_SOURCE"] = "athena"
        with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
            response = self.call("/dashboard")
        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(self.body_of(response)["error"], "internal_error")
        self.assertIn("DataSourceConfigError", "\n".join(captured.output))


class DashboardRequestTest(DashboardTestCase):

    def test_query_parameters_do_not_change_target(self):
        """userId 등 쿼리를 보내도 조회 대상이나 응답이 바뀌지 않는다."""
        expected = self.body_of(self.call("/dashboard"))
        for query in ({"userId": "1000000002"}, {"user_id": "1"}, None, ["not", "a", "dict"]):
            response = self.call("/dashboard", query=query)
            self.assertEqual(response["statusCode"], 200, query)
            self.assertEqual(self.body_of(response), expected, query)
            self.assertNotIn("1000000002", response["body"])

    def test_unsupported_methods_and_paths_return_404(self):
        for method, path in (("POST", "/dashboard"), ("PUT", "/dashboard"),
                             ("POST", "/ai-guide"), ("DELETE", "/ai-guide"),
                             ("GET", "/dashboard/extra"), ("GET", "/Dashboard")):
            response = self.call(path, method=method)
            self.assertEqual(response["statusCode"], 404, (method, path))
            self.assertEqual(self.body_of(response)["error"], "not_found")


# ---------------------------------------------------------------------------
# GET /ai-guide
# ---------------------------------------------------------------------------
class AiGuideTest(DashboardTestCase):

    def test_follows_ai_guide_schema(self):
        response = self.call("/ai-guide")
        self.assertEqual(response["statusCode"], 200)
        self.assert_ai_guide_schema(self.body_of(response), where="/ai-guide")

    def test_same_structure_as_dashboard_ai_guide(self):
        guide = self.body_of(self.call("/ai-guide"))
        dashboard_guide = self.body_of(self.call("/dashboard"))["aiGuide"]
        self.assertEqual(guide, dashboard_guide)
        self.assertEqual(guide, build_ai_guide_mock())

    def test_is_marked_as_mock(self):
        guide = self.body_of(self.call("/ai-guide"))
        self.assertIn("MOCK", guide["model"])
        self.assertNotIn("Bedrock", guide["model"])
        self.assertTrue(guide["headline"].startswith("[예시]"))
        self.assertIn("대체하지 않습니다", guide["text"])

    def test_stays_mock_regardless_of_data_source(self):
        """AI/ML 연동 전이므로 DATA_SOURCE 와 관계없이 예시 가이드를 돌려준다(기존 /guides 와 같음)."""
        for value in ("real", "athena"):
            os.environ["DATA_SOURCE"] = value
            response = self.call("/ai-guide")
            self.assertEqual(response["statusCode"], 200, value)
            self.assertEqual(self.body_of(response), build_ai_guide_mock(), value)
        self.client_factory.assert_not_called()


# ---------------------------------------------------------------------------
# 기존 API 유지
# ---------------------------------------------------------------------------
class ExistingApisUnchangedTest(DashboardTestCase):

    def test_existing_endpoints_unchanged(self):
        health = self.call("/health")
        self.assertEqual(self.body_of(health),
                         {"status": "ok", "service": "WearCare Mate Backend"})
        cases = [
            ("health-data", build_health_data_mock),
            ("anomalies", build_anomalies_mock),
            ("guides", build_guides_mock),
        ]
        for resource, builder in cases:
            response = self.call(f"/users/u-1001/{resource}")
            self.assertEqual(response["statusCode"], 200, resource)
            self.assertEqual(self.body_of(response), builder("u-1001", {}), resource)
        self.assertEqual(self.call("/unknown")["statusCode"], 404)


if __name__ == "__main__":
    unittest.main()
