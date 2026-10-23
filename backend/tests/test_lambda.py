"""lambda_function 모듈에 대한 단위 테스트.

외부 패키지 없이 파이썬 표준 라이브러리 unittest 만 사용합니다.

실행 방법(backend 폴더 기준):
    python -m unittest discover -s tests -v
"""

import json
import os
import sys
import unittest

# 이 테스트 파일에서 src 패키지를 import 할 수 있도록
# backend 폴더(= 이 파일의 상위 폴더)를 모듈 검색 경로에 추가합니다.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.lambda_function import lambda_handler  # noqa: E402
from src.mock_data import build_anomalies_mock  # noqa: E402


def make_event(method, path, query="__default__"):
    """테스트용 API Gateway HTTP API(payload 2.0) 이벤트를 만듭니다.

    query 인자:
    - 생략하면(기본값) queryStringParameters 키를 아예 넣지 않습니다.
      → 기존 6개 테스트가 그대로 동작하도록 하위 호환을 지킵니다.
    - dict 를 주면 그대로 queryStringParameters 로 넣습니다.
    - None 이나 잘못된 타입(list 등)을 주면 그 값을 그대로 넣어
      '쿼리 없음' / '형식 오류' 상황을 테스트할 수 있습니다.
    """
    event = {
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
            }
        }
    }
    if query != "__default__":
        event["queryStringParameters"] = query
    return event


class LambdaHandlerTest(unittest.TestCase):
    """lambda_handler 의 동작을 검증하는 테스트 모음."""

    def test_health_returns_200(self):
        """GET /health 는 200 과 정상 상태 JSON 을 반환해야 한다."""
        response = lambda_handler(make_event("GET", "/health"), None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["service"], "WearCare Mate Backend")

    def test_unknown_path_returns_404(self):
        """등록되지 않은 경로는 404 를 반환해야 한다."""
        response = lambda_handler(make_event("GET", "/unknown"), None)
        self.assertEqual(response["statusCode"], 404)

    def test_wrong_method_on_health_returns_404(self):
        """같은 경로라도 지원하지 않는 메서드는 404 를 반환해야 한다."""
        response = lambda_handler(make_event("POST", "/health"), None)
        self.assertEqual(response["statusCode"], 404)

    def test_malformed_event_returns_400(self):
        """requestContext 가 없는 잘못된 이벤트는 400 을 반환해야 한다."""
        response = lambda_handler({"foo": "bar"}, None)
        self.assertEqual(response["statusCode"], 400)

    def test_non_dict_event_returns_400(self):
        """dict 가 아닌 이벤트도 400 으로 안전하게 처리해야 한다."""
        response = lambda_handler("not-a-dict", None)
        self.assertEqual(response["statusCode"], 400)

    def test_response_body_is_valid_json(self):
        """응답 body 는 항상 유효한 JSON 문자열이어야 한다."""
        response = lambda_handler(make_event("GET", "/health"), None)
        self.assertIsInstance(response["body"], str)
        # 파싱이 실패하면 예외가 발생하여 테스트가 실패합니다.
        json.loads(response["body"])


class HealthDataMockApiTest(unittest.TestCase):
    """GET /users/{userId}/health-data (MOCK) 동작을 검증하는 테스트 모음."""

    def test_health_data_returns_200_and_userid(self):
        """정상 요청은 200 과 요청한 userId 를 담은 응답을 반환해야 한다."""
        response = lambda_handler(
            make_event("GET", "/users/u-1001/health-data"), None
        )
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["userId"], "u-1001")
        self.assertIsInstance(body["items"], list)

    def test_health_data_has_mock_markers(self):
        """응답에는 mock=true 와 _note 가 포함되어 가짜 데이터임을 표시해야 한다."""
        response = lambda_handler(
            make_event("GET", "/users/u-1001/health-data"), None
        )
        body = json.loads(response["body"])
        self.assertIs(body["mock"], True)
        self.assertIn("_note", body)
        self.assertIn("MOCK", body["_note"])

    def test_health_data_echoes_from_to(self):
        """from/to 쿼리는 requestedRange 로 그대로 반영되어야 한다(필터링 아님)."""
        response = lambda_handler(
            make_event(
                "GET",
                "/users/u-1001/health-data",
                {"from": "2099-01-01", "to": "2099-01-02"},
            ),
            None,
        )
        body = json.loads(response["body"])
        self.assertEqual(body["requestedRange"]["from"], "2099-01-01")
        self.assertEqual(body["requestedRange"]["to"], "2099-01-02")

    def test_health_data_empty_userid_returns_400(self):
        """빈 userId(/users//health-data)는 400 을 반환해야 한다."""
        response = lambda_handler(
            make_event("GET", "/users//health-data"), None
        )
        self.assertEqual(response["statusCode"], 400)

    def test_health_data_none_query_is_ok(self):
        """queryStringParameters 가 None 이면 빈 쿼리로 보고 200 이어야 한다."""
        response = lambda_handler(
            make_event("GET", "/users/u-1001/health-data", None), None
        )
        self.assertEqual(response["statusCode"], 200)

    def test_health_data_invalid_query_returns_400(self):
        """queryStringParameters 가 dict 가 아니면(예: list) 400 을 반환해야 한다."""
        response = lambda_handler(
            make_event("GET", "/users/u-1001/health-data", ["not", "a", "dict"]),
            None,
        )
        self.assertEqual(response["statusCode"], 400)

    def test_health_data_wrong_method_returns_404(self):
        """같은 경로라도 지원하지 않는 메서드(POST)는 404 를 반환해야 한다."""
        response = lambda_handler(
            make_event("POST", "/users/u-1001/health-data"), None
        )
        self.assertEqual(response["statusCode"], 404)


