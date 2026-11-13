"""Account-owned report settings and scheduled delivery."""

import base64
import hashlib
import json
import os
from datetime import datetime, timezone

from botocore.config import Config
from botocore.exceptions import ClientError
import boto3

from src.daily_report import REPORT_TIMEZONE, format_report, report_date, validate_schedule
from src.history_service import HistoryError, create_client, principal


def _s(value):
    return {"S": value}


def _key(owner):
    return {"pk": _s("USER#" + owner), "sk": _s("DAILY_REPORT")}


def _public(item, day):
    return {
        "enabled": item.get("enabled", {}).get("BOOL", False),
        "time": item.get("sendTime", {}).get("S", "21:00"),
        "record": json.loads(item["record"]["S"]) if item.get("recordDate") == _s(day) else None,
    }


def handle_report(event, method):
    owner = principal(event)
    table = os.environ.get("HISTORY_TABLE")
    if not table or not os.environ.get("REPORT_FROM"):
        raise HistoryError(503, "report_unavailable")
    day = report_date(datetime.now(timezone.utc))
    region = os.environ["AWS_REGION"]
    db = create_client("dynamodb", region)
    args = {"TableName": table, "Key": _key(owner)}
    if method == "GET":
        item = db.get_item(**args, ConsistentRead=True).get("Item", {})
        return _public(item, day.isoformat())

    try:
        raw = event.get("body") or ""
        if len(raw) > 2048:
            raise ValueError()
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw, validate=True)
        body = json.loads(raw)
        if not isinstance(body, dict) or set(body) not in ({"enabled", "time"}, {"record"}):
            raise ValueError()
        if "record" in body:
            record = body["record"]
            if not isinstance(record, dict) or set(record) != {"steps", "goal", "sleep"}:
                raise ValueError()
            format_report(day, record["steps"], record["goal"], record["sleep"])
        else:
            validate_schedule(body["enabled"], body["time"])
    except (ValueError, TypeError):
        raise HistoryError(400, "invalid_report") from None

    if "record" in body:
        expression = "SET recordDate = :day, #record = :record"
        values = {":day": _s(day.isoformat()), ":record": _s(json.dumps(body["record"]))}
        args["ExpressionAttributeNames"] = {"#record": "record"}
    else:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
        username = claims.get("username") or claims.get("cognito:username")
        if body["enabled"] and not _verified_email(region, username, owner):
            raise HistoryError(422, "verified_email_required")
        expression = "SET enabled = :enabled, sendTime = :time"
        values = {":enabled": {"BOOL": body["enabled"]}, ":time": _s(body["time"])}
        if body["enabled"]:
            expression += ", username = :username"
            values[":username"] = _s(username)

    item = db.update_item(**args, UpdateExpression=expression,
                          ExpressionAttributeValues=values, ReturnValues="ALL_NEW")["Attributes"]
    return _public(item, day.isoformat())


def _verified_email(region, username, owner):
    if not username:
        return None
    cognito = create_client("cognito-idp", region)
    try:
        user = cognito.admin_get_user(UserPoolId=os.environ["REPORT_USER_POOL"], Username=username)
    except cognito.exceptions.UserNotFoundException:
        return None
    attrs = {attr["Name"]: attr["Value"] for attr in user["UserAttributes"]}
    subject = attrs.get("sub", "")
    if (user["Enabled"] and attrs.get("email_verified") == "true"
            and hashlib.sha256(subject.encode()).hexdigest() == owner):
        return attrs.get("email")
    return None


def send_due_reports(now=None):
    sender = os.environ.get("REPORT_FROM")
    table = os.environ.get("HISTORY_TABLE")
    if not sender or not table:
        return {"accepted": 0}
    local = (now or datetime.now(timezone.utc)).astimezone(REPORT_TIMEZONE)
    day = local.date()
    minute = local.strftime("%H:%M")
    region = os.environ["AWS_REGION"]
    db = create_client("dynamodb", region)
    ses = boto3.client("sesv2", region_name=region, config=Config(
        connect_timeout=3, read_timeout=8, retries={"total_max_attempts": 1}))
    accepted = failed = 0
    values = {":kind": _s("DAILY_REPORT"), ":on": {"BOOL": True},
              ":day": _s(day.isoformat()), ":time": _s(minute)}
    for page in db.get_paginator("scan").paginate(
        TableName=table,
        FilterExpression="sk = :kind AND enabled = :on AND recordDate = :day AND sendTime = :time",
        ExpressionAttributeValues=values,
    ):
        for item in page.get("Items", []):
            try:
                email = _verified_email(region, item["username"]["S"], item["pk"]["S"][5:])
                if not email:
                    continue
                try:
                    claimed = db.update_item(
                        TableName=table, Key={key: item[key] for key in ("pk", "sk")},
                        UpdateExpression="SET lastAttemptDate = :day",
                        ConditionExpression="enabled = :on AND recordDate = :day AND sendTime = :time "
                        "AND (attribute_not_exists(lastAttemptDate) OR lastAttemptDate < :day)",
                        ExpressionAttributeValues={key: values[key] for key in (":on", ":day", ":time")},
                        ReturnValues="ALL_NEW",
                    )["Attributes"]
                except db.exceptions.ConditionalCheckFailedException:
                    continue
                record = json.loads(claimed["record"]["S"])
                subject, message = format_report(day, record["steps"], record["goal"], record["sleep"])
                ses.send_email(
                    FromEmailAddress=sender, Destination={"ToAddresses": [email]},
                    Content={"Simple": {"Subject": {"Data": subject, "Charset": "UTF-8"},
                                         "Body": {"Text": {"Data": message, "Charset": "UTF-8"}}}},
                )
                accepted += 1
            except ClientError:
                failed += 1
    return {"accepted": accepted, "failed": failed}
