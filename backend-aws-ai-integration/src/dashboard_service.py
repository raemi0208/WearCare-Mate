"""WearCare Mate 백엔드 - /dashboard 걸음 수 통계 계산 (순수 함수).

입력은 health_service.build_activity_items() 의 결과입니다.
    [{"date": "2016-04-04", "activity": {"totalSteps": 8200, ...}}, ...]

출력은 프론트엔드 API.md 의 필드 이름·타입을 따릅니다.
    - summaryStats[] 의 steps 카드: {id, icon, label, value(str), unit, delta(number), deltaLabel}
    - timeseries.steps[]: {label(요일), value(number), anomaly(bool)}

계산 규칙 (임시 처리 방식 — 프론트엔드 협의 필요 사항은 README/api-spec 참고):
    - 기준 주: 데이터 중 걸음 수가 있는 "가장 최근 날짜"가 속한 주(월~일).
      실제 Fitbit 데이터가 2016년이므로 오늘 날짜를 기준으로 삼지 않는다.
    - 하루 평균: 기준 주에서 걸음 수가 있는 날만 평균낸다.
      데이터가 없는 날을 0걸음으로 보지 않는다. (실제로 기록된 0걸음은 0으로 포함)
    - 지난주 대비: (이번 주 평균 - 지난주 평균) / 지난주 평균 × 100, 정수 반올림.
      지난주 데이터가 없거나 지난주 평균이 0이면 계산하지 않는다(delta=None).
      임의로 0% 라고 표시하지 않는다.
    - 시계열: 기준 주의 월~일 중 데이터가 있는 날만 넣는다. 빠진 날은 만들지 않는다.
      anomaly 는 AI/ML 연동 전이므로 항상 False.
    - 걸음 수로 쓸 수 없는 값(None, bool, 음수, 정수가 아닌 값)과 잘못된 날짜는 제외한다.
    - 같은 날짜에 서로 다른 걸음 수가 있으면 어느 값이 맞는지 알 수 없으므로 그 날짜를 제외한다.
      (같은 값이 중복된 경우는 하나로 본다)
    - 반올림은 0.5 를 0에서 먼 쪽으로 올린다. (Python round 의 짝수 반올림을 쓰지 않음)
"""

from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

WEEKDAY_LABELS = ("월", "화", "수", "목", "금", "토", "일")

STEPS_CARD_ID = "steps"
STEPS_CARD_ICON = "👟"
STEPS_CARD_LABEL = "평균 걸음 수"
STEPS_CARD_UNIT = "보"


