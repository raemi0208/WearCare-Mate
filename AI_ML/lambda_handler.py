"""WearCare Mate AI/ML Lambda 핸들러 (스펙 v0.3).

API Gateway(프록시 통합) 또는 직접 호출의 입력(스펙 6번)을 받아 출력(스펙 7번)을 돌려준다.
배포 파일: lambda_handler.py + detector.py (외부 라이브러리 없음, boto3는 Lambda 기본 포함).
환경 변수
  BEDROCK_MODEL_ID  기본값 global.anthropic.claude-haiku-4-5-20251001-v1:0 (서울에서 노트북 호출 확인함). 빈 문자열로 두면 가이드 생략
  BEDROCK_REGION    기본 ap-northeast-2
  ATHENA_REGION(us-east-2) ATHENA_DB ATHENA_WORKGROUP ATHENA_OUTPUT ATHENA_TIMEOUT(10초)
  STEPS_TABLE USER_COL DATE_COL STEPS_COL  걸음 수 테이블/컬럼명 (기본 fitbit_activity_table / id / activitydate / totalsteps)
필요 권한(Lambda 실행 역할): bedrock:InvokeModel, 그리고 us-east-2의 athena:StartQueryExecution/GetQueryExecution/GetQueryResults,
  glue:GetDatabase/GetTable/GetPartitions, 데이터 버킷 읽기 + 결과 위치(ATHENA_OUTPUT) 쓰기.
요청에 history_steps가 있으면 Athena를 조회하지 않고 그 값을 쓴다.
"""
import json
import os
import re
import time

from detector import detect, generate_guide

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "ap-northeast-2")
# Athena 조회 설정 (리전은 us-east-2, 서비스별로 따로 지정). 테이블/컬럼은 스키마 확정 후 환경 변수로 수정
ATHENA_REGION = os.environ.get("ATHENA_REGION", "us-east-2")
ATHENA_DB = os.environ.get("ATHENA_DB", "wearcare_mate_db")
ATHENA_WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "")
ATHENA_OUTPUT = os.environ.get("ATHENA_OUTPUT", "s3://wearcare-mate-bucket-2026/athena-results/")
ATHENA_TIMEOUT = float(os.environ.get("ATHENA_TIMEOUT", "10"))
STEPS_TABLE = os.environ.get("STEPS_TABLE", "fitbit_activity_table")
USER_COL = os.environ.get("USER_COL", "id")
DATE_COL = os.environ.get("DATE_COL", "activitydate")
STEPS_COL = os.environ.get("STEPS_COL", "totalsteps")


def load_history_steps(user_id, date):
    """기준일(date) 이전 걸음 수 기록 최대 14개를 Athena(us-east-2)에서 조회해 오래된 순으로 반환.
    실패하거나 결과가 없으면 [] -> ACTIVITY_DROP만 insufficient_data, 나머지 판정은 그대로 동작.
    테이블/컬럼명은 환경 변수로 바꿀 수 있다 (스키마 확정 전 가정값)."""
    if not (isinstance(user_id, (str, int)) and re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", str(user_id))):
        return []
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)[:10]):
        return []
    sql = (f"SELECT {STEPS_COL} FROM {STEPS_TABLE} "
           f"WHERE CAST({USER_COL} AS varchar) = ? AND CAST({DATE_COL} AS date) < CAST(? AS date) "
           f"ORDER BY CAST({DATE_COL} AS date) DESC LIMIT 14")
    try:
        import boto3
        athena = boto3.client("athena", region_name=ATHENA_REGION)
        qid = athena.start_query_execution(
            QueryString=sql,
            ExecutionParameters=[f"'{user_id}'", f"'{str(date)[:10]}'"],
            QueryExecutionContext={"Database": ATHENA_DB},
            ResultConfiguration={"OutputLocation": ATHENA_OUTPUT},
            **({"WorkGroup": ATHENA_WORKGROUP} if ATHENA_WORKGROUP else {}),
        )["QueryExecutionId"]
        deadline = time.time() + ATHENA_TIMEOUT
        while True:
            st = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]["State"]
            if st == "SUCCEEDED":
                break
            if st in ("FAILED", "CANCELLED") or time.time() > deadline:
                print("ATHENA_FAILED:", st)
                return []
            time.sleep(0.5)
        rows = athena.get_query_results(QueryExecutionId=qid)["ResultSet"]["Rows"][1:]  # 첫 행은 헤더
        vals = []
        for r in rows:
            try:
                vals.append(float(r["Data"][0]["VarCharValue"]))
            except (KeyError, ValueError, IndexError):
                continue
        return vals[::-1]  # 오래된 순
    except Exception as e:
        print("ATHENA_ERROR:", repr(e))
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
