"""dashboard_service (걸음 수 주간 통계, 순수 함수) 테스트.

날짜는 실제 Fitbit 데이터 기간(2016년)과 같은 구간을 쓰지만, 값은 모두 가상입니다.
참고: 2016-04-04 는 월요일, 2016-04-10 은 일요일입니다.
"""

import copy
import os
import sys
import unittest
from datetime import date

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.dashboard_service import (  # noqa: E402
    build_steps_summary_card,
    build_steps_timeseries,
    collect_daily_steps,
    compute_weekly_steps,
    round_half_up,
)


def item(day, steps, **activity):
    return {"date": day, "activity": {"totalSteps": steps, **activity}}


# 기준 주: 2016-04-04(월) ~ 2016-04-10(일). 마지막 데이터는 2016-04-09(토).
THIS_WEEK = [
    item("2016-04-04", 1000),
    item("2016-04-05", 2000),
    item("2016-04-07", 3000),   # 04-06(수) 데이터 없음
    item("2016-04-09", 6000),   # 04-08(금), 04-10(일) 데이터 없음
]
# 지난주: 2016-03-28(월) ~ 2016-04-03(일)
LAST_WEEK = [
    item("2016-03-28", 2000),
    item("2016-04-03", 2000),
]


class RoundHalfUpTest(unittest.TestCase):

    def test_rounds_half_away_from_zero(self):
        self.assertEqual(round_half_up(2.5), 3)
        self.assertEqual(round_half_up(3.5), 4)
        self.assertEqual(round_half_up(-2.5), -3)
        self.assertEqual(round_half_up(2.4), 2)
        self.assertEqual(round_half_up(0), 0)


class CollectDailyStepsTest(unittest.TestCase):

    def test_excludes_unusable_values_and_dates(self):
        items = [
            item("2016-04-04", 100),
            item("2016-04-05", None),
            item("2016-04-06", True),
            item("2016-04-07", -5),
            item("2016-04-08", "300"),
            item("2016-04-09", 12.5),
            item("bad-date", 100),
            item("2016-4-9", 100),
            item("2016-02-30", 100),
            {"date": "2016-04-10"},                       # activity 없음
            {"date": "2016-04-10", "activity": "bad"},     # activity 형식 오류
        ]
        self.assertEqual(collect_daily_steps(items), {date(2016, 4, 4): 100})

    def test_zero_steps_is_real_value(self):
        """기록된 0걸음은 실제 값이므로 포함한다."""
        self.assertEqual(collect_daily_steps([item("2016-04-04", 0)]), {date(2016, 4, 4): 0})

    def test_duplicate_dates(self):
        """같은 값의 중복은 하나로 보고, 값이 다르면 그 날짜를 제외한다."""
        items = [
            item("2016-04-04", 100), item("2016-04-04", 100),
            item("2016-04-05", 100), item("2016-04-05", 200),
        ]
        self.assertEqual(collect_daily_steps(items), {date(2016, 4, 4): 100})

    def test_invalid_input_raises(self):
        with self.assertRaises(ValueError):
            collect_daily_steps("not-a-list")
        with self.assertRaises(ValueError):
            collect_daily_steps(["not-a-dict"])


class ComputeWeeklyStepsTest(unittest.TestCase):

    def test_reference_week_is_week_of_latest_date(self):
        """오늘 날짜가 아니라 데이터의 가장 최근 날짜가 속한 주(월~일)를 기준으로 한다."""
        stats = compute_weekly_steps(THIS_WEEK + LAST_WEEK)
        self.assertEqual(stats["weekStart"], date(2016, 4, 4))
        self.assertEqual(stats["weekEnd"], date(2016, 4, 10))

    def test_latest_date_ignores_rows_without_steps(self):
        """걸음 수가 없는 행의 날짜는 '가장 최근 날짜'로 쓰지 않는다."""
        stats = compute_weekly_steps(THIS_WEEK + [item("2016-04-20", None)])
        self.assertEqual(stats["weekStart"], date(2016, 4, 4))

    def test_average_excludes_missing_days(self):
        """빠진 날을 0걸음으로 보지 않는다. (1000+2000+3000+6000)/4 = 3000"""
        stats = compute_weekly_steps(THIS_WEEK)
        self.assertEqual(stats["average"], 3000)
        self.assertEqual(len(stats["days"]), 4)

    def test_delta_against_previous_week(self):
        """(3000 - 2000) / 2000 × 100 = 50"""
        stats = compute_weekly_steps(THIS_WEEK + LAST_WEEK)
        self.assertEqual(stats["previousAverage"], 2000)
        self.assertEqual(stats["previousDayCount"], 2)
        self.assertEqual(stats["delta"], 50)

    def test_negative_delta_and_rounding(self):
        """(1000 - 3000) / 3000 × 100 = -66.67 → -67"""
        stats = compute_weekly_steps([item("2016-04-04", 1000), item("2016-03-28", 3000)])
        self.assertEqual(stats["delta"], -67)

    def test_no_previous_week_gives_none_not_zero(self):
        stats = compute_weekly_steps(THIS_WEEK)
        self.assertIsNone(stats["previousAverage"])
        self.assertIsNone(stats["delta"])

    def test_previous_week_zero_average_gives_none(self):
        stats = compute_weekly_steps([item("2016-04-04", 100), item("2016-03-28", 0)])
        self.assertEqual(stats["previousAverage"], 0)
        self.assertIsNone(stats["delta"])

    def test_older_weeks_are_not_used(self):
        """2주 이상 지난 데이터는 지난주 평균에 넣지 않는다."""
        stats = compute_weekly_steps(THIS_WEEK + [item("2016-03-27", 9999)])
        self.assertIsNone(stats["previousAverage"])

    def test_unsorted_input(self):
        shuffled = [THIS_WEEK[3], LAST_WEEK[0], THIS_WEEK[0], THIS_WEEK[2], LAST_WEEK[1], THIS_WEEK[1]]
        self.assertEqual(compute_weekly_steps(shuffled), compute_weekly_steps(THIS_WEEK + LAST_WEEK))

    def test_empty_or_unusable_input_returns_none(self):
        self.assertIsNone(compute_weekly_steps([]))
        self.assertIsNone(compute_weekly_steps([item("2016-04-04", None), item("bad", 100)]))

    def test_input_is_not_modified(self):
        items = THIS_WEEK + LAST_WEEK
        snapshot = copy.deepcopy(items)
        compute_weekly_steps(items)
        self.assertEqual(items, snapshot)