def round_half_up(value):
    """0.5 를 0에서 먼 쪽으로 반올림한 정수. 예) 2.5→3, -2.5→-3, 2.4→2"""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _parse_date(value):
    """엄격한 YYYY-MM-DD 문자열이면 date, 아니면 None."""
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _valid_steps(value):
    """걸음 수로 쓸 수 있는 0 이상의 정수면 그 값, 아니면 None."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def collect_daily_steps(items):
    """items 에서 날짜별 걸음 수를 모은다. (입력은 바꾸지 않음)

    Returns:
        dict[date, int]: 유효한 날짜 → 걸음 수. 값이 충돌하는 날짜는 제외된다.

    Raises:
        ValueError: items 가 list/tuple 이 아니거나 항목이 dict 가 아닐 때.
    """
    if not isinstance(items, (list, tuple)):
        raise ValueError("activity items 는 list 형식이어야 합니다.")

    values_by_date = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("activity item 은 dict 형식이어야 합니다.")
        day = _parse_date(item.get("date"))
        activity = item.get("activity")
        steps = _valid_steps(activity.get("totalSteps")) if isinstance(activity, dict) else None
        if day is None or steps is None:
            continue
        values_by_date.setdefault(day, set()).add(steps)

    # 같은 날짜에 값이 하나뿐인 경우만 사용한다.
    return {day: next(iter(values)) for day, values in values_by_date.items() if len(values) == 1}


def week_start_of(day):
    """그 날짜가 속한 주의 월요일."""
    return day - timedelta(days=day.weekday())


def _days_in_week(daily_steps, week_start):
    week_end = week_start + timedelta(days=6)
    return {day: steps for day, steps in daily_steps.items() if week_start <= day <= week_end}


def _average(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def compute_weekly_steps(items):
    """기준 주와 지난주의 걸음 수 통계를 계산한다.

    Returns:
        dict | None: 걸음 수 데이터가 하나도 없으면 None. 있으면
            {
              "weekStart": date, "weekEnd": date,
              "days": {date: steps, ...},        # 기준 주에서 데이터가 있는 날
              "average": float,                  # 기준 주 하루 평균
              "previousAverage": float | None,   # 지난주 하루 평균 (없으면 None)
              "previousDayCount": int,
              "delta": int | None,               # 지난주 대비 % (계산 불가면 None)
            }
    """
    daily_steps = collect_daily_steps(items)
    if not daily_steps:
        return None

    latest = max(daily_steps)
    week_start = week_start_of(latest)
    previous_start = week_start - timedelta(days=7)

    this_week = _days_in_week(daily_steps, week_start)
    previous_week = _days_in_week(daily_steps, previous_start)

    average = _average(this_week.values())
    previous_average = _average(previous_week.values())

    if previous_average is None or previous_average == 0:
        delta = None
    else:
        delta = round_half_up((average - previous_average) / previous_average * 100)

    return {
        "weekStart": week_start,
        "weekEnd": week_start + timedelta(days=6),
        "days": dict(sorted(this_week.items())),
        "average": average,
        "previousAverage": previous_average,
        "previousDayCount": len(previous_week),
        "delta": delta,
    }


def _period_label(stats):
    return f"{stats['weekStart'].isoformat()} ~ {stats['weekEnd'].isoformat()}"


def build_steps_summary_card(stats):
    """summaryStats 의 steps 카드를 만든다. stats 가 None 이면 None.

    ⚠️ delta 가 계산되지 않으면 None(JSON null) 이 된다.
       API.md 의 delta 타입(number)과 다르므로 프론트엔드 확인이 필요하다.
       0 으로 채우면 '변동없음'으로 잘못 보이기 때문에 0 을 넣지 않는다.
    """
    if stats is None:
        return None

    if stats["delta"] is not None:
        delta_label = f"지난주 대비 · {_period_label(stats)}"
    elif stats["previousAverage"] is None:
        delta_label = f"지난주 데이터 없음 · {_period_label(stats)}"
    else:
        delta_label = f"지난주 대비 계산 불가 · {_period_label(stats)}"

    return {
        "id": STEPS_CARD_ID,
        "icon": STEPS_CARD_ICON,
        "label": STEPS_CARD_LABEL,
        "value": f"{round_half_up(stats['average']):,}",
        "unit": STEPS_CARD_UNIT,
        "delta": stats["delta"],
        "deltaLabel": delta_label,
    }


def _normalize_anomaly_dates(anomaly_dates):
    """이상 날짜 목록을 date 집합으로 만든다. None 이면 빈 집합.

    date 객체 또는 엄격한 YYYY-MM-DD 문자열만 허용한다. 그 외 값은 ValueError.
    (잘못된 값을 조용히 무시하면 이상 표시가 누락된 것을 알아챌 수 없기 때문)
    """
    if anomaly_dates is None:
        return set()
    if isinstance(anomaly_dates, (str, bytes)) or not hasattr(anomaly_dates, "__iter__"):
        raise ValueError("anomaly_dates 는 날짜 목록이어야 합니다.")
    normalized = set()
    for value in anomaly_dates:
        if isinstance(value, datetime):
            raise ValueError("anomaly_dates 에는 시간 없는 날짜만 넣어야 합니다.")
        if hasattr(value, "isoformat") and hasattr(value, "weekday"):
            normalized.add(value)
            continue
        parsed = _parse_date(value)
        if parsed is None:
            raise ValueError("anomaly_dates 에 올바르지 않은 날짜가 있습니다.")
        normalized.add(parsed)
    return normalized


def build_steps_timeseries(stats, anomaly_dates=None):
    """기준 주 월~일 중 데이터가 있는 날의 걸음 수 시계열을 만든다. stats 가 None 이면 빈 목록.

    Args:
        stats (dict | None): compute_weekly_steps() 결과.
        anomaly_dates (Iterable[date | str] | None): 걸음 수 이상으로 판정된 날짜.
            None(기본값)이면 모든 지점의 anomaly 가 False 이다. (기존 동작과 동일)
            ⚠️ 실제 AI/ML 결과는 아직 연결하지 않았다. 기준 주 밖의 날짜는 무시된다.
            판정하지 않은 날짜의 False 는 "정상"이 아니라 "이상으로 표시하지 않음"을 뜻한다.
    """
    if stats is None:
        return []
    flagged = _normalize_anomaly_dates(anomaly_dates)
    return [
        {"label": WEEKDAY_LABELS[day.weekday()], "value": steps, "anomaly": day in flagged}
        for day, steps in sorted(stats["days"].items())
    ]
