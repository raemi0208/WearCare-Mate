"""WearCare Mate AI/ML Lambda 핸들러 (스펙 v0.3).

API Gateway(프록시 통합) 또는 직접 호출의 입력(스펙 6번)을 받아 출력(스펙 7번)을 돌려준다.
배포 파일: lambda_handler.py + detector.py (외부 라이브러리 없음, boto3는 Lambda 기본 포함).
환경 변수
  BEDROCK_MODEL_ID  기본값 global.anthropic.claude-haiku-4-5-20251001-v1:0 (서울에서 노트북 호출 확인함). 빈 문자열로 두면 가이드 생략
  BEDROCK_REGION    기본 ap-northeast-2
필요 권한: bedrock:InvokeModel (Lambda 실행 역할). Athena 조회를 붙이면 us-east-2의 athena/glue/s3 읽기 권한이 추가로 필요.
"""
import json
import os

from detector import detect, generate_guide

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "ap-northeast-2")


def load_history_steps(user_id, date):
    """기준일 직전 걸음 수 기록(최대 14개). [미구현] Athena(us-east-2) 조회를 붙일 자리.
    지금은 요청에 history_steps가 없으면 빈 리스트 -> ACTIVITY_DROP은 insufficient_data, 집단 기준 판정은 그대로 동작."""
    return []


def _response(code, body):
    return {"statusCode": code, "headers": {"Content-Type": "application/json; charset=utf-8"},
            "body": json.dumps(body, ensure_ascii=False)}


def _error(code, err_code, message):
    return _response(code, {"error": {"code": err_code, "message": message}})


def lambda_handler(event, context=None):
    try:
        body = event if "metrics" in event else json.loads(event.get("body") or "{}")
    except (TypeError, ValueError):
        return _error(400, "INVALID_INPUT", "body가 JSON이 아님")

    if not body.get("user_id") or not body.get("date") or not isinstance(body.get("metrics"), dict):
        return _error(400, "INVALID_INPUT", "user_id, date, metrics는 필수")
    for k, v in body["metrics"].items():
        if v is not None and not isinstance(v, (int, float)):
            return _error(400, "INVALID_INPUT", f"metrics.{k}는 숫자여야 함")

    try:
        history = body.get("history_steps")
        if history is None:
            history = load_history_steps(body["user_id"], body["date"])
        out = detect(body, history)
    except Exception as e:  # MODEL_ERROR
        print("MODEL_ERROR:", repr(e))
        return _error(500, "MODEL_ERROR", "이상 탐지 중 오류")

    # 스펙: guide는 status가 anomaly일 때만 생성. 실패해도 탐지 결과는 돌려준다 (guide: null)
    if out["status"] == "anomaly" and MODEL_ID:
        out["guide"] = generate_guide(out["anomalies"], MODEL_ID, BEDROCK_REGION, body.get("context"))
    return _response(200, out)
