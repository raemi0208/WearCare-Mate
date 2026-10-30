"""lambda_function 모듈에 대한 단위 테스트.

외부 패키지 없이 파이썬 표준 라이브러리 unittest 만 사용합니다.

실행 방법(backend 폴더 기준):
    python -m unittest discover -s tests -v
"""

import json
import os
import sys
import unittest
from unittest import mock

# 이 테스트 파일에서 src 패키지를 import 할 수 있도록
# backend 폴더(= 이 파일의 상위 폴더)를 모듈 검색 경로에 추가합니다.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.data_source import DATA_SOURCE_ENV  # noqa: E402
from src.lambda_function import lambda_handler  # noqa: E402
from src.mock_data import build_anomalies_mock  # noqa: E402


# ---------------------------------------------------------------------------
# 환경변수 격리
# ---------------------------------------------------------------------------
# 이 모듈의 테스트는 기존 MOCK 응답을 검증하므로, 개발 PC 에 DATA_SOURCE 가
# 어떤 값으로 설정되어 있든 항상 DATA_SOURCE=mock 으로 실행되어야 한다.
# - setUpModule: 이 모듈의 첫 테스트 전에 한 번 실행. os.environ 을 patch.dict 로
#   감싸고 DATA_SOURCE=mock 을 적용한다.
# - tearDownModule: 이 모듈의 마지막 테스트 후 한 번 실행. 원래 환경변수로 복원한다.
# 환경변수별 동작 검증은 tests/test_data_source.py 에서 별도로 수행한다.
_env_patcher = mock.patch.dict(os.environ, {DATA_SOURCE_ENV: "mock"})


def setUpModule():
    _env_patcher.start()


def tearDownModule():
    _env_patcher.stop()


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


# 강제로 발생시키는 예외에 넣을 "민감한 정보" 예시 (응답/로그에 노출되면 안 됨)
SENSITIVE_DETAIL = "secret-db-password-1234"
SENSITIVE_USER_ID = "u-sensitive-9999"

# 예외를 강제로 일으킬 때 바꿔치기할 대상(모듈 안의 이름)
PATCH_HEALTH = "src.lambda_function.build_health_data_mock"
PATCH_ANOMALIES = "src.lambda_function.build_anomalies_mock"
PATCH_GUIDES = "src.lambda_function.build_guides_mock"
PATCH_ROUTE = "src.lambda_function._extract_route"
LOGGER_NAME = "src.lambda_function"


def raise_runtime_error(*args, **kwargs):
    """민감한 정보가 담긴 예외를 일부러 발생시킨다."""
    raise RuntimeError(f"{SENSITIVE_DETAIL} for {SENSITIVE_USER_ID}")


