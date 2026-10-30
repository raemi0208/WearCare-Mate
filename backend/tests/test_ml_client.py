"""ml_client (AI/ML Lambda 호출 래퍼) 테스트.

- AWS 에 접속하지 않습니다. Lambda 클라이언트는 가짜(FakeLambdaClient)를 주입합니다.
- 응답은 v0.3 lambda_handler 와 같은 API Gateway 형식으로 감싸서 만듭니다.
- 샘플 응답은 tests/ml_samples.py (origin/ai-ml 의 docs/sample_responses.json 복사본)를 사용합니다.
- boto3 가 설치되지 않은 환경에서도 실행됩니다.
"""

import io
import json
import os
import sys
import unittest
from unittest import mock

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.data_source import DataSourceConfigError, DataSourceUnavailableError  # noqa: E402
from src.ml_adapter import MLRequestError, MLResponseError  # noqa: E402
from src.ml_client import (  # noqa: E402
    DEFAULT_REGION,
    DEFAULT_TIMEOUT_SECONDS,
    MLClient,
    MLConfig,
    MLConfigError,
    MLErrorResponse,
    MLInvocationError,
    create_lambda_client,
    unwrap_api_gateway_response,
)
from tests.ml_samples import SAMPLE_NAMES, sample  # noqa: E402

FUNCTION_ARN = "arn:aws:lambda:ap-northeast-2:123456789012:function:wearcare-ml"
SECRET = "secret-detail-98765"


def envelope(status_code, body):
    """v0.3 lambda_handler._response 와 같은 API Gateway 형식."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def invoke_response(payload_obj=None, raw=None, status=200, function_error=None):
    """boto3 invoke() 응답 흉내. Payload 는 읽을 수 있는 스트림."""
    data = raw if raw is not None else json.dumps(payload_obj, ensure_ascii=False).encode("utf-8")
    response = {"StatusCode": status, "Payload": io.BytesIO(data), "ExecutedVersion": "$LATEST"}
    if function_error:
        response["FunctionError"] = function_error
    return response


class FakeLambdaClient:
    """invoke() 호출을 기록하고 준비된 응답을 돌려준다."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def make_client(response=None, error=None, **config):
    fake = FakeLambdaClient(response=response, error=error)
    return MLClient(fake, MLConfig(function_name=config.pop("function_name", FUNCTION_ARN),
                                   **config)), fake


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
class MLConfigTest(unittest.TestCase):

    def test_defaults(self):
        config = MLConfig(function_name="wearcare-ml")
        self.assertEqual(config.region, "ap-northeast-2")
        self.assertEqual(config.timeout_seconds, 15.0)
        self.assertEqual((DEFAULT_REGION, DEFAULT_TIMEOUT_SECONDS), ("ap-northeast-2", 15.0))

    def test_from_env(self):
        config = MLConfig.from_env({
            "ML_FUNCTION_NAME": f" {FUNCTION_ARN} ",
            "ML_TIMEOUT_SECONDS": "12.5",
        })
        self.assertEqual(config.function_name, FUNCTION_ARN)
        self.assertEqual(config.region, "ap-northeast-2")
        self.assertEqual(config.timeout_seconds, 12.5)

    def test_from_env_reads_os_environ_by_default(self):
        with mock.patch.dict(os.environ, {"ML_FUNCTION_NAME": "wearcare-ml", "ML_REGION": "us-east-2"}):
            config = MLConfig.from_env()
        self.assertEqual((config.function_name, config.region), ("wearcare-ml", "us-east-2"))

    def test_accepts_name_alias_and_arn(self):
        for name in ("wearcare-ml", "wearcare_ml:prod", "wearcare-ml:1", FUNCTION_ARN,
                     FUNCTION_ARN + ":live"):
            MLConfig(function_name=name)

    def test_missing_function_name(self):
        for env in ({}, {"ML_FUNCTION_NAME": "  "}):
            with self.assertRaises(MLConfigError):
                MLConfig.from_env(env)

    def test_invalid_values_without_echoing_them(self):
        invalid = [
            {"function_name": "bad name"},
            {"function_name": "x" * 65},
            {"function_name": "arn:aws:lambda:ap-northeast-2:123:function:short-account"},
            {"function_name": "wearcare-ml", "region": "Seoul"},
            {"function_name": FUNCTION_ARN, "region": "us-east-2"},   # ARN 리전과 불일치
            {"function_name": "wearcare-ml", "timeout_seconds": 0},
            {"function_name": "wearcare-ml", "timeout_seconds": 30},    # API Gateway 30초 이상
            {"function_name": "wearcare-ml", "timeout_seconds": float("nan")},
            {"function_name": "wearcare-ml", "timeout_seconds": True},
        ]
        for values in invalid:
            with self.assertRaises(MLConfigError, msg=values) as context:
                MLConfig(**values)
            self.assertNotIn("bad name", str(context.exception))

    def test_invalid_timeout_text(self):
        with self.assertRaises(MLConfigError):
            MLConfig.from_env({"ML_FUNCTION_NAME": "wearcare-ml", "ML_TIMEOUT_SECONDS": "fast"})

    def test_config_error_is_500_family(self):
        self.assertTrue(issubclass(MLConfigError, DataSourceConfigError))

    def test_client_requires_config_object(self):
        with self.assertRaises(MLConfigError):
            MLClient(FakeLambdaClient(), {"function_name": "wearcare-ml"})


