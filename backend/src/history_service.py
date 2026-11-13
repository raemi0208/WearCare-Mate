"""Account-scoped durable demo results and explicit SNS delivery requests.

No TTL: records survive refresh, logout and Lambda restarts. Never accept a
subject, recipient, topic, metrics or message from request bodies. SNS publish
has no automatic retries; an uncertain delivery is retained and never resent.
"""
import base64
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

import boto3
from botocore.config import Config

from src.demo_anomaly import SCENARIOS, run_demo_anomaly


class HistoryError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def principal(event):
    subject = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {}).get("sub")
    if not isinstance(subject, str) or not subject or len(subject) > 256:
        raise HistoryError(401, "authentication_required")
    return hashlib.sha256(subject.encode()).hexdigest()


def enabled():
    return bool(os.environ.get("HISTORY_TABLE"))


def create_client(service, region):
    return boto3.client(service, region_name=region, config=Config(
        connect_timeout=3, read_timeout=8,
        retries={"total_max_attempts": 1 if service == "sns" else 3, "mode": "standard"}))


class HistoryStore:
    def __init__(self, owner, client=None, table=None):
        self.owner = owner
        self.pk = "USER#" + owner
        self.table = table or os.environ.get("HISTORY_TABLE")
        if not self.table:
            raise HistoryError(503, "history_not_configured")
        self.client = client or create_client("dynamodb", os.environ.get("AWS_REGION", "ap-northeast-2"))

    def key(self, event_id):
        if not isinstance(event_id, str) or not re.fullmatch(r"[0-9a-f]{32}", event_id):
            raise HistoryError(400, "invalid_event")
        return {"pk": {"S": self.pk}, "sk": {"S": "EVENT#" + event_id}}

    def get(self, event_id):
        item = self.client.get_item(TableName=self.table, Key=self.key(event_id), ConsistentRead=True).get("Item")
        return json.loads(item["payload"]["S"]) if item else None

    def put(self, event_id, payload):
        self.client.put_item(TableName=self.table,
            Item=dict(self.key(event_id), payload={"S": json.dumps(payload, ensure_ascii=False)}),
            ConditionExpression="attribute_not_exists(pk)")

    def update(self, event_id, payload, notification_status=None):
        args = dict(TableName=self.table, Key=self.key(event_id),
                    UpdateExpression="SET payload = :payload",
                    ExpressionAttributeValues={":payload": {"S": json.dumps(payload, ensure_ascii=False)}},
                    ConditionExpression="attribute_exists(pk)")
        if notification_status is not None:
            args["UpdateExpression"] += ", delivery = :delivery"
            args["ExpressionAttributeValues"][":delivery"] = {"S": notification_status}
        self.client.update_item(**args)

    def claim_delivery(self, event_id, payload):
        self.client.update_item(TableName=self.table, Key=self.key(event_id),
            UpdateExpression="SET delivery = :pending, payload = :payload",
            ConditionExpression="attribute_exists(pk) AND attribute_not_exists(delivery)",
            ExpressionAttributeValues={":pending": {"S": "pending"},
                ":payload": {"S": json.dumps(payload, ensure_ascii=False)}})

    def hide_notification(self, event_id):
        saved = self.get(event_id)
        if not saved or not saved.get("notification"):
            raise HistoryError(404, "notification_not_found")
        # Keep the original delivery receipt and duplicate-send lock intact.
        self.client.update_item(TableName=self.table, Key=self.key(event_id),
            UpdateExpression="SET notificationHidden = :hidden",
            ConditionExpression="attribute_exists(pk)",
            ExpressionAttributeValues={":hidden": {"BOOL": True}})

    def hide_guide(self, event_id):
        saved = self.get(event_id)
        if not saved or saved.get("result", {}).get("aiGuide", {}).get("status") != "generated":
            raise HistoryError(404, "guide_not_found")
        self.client.update_item(TableName=self.table, Key=self.key(event_id),
            UpdateExpression="SET guideHidden = :hidden",
            ConditionExpression="attribute_exists(pk)",
            ExpressionAttributeValues={":hidden": {"BOOL": True}})

    def page(self, cursor=None):
        args = dict(TableName=self.table, KeyConditionExpression="pk = :pk AND begins_with(sk, :prefix)",
            ExpressionAttributeValues={":pk": {"S": self.pk}, ":prefix": {"S": "EVENT#"}},
            ScanIndexForward=False, ConsistentRead=True, Limit=25)
        if cursor:
            try:
                event_id = base64.urlsafe_b64decode(cursor.encode()).decode()
                args["ExclusiveStartKey"] = self.key(event_id)
            except (ValueError, UnicodeError):
                raise HistoryError(400, "invalid_cursor") from None
        response = self.client.query(**args)
        last = response.get("LastEvaluatedKey")
        next_cursor = base64.urlsafe_b64encode(last["sk"]["S"][6:].encode()).decode() if last else None
        guides, notifications = [], []
        for row in response.get("Items", []):
            item = json.loads(row["payload"]["S"])
            result = item.get("result", {})
            guide = result.get("aiGuide", {})
            if guide.get("status") == "generated" and not row.get("guideHidden", {}).get("BOOL"):
                guides.append(dict(id=item["id"], date=item["createdAt"],
                    referenceDate=result.get("referenceDate"), headline=guide.get("headline"),
                    text=guide.get("text"), lines=guide.get("lines", []),
                    tag=("가상 시연 · " if result.get("inputKind") == "virtual" else "실제 기록 · ") + result.get("scenarioLabel", "걸음 수"),
                    inputKind=result.get("inputKind", "real")))
            if item.get("notification") and not row.get("notificationHidden", {}).get("BOOL"):
                notifications.append(item["notification"])
        return dict(guideHistory=guides, notifications=notifications, nextCursor=next_cursor, historyStatus="ok")


