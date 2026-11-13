"""WearCare Mate 백엔드 - AI/ML Lambda 호출 래퍼.

AI/ML Lambda(서울 리전, origin/ai-ml @ 3dc9a94 의 AI_ML/lambda_handler.py)를 동기 호출하고,
v0.3 출력 구조로 검증된 body 를 돌려줍니다.

현재 API(/dashboard, /ai-guide)는 ai_service.py를 통해 이 래퍼를 사용합니다.
   단위 테스트는 가짜 Lambda 클라이언트만 사용하며 AWS 에 접속하지 않습니다.

설정 (환경변수):
    ML_FUNCTION_NAME    필수. 함수 이름 또는 ARN (리전 간 호출에는 ARN 권장)
    ML_REGION           기본 ap-northeast-2. ARN 을 쓰면 ARN 의 리전과 같아야 한다.
    ML_TIMEOUT_SECONDS  기본 15. 읽기 제한 시간. (API Gateway 30초 안에서 Athena 조회 시간과 합산해 정한다)

호출 방식:
    - InvocationType=RequestResponse (동기)
    - 자동 재시도 없음 (botocore max_attempts=1). 동기 호출은 멱등이 아니라
      재시도하면 Bedrock 가이드 생성이 중복될 수 있기 때문이다.
    - 자격 증명은 코드에 두지 않는다. (Lambda 실행 역할 등 기본 자격 증명 체인)
    - boto3 는 create_lambda_client() 안에서만 import 한다. (boto3 가 없는 로컬에서도 테스트 가능)

응답 처리 (v0.3 실제 코드 기준):
    v0.3 lambda_handler 는 직접 호출에도 항상 API Gateway 형식으로 감싸서 돌려준다.
        {"statusCode": 200|400|500, "headers": {...}, "body": "<JSON 문자열>"}
    - invoke 응답에 FunctionError 가 있으면 함수 자체가 실패한 것 (미처리 예외, 시간 초과 등)
    - statusCode 400/500 이면 body 는 {"error": {"code": ..., "message": ...}}
    - statusCode 200 이면 body 를 v0.3 출력으로 검증한다. (ml_adapter.validate_detection_result)

오류 구분:
    - MLConfigError (DataSourceConfigError, 500): 설정 누락·형식 오류, boto3 미설치
    - MLRequestError (ml_adapter, 500 처리 예정): 요청을 JSON 으로 만들 수 없음
    - MLInvocationError (DataSourceUnavailableError, 503): 호출 실패, 시간 초과, 네트워크 오류,
      FunctionError, 응답 래핑/JSON 형식 오류
    - MLErrorResponse (MLInvocationError, 503): AI/ML 이 statusCode 400/500 오류 응답을 돌려줌.
      error_code 속성에 INVALID_INPUT / MODEL_ERROR / GUIDE_FAILED / UNKNOWN 중 하나를 담는다.
    - MLResponseError (ml_adapter, 503): body 가 v0.3 출력 구조와 다름

보안:
    요청·응답 원문, 사용자 ID, 걸음 수, AI/ML 오류 message 는 예외 메시지와 로그에 넣지 않는다.
    이 모듈은 로그를 남기지 않는다. (상위 lambda_handler 가 예외 타입 이름만 기록)
"""

import json
import math
import os
import re
from dataclasses import dataclass

from src.data_source import DataSourceConfigError, DataSourceUnavailableError
from src.ml_adapter import MLRequestError, validate_detection_result

ENV_FUNCTION_NAME = "ML_FUNCTION_NAME"
ENV_REGION = "ML_REGION"
ENV_TIMEOUT = "ML_TIMEOUT_SECONDS"

DEFAULT_REGION = "ap-northeast-2"
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TIMEOUT_SECONDS = 29.0          # API Gateway HTTP API 최대 대기 시간(30초)보다 짧게
CONNECT_TIMEOUT_SECONDS = 3

KNOWN_ERROR_CODES = ("INVALID_INPUT", "MODEL_ERROR", "GUIDE_FAILED")

