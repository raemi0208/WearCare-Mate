"""GET /dashboard REAL 모드(걸음 수만 Athena 실제 데이터) 통합 테스트.

lambda_handler → data_source → dashboard_data → real_health_data → athena_repository
→ mappers → health_service → dashboard_service 전체 흐름을 가짜 Athena 클라이언트로 검증합니다.

- AWS 에 접속하지 않습니다. 기본적으로 클라이언트 생성을 차단하고(BaseException),
  필요한 테스트에서만 가짜 클라이언트를 돌려줍니다.
- 데이터 소스 관련 환경변수는 테스트마다 격리합니다. (DashboardTestCase)
- 값은 모두 가상이며, 날짜만 실제 Fitbit 데이터 기간(2016년)과 같은 구간을 씁니다.
  2016-04-04 는 월요일입니다.
"""

import json
import os
import sys
import unittest
from unittest import mock

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.dashboard_mock_data import build_dashboard_mock  # noqa: E402
from tests.test_athena_repository import (  # noqa: E402
    FakeAthenaClient,
    data_row,
    header_row,
    results_page,
)
from tests.test_dashboard import LOGGER_NAME, DashboardTestCase  # noqa: E402

USER_ID = "1000000001"
OTHER_USER_ID = "1000000002"
SECRET = "secret-aws-detail-1234"

# 기준 주 2016-04-04(월)~04-10(일): 월 1000, 화 2000, 목 3000, 토 6000 → 평균 3000
# 지난주 2016-03-28(월)~04-03(일): 2000, 2000 → 평균 2000 → +50%
THIS_WEEK_ROWS = [
    data_row(USER_ID, "2016-04-04", "1000", "1800", "10"),
    data_row(USER_ID, "2016-04-05", "2000", "1900", None),
    data_row(USER_ID, "2016-04-07", "3000", "2000", "20"),
    data_row(USER_ID, "2016-04-09", "6000", "2100", "30"),
]
LAST_WEEK_ROWS = [
    data_row(USER_ID, "2016-03-28", "2000", "1700", "5"),
    data_row(USER_ID, "2016-04-03", "2000", "1750", "5"),
]


def pages(*rows):
    return [results_page([header_row(), *rows])]


class RealDashboardTestCase(DashboardTestCase):
    """REAL 진입 조건을 설정하는 도우미."""

    def enable_real(self, **overrides):
        values = {
            "DATA_SOURCE": "real",
            "ENABLE_REAL_DATA_TESTING": "true",
            "DASHBOARD_USER_ID": USER_ID,
            "ATHENA_DATABASE": "test_db",
            "ATHENA_TABLE": "test_table",
        }
        values.update(overrides)
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def use_fake_client(self, client):
        self.client_factory.side_effect = None
        self.client_factory.return_value = client
        return client

    def get_dashboard(self, query="__default__"):
        return self.call("/dashboard", query=query)

    def assert_error(self, response, status, error):
        self.assertEqual(response["statusCode"], status)
        body = self.body_of(response)
        self.assertEqual(set(body.keys()), {"error", "message"})
        self.assertEqual(body["error"], error)


