"""demo_anomaly (웹 발표용 가상 이상 시연) 모듈 테스트.

실제 AWS 에 접속하지 않습니다. Lambda 클라이언트는 가짜를 주입하고,
AI/ML 응답은 AI/ML lambda_handler 와 같은 API Gateway 형식으로 감쌉니다.

검증 범위:
    - 기능 스위치가 꺼져 있으면(기본) AI/ML 을 호출하지 않고 404.
    - 켜져 있으면 서버가 고정한 입력(클라이언트가 못 바꿈)을 그대로 보낸다.
      user_id/date/metrics(steps, tracked_minutes)/history_steps/notify=False.
    - 성공 응답에 aiGuide, anomalies, inputKind="virtual" 포함.
    - 실패(설정 오류, 호출 실패, 응답 검증 실패)는 오류로 돌려주고 예시 가이드로 대체하지 않는다.
"""

import io
import json
import os
import sys
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src import demo_anomaly  # noqa: E402

# 스위치 켜짐 + ML 설정이 들어 있는 환경변수
ENV_ON = {
    "ENABLE_DEMO_ANOMALY": "true",
    "ML_FUNCTION_NAME": "wearcare-mate-ml",
    "ML_REGION": "ap-northeast-2",
}


def anomaly_body(guide="default", warnings=None):
    """AI/ML v0.3 출력 구조의 anomaly 응답 body(고정 가상 입력에 대응)."""
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
    """invoke() 를 가진 가짜 Lambda 클라이언트. 호출 인자를 calls 에 기록한다."""

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


def run(fake, environ=ENV_ON):
    return demo_anomaly.run_demo_anomaly(
        lambda_client_factory=lambda config: fake, environ=environ)


class SwitchDefaultOffTest(unittest.TestCase):
    """기능 스위치는 기본 비활성이어야 한다."""

    def test_disabled_by_default_when_unset(self):
        self.assertFalse(demo_anomaly.is_demo_anomaly_enabled({}))

    def test_disabled_for_non_true_values(self):
        for value in ("1", "yes", "True ", "", "false", "TRUE", "on"):
            # 공백/대소문자만 무시하므로 "true"(정확히) 외에는 모두 비활성.
            environ = {"ENABLE_DEMO_ANOMALY": value}
            expected = value.strip().lower() == "true"
            self.assertEqual(demo_anomaly.is_demo_anomaly_enabled(environ), expected, repr(value))

    def test_enabled_only_for_true(self):
        for value in ("true", "TRUE", "  true  ", "True"):
            self.assertTrue(demo_anomaly.is_demo_anomaly_enabled({"ENABLE_DEMO_ANOMALY": value}),
                            repr(value))

    def test_run_returns_404_without_invoke_when_disabled(self):
        """스위치가 꺼져 있으면 AI/ML 을 호출하지 않고 404 를 돌려준다."""
        fake = FakeLambda(body=anomaly_body())
        environ = {"ML_FUNCTION_NAME": "wearcare-mate-ml"}  # 스위치 없음(비활성)
        result = demo_anomaly.run_demo_anomaly(
            lambda_client_factory=lambda config: fake, environ=environ)
        self.assertEqual(result["statusCode"], 404)
        self.assertEqual(result["error"], "not_found")
        self.assertEqual(fake.calls, [])  # ML 미호출


class FixedInputTest(unittest.TestCase):
    """서버가 입력을 고정하고 클라이언트가 바꾸지 못한다."""

    def test_sends_server_fixed_input(self):
        fake = FakeLambda(body=anomaly_body())
        run(fake)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0]["FunctionName"], "wearcare-mate-ml")
        self.assertEqual(fake.calls[0]["InvocationType"], "RequestResponse")
        payload = json.loads(fake.calls[0]["Payload"].decode("utf-8"))
        self.assertEqual(payload, {
            "user_id": "test-user",
            "date": "2026-10-30",
            "metrics": {"steps": 1000, "tracked_minutes": 800},
            "history_steps": [10000, 10500, 9800, 10200, 10100, 9900],
            "notify": False,
        })

    def test_notify_is_false(self):
        """SNS 미발송을 위해 요청 최상위 notify 는 반드시 False 여야 한다."""
        fake = FakeLambda(body=anomaly_body())
        run(fake)
        payload = json.loads(fake.calls[0]["Payload"].decode("utf-8"))
        self.assertIs(payload["notify"], False)

    def test_build_demo_request_does_not_mutate_original(self):
        """반환된 요청을 바꿔도 모듈 상수 DEMO_REQUEST 원본은 변하지 않아야 한다."""
        request = demo_anomaly.build_demo_request()
        request["metrics"]["steps"] = 99999
        request["history_steps"].append(0)
        request["notify"] = True
        self.assertEqual(demo_anomaly.DEMO_REQUEST["metrics"], {"steps": 1000, "tracked_minutes": 800})
        self.assertEqual(demo_anomaly.DEMO_REQUEST["history_steps"],
                         [10000, 10500, 9800, 10200, 10100, 9900])
        self.assertIs(demo_anomaly.DEMO_REQUEST["notify"], False)