class AnomaliesMockApiTest(unittest.TestCase):
    """GET /users/{userId}/anomalies (MOCK) 동작을 검증하는 테스트 모음."""

    def test_anomalies_returns_200_and_userid(self):
        """정상 요청은 200 과 요청한 userId 를 담은 응답을 반환해야 한다."""
        response = lambda_handler(
            make_event("GET", "/users/u-1001/anomalies"), None
        )
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["userId"], "u-1001")
        self.assertIsInstance(body["items"], list)

    def test_anomalies_has_mock_markers(self):
        """응답에는 mock=true 와 _note 가 포함되어 가짜 데이터임을 표시해야 한다."""
        response = lambda_handler(
            make_event("GET", "/users/u-1001/anomalies"), None
        )
        body = json.loads(response["body"])
        self.assertIs(body["mock"], True)
        self.assertIn("_note", body)
        self.assertIn("MOCK", body["_note"])

    def test_anomalies_item_has_expected_fields(self):
        """각 이상탐지 항목은 명세 4.3절의 임시 필드를 모두 포함해야 한다."""
        response = lambda_handler(
            make_event("GET", "/users/u-1001/anomalies"), None
        )
        body = json.loads(response["body"])
        self.assertGreater(len(body["items"]), 0)
        first = body["items"][0]
        for field in ("anomalyId", "detectedAt", "metric", "severity", "score", "description"):
            self.assertIn(field, first)

    def test_anomalies_echoes_range_and_filters(self):
        """from/to 는 requestedRange, severity 는 requestedFilters 로 echo 되어야 한다."""
        response = lambda_handler(
            make_event(
                "GET",
                "/users/u-1001/anomalies",
                {"from": "2099-01-01", "to": "2099-01-02", "severity": "high"},
            ),
            None,
        )
        body = json.loads(response["body"])
        self.assertEqual(body["requestedRange"]["from"], "2099-01-01")
        self.assertEqual(body["requestedRange"]["to"], "2099-01-02")
        self.assertEqual(body["requestedFilters"]["severity"], "high")

    def test_anomalies_empty_userid_returns_400(self):
        """빈 userId(/users//anomalies)는 400 을 반환해야 한다."""
        response = lambda_handler(
            make_event("GET", "/users//anomalies"), None
        )
        self.assertEqual(response["statusCode"], 400)

    def test_anomalies_none_query_is_ok(self):
        """queryStringParameters 가 None 이면 빈 쿼리로 보고 200 이어야 한다."""
        response = lambda_handler(
            make_event("GET", "/users/u-1001/anomalies", None), None
        )
        self.assertEqual(response["statusCode"], 200)

    def test_anomalies_invalid_query_returns_400(self):
        """queryStringParameters 가 dict 가 아니면(예: list) 400 을 반환해야 한다."""
        response = lambda_handler(
            make_event("GET", "/users/u-1001/anomalies", ["not", "a", "dict"]),
            None,
        )
        self.assertEqual(response["statusCode"], 400)

    def test_anomalies_wrong_method_returns_404(self):
        """같은 경로라도 지원하지 않는 메서드(POST)는 404 를 반환해야 한다."""
        response = lambda_handler(
            make_event("POST", "/users/u-1001/anomalies"), None
        )
        self.assertEqual(response["statusCode"], 404)