class RealDashboardSuccessTest(RealDashboardTestCase):

    def setUp(self):
        super().setUp()
        self.enable_real()

    def test_steps_are_real_and_other_health_data_is_empty(self):
        self.use_fake_client(FakeAthenaClient(pages=pages(*THIS_WEEK_ROWS, *LAST_WEEK_ROWS)))
        response = self.get_dashboard()
        self.assertEqual(response["statusCode"], 200)
        body = self.body_of(response)
        self.assert_dashboard_schema(body)

        # 실제 데이터: steps 카드 1개와 걸음 수 시계열
        self.assertEqual(body["summaryStats"], [{
            "id": "steps", "icon": "👟", "label": "평균 걸음 수", "value": "3,000",
            "unit": "보", "delta": 50, "deltaLabel": "지난주 대비 · 2016-04-04 ~ 2016-04-10",
        }])
        self.assertEqual(body["timeseries"]["steps"], [
            {"label": "월", "value": 1000, "anomaly": False},
            {"label": "화", "value": 2000, "anomaly": False},
            {"label": "목", "value": 3000, "anomaly": False},
            {"label": "토", "value": 6000, "anomaly": False},
        ])
        # 데이터가 없는 항목: 임의 수치를 만들지 않음
        self.assertEqual(body["timeseries"]["sleep"], [])
        self.assertEqual(body["timeseries"]["heartRate"], [])
        self.assertEqual(body["sleepStages"], {"totalLabel": "데이터 없음", "segments": []})

    def test_mock_sections_stay_marked(self):
        """anomalies / aiGuide / notifications 는 '[예시]' 표시가 있는 MOCK 그대로."""
        self.use_fake_client(FakeAthenaClient(pages=pages(*THIS_WEEK_ROWS)))
        body = self.body_of(self.get_dashboard())
        mock = build_dashboard_mock()
        for key in ("anomalies", "aiGuide", "notifications"):
            self.assertEqual(body[key], mock[key], key)
        self.assertIn("MOCK", body["aiGuide"]["model"])

    def test_user_is_demo_label_without_user_id(self):
        self.use_fake_client(FakeAthenaClient(pages=pages(*THIS_WEEK_ROWS)))
        response = self.get_dashboard()
        body = self.body_of(response)
        self.assertEqual(body["user"]["name"], "데모 사용자")
        self.assertIn("인증 미적용", body["user"]["meta"])
        self.assertNotIn(USER_ID, response["body"])

    def test_queries_only_dashboard_user_without_date_filter(self):
        client = self.use_fake_client(FakeAthenaClient(pages=pages(*THIS_WEEK_ROWS)))
        self.get_dashboard(query={"userId": OTHER_USER_ID, "from": "2016-01-01"})
        self.client_factory.assert_called_once_with("us-east-2")
        start = client.calls_of("start")[0]
        self.assertEqual(start["ExecutionParameters"], ["1000000001"])
        self.assertNotIn(USER_ID, start["QueryString"])

    def test_rows_of_other_users_are_excluded(self):
        self.use_fake_client(FakeAthenaClient(pages=pages(
            *THIS_WEEK_ROWS, data_row(OTHER_USER_ID, "2016-04-10", "99999", "1", "1"),
        )))
        response = self.get_dashboard()
        body = self.body_of(response)
        self.assertEqual(body["summaryStats"][0]["value"], "3,000")
        self.assertNotIn("99999", response["body"])
        self.assertEqual(len(body["timeseries"]["steps"]), 4)

    def test_without_previous_week_delta_is_not_zero(self):
        """지난주 데이터가 없으면 delta 는 0 이 아니라 null, 라벨로 사유를 알린다."""
        self.use_fake_client(FakeAthenaClient(pages=pages(*THIS_WEEK_ROWS)))
        card = self.body_of(self.get_dashboard())["summaryStats"][0]
        self.assertIsNone(card["delta"])
        self.assertTrue(card["deltaLabel"].startswith("지난주 데이터 없음"))

    def test_missing_steps_values_are_not_counted_as_zero(self):
        self.use_fake_client(FakeAthenaClient(pages=pages(
            *THIS_WEEK_ROWS, data_row(USER_ID, "2016-04-06", None, "1850", None),
        )))
        body = self.body_of(self.get_dashboard())
        self.assertEqual(body["summaryStats"][0]["value"], "3,000")
        self.assertNotIn("수", [point["label"] for point in body["timeseries"]["steps"]])

    def test_zero_rows_returns_200_with_empty_steps(self):
        self.use_fake_client(FakeAthenaClient(pages=pages()))
        response = self.get_dashboard()
        self.assertEqual(response["statusCode"], 200)
        body = self.body_of(response)
        self.assert_dashboard_schema(body)
        self.assertEqual(body["summaryStats"], [])
        self.assertEqual(body["timeseries"], {"sleep": [], "heartRate": [], "steps": []})

    def test_reference_week_uses_latest_2016_data_not_today(self):
        """2016-03-12 ~ 2016-04-09 데이터에서 기준 주는 2016-04-04 주."""
        rows = [data_row(USER_ID, f"2016-03-{day:02d}", "1000", "1", "1") for day in range(12, 32)]
        rows += [data_row(USER_ID, f"2016-04-{day:02d}", "4000", "1", "1") for day in range(1, 10)]
        self.use_fake_client(FakeAthenaClient(pages=pages(*rows)))
        body = self.body_of(self.get_dashboard())
        card = body["summaryStats"][0]
        self.assertTrue(card["deltaLabel"].endswith("2016-04-04 ~ 2016-04-10"))
        self.assertEqual([p["label"] for p in body["timeseries"]["steps"]],
                         ["월", "화", "수", "목", "금", "토"])