class CreateLambdaClientTest(unittest.TestCase):

    def test_missing_boto3_raises_config_error(self):
        with mock.patch.dict(sys.modules, {"boto3": None}):
            with self.assertRaises(MLConfigError):
                create_lambda_client(MLConfig(function_name="wearcare-ml"))

    def test_region_timeout_and_no_retry(self):
        """서울 리전, 읽기 제한 시간=설정값, 자동 재시도 없음(max_attempts=1)."""
        fake_boto3 = mock.Mock()
        fake_botocore_config = mock.Mock()
        modules = {"boto3": fake_boto3, "botocore": mock.Mock(),
                   "botocore.config": fake_botocore_config}
        with mock.patch.dict(sys.modules, modules):
            client = create_lambda_client(MLConfig(function_name="wearcare-ml", timeout_seconds=12))
        self.assertIs(client, fake_boto3.client.return_value)
        args, kwargs = fake_boto3.client.call_args
        self.assertEqual(args, ("lambda",))
        self.assertEqual(kwargs["region_name"], "ap-northeast-2")
        config_kwargs = fake_botocore_config.Config.call_args.kwargs
        self.assertEqual(config_kwargs["read_timeout"], 12)
        self.assertEqual(config_kwargs["connect_timeout"], 3)
        self.assertEqual(config_kwargs["retries"], {"max_attempts": 1, "mode": "standard"})

    def test_requires_config_object(self):
        with self.assertRaises(MLConfigError):
            create_lambda_client({"function_name": "wearcare-ml"})


# ---------------------------------------------------------------------------
# 정상 호출
# ---------------------------------------------------------------------------
class InvokeSuccessTest(unittest.TestCase):

    def test_all_samples_round_trip(self):
        """샘플 4종(이상 high, 집단 기준 복합, 정상, 데이터 부족)이 검증을 통과해 그대로 돌아온다."""
        for name in SAMPLE_NAMES:
            case = sample(name)
            client, _ = make_client(invoke_response(envelope(200, case["response"])))
            self.assertEqual(client.invoke_detection(case["request"]), case["response"], name)

    def test_invoke_parameters(self):
        case = sample("activity_drop_high")
        client, fake = make_client(invoke_response(envelope(200, case["response"])))
        client.invoke_detection(case["request"])
        self.assertEqual(len(fake.calls), 1)
        call = fake.calls[0]
        self.assertEqual(call["FunctionName"], FUNCTION_ARN)
        self.assertEqual(call["InvocationType"], "RequestResponse")
        self.assertEqual(json.loads(call["Payload"].decode("utf-8")), case["request"])

    def test_payload_as_bytes_or_dict_body(self):
        """Payload 가 스트림이 아닌 bytes 여도, body 가 문자열이 아닌 dict 여도 읽는다."""
        case = sample("normal")
        raw_envelope = {"statusCode": 200, "body": case["response"]}
        response = {"StatusCode": 200, "Payload": json.dumps(raw_envelope).encode("utf-8")}
        client, _ = make_client(response)
        self.assertEqual(client.invoke_detection(case["request"])["status"], "normal")

    def test_guide_null_anomaly_is_returned_not_rejected(self):
        """이상이 있는데 guide=null (가이드 생성 실패) 도 유효한 탐지 결과로 돌려준다."""
        case = sample("activity_drop_high")
        case["response"]["guide"] = None
        client, _ = make_client(invoke_response(envelope(200, case["response"])))
        result = client.invoke_detection(case["request"])
        self.assertEqual(result["status"], "anomaly")
        self.assertIsNone(result["guide"])


