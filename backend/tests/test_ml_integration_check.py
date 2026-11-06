"""ml_integration_check (콘솔 전용 Athena 실데이터 경계 검증) 테스트.

AWS 에 접속하지 않습니다. Athena 조회(build_real_health_data), ML 설정·클라이언트는 모두 패치합니다.
걸음 수·기록 시간은 가상 값이며, 기대 비교값(962/10057, 41/224)에 맞춘 활동 시간 조합을 씁니다.
"""

import unittest
from unittest.mock import patch

from src import ml_integration_check as probe
from src.ml_client import MLConfig

USER_ID = "1503960366"
FAKE_CONFIG = MLConfig(function_name="wearcare-mate-ml", region="ap-northeast-2")


def activity(steps, very, fairly, lightly, sedentary):
    """mappers 가 만든 activity 형태(네 활동 시간 + trackedMinutes 합계)."""
    a = {"totalSteps": steps, "veryActiveMinutes": very, "fairlyActiveMinutes": fairly,
         "lightlyActiveMinutes": lightly, "sedentaryMinutes": sedentary}
    a["trackedMinutes"] = very + fairly + lightly + sedentary
    return a


# 사용자 전체 행(날짜 필터 없이 조회된다고 가정). 과거 기록 + 04-10(962분) + 04-12(41분).
def health_items():
    return {"items": [
        {"date": "2016-04-03", "activity": activity(9800, 30, 20, 300, 1000)},
        {"date": "2016-04-04", "activity": activity(10200, 35, 25, 320, 1020)},
        {"date": "2016-04-05", "activity": activity(9900, 28, 22, 310, 1010)},
        {"date": "2016-04-06", "activity": activity(10500, 40, 20, 330, 1030)},
        {"date": "2016-04-07", "activity": activity(10100, 32, 18, 305, 1005)},
        {"date": "2016-04-08", "activity": activity(10000, 30, 20, 300, 1000)},
        {"date": "2016-04-09", "activity": activity(10300, 33, 21, 311, 1015)},
        # 962 = 40+22+400+500,  41 = 1+0+10+30
        {"date": "2016-04-10", "activity": activity(10057, 40, 22, 400, 500)},
        {"date": "2016-04-12", "activity": activity(224, 1, 0, 10, 30)},
    ]}


def anomaly_result(date_str):
    return {"user_id": USER_ID, "date": date_str, "status": "anomaly", "overall_severity": "high",
            "anomalies": [{"type": "ACTIVITY_DROP", "basis": "personal", "metric": "steps",
                           "value": 224, "baseline_mean": 10000, "baseline_std": 300,
                           "z_score": -32.0, "drop_pct": -97.8, "severity": "high"}],
            "anomaly_score": None, "guide": None,
            "model_version": "activity-zscore-v0.2+pop-v0.3",
            "alert_sent": False, "alert_reason": "notify_false"}


def normal_result(date_str):
    return {"user_id": USER_ID, "date": date_str, "status": "normal", "overall_severity": "none",
            "anomalies": [], "anomaly_score": None, "guide": None,
            "model_version": "activity-zscore-v0.2+pop-v0.3",
            "alert_sent": False, "alert_reason": "below_threshold"}


def insufficient_result(date_str):
    """기록 시간<800 → 걸음 수 판정 제외 → (다른 지표 없으면) insufficient_data, ACTIVITY_DROP 없음."""
    return {"user_id": USER_ID, "date": date_str, "status": "insufficient_data",
            "overall_severity": "none", "anomalies": [], "anomaly_score": None, "guide": None,
            "model_version": "activity-zscore-v0.2+pop-v0.3",
            "alert_sent": False, "alert_reason": "notify_false"}


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def invoke_detection(self, request):
        self.requests.append(request)
        return self.result


def run(event, result):
    client = FakeClient(result)
    with patch.object(probe, "build_real_health_data", return_value=health_items()), \
         patch.object(probe, "get_allowed_user_id", return_value=USER_ID), \
         patch.object(probe.MLConfig, "from_env", return_value=FAKE_CONFIG), \
         patch.object(probe, "create_lambda_client", return_value=object()), \
         patch.object(probe, "MLClient", return_value=client):
        response = probe.lambda_handler(event, None)
    return response, client