class StepsCardTest(unittest.TestCase):

    def test_card_with_delta(self):
        card = build_steps_summary_card(compute_weekly_steps(THIS_WEEK + LAST_WEEK))
        self.assertEqual(card, {
            "id": "steps", "icon": "👟", "label": "평균 걸음 수",
            "value": "3,000", "unit": "보", "delta": 50,
            "deltaLabel": "지난주 대비 · 2016-04-04 ~ 2016-04-10",
        })

    def test_value_is_rounded_and_formatted(self):
        """평균 7928.5 → "7,929" (표시용 문자열, 천 단위 콤마)"""
        card = build_steps_summary_card(
            compute_weekly_steps([item("2016-04-04", 7928), item("2016-04-05", 7929)])
        )
        self.assertEqual(card["value"], "7,929")
        self.assertIsInstance(card["value"], str)

    def test_card_without_previous_week(self):
        """지난주 데이터가 없으면 delta 를 0 으로 채우지 않고 None, 라벨로 사유를 알린다."""
        card = build_steps_summary_card(compute_weekly_steps(THIS_WEEK))
        self.assertIsNone(card["delta"])
        self.assertEqual(card["deltaLabel"], "지난주 데이터 없음 · 2016-04-04 ~ 2016-04-10")

    def test_card_with_zero_previous_average(self):
        card = build_steps_summary_card(
            compute_weekly_steps([item("2016-04-04", 100), item("2016-03-28", 0)])
        )
        self.assertIsNone(card["delta"])
        self.assertTrue(card["deltaLabel"].startswith("지난주 대비 계산 불가"))

    def test_no_data_gives_no_card(self):
        self.assertIsNone(build_steps_summary_card(None))


class StepsTimeseriesTest(unittest.TestCase):

    def test_monday_to_sunday_order_with_missing_days_omitted(self):
        """빠진 날(수·금·일)은 만들지 않고, 월→일 순서로 정렬한다."""
        series = build_steps_timeseries(compute_weekly_steps(list(reversed(THIS_WEEK))))
        self.assertEqual(series, [
            {"label": "월", "value": 1000, "anomaly": False},
            {"label": "화", "value": 2000, "anomaly": False},
            {"label": "목", "value": 3000, "anomaly": False},
            {"label": "토", "value": 6000, "anomaly": False},
        ])

    def test_only_reference_week_is_included(self):
        series = build_steps_timeseries(compute_weekly_steps(THIS_WEEK + LAST_WEEK))
        self.assertEqual(len(series), 4)

    def test_value_is_number_and_anomaly_is_false(self):
        for point in build_steps_timeseries(compute_weekly_steps(THIS_WEEK)):
            self.assertIsInstance(point["value"], int)
            self.assertNotIsInstance(point["value"], bool)
            self.assertIs(point["anomaly"], False)

    def test_sunday_label(self):
        series = build_steps_timeseries(compute_weekly_steps([item("2016-04-10", 500)]))
        self.assertEqual(series, [{"label": "일", "value": 500, "anomaly": False}])

    def test_no_data_gives_empty_series(self):
        self.assertEqual(build_steps_timeseries(None), [])


class StepsTimeseriesAnomalyDatesTest(unittest.TestCase):
    """이상 날짜 선택 인자 (AI/ML 결과는 아직 연결하지 않음)."""

    def setUp(self):
        self.stats = compute_weekly_steps(THIS_WEEK)   # 04-04(월), 04-05(화), 04-07(목), 04-09(토)

    def flags(self, anomaly_dates=None):
        return [p["anomaly"] for p in build_steps_timeseries(self.stats, anomaly_dates)]

    def test_default_is_unchanged(self):
        self.assertEqual(build_steps_timeseries(self.stats),
                         build_steps_timeseries(self.stats, anomaly_dates=None))
        self.assertEqual(self.flags(), [False, False, False, False])
        self.assertEqual(self.flags([]), [False, False, False, False])

    def test_marks_given_dates(self):
        self.assertEqual(self.flags({date(2016, 4, 7)}), [False, False, True, False])
        self.assertEqual(self.flags(["2016-04-04", "2016-04-09"]), [True, False, False, True])

    def test_dates_outside_week_or_without_data_are_ignored(self):
        """기준 주 밖이거나 데이터가 없는 날(04-06)은 지점을 만들지 않는다."""
        series = build_steps_timeseries(self.stats, ["2016-03-28", "2016-04-06"])
        self.assertEqual(len(series), 4)
        self.assertTrue(all(point["anomaly"] is False for point in series))

    def test_invalid_dates_raise(self):
        for value in ("2016-04-07", ["2016-4-7"], ["bad"], [20160407], 5):
            with self.assertRaises(ValueError, msg=repr(value)):
                build_steps_timeseries(self.stats, value)
        from datetime import datetime
        with self.assertRaises(ValueError):
            build_steps_timeseries(self.stats, [datetime(2016, 4, 7, 9, 0)])


if __name__ == "__main__":
    unittest.main()
