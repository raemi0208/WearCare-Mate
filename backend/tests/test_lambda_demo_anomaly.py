"""lambda_function 의 POST /demo/anomaly 라우팅 테스트.

실제 AWS 에 접속하지 않습니다.
    - 스위치 기본 비활성 → 404 (라우트가 없는 것처럼), 실제 AI/ML 경로를 타지 않음
    - 스위치 켜짐 → run_demo_anomaly 를 패치해 statusCode/본문이 응답으로 변환되는지 확인
    - 기존 GET 경로(/health, /dashboard, /ai-guide, /users/...)는 그대로 보존

run_demo_anomaly 자체의 동작은 test_demo_anomaly.py 에서 가짜 Lambda 로 검증한다.
여기서는 "라우팅 + 스위치 + 응답 변환"만 본다.
"""

import json
import os
import sys
import unittest
from unittest import mock

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.lambda_function import lambda_handler  # noqa: E402


def make_event(method, path, query="__default__"):
    event = {"requestContext": {"http": {"method": method, "path": path}}}
    if query != "__default__":
        event["queryStringParameters"] = query
    return event


def env(**overrides):
    """DATA_SOURCE=mock 기본 + 필요한 스위치만 덧붙인 환경변수 dict."""
    base = {"DATA_SOURCE": "mock"}
    base.update(overrides)
    return base


class DemoAnomalyDisabledTest(unittest.TestCase):
    """스위치가 꺼져 있으면(기본) 404 이고, AI/ML 경로를 타지 않는다."""

    def test_returns_404_when_switch_unset(self):
        with mock.patch.dict(os.environ, env(), clear=True):
            with mock.patch("src.demo_anomaly.run_demo_anomaly") as run:
                response = lambda_handler(make_event("POST", "/demo/anomaly"), None)
        self.assertEqual(response["statusCode"], 404)
        self.assertEqual(json.loads(response["body"])["error"], "not_found")
        run.assert_not_called()  # 비활성이면 시연 로직 자체를 부르지 않는다

    def test_returns_404_when_switch_not_true(self):
        with mock.patch.dict(os.environ, env(ENABLE_DEMO_ANOMALY="1"), clear=True):
            with mock.patch("src.demo_anomaly.run_demo_anomaly") as run:
                response = lambda_handler(make_event("POST", "/demo/anomaly"), None)
        self.assertEqual(response["statusCode"], 404)
        run.assert_not_called()

    def test_get_on_demo_path_is_404(self):
        """GET /demo/anomaly 는 스위치와 무관하게 지원하지 않는 경로(404)."""
        with mock.patch.dict(os.environ, env(ENABLE_DEMO_ANOMALY="true"), clear=True):
            response = lambda_handler(make_event("GET", "/demo/anomaly"), None)
        self.assertEqual(response["statusCode"], 404)


class DemoAnomalyEnabledTest(unittest.TestCase):
    """스위치가 켜져 있으면 run_demo_anomaly 결과를 응답으로 변환한다."""

    def test_success_is_converted_to_api_response(self):
        fake_result = {
            "statusCode": 200, "inputKind": "virtual", "referenceDate": "2026-11-14",
            "analysisStatus": "anomaly", "overallSeverity": "high",
            "aiGuide": {"status": "generated"}, "anomalies": [{"severity": "danger"}],
            "request": {"notify": False},
        }
        with mock.patch.dict(os.environ, env(ENABLE_DEMO_ANOMALY="true"), clear=True):
            with mock.patch("src.demo_anomaly.run_demo_anomaly",
                            return_value=dict(fake_result)) as run:
                response = lambda_handler(make_event("POST", "/demo/anomaly"), None)
        run.assert_called_once()
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["headers"]["Content-Type"], "application/json")
        body = json.loads(response["body"])
        self.assertEqual(body["inputKind"], "virtual")
        self.assertIn("aiGuide", body)
        self.assertIn("anomalies", body)
        self.assertNotIn("statusCode", body)  # statusCode 는 응답 본문에서 분리됨

    def test_failure_status_code_is_propagated(self):
        """run_demo_anomaly 가 502/503 을 돌려주면 그 상태 코드로 응답한다(예시 대체 없음)."""
        fake_result = {
            "statusCode": 502, "inputKind": "virtual", "error": "unavailable",
            "stage": "invoke_or_validate", "errorType": "TimeoutError",
            "message": "가상 이상 시연을 완료하지 못했습니다.",
        }
        with mock.patch.dict(os.environ, env(ENABLE_DEMO_ANOMALY="true"), clear=True):
            with mock.patch("src.demo_anomaly.run_demo_anomaly",
                            return_value=dict(fake_result)):
                response = lambda_handler(make_event("POST", "/demo/anomaly"), None)
        self.assertEqual(response["statusCode"], 502)
        body = json.loads(response["body"])
        self.assertEqual(body["error"], "unavailable")
        self.assertNotIn("aiGuide", body)


class ExistingRoutesPreservedTest(unittest.TestCase):
    """demo 경로 추가 후에도 기존 GET 경로가 그대로 동작해야 한다."""

    def test_health_still_200(self):
        with mock.patch.dict(os.environ, env(ENABLE_DEMO_ANOMALY="true"), clear=True):
            response = lambda_handler(make_event("GET", "/health"), None)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["status"], "ok")

    def test_dashboard_mock_still_200(self):
        with mock.patch.dict(os.environ, env(ENABLE_DEMO_ANOMALY="true"), clear=True):
            response = lambda_handler(make_event("GET", "/dashboard"), None)
        self.assertEqual(response["statusCode"], 200)

    def test_ai_guide_mock_still_200(self):
        with mock.patch.dict(os.environ, env(ENABLE_DEMO_ANOMALY="true"), clear=True):
            response = lambda_handler(make_event("GET", "/ai-guide"), None)
        self.assertEqual(response["statusCode"], 200)

    def test_health_data_mock_still_200(self):
        with mock.patch.dict(os.environ, env(ENABLE_DEMO_ANOMALY="true"), clear=True):
            response = lambda_handler(make_event("GET", "/users/u-1001/health-data"), None)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["userId"], "u-1001")

    def test_anomalies_mock_still_200(self):
        with mock.patch.dict(os.environ, env(ENABLE_DEMO_ANOMALY="true"), clear=True):
            response = lambda_handler(make_event("GET", "/users/u-1001/anomalies"), None)
        self.assertEqual(response["statusCode"], 200)

    def test_unknown_path_still_404(self):
        with mock.patch.dict(os.environ, env(ENABLE_DEMO_ANOMALY="true"), clear=True):
            response = lambda_handler(make_event("GET", "/unknown"), None)
        self.assertEqual(response["statusCode"], 404)


if __name__ == "__main__":
    unittest.main()