class AprilTenTest(unittest.TestCase):
    def test_sends_962_minutes_and_10057_steps_with_notify_false(self):
        response, client = run({"target_date": "2016-04-10"}, normal_result("2016-04-10"))
        self.assertEqual(len(client.requests), 1)  # ML 한 번만
        req = client.requests[0]
        self.assertEqual(req["date"], "2016-04-10")
        self.assertEqual(req["metrics"], {"steps": 10057, "tracked_minutes": 962})
        self.assertIs(req["notify"], False)
        self.assertEqual(response["verdict"], "OK")
        self.assertEqual(response["sentSteps"], 10057)
        self.assertEqual(response["sentTrackedMinutes"], 962)
        self.assertTrue(response["matchesExpectedSteps"])
        self.assertTrue(response["matchesExpectedTrackedMinutes"])
        self.assertFalse(response["trackedMinutesBelowThreshold"])  # 962 >= 800
        self.assertEqual(response["ml"]["status"], "normal")        # normal 이어도 됨
        self.assertIs(response["alertSent"], False)
        self.assertEqual(response["alertReason"], "below_threshold")


class AprilTwelveTest(unittest.TestCase):
    def test_sends_41_minutes_and_224_steps(self):
        response, client = run({"target_date": "2016-04-12"}, insufficient_result("2016-04-12"))
        req = client.requests[0]
        self.assertEqual(req["date"], "2016-04-12")
        self.assertEqual(req["metrics"], {"steps": 224, "tracked_minutes": 41})
        self.assertIs(req["notify"], False)
        self.assertTrue(response["matchesExpectedSteps"])
        self.assertTrue(response["matchesExpectedTrackedMinutes"])
        self.assertTrue(response["trackedMinutesBelowThreshold"])  # 41 < 800

    def test_step_judgment_skipped_evidence(self):
        """41분 케이스: ACTIVITY_DROP 없음 + 기록 시간<800 → stepJudgmentSkipped=True."""
        response, _ = run({"target_date": "2016-04-12"}, insufficient_result("2016-04-12"))
        self.assertFalse(response["ml"]["stepAnomalyDetected"])
        self.assertNotIn("ACTIVITY_DROP", response["ml"]["anomalyTypes"])
        self.assertTrue(response["stepJudgmentSkipped"])
        self.assertIs(response["alertSent"], False)
        self.assertEqual(response["alertReason"], "notify_false")

    def test_skip_evidence_false_if_ml_still_flags_drop(self):
        """방어: 기록 시간<800 인데도 ML 이 ACTIVITY_DROP 을 주면 제외 근거는 성립하지 않는다."""
        response, _ = run({"target_date": "2016-04-12"}, anomaly_result("2016-04-12"))
        self.assertTrue(response["ml"]["stepAnomalyDetected"])
        self.assertFalse(response["stepJudgmentSkipped"])


class DispatchAndGuardTest(unittest.TestCase):
    def test_default_date_is_april_ten(self):
        response, client = run({}, normal_result("2016-04-10"))
        self.assertEqual(client.requests[0]["date"], "2016-04-10")
        self.assertEqual(response["targetDate"], "2016-04-10")

    def test_unsupported_date_rejected_before_invoke(self):
        for value in ("2016-04-11", "2016-04-13", "bad", "", None, 20160410):
            client = FakeClient(normal_result("2016-04-10"))
            with patch.object(probe, "build_real_health_data") as athena, \
                 patch.object(probe, "get_allowed_user_id", return_value=USER_ID), \
                 patch.object(probe, "MLClient", return_value=client):
                response = probe.lambda_handler({"target_date": value}, None)
            self.assertEqual(response["verdict"], "REJECTED", repr(value))
            self.assertEqual(response["statusCode"], 400)
            self.assertFalse(response["mlInvoked"])
            self.assertEqual(client.requests, [])        # ML 미호출
            athena.assert_not_called()                   # Athena 조회도 안 함

    def test_api_gateway_event_refused_without_invoke(self):
        client = FakeClient(normal_result("2016-04-10"))
        with patch.object(probe, "build_real_health_data") as athena, \
             patch.object(probe, "MLClient", return_value=client):
            event = {"requestContext": {"http": {"method": "GET"}}, "target_date": "2016-04-10"}
            response = probe.lambda_handler(event, None)
        self.assertEqual(response["verdict"], "REFUSED")
        self.assertEqual(client.requests, [])
        athena.assert_not_called()


if __name__ == "__main__":
    unittest.main()