def read_history(event, store_factory=HistoryStore):
    owner = principal(event)
    cursor = (event.get("queryStringParameters") or {}).get("cursor")
    if cursor is not None and (not isinstance(cursor, str) or len(cursor) > 100):
        raise HistoryError(400, "invalid_cursor")
    return store_factory(owner).page(cursor)


def attach_history(body, event):
    if not enabled():
        return body
    # Require API Gateway's verified subject, never a body/query user ID.
    owner = principal(event)
    try:
        store = HistoryStore(owner)
        persist_real_guide(store, body.get("aiGuide"))
        body.update(store.page())
    except Exception:
        body["historyStatus"] = "unavailable"
    return body


def persist_real_guide(store, guide):
    if not guide or guide.get("status") != "generated":
        return
    stamp = guide["updatedAt"]
    when = datetime.fromisoformat(stamp)
    digest = hashlib.sha256(json.dumps(guide, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    event_id = f"{int(when.timestamp() * 1000000):016x}" + digest
    saved = dict(id=event_id, createdAt=stamp, state="complete", result=dict(
        inputKind="real", referenceDate=guide["referenceDate"], scenarioLabel="걸음 수", aiGuide=guide))
    try:
        store.put(event_id, saved)
    except store.client.exceptions.ConditionalCheckFailedException:
        pass  # Same generated guide already persisted; reads do not duplicate it.


def attach_guide(guide, event):
    if not enabled():
        return guide
    owner = principal(event)
    try:
        persist_real_guide(HistoryStore(owner), guide)
        guide["persistenceStatus"] = "saved" if guide.get("status") == "generated" else "not_applicable"
    except Exception:
        guide["persistenceStatus"] = "unavailable"
    return guide


def parse_body(event):
    raw = event.get("body") or "{}"
    try:
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw, validate=True).decode()
        if not isinstance(raw, str) or len(raw) > 2048:
            raise ValueError()
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        raise HistoryError(400, "invalid_body") from None
    if not isinstance(body, dict) or set(body) - {"scenario", "action", "eventId"}:
        raise HistoryError(400, "invalid_body")
    return body


def handle_demo(event, store_factory=HistoryStore, runner=run_demo_anomaly, sns_factory=None):
    owner = principal(event)
    body = parse_body(event)
    action = body.get("action", "analyze")
    if not isinstance(action, str) or action not in ("analyze", "send", "hide_notification", "hide_guide"):
        raise HistoryError(400, "invalid_action")
    scenario = body.get("scenario", "steps")
    if not isinstance(scenario, str) or scenario not in SCENARIOS:
        raise HistoryError(400, "invalid_scenario")
    store = store_factory(owner)
    if action == "hide_notification":
        store.hide_notification(body.get("eventId"))
        return dict(statusCode=200, hiddenEventId=body.get("eventId"))
    if action == "hide_guide":
        store.hide_guide(body.get("eventId"))
        return dict(statusCode=200, hiddenEventId=body.get("eventId"))
    if action == "send":
        return send_saved(store, body.get("eventId"), sns_factory)
    if "eventId" in body:
        raise HistoryError(400, "invalid_body")
    # Time prefix keeps chronological query order; suffix prevents collisions.
    now = datetime.now(timezone.utc)
    event_id = f"{int(now.timestamp() * 1000000):016x}" + uuid.uuid4().hex[:16]
    saved = {"id": event_id, "createdAt": now.isoformat(), "state": "pending"}
    store.put(event_id, saved)  # Fail before costly ML invocation if storage is unavailable.
    result = runner(scenario=scenario)
    if result.get("statusCode") != 200:
        saved["state"] = "failed"
        store.update(event_id, saved)
        return result
    saved.update(state="complete", result={k: v for k, v in result.items() if k not in ("statusCode", "request")})
    try:
        store.update(event_id, saved)
    except Exception:
        result.update(persistenceStatus="unavailable", eventId=None)
        return result
    result.update(persistenceStatus="saved", eventId=event_id)
    try:
        result.update(store.page())
    except Exception:
        result["historyStatus"] = "unavailable"
    return result


def send_saved(store, event_id, sns_factory=None):
    topic = os.environ.get("DEMO_SNS_TOPIC_ARN", "")
    if not topic:
        raise HistoryError(503, "sns_not_configured")
    saved = store.get(event_id)
    if not saved or saved.get("state") != "complete":
        raise HistoryError(404, "event_not_found")
    guide = saved["result"].get("aiGuide", {})
    if guide.get("status") != "generated":
        raise HistoryError(409, "guide_not_generated")
    if saved.get("notification"):
        return dict(statusCode=200, notification=saved["notification"], duplicate=True, **store.page())
    stamp = datetime.now(timezone.utc).isoformat()
    notice = dict(id=event_id, title="가상 시연 이메일 · 발송 처리 중", time=stamp,
                  status="pending", inputKind="virtual", scenario=saved["result"].get("scenario"))
    saved["notification"] = notice
    try:
        store.claim_delivery(event_id, saved)
    except store.client.exceptions.ConditionalCheckFailedException:
        latest = store.get(event_id)
        return dict(statusCode=200, notification=latest.get("notification"), duplicate=True, **store.page())
    # Claim is permanent: timeout/crash cannot cause duplicate automatic sends.
    try:
        sns = sns_factory() if sns_factory else create_client("sns", topic.split(":")[3])
        message = ("[가상 이상 시연 · 실제 사용자 기록 아님]\n"
            + "시연 기준일: " + saved["result"]["referenceDate"] + "\n"
            + "시나리오: " + saved["result"]["scenarioLabel"] + "\n\n" + guide["text"])
        response = sns.publish(TopicArn=topic, Subject="WearCare Mate 가상 이상 알림 시연", Message=message)
        notice.update(status="accepted", title="가상 시연 이메일 · SNS 발송 요청 접수", messageId=response["MessageId"])
    except Exception:
        notice.update(status="unknown", title="가상 시연 이메일 · 발송 결과 확인 필요")
    try:
        store.update(event_id, saved, notification_status=notice["status"])
    except Exception:
        # SNS may have accepted it. Never advise resending or report durable success.
        return dict(statusCode=200, notification=notice, persistenceStatus="unavailable")
    return dict(statusCode=200, notification=notice, persistenceStatus="saved", **store.page())