_REGION_PATTERN = re.compile(r"[a-z]{2}(-[a-z]+)+-[0-9]")
# 함수 이름 (선택적으로 :버전/별칭)
_FUNCTION_NAME_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}(:[A-Za-z0-9_$-]{1,128})?")
# 전체 ARN: arn:aws:lambda:<region>:<12자리 계정>:function:<이름>[:<버전/별칭>]
_FUNCTION_ARN_PATTERN = re.compile(
    r"arn:aws:lambda:(?P<region>[a-z]{2}(-[a-z]+)+-[0-9]):[0-9]{12}:function:"
    r"[A-Za-z0-9_-]{1,64}(:[A-Za-z0-9_$-]{1,128})?"
)


class MLConfigError(DataSourceConfigError):
    """AI/ML 호출 설정 오류 (500). 메시지에는 설정값 자체를 넣지 않는다."""


class MLInvocationError(DataSourceUnavailableError):
    """AI/ML Lambda 호출 실패 (503)."""


class MLErrorResponse(MLInvocationError):
    """AI/ML Lambda 가 statusCode 400/500 오류 응답을 돌려줌 (503).

    Attributes:
        status_code (int): AI/ML 응답의 statusCode
        error_code (str): INVALID_INPUT / MODEL_ERROR / GUIDE_FAILED / UNKNOWN
            (AI/ML 의 error.message 는 담지 않는다)
    """

    def __init__(self, status_code, error_code):
        super().__init__(f"AI/ML 오류 응답 (statusCode={status_code}, code={error_code})")
        self.status_code = status_code
        self.error_code = error_code


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MLConfig:
    """AI/ML Lambda 호출 설정. 생성할 때 형식을 검증한다."""

    function_name: str
    region: str = DEFAULT_REGION
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self):
        name = self.function_name
        if not isinstance(name, str) or not name:
            raise MLConfigError(f"{ENV_FUNCTION_NAME} 값이 설정되지 않았습니다.")
        arn_match = _FUNCTION_ARN_PATTERN.fullmatch(name)
        if arn_match is None and _FUNCTION_NAME_PATTERN.fullmatch(name) is None:
            raise MLConfigError(f"{ENV_FUNCTION_NAME} 형식이 올바르지 않습니다.")

        if not isinstance(self.region, str) or _REGION_PATTERN.fullmatch(self.region) is None:
            raise MLConfigError(f"{ENV_REGION} 형식이 올바르지 않습니다.")
        if arn_match is not None and arn_match.group("region") != self.region:
            raise MLConfigError(f"{ENV_FUNCTION_NAME} 의 리전이 {ENV_REGION} 와 다릅니다.")

        timeout = self.timeout_seconds
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or not 0 < timeout <= MAX_TIMEOUT_SECONDS
        ):
            raise MLConfigError(f"{ENV_TIMEOUT} 값이 올바르지 않습니다.")

    @classmethod
    def from_env(cls, environ=None):
        """환경변수에서 설정을 읽는다. environ 에 dict 를 넘기면 os.environ 을 읽지 않는다."""
        env = os.environ if environ is None else environ

        def read(name):
            value = env.get(name)
            if value is None:
                return None
            value = str(value).strip()
            return value or None

        timeout_text = read(ENV_TIMEOUT)
        if timeout_text is None:
            timeout = DEFAULT_TIMEOUT_SECONDS
        else:
            try:
                timeout = float(timeout_text)
            except ValueError:
                raise MLConfigError(f"{ENV_TIMEOUT} 값이 올바르지 않습니다.") from None

        return cls(
            function_name=read(ENV_FUNCTION_NAME) or "",
            region=read(ENV_REGION) or DEFAULT_REGION,
            timeout_seconds=timeout,
        )


# ---------------------------------------------------------------------------
# 클라이언트
# ---------------------------------------------------------------------------
def create_lambda_client(config):
    """boto3 Lambda 클라이언트를 만든다. (이 함수를 호출할 때만 boto3 를 import)

    - 리전: config.region (기본 ap-northeast-2). 백엔드가 us-east-2 에 있어도 서울 함수를 호출할 수 있다.
    - 읽기 제한 시간: config.timeout_seconds, 연결 제한 시간: 3초
    - 재시도: max_attempts=1 (첫 시도만, 자동 재시도 없음)

    Raises:
        MLConfigError: boto3 미설치 또는 설정 객체가 아님
    """
    if not isinstance(config, MLConfig):
        raise MLConfigError("AI/ML 호출 설정이 올바르지 않습니다.")
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        raise MLConfigError("boto3 가 설치되어 있지 않습니다.") from None

    client_config = Config(
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        read_timeout=config.timeout_seconds,
        retries={"max_attempts": 1, "mode": "standard"},
    )
    return boto3.client("lambda", region_name=config.region, config=client_config)