class RealDashboardErrorTest(RealDashboardTestCase):

    def test_switch_off_returns_503_without_aws_call(self):
        self.enable_real(ENABLE_REAL_DATA_TESTING=None)
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            response = self.get_dashboard()
        self.assert_error(response, 503, "unavailable")
        self.client_factory.assert_not_called()

    def test_missing_or_invalid_dashboard_user_returns_500(self):
        for value in (None, "", "u-1001"):
            self.enable_real(DASHBOARD_USER_ID=value)
            with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
                response = self.get_dashboard()
            self.assert_error(response, 500, "internal_error")
            self.assertIn("DataSourceConfigError", "\n".join(captured.output))
        self.client_factory.assert_not_called()

    def test_missing_athena_config_returns_500(self):
        self.enable_real(ATHENA_TABLE=None)
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            response = self.get_dashboard()
        self.assert_error(response, 500, "internal_error")
        self.client_factory.assert_not_called()

    def test_athena_failure_returns_503_without_mock_fallback(self):
        for state in ("FAILED", "CANCELLED"):
            self.enable_real()
            self.use_fake_client(FakeAthenaClient(states=[state]))
            with self.assertLogs(LOGGER_NAME, level="ERROR"):
                response = self.get_dashboard()
            self.assert_error(response, 503, "unavailable")
            self.assertNotIn("예시", response["body"])

    def test_client_error_returns_503_without_leak(self):
        self.enable_real()
        client = FakeAthenaClient()
        client.results_error = RuntimeError(f"{SECRET} 98765 steps")
        self.use_fake_client(client)
        with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
            response = self.get_dashboard()
        self.assert_error(response, 503, "unavailable")
        log_text = "\n".join(captured.output)
        for leaked in (SECRET, "98765", USER_ID):
            self.assertNotIn(leaked, response["body"])
            self.assertNotIn(leaked, log_text)

    def test_max_rows_reached_returns_503(self):
        """최대 행 수에 도달하면 최근 주를 보장할 수 없으므로 잘못된 통계 대신 503."""
        self.enable_real(ATHENA_MAX_ROWS="3")
        self.use_fake_client(FakeAthenaClient(pages=pages(*THIS_WEEK_ROWS[:3])))
        with self.assertLogs(LOGGER_NAME, level="ERROR"):
            response = self.get_dashboard()
        self.assert_error(response, 503, "unavailable")

    def test_below_max_rows_is_allowed(self):
        self.enable_real(ATHENA_MAX_ROWS="4")
        self.use_fake_client(FakeAthenaClient(pages=pages(*THIS_WEEK_ROWS[:3])))
        self.assertEqual(self.get_dashboard()["statusCode"], 200)