class SuccessResponseTest(unittest.TestCase):
    """성공 응답에 aiGuide, anomalies, inputKind=virtual 이 들어 있다."""

    def test_success_includes_ai_guide_and_anomalies(self):
        result = run(FakeLambda(body=anomaly_body()))
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["inputKind"], "virtual")
        self.assertEqual(result["referenceDate"], "2026-10-30")
        self.assertEqual(result["analysisStatus"], "anomaly")
        self.assertEqual(result["overallSeverity"], "high")
        self.assertIn("aiGuide", result)
        self.assertIn("anomalies", result)

    def test_reuses_existing_screen_conversion(self):
        """기존 guide_for_frontend / anomalies_for_frontend 결과를 그대로 쓴다."""
        result = run(FakeLambda(body=anomaly_body()))
        self.assertEqual(result["aiGuide"], demo_anomaly.guide_for_frontend(anomaly_body()))
        self.assertEqual(result["anomalies"], demo_anomaly.anomalies_for_frontend(anomaly_body()))
        guide = result["aiGuide"]
        self.assertEqual(guide["status"], "generated")
        self.assertTrue(guide["model"].startswith("Amazon Bedrock"))
        self.assertNotIn("MOCK", guide["model"])
        self.assertEqual(result["anomalies"][0]["severity"], "danger")


class FailureNotMockedTest(unittest.TestCase):
    """실패 시 예시 가이드로 대체하지 않는다."""

    def test_config_error_returns_503_without_invoke(self):
        """ML 설정이 없으면 호출 전에 503(config)으로 실패한다."""
        fake = FakeLambda(body=anomaly_body())
        result = demo_anomaly.run_demo_anomaly(
            lambda_client_factory=lambda config: fake,
            environ={"ENABLE_DEMO_ANOMALY": "true"})  # ML_FUNCTION_NAME 없음
        self.assertEqual(result["statusCode"], 503)
        self.assertEqual(result["stage"], "config")
        self.assertEqual(fake.calls, [])
        self.assertNotIn("aiGuide", result)

    def test_invoke_exception_returns_502(self):
        result = run(FakeLambda(error=TimeoutError("t")))
        self.assertEqual(result["statusCode"], 502)
        self.assertEqual(result["stage"], "invoke_or_validate")
        self.assertNotIn("aiGuide", result)
        self.assertNotIn("MOCK", json.dumps(result, ensure_ascii=False))

    def test_function_error_returns_502(self):
        result = run(FakeLambda(body=anomaly_body(), function_error="Unhandled"))
        self.assertEqual(result["statusCode"], 502)
        self.assertEqual(result["stage"], "invoke_or_validate")

    def test_ml_error_response_carries_code(self):
        fake = FakeLambda(status_code=500, body={"error": {"code": "MODEL_ERROR", "message": "x"}})
        result = run(fake)
        self.assertEqual(result["statusCode"], 502)
        self.assertEqual(result["mlErrorCode"], "MODEL_ERROR")
        self.assertEqual(result["mlStatusCode"], 500)
        self.assertNotIn("aiGuide", result)

    def test_normal_result_still_returns_200_without_mock_guide(self):
        """정상(이상 없음) 응답도 200 으로 돌려주되, 예시 가이드로 꾸미지 않는다."""
        result = run(FakeLambda(body=normal_body()))
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["analysisStatus"], "normal")
        # guide_for_frontend 가 "생성형 가이드 없음" 상태를 그대로 전달한다(예시 문구 대체 아님).
        self.assertEqual(result["aiGuide"]["status"], "not_applicable")
        self.assertEqual(result["anomalies"], [])
        self.assertNotIn("MOCK", json.dumps(result, ensure_ascii=False))

    def test_failure_message_does_not_leak_exception_text(self):
        """실패 응답 본문에 예외 원문 메시지가 들어가지 않는다(타입 이름만)."""
        secret = "secret-trace-detail-9999"
        result = run(FakeLambda(error=RuntimeError(secret)))
        # 응답에는 원문 메시지가 없어야 한다(민감 정보 비노출).
        self.assertNotIn(secret, json.dumps(result, ensure_ascii=False))
        # MLClient.invoke_detection 이 호출 예외를 MLInvocationError 로 감싸므로
        # errorType 은 래핑된 타입(MLInvocationError)이고, 안전한 타입 이름만 남는다.
        self.assertEqual(result["errorType"], "MLInvocationError")


if __name__ == "__main__":
    unittest.main()