def _read_payload(payload):
    """invoke 응답의 Payload(StreamingBody 또는 bytes/str)를 문자열로 읽는다."""
    if hasattr(payload, "read"):
        payload = payload.read()
    if isinstance(payload, bytes):
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError:
            raise MLInvocationError("AI/ML 응답을 읽을 수 없습니다.") from None
    if isinstance(payload, str):
        return payload
    raise MLInvocationError("AI/ML 응답 형식이 올바르지 않습니다.")


def _parse_json(text, what):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        raise MLInvocationError(f"{what} 가 JSON 이 아닙니다.") from None


def unwrap_api_gateway_response(envelope):
    """v0.3 lambda_handler 의 API Gateway 형식 응답을 풀어 (statusCode, body dict) 를 돌려준다."""
    if not isinstance(envelope, dict) or "statusCode" not in envelope or "body" not in envelope:
        raise MLInvocationError("AI/ML 응답이 API Gateway 형식이 아닙니다.")
    status_code = envelope["statusCode"]
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        raise MLInvocationError("AI/ML 응답의 statusCode 형식이 올바르지 않습니다.")
    raw_body = envelope["body"]
    body = _parse_json(raw_body, "AI/ML 응답 body") if isinstance(raw_body, str) else raw_body
    if not isinstance(body, dict):
        raise MLInvocationError("AI/ML 응답 body 형식이 올바르지 않습니다.")
    return status_code, body


def _error_code_of(body):
    error = body.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    return code if code in KNOWN_ERROR_CODES else "UNKNOWN"


class MLClient:
    """AI/ML 이상 탐지 Lambda 를 호출한다.

    Args:
        client: boto3 Lambda 클라이언트 또는 invoke() 를 가진 가짜 객체.
        config (MLConfig): 호출 설정.
    """

    def __init__(self, client, config):
        if not isinstance(config, MLConfig):
            raise MLConfigError("AI/ML 호출 설정이 올바르지 않습니다.")
        self._client = client
        self._config = config

    def invoke_detection(self, request):
        """요청을 보내고, v0.3 출력으로 검증된 body 를 돌려준다.

        요청은 ml_adapter.build_detection_request() 결과를 넣는다.
        응답의 user_id/date 가 요청과 다르면 MLResponseError 로 거절한다.

        Raises:
            MLRequestError: 요청을 JSON 으로 만들 수 없음
            MLInvocationError / MLErrorResponse / MLResponseError: 호출·응답 오류 (모두 503 계열)
        """
        if not isinstance(request, dict):
            raise MLRequestError("AI/ML 요청은 dict 여야 합니다.")
        try:
            payload = json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            raise MLRequestError("AI/ML 요청을 JSON 으로 만들 수 없습니다.") from None

        try:
            response = self._client.invoke(
                FunctionName=self._config.function_name,
                InvocationType="RequestResponse",
                Payload=payload,
            )
        except Exception as error:  # noqa: BLE001 - 시간 초과·네트워크·권한 오류 등을 모두 503 으로 감쌈
            raise MLInvocationError("AI/ML Lambda 를 호출하지 못했습니다.") from error

        if not isinstance(response, dict):
            raise MLInvocationError("AI/ML 호출 응답 형식이 올바르지 않습니다.")
        if response.get("StatusCode") != 200:
            raise MLInvocationError("AI/ML 호출이 정상 완료되지 않았습니다.")
        if response.get("FunctionError"):
            # 함수 자체 실패 (미처리 예외, 시간 초과, 메모리 부족 등). 오류 본문은 읽지 않는다.
            raise MLInvocationError("AI/ML Lambda 실행이 실패했습니다.")

        envelope = _parse_json(_read_payload(response.get("Payload")), "AI/ML 응답")
        status_code, body = unwrap_api_gateway_response(envelope)
        if status_code != 200:
            raise MLErrorResponse(status_code, _error_code_of(body))
        if "error" in body:
            raise MLErrorResponse(status_code, _error_code_of(body))

        return validate_detection_result(
            body,
            expected_user_id=request.get("user_id"),
            expected_date=request.get("date"),
        )