# ---------------------------------------------------------------------------
# 오류 처리
# ---------------------------------------------------------------------------
class RequestWithoutHistoryTest(unittest.TestCase):
    """history_steps 를 보내지 않는 새 요청 방식 (AI/ML 담당자 요청 반영)."""

    def setUp(self):
        from datetime import date

        from src.ml_adapter import build_detection_request, summarize_detection
        self.summarize = summarize_detection
        self.request = build_detection_request(
            "1000000001", "2016-04-10", {date(2016, 4, 9): 9000, date(2016, 4, 10): 2100}
        )

    def test_payload_has_no_history_steps(self):
        response = {
            "user_id": "1000000001", "date": "2016-04-10", "anomalies": [],
            "anomaly_score": None, "guide": None,
            "model_version": "activity-zscore-v0.2+pop-v0.3",
            "status": "insufficient_data", "overall_severity": "none",
        }
        client, fake = make_client(invoke_response(envelope(200, response)))
        client.invoke_detection(self.request)
        sent = json.loads(fake.calls[0]["Payload"].decode("utf-8"))
        self.assertEqual(sent, {"user_id": "1000000001", "date": "2016-04-10",
                                "metrics": {"steps": 2100}})

    def test_current_lambda_without_athena_returns_insufficient_data(self):
        """3dc9a94 의 load_history_steps 는 미구현([] 반환)이라, history 없이 보내면
        v0.3 코드상 걸음 수 판정은 insufficient_data 가 된다. 그 응답도 유효한 결과로 받되,
        실제 판정이 된 것으로 보지 않는다(요약에서 status 로 구분)."""
        response = {
            "user_id": "1000000001", "date": "2016-04-10", "anomalies": [],
            "anomaly_score": None, "guide": None,
            "model_version": "activity-zscore-v0.2+pop-v0.3",
            "status": "insufficient_data", "overall_severity": "none",
        }
        client, _ = make_client(invoke_response(envelope(200, response)))
        summary = self.summarize(client.invoke_detection(self.request))
        self.assertEqual(summary["status"], "insufficient_data")
        self.assertFalse(summary["stepAnomaly"])


