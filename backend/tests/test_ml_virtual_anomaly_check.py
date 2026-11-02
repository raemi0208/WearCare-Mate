"""ml_virtual_anomaly_check (콘솔 전용 가상 이상 검증 도구) 테스트.

AWS 에 접속하지 않습니다. Lambda 클라이언트는 가짜를 주입하고,
AI/ML 응답은 AI/ML lambda_handler 와 같은 API Gateway 형식으로 감쌉니다.
"""

import io
import json
import unittest
from unittest import mock

from src import ml_virtual_anomaly_check as probe

ENV = {"ML_FUNCTION_NAME": "wearcare-mate-ml", "ML_REGION": "ap-northeast-2"}


def anomaly_body(guide="default", warnings=None):
    body = {
        "user_id": "test-user", "date": "2026-10-30",
        "anomalies": [{
            "type": "ACTIVITY_DROP", "basis": "personal", "metric": "steps", "value": 1000,
            "baseline_mean": 10083, "baseline_std": 250, "z_score": -18.17,
            "drop_pct": -90.1, "severity": "high",
        }],
        "anomaly_score": None,
        "guide": {
            "text": "오늘 걸음 수가 평소 10,083걸음보다 1,000걸음으로 크게 줄었어요.\n"
                    "오늘 10분 걷기를 해 보세요.\n증상이 지속되거나 불편하면 전문가와 상담해보세요.",
            "lines": ["오늘 걸음 수가 평소 10,083걸음보다 1,000걸음으로 크게 줄었어요.",
                      "오늘 10분 걷기를 해 보세요.",
                      "증상이 지속되거나 불편하면 전문가와 상담해보세요."],
            "model_id": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
            "warnings": warnings or [],
            "generated_at": "2026-10-30T14:40:09+09:00",
        },
        "model_version": "activity-zscore-v0.2+pop-v0.3",
        "overall_severity": "high", "status": "anomaly",
    }
    if guide is None:
        body["guide"] = None
    return body


def normal_body():
    return {"user_id": "test-user", "date": "2026-10-30", "anomalies": [],
            "anomaly_score": None, "guide": None,
            "model_version": "activity-zscore-v0.2+pop-v0.3",
            "overall_severity": "none", "status": "normal"}


class FakeLambda:
    def __init__(self, status_code=200, body=None, error=None, function_error=None):
        self.status_code, self.body, self.error = status_code, body, error
        self.function_error = function_error
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        envelope = {"statusCode": self.status_code, "headers": {},
                    "body": json.dumps(self.body, ensure_ascii=False)}
        response = {"StatusCode": 200, "Payload": io.BytesIO(json.dumps(envelope).encode())}
        if self.function_error:
            response["FunctionError"] = self.function_error
        return response


def run(fake):
    return probe.run_check(lambda_client_factory=lambda config: fake, environ=ENV)


class VirtualAnomalyCheckTest(unittest.TestCase):

    def test_sends_virtual_request_matching_ml_interface(self):
        fake = FakeLambda(body=anomaly_body())
        run(fake)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0]["FunctionName"], "wearcare-mate-ml")
        self.assertEqual(fake.calls[0]["InvocationType"], "RequestResponse")
        self.assertEqual(json.loads(fake.calls[0]["Payload"].decode("utf-8")), {
            "user_id": "test-user", "date": "2026-10-30", "metrics": {"steps": 1000},
            "history_steps": [10000, 10500, 9800, 10200, 10100, 9900],
        })

    def test_pass_uses_existing_screen_conversion(self):
        result = run(FakeLambda(body=anomaly_body()))
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["inputKind"], "virtual")
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["ml"]["overallSeverity"], "high")
        self.assertTrue(result["ml"]["guideGenerated"])
        guide = result["screen"]["aiGuide"]
        expected = probe.guide_for_frontend(anomaly_body())
        self.assertEqual(guide, expected)                       # 기존 변환 결과 그대로
        self.assertEqual(guide["status"], "generated")
        self.assertTrue(guide["model"].startswith("Amazon Bedrock"))
        self.assertNotIn("MOCK", guide["model"])
        self.assertEqual(guide["actions"], ["오늘 10분 걷기를 해 보세요."])
        self.assertEqual(result["screen"]["anomalies"][0]["severity"], "danger")

    def test_warnings_are_reported(self):
        result = run(FakeLambda(body=anomaly_body(warnings=["줄 수 2"])))
        self.assertEqual(result["verdict"], "PASS_WITH_WARNINGS")
        self.assertEqual(result["ml"]["guideWarnings"], ["줄 수 2"])

    def test_missing_guide_is_failure_not_mock(self):
        result = run(FakeLambda(body=anomaly_body(guide=None)))
        self.assertEqual(result["verdict"], "FAIL")
        self.assertFalse(result["checks"]["guideGenerated"])
        self.assertEqual(result["screen"]["aiGuide"]["status"], "missing")
        self.assertNotIn("MOCK", json.dumps(result, ensure_ascii=False))

    def test_normal_result_is_failure(self):
        result = run(FakeLambda(body=normal_body()))
        self.assertEqual(result["verdict"], "FAIL")
        self.assertFalse(result["checks"]["statusIsAnomaly"])

    def test_ml_error_response_is_failure(self):
        fake = FakeLambda(status_code=500, body={"error": {"code": "MODEL_ERROR", "message": "x"}})
        result = run(fake)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["mlErrorCode"], "MODEL_ERROR")
        self.assertNotIn("screen", result)

    def test_invoke_exception_and_function_error_are_failures(self):
        for fake in (FakeLambda(error=TimeoutError("t")),
                     FakeLambda(body=anomaly_body(), function_error="Unhandled")):
            result = run(fake)
            self.assertEqual(result["verdict"], "FAIL")
            self.assertEqual(result["stage"], "invoke_or_validate")

    def test_missing_config_is_failure_without_invoke(self):
        fake = FakeLambda(body=anomaly_body())
        result = probe.run_check(lambda_client_factory=lambda config: fake, environ={})
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["stage"], "config")
        self.assertEqual(fake.calls, [])

    def test_api_gateway_event_is_refused_without_invoke(self):
        with mock.patch.object(probe, "run_check") as run_check:
            response = probe.lambda_handler({"requestContext": {"http": {"method": "GET"}}}, None)
        self.assertEqual(response["verdict"], "REFUSED")
        run_check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
