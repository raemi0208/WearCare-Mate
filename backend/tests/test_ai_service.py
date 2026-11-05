import copy
import json
import os
import unittest
from unittest.mock import patch

from src import ai_service
from src.data_source import DataSourceUnavailableError
from src.lambda_function import lambda_handler
from src.ml_adapter import MLResponseError
from tests.ml_samples import sample


ENV = {
    "AI_SOURCE": "real", "DATA_SOURCE": "real", "ENABLE_REAL_DATA_TESTING": "true",
    "DASHBOARD_USER_ID": "1503960366", "ML_FUNCTION_NAME": "wearcare-mate-ml",
    "ML_REGION": "ap-northeast-2", "ML_TARGET_DATE": "2016-04-10",
}
ITEMS = [
    {"date": "2016-04-09", "activity": {"totalSteps": 10000}},
    {"date": "2016-04-10", "activity": {"totalSteps": 2100}},
    {"date": "2016-04-11", "activity": {"totalSteps": 15000}},
]


def result_for(kind="activity_drop_high"):
    result = sample(kind)["response"]
    result.update(user_id="1503960366", date="2016-04-10")
    return result


class FakeLambda:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def invoke(self, **kwargs):
        self.requests.append(json.loads(kwargs["Payload"]))
        return {"StatusCode": 200, "Payload": json.dumps({
            "statusCode": 200, "body": json.dumps(self.result)
        }).encode()}