class GuidesMockApiTest(unittest.TestCase):
    """GET /users/{userId}/guides (MOCK) 동작을 검증하는 테스트 모음."""

    def test_guides_returns_200_and_userid(self):
        """정상 요청은 200 과 요청한 userId 를 담은 응답을 반환해야 한다."""
        response = lambda_handler(make_event("GET", "/users/u-1001/guides"), None)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["userId"], "u-1001")
        self.assertIsInstance(body["items"], list)

    def test_guides_has_mock_markers(self):
        """응답에는 mock=true 와 _note 가 포함되어 가짜 데이터임을 표시해야 한다."""
        response = lambda_handler(make_event("GET", "/users/u-1001/guides"), None)
        body = json.loads(response["body"])
        self.assertIs(body["mock"], True)
        self.assertIn("_note", body)
        self.assertIn("MOCK", body["_note"])

    def test_guides_has_disclaimer(self):
        """응답에는 의료 행위가 아님을 알리는 disclaimer 가 포함되어야 한다."""
        response = lambda_handler(make_event("GET", "/users/u-1001/guides"), None)
        body = json.loads(response["body"])
        self.assertIn("disclaimer", body)
        self.assertIn("진단", body["disclaimer"])
        self.assertIn("치료", body["disclaimer"])

    def test_guides_item_has_expected_fields(self):
        """각 가이드 항목은 명세 4.4절의 필드를 모두 포함해야 한다."""
        response = lambda_handler(make_event("GET", "/users/u-1001/guides"), None)
        body = json.loads(response["body"])
        self.assertGreater(len(body["items"]), 0)
        first = body["items"][0]
        for field in ("guideId", "relatedAnomalyId", "title", "message", "category", "createdAt"):
            self.assertIn(field, first)

    def test_guides_related_anomaly_id_matches_anomalies(self):
        """가이드의 relatedAnomalyId 는 anomalies MOCK 의 anomalyId 목록에 실제로 존재해야 한다."""
        # anomalies MOCK 에서 실제 anomalyId 목록을 추출한다.
        anomalies = build_anomalies_mock("u-1001", {})
        valid_anomaly_ids = {item["anomalyId"] for item in anomalies["items"]}

        response = lambda_handler(make_event("GET", "/users/u-1001/guides"), None)
        body = json.loads(response["body"])
        for guide in body["items"]:
            self.assertIn(guide["relatedAnomalyId"], valid_anomaly_ids)

    def test_guides_echoes_anomaly_id_without_filtering(self):
        """anomalyId 쿼리는 requestedFilters 로 echo 되지만 실제 필터링은 하지 않아야 한다."""
        # 필터를 걸지 않은 기준 응답의 항목 수
        base = lambda_handler(make_event("GET", "/users/u-1001/guides"), None)
        base_count = len(json.loads(base["body"])["items"])

        # anomalyId 쿼리를 넣어도 항목 수가 줄지 않아야 한다(= 실제 필터링 아님).
        response = lambda_handler(
            make_event("GET", "/users/u-1001/guides", {"anomalyId": "mock-anomaly-001"}),
            None,
        )
        body = json.loads(response["body"])
        self.assertEqual(body["requestedFilters"]["anomalyId"], "mock-anomaly-001")
        self.assertEqual(len(body["items"]), base_count)

    def test_guides_empty_userid_returns_400(self):
        """빈 userId(/users//guides)는 400 을 반환해야 한다."""
        response = lambda_handler(make_event("GET", "/users//guides"), None)
        self.assertEqual(response["statusCode"], 400)

    def test_guides_none_query_is_ok(self):
        """queryStringParameters 가 None 이면 빈 쿼리로 보고 200 이어야 한다."""
        response = lambda_handler(
            make_event("GET", "/users/u-1001/guides", None), None
        )
        self.assertEqual(response["statusCode"], 200)

    def test_guides_invalid_query_returns_400(self):
        """queryStringParameters 가 dict 가 아니면(예: list) 400 을 반환해야 한다."""
        response = lambda_handler(
            make_event("GET", "/users/u-1001/guides", ["not", "a", "dict"]), None
        )
        self.assertEqual(response["statusCode"], 400)

    def test_guides_wrong_method_returns_404(self):
        """같은 경로라도 지원하지 않는 메서드(POST)는 404 를 반환해야 한다."""
        response = lambda_handler(make_event("POST", "/users/u-1001/guides"), None)
        self.assertEqual(response["statusCode"], 404)


if __name__ == "__main__":
    unittest.main()