class UnexpectedErrorHandlingTest(unittest.TestCase):
    """처리되지 않은 예외 → HTTP 500 변환과 정보 비노출을 검증한다."""

    def assert_internal_error(self, response):
        """500 응답이 명세의 {error, message} 형식이고 민감 정보가 없는지 확인한다."""
        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(response["headers"]["Content-Type"], "application/json")
        body = json.loads(response["body"])
        self.assertEqual(set(body.keys()), {"error", "message"})
        self.assertEqual(body["error"], "internal_error")
        # 예외 메시지, 사용자 ID, 스택 트레이스가 응답에 없어야 한다.
        for leaked in (SENSITIVE_DETAIL, SENSITIVE_USER_ID, "Traceback", "RuntimeError"):
            self.assertNotIn(leaked, response["body"])

    def test_health_data_exception_returns_500(self):
        """health-data 처리 중 예외가 나면 500 을 반환해야 한다."""
        event = make_event("GET", f"/users/{SENSITIVE_USER_ID}/health-data")
        with mock.patch(PATCH_HEALTH, side_effect=raise_runtime_error):
            with self.assertLogs(LOGGER_NAME, level="ERROR"):
                response = lambda_handler(event, None)
        self.assert_internal_error(response)

    def test_anomalies_exception_returns_500(self):
        """anomalies 처리 중 예외(KeyError)가 나면 500 을 반환해야 한다."""
        event = make_event("GET", f"/users/{SENSITIVE_USER_ID}/anomalies")
        with mock.patch(PATCH_ANOMALIES, side_effect=KeyError(SENSITIVE_DETAIL)):
            with self.assertLogs(LOGGER_NAME, level="ERROR"):
                response = lambda_handler(event, None)
        self.assert_internal_error(response)

    def test_guides_non_serializable_body_returns_500(self):
        """응답을 JSON 으로 만들 수 없는 경우(직렬화 실패)도 500 이어야 한다."""
        event = make_event("GET", f"/users/{SENSITIVE_USER_ID}/guides")
        with mock.patch(PATCH_GUIDES, return_value={"items": object()}):
            with self.assertLogs(LOGGER_NAME, level="ERROR"):
                response = lambda_handler(event, None)
        self.assert_internal_error(response)

    def test_value_error_from_builder_returns_500(self):
        """검증 단계가 아닌 곳의 ValueError 는 400 이 아니라 500 이어야 한다."""
        event = make_event("GET", f"/users/{SENSITIVE_USER_ID}/health-data")
        with mock.patch(PATCH_HEALTH, side_effect=ValueError(SENSITIVE_DETAIL)):
            with self.assertLogs(LOGGER_NAME, level="ERROR"):
                response = lambda_handler(event, None)
        self.assert_internal_error(response)

    def test_exception_in_route_extraction_returns_500(self):
        """라우팅 정보 추출 단계에서 ValueError 가 아닌 예외가 나면 500 이어야 한다."""
        with mock.patch(PATCH_ROUTE, side_effect=TypeError(SENSITIVE_DETAIL)):
            with self.assertLogs(LOGGER_NAME, level="ERROR"):
                response = lambda_handler(make_event("GET", "/health"), None)
        self.assert_internal_error(response)

    def test_log_contains_only_exception_type(self):
        """로그에는 예외 타입만 남고, 예외 메시지나 사용자 ID 는 남지 않아야 한다."""
        event = make_event("GET", f"/users/{SENSITIVE_USER_ID}/health-data")
        with mock.patch(PATCH_HEALTH, side_effect=raise_runtime_error):
            with self.assertLogs(LOGGER_NAME, level="ERROR") as captured:
                lambda_handler(event, None)
        log_text = "\n".join(captured.output)
        self.assertIn("RuntimeError", log_text)
        self.assertNotIn(SENSITIVE_DETAIL, log_text)
        self.assertNotIn(SENSITIVE_USER_ID, log_text)

    def test_base_exception_is_not_swallowed(self):
        """KeyboardInterrupt 같은 BaseException 은 500 으로 바꾸지 않고 그대로 전달해야 한다."""
        event = make_event("GET", "/users/u-1001/health-data")
        with mock.patch(PATCH_HEALTH, side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                lambda_handler(event, None)

    def test_error_body_constant_is_not_mutated(self):
        """500 응답을 여러 번 만들어도 매번 같은 고정 문구여야 한다."""
        event = make_event("GET", "/users/u-1001/health-data")
        with mock.patch(PATCH_HEALTH, side_effect=raise_runtime_error):
            with self.assertLogs(LOGGER_NAME, level="ERROR"):
                first = lambda_handler(event, None)
                second = lambda_handler(event, None)
        self.assertEqual(first["body"], second["body"])


class ErrorHandlingScopeTest(unittest.TestCase):
    """예외 처리 범위가 넓어져 기존 400/404 를 500 으로 바꾸지 않는지 검증한다.

    모든 MOCK 빌더가 예외를 던지도록 바꿔 둔 상태에서도,
    빌더를 호출하기 전에 결정되는 200/400/404 응답은 그대로여야 한다.
    """

    def setUp(self):
        patchers = [
            mock.patch(PATCH_HEALTH, side_effect=raise_runtime_error),
            mock.patch(PATCH_ANOMALIES, side_effect=raise_runtime_error),
            mock.patch(PATCH_GUIDES, side_effect=raise_runtime_error),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_health_still_200(self):
        """GET /health 는 빌더와 무관하므로 계속 200 이어야 한다."""
        response = lambda_handler(make_event("GET", "/health"), None)
        self.assertEqual(response["statusCode"], 200)

    def test_unknown_path_still_404(self):
        """등록되지 않은 경로는 계속 404 여야 한다."""
        response = lambda_handler(make_event("GET", "/unknown"), None)
        self.assertEqual(response["statusCode"], 404)
        self.assertEqual(json.loads(response["body"])["error"], "not_found")

    def test_wrong_method_still_404(self):
        """지원하지 않는 메서드는 계속 404 여야 한다."""
        for path in ("/health", "/users/u-1001/health-data", "/users/u-1001/guides"):
            response = lambda_handler(make_event("POST", path), None)
            self.assertEqual(response["statusCode"], 404, path)

    def test_malformed_event_still_400(self):
        """잘못된 이벤트 형식은 계속 400 이어야 한다."""
        for event in ({"foo": "bar"}, "not-a-dict", None):
            response = lambda_handler(event, None)
            self.assertEqual(response["statusCode"], 400)
            self.assertEqual(json.loads(response["body"])["error"], "bad_request")

    def test_empty_user_id_still_400(self):
        """빈 userId 는 빌더 호출 전에 걸러지므로 계속 400 이어야 한다."""
        for resource in ("health-data", "anomalies", "guides"):
            response = lambda_handler(make_event("GET", f"/users//{resource}"), None)
            self.assertEqual(response["statusCode"], 400, resource)

    def test_invalid_query_still_400(self):
        """잘못된 쿼리 형식은 빌더 호출 전에 걸러지므로 계속 400 이어야 한다."""
        for resource in ("health-data", "anomalies", "guides"):
            response = lambda_handler(
                make_event("GET", f"/users/u-1001/{resource}", ["not", "a", "dict"]),
                None,
            )
            self.assertEqual(response["statusCode"], 400, resource)


if __name__ == "__main__":
    unittest.main()