class AIServiceTest(unittest.TestCase):
    def run_route(self, path, result):
        client = FakeLambda(result)
        with patch.dict(os.environ, ENV, clear=True), \
             patch.object(ai_service, "fetch_dashboard_activity_items", return_value=copy.deepcopy(ITEMS)) as fetch, \
             patch.object(ai_service, "create_lambda_client", return_value=client):
            response = lambda_handler({"requestContext": {"http": {"method": "GET", "path": path}}}, None)
        return response, client, fetch

    def test_dashboard_real_route_maps_guide_and_anomalies(self):
        response, client, fetch = self.run_route("/dashboard", result_for())
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["anomalies"][0]["severity"], "danger")
        self.assertEqual(body["aiGuide"]["status"], "generated")
        self.assertEqual(len(body["aiGuide"]["actions"]), 1)
        self.assertEqual(body["notifications"], [])
        self.assertEqual(body["devices"], [])
        self.assertEqual(body["guideHistory"], [])
        self.assertEqual(body["timeseries"]["sleep"], [])
        self.assertEqual([v["value"] for v in body["timeseries"]["steps"]], [10000, 2100])
        self.assertEqual([v["anomaly"] for v in body["timeseries"]["steps"]], [False, True])
        self.assertEqual(client.requests, [{"user_id": "1503960366", "date": "2016-04-10", "metrics": {"steps": 2100}}])
        fetch.assert_called_once()

    def test_guide_route_normal_has_no_fabricated_generation(self):
        response, _, _ = self.run_route("/ai-guide", result_for("normal"))
        self.assertEqual(response["statusCode"], 200)
        guide = json.loads(response["body"])
        self.assertEqual(guide["status"], "not_applicable")
        self.assertEqual(guide["actions"], [])
        self.assertNotIn("Bedrock", guide["model"])

    def test_insufficient_and_generation_failure_remain_distinct(self):
        missing = result_for()
        missing["guide"] = None
        insufficient = result_for("normal")
        insufficient["status"] = "insufficient_data"
        a = ai_service.guide_for_frontend(missing)
        b = ai_service.guide_for_frontend(insufficient)
        self.assertEqual(a["status"], "missing")
        self.assertEqual(b["analysisStatus"], "insufficient_data")
        self.assertNotEqual(a["headline"], b["headline"])

    def test_activity_drop_desc_uses_step_unit(self):
        anomaly = ai_service.anomalies_for_frontend(result_for())[0]
        self.assertEqual(anomaly["desc"], "기준일 걸음 수 2,100걸음 · 과거 기록 평균 12,271걸음")
        self.assertNotIn("보", anomaly["desc"])

    def test_warning_details_are_preserved(self):
        result = result_for()
        result["guide"]["warnings"] = ["줄 수 2"]
        self.assertEqual(ai_service.guide_for_frontend(result)["warnings"], ["줄 수 2"])

    def test_guide_lines_are_preserved_for_frontend(self):
        """guide.lines 배열을 화면용 응답에 lines 로 그대로 전달한다(줄별 표시용)."""
        result = result_for()
        guide = ai_service.guide_for_frontend(result)
        self.assertEqual(guide["lines"], result["guide"]["lines"])
        # text 도 유지한다.
        self.assertEqual(guide["text"], result["guide"]["text"])

    def test_alert_sent_is_passed_through(self):
        """응답 최상위 alert_sent true/false/필드 없음을 각각 True/False/None 으로 전달한다."""
        true_result = result_for()
        true_result["alert_sent"] = True
        self.assertIs(ai_service.guide_for_frontend(true_result)["alertSent"], True)

        false_result = result_for()
        false_result["alert_sent"] = False
        self.assertIs(ai_service.guide_for_frontend(false_result)["alertSent"], False)

        no_field = result_for()  # 샘플에는 최상위 alert_sent 없음
        self.assertIsNone(ai_service.guide_for_frontend(no_field)["alertSent"])

    def test_alert_sent_preserved_when_guide_null(self):
        """guide 가 null 이어도 최상위 alert_sent 가 화면용 alertSent 로 보존된다."""
        missing = result_for()
        missing["guide"] = None
        missing["alert_sent"] = True
        guide = ai_service.guide_for_frontend(missing)
        self.assertEqual(guide["status"], "missing")
        self.assertIs(guide["alertSent"], True)

        normal = result_for("normal")
        normal["alert_sent"] = False
        self.assertIs(ai_service.guide_for_frontend(normal)["alertSent"], False)

    def test_tracked_minutes_sent_when_items_have_minutes(self):
        """활동 시간 네 값이 모두 있는 기준일이면 요청 metrics 에 tracked_minutes 를 담는다."""
        items = [
            {"date": "2016-04-09", "activity": {"totalSteps": 10000}},
            {"date": "2016-04-10", "activity": {
                "totalSteps": 2100, "veryActiveMinutes": 10, "fairlyActiveMinutes": 10,
                "lightlyActiveMinutes": 100, "sedentaryMinutes": 679, "trackedMinutes": 799,
            }},
        ]
        client = FakeLambda(result_for())
        with patch.dict(os.environ, ENV, clear=True), \
             patch.object(ai_service, "fetch_dashboard_activity_items", return_value=copy.deepcopy(items)), \
             patch.object(ai_service, "create_lambda_client", return_value=client):
            ai_service.build_ai_guide()
        self.assertEqual(client.requests[0]["metrics"],
                         {"steps": 2100, "tracked_minutes": 799})

    def test_guard_blocks_aws_before_incomplete_or_disabled_setup(self):
        for changes in ({"ENABLE_REAL_DATA_TESTING": "false"}, {"DATA_SOURCE": "mock"},
                        {"ML_TARGET_DATE": ""}, {"ML_TARGET_DATE": "2016-04-12"},
                        {"ML_TARGET_DATE": "bad"}):
            with self.subTest(changes=changes), \
                 patch.object(ai_service, "fetch_dashboard_activity_items") as fetch:
                with self.assertRaises(DataSourceUnavailableError):
                    ai_service.build_ai_guide(environ=dict(ENV, **changes))
                fetch.assert_not_called()

    def test_missing_or_conflicting_target_steps_do_not_invoke_ml(self):
        for items in ([], [ITEMS[1], {"date": "2016-04-10", "activity": {"totalSteps": 999}}]):
            with patch.object(ai_service, "fetch_dashboard_activity_items", return_value=items), \
                 patch.object(ai_service, "create_lambda_client") as factory:
                with self.assertRaises(DataSourceUnavailableError):
                    ai_service.build_ai_guide(environ=ENV)
                factory.assert_not_called()

    def test_mismatched_ml_response_is_rejected(self):
        result = result_for()
        result["user_id"] = "other"
        with patch.object(ai_service, "fetch_dashboard_activity_items", return_value=ITEMS):
            with self.assertRaises(MLResponseError):
                ai_service.build_ai_guide(environ=ENV, ml_client_factory=lambda _: FakeLambda(result))

    def test_ml_failure_returns_503_without_mock_fallback(self):
        with patch.dict(os.environ, ENV, clear=True), \
             patch.object(ai_service, "fetch_dashboard_activity_items", return_value=ITEMS), \
             patch.object(ai_service, "create_lambda_client", side_effect=DataSourceUnavailableError("failed")):
            with self.assertLogs("src.lambda_function", level="ERROR"):
                response = lambda_handler({"requestContext": {"http": {"method": "GET", "path": "/dashboard"}}}, None)
        self.assertEqual(response["statusCode"], 503)
        self.assertNotIn("MOCK", response["body"])