class InvokeErrorTest(unittest.TestCase):

    def setUp(self):
        self.case = sample("activity_drop_high")

    def call_with(self, response=None, error=None):
        client, fake = make_client(response, error)
        return client, fake

    def assert_unavailable(self, response=None, error=None, expected=MLInvocationError):
        client, _ = self.call_with(response, error)
        with self.assertRaises(expected) as context:
            client.invoke_detection(self.case["request"])
        self.assertIsInstance(context.exception, DataSourceUnavailableError)
        message = str(context.exception)
        for leaked in (SECRET, "demo-user-1", "2100", "12,271"):
            self.assertNotIn(leaked, message)
        return context.exception

    def test_timeout_and_network_errors(self):
        """읽기 시간 초과·연결 오류·권한 오류 등 invoke 예외는 모두 503 계열."""
        for error in (TimeoutError(SECRET), ConnectionError(SECRET), OSError(SECRET),
                      RuntimeError(f"AccessDenied {SECRET}")):
            self.assert_unavailable(error=error)

    def test_function_error(self):
        """FunctionError(미처리 예외, 시간 초과 등)는 503. 오류 본문은 읽지 않는다."""
        for kind in ("Unhandled", "Handled"):
            body = {"errorMessage": SECRET, "errorType": "Runtime.ExitError"}
            self.assert_unavailable(invoke_response(body, function_error=kind))

    def test_invoke_status_code_not_200(self):
        self.assert_unavailable(invoke_response(envelope(200, self.case["response"]), status=202))
        self.assert_unavailable({"Payload": io.BytesIO(b"{}")})              # StatusCode 없음
        self.assert_unavailable("not-a-dict")

    def test_internal_400_and_500_error_responses(self):
        cases = [
            (400, {"error": {"code": "INVALID_INPUT", "message": f"metrics.steps {SECRET}"}}, "INVALID_INPUT"),
            (500, {"error": {"code": "MODEL_ERROR", "message": SECRET}}, "MODEL_ERROR"),
            (500, {"error": {"code": "SOMETHING_NEW", "message": SECRET}}, "UNKNOWN"),
            (502, {"message": SECRET}, "UNKNOWN"),
            (200, {"error": {"code": "GUIDE_FAILED", "message": SECRET}}, "GUIDE_FAILED"),
        ]
        for status_code, body, expected_code in cases:
            error = self.assert_unavailable(invoke_response(envelope(status_code, body)),
                                            expected=MLErrorResponse)
            self.assertEqual(error.status_code, status_code)
            self.assertEqual(error.error_code, expected_code)

    def test_invalid_json(self):
        self.assert_unavailable(invoke_response(raw=b"not json"))
        self.assert_unavailable(invoke_response(raw=b"\xff\xfe"))
        bad_body = {"statusCode": 200, "body": "{not json"}
        self.assert_unavailable(invoke_response(bad_body))

    def test_not_api_gateway_envelope(self):
        """v0.3 은 항상 API Gateway 형식으로 감싼다. 감싸지 않은 응답은 거절한다."""
        self.assert_unavailable(invoke_response(self.case["response"]))
        self.assert_unavailable(invoke_response({"statusCode": "200", "body": "{}"}))
        self.assert_unavailable(invoke_response({"statusCode": 200, "body": "[1, 2]"}))
        self.assert_unavailable(invoke_response({"statusCode": 200}))

    def test_invalid_output_fields(self):
        body = self.case["response"]
        body["anomalies"][0]["severity"] = "danger"
        self.assert_unavailable(invoke_response(envelope(200, body)), expected=MLResponseError)

    def test_response_for_other_user_or_date_is_rejected(self):
        for key, value in (("user_id", "demo-user-9"), ("date", "2026-10-31")):
            body = sample("activity_drop_high")["response"]
            body[key] = value
            self.assert_unavailable(invoke_response(envelope(200, body)), expected=MLResponseError)

    def test_request_that_cannot_be_serialized(self):
        client, fake = make_client(invoke_response(envelope(200, self.case["response"])))
        for request in ({"user_id": "1", "metrics": {"steps": float("nan")}}, {"x": object()}, []):
            with self.assertRaises(MLRequestError):
                client.invoke_detection(request)
        self.assertEqual(fake.calls, [])

    def test_no_logs_are_written(self):
        """이 모듈은 로그를 남기지 않는다. (응답 원문·건강 데이터 비노출)"""
        client, _ = make_client(invoke_response(envelope(500, {"error": {"code": "MODEL_ERROR",
                                                                          "message": SECRET}})))
        with self.assertNoLogs(level="DEBUG"):
            with self.assertRaises(MLErrorResponse):
                client.invoke_detection(self.case["request"])


class UnwrapTest(unittest.TestCase):

    def test_unwrap(self):
        status, body = unwrap_api_gateway_response(envelope(400, {"error": {"code": "INVALID_INPUT"}}))
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "INVALID_INPUT")

    def test_unwrap_rejects_bool_status(self):
        with self.assertRaises(MLInvocationError):
            unwrap_api_gateway_response({"statusCode": True, "body": "{}"})


if __name__ == "__main__":
    unittest.main()
