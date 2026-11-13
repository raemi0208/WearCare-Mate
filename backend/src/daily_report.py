"""Validate and format manually entered daily health report values."""

import math
import re

from datetime import date, datetime, timedelta, timezone


REPORT_TIMEZONE = timezone(timedelta(hours=9), "KST")


def report_date(now):
    if now.utcoffset() is None:
        raise ValueError("Report time must include a time zone")
    return now.astimezone(REPORT_TIMEZONE).date()


def validate_schedule(enabled, send_time):
    if type(enabled) is not bool:
        raise ValueError("Invalid report enabled setting")
    if not isinstance(send_time, str) or not re.fullmatch(
        r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", send_time
    ):
        raise ValueError("Invalid report time")


def format_report(record_date, steps, goal, sleep_hours=None):
    if type(record_date) is not date:
        raise ValueError("Invalid report date")
    if type(steps) is not int or not 0 <= steps <= 2**53 - 1:
        raise ValueError("Invalid daily step count")
    if type(goal) is not int or not 1 <= goal <= 2**53 - 1:
        raise ValueError("Invalid step goal")
    if sleep_hours is not None and (
        type(sleep_hours) not in (int, float)
        or not 0 <= sleep_hours <= 24
        or not math.isfinite(sleep_hours)
    ):
        raise ValueError("Invalid sleep duration")

    sleep = "미입력" if sleep_hours is None else f"{sleep_hours:g}시간"
    return (
        f"[WearCare Mate] {record_date.isoformat()} 건강 리포트",
        f"오늘 걸음 수 {steps:,}걸음 / 목표 {goal:,}걸음\n"
        f"목표 달성률 {steps / goal:.1%}\n"
        f"수면 시간 {sleep}\n\n"
        "직접 입력한 기록을 기준으로 집계했습니다.",
    )