class RealDashboardDatasetSummaryTest(RealDashboardTestCase):
    """ENABLE_DATASET_SUMMARY=true 일 때 /dashboard 에 세 데이터셋 요약이 추가되는지."""

    def setUp(self):
        super().setUp()
        self.enable_real(ENABLE_DATASET_SUMMARY="true")

    def _summary_client(self, responses, fail_on_substring=None):
        """dataset_summary.create_athena_client 를 가짜로 바꾼다(집계 전용)."""
        from tests.test_dataset_summary import FakeSummaryClient
        import src.dataset_summary as ds
        client = FakeSummaryClient(responses, fail_on_substring=fail_on_substring)
        patcher = mock.patch.object(ds, "create_athena_client", lambda region: client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return client

    def test_three_dataset_summaries_added_with_real_aggregates(self):
        from tests.test_dataset_summary import ok_responses
        self._summary_client(ok_responses())
        # 지난주 행도 함께 주어 delta 가 number 로 나오게 한다(스키마 검증 통과).
        self.use_fake_client(FakeAthenaClient(pages=pages(*THIS_WEEK_ROWS, *LAST_WEEK_ROWS)))
        body = self.body_of(self.get_dashboard())
        self.assert_dashboard_schema(body)
        # 걸음 수(기존)는 그대로 유지
        self.assertEqual(body["summaryStats"][0]["value"], "3,000")
        # 세 요약 필드 추가
        self.assertEqual(body["sleepDatasetSummary"]["recordCount"], 1000)
        self.assertEqual(body["sleepDatasetSummary"]["averageHours"], 7.47)
        self.assertEqual(body["sleepDatasetSummary"]["sourceLabel"], "별도 데이터셋")
        # Shared fixture uses local test values, not Athena measurements.
        self.assertEqual(body["heartRateDatasetSummary"]["totalRows"], 1616)
        self.assertEqual(body["heartRateDatasetSummary"]["positiveRows"], 1610)
        self.assertEqual(sum(d["includedRows"] for d in body["heartRateDatasetSummary"]["dailySeries"]), 1610)
        files = {f["id"]: f["rowCount"] for f in body["psychologyDatasetSummary"]["files"]}
        self.assertEqual(files, {"integrated": 1328, "validation": 175})

    def test_summary_failure_does_not_break_steps_or_guide(self):
        """심박 집계만 실패해도 걸음 수·AI 가이드·다른 집계는 그대로."""
        from tests.test_dataset_summary import SLEEP_COLS, SLEEP_OK_VALUES, PSY_COLS, result_page
        responses = [
            result_page(SLEEP_COLS, SLEEP_OK_VALUES),
            result_page(PSY_COLS, ["1328"]),
            result_page(PSY_COLS, ["175"]),
        ]
        self._summary_client(responses, fail_on_substring="heart_rate_table")
        self.use_fake_client(FakeAthenaClient(pages=pages(*THIS_WEEK_ROWS)))
        response = self.get_dashboard()
        self.assertEqual(response["statusCode"], 200)
        body = self.body_of(response)
        self.assertEqual(body["summaryStats"][0]["value"], "3,000")  # 걸음 수 보존
        self.assertEqual(body["sleepDatasetSummary"]["status"], "ok")
        self.assertEqual(body["heartRateDatasetSummary"]["status"], "error")
        self.assertIsNone(body["heartRateDatasetSummary"]["totalRows"])  # 0 이 아니라 None
        self.assertEqual(body["psychologyDatasetSummary"]["status"], "ok")

    def test_summary_off_keeps_dashboard_without_new_fields(self):
        """스위치 꺼짐이면 세 필드가 없어야 한다(기존 응답 유지)."""
        self.enable_real(ENABLE_DATASET_SUMMARY=None)
        self.use_fake_client(FakeAthenaClient(pages=pages(*THIS_WEEK_ROWS)))
        body = self.body_of(self.get_dashboard())
        for key in ("sleepDatasetSummary", "heartRateDatasetSummary", "psychologyDatasetSummary"):
            self.assertNotIn(key, body)


class RealDashboardRegressionTest(RealDashboardTestCase):
    """REAL 환경변수가 모두 설정된 상태에서도 기존 동작이 유지되는지."""

    def test_mock_mode_unchanged_even_with_real_settings(self):
        self.enable_real(DATA_SOURCE="mock")
        response = self.get_dashboard()
        self.assertEqual(self.body_of(response), build_dashboard_mock())
        self.client_factory.assert_not_called()

    def test_health_data_real_behavior_unchanged(self):
        """health-data REAL: 허용 사용자는 200, 다른 사용자는 404 (클라이언트 생성 없음)."""
        self.enable_real()
        self.use_fake_client(FakeAthenaClient(pages=pages(*THIS_WEEK_ROWS)))
        response = self.call(f"/users/{USER_ID}/health-data")
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(set(self.body_of(response).keys()), {"userId", "range", "items"})
        self.assertEqual(len(self.body_of(response)["items"]), 4)

        self.client_factory.reset_mock()
        other = self.call(f"/users/{OTHER_USER_ID}/health-data")
        self.assert_error(other, 404, "not_found")
        self.client_factory.assert_not_called()

    def test_ai_guide_and_other_mock_apis_unchanged(self):
        self.enable_real()
        guide = self.call("/ai-guide")
        self.assertEqual(guide["statusCode"], 200)
        self.assertIn("MOCK", json.loads(guide["body"])["model"])
        for resource in ("anomalies", "guides"):
            response = self.call(f"/users/{USER_ID}/{resource}")
            self.assertIs(self.body_of(response)["mock"], True, resource)
        self.client_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
