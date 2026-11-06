"""ml_adapter (AI/ML 요청 생성, v0.3 응답 검증) 테스트.

AWS 에 접속하지 않습니다. 걸음 수는 모두 가상의 값이며, 응답 샘플은 tests/ml_samples.py
(origin/ai-ml 의 docs/sample_responses.json 복사본)를 사용합니다.
"""

import os
import sys
import unittest
from datetime import date, timedelta

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.data_source import DataSourceUnavailableError  # noqa: E402
from src.ml_adapter import (  # noqa: E402
    GUIDE_GENERATED,
    GUIDE_MISSING,
    GUIDE_NOT_APPLICABLE,
    MLRequestError,
    MLResponseError,
    TargetNotEligibleError,
    build_detection_request,
    build_history_steps,
    collect_daily_tracked_minutes,
    daily_steps_for_user,
    step_anomaly_dates,
    summarize_detection,
    validate_detection_result,
)
from tests.ml_samples import SAMPLE_NAMES, sample  # noqa: E402

USER_ID = "1000000001"
OTHER_USER_ID = "1000000002"
TARGET = date(2016, 4, 10)


def days_before(target, count, start_value=1000):
    """기준일 직전 count 일의 {date: steps} (값은 오래된 날부터 1000, 1001, ...)."""
    return {target - timedelta(days=count - i): start_value + i for i in range(count)}


def mapped(user_id, day, steps):
    """mappers.map_fitbit_activity_row 결과 형태의 가상 행."""
    return {"userId": user_id, "date": day, "activity": {"totalSteps": steps, "calories": 1}}


# ---------------------------------------------------------------------------
# history_steps
# ---------------------------------------------------------------------------
class BuildHistoryStepsTest(unittest.TestCase):

    def test_excludes_target_and_later_dates(self):
        daily = {
            date(2016, 4, 8): 8000,
            date(2016, 4, 9): 9000,
            TARGET: 3000,                 # 기준일 당일
            date(2016, 4, 11): 9999,      # 기준일 이후
        }
        self.assertEqual(build_history_steps(daily, TARGET), [8000, 9000])

    def test_oldest_first_regardless_of_input_order(self):
        daily = {date(2016, 4, 9): 3, date(2016, 4, 1): 1, date(2016, 4, 5): 2}
        self.assertEqual(build_history_steps(daily, TARGET), [1, 2, 3])

    def test_keeps_most_recent_14(self):
        """20개 기록 중 기준일에 가까운 최근 14개만, 오래된 순으로."""
        daily = days_before(TARGET, 20)            # 1000(가장 오래됨) ~ 1019(전날)
        history = build_history_steps(daily, TARGET)
        self.assertEqual(len(history), 14)
        self.assertEqual(history, list(range(1006, 1020)))

    def test_excludes_zero_steps_before_counting_14(self):
        """0걸음은 제외하고 남은 기록 중 최근 14개를 쓴다. (v0.3 personal_check 와 같은 순서)"""
        daily = days_before(TARGET, 16)            # 1000 ~ 1015
        daily[TARGET - timedelta(days=1)] = 0      # 전날 0걸음
        daily[TARGET - timedelta(days=2)] = 0
        history = build_history_steps(daily, TARGET)
        self.assertNotIn(0, history)
        self.assertEqual(history, list(range(1000, 1014)))

    def test_missing_dates_are_not_filled(self):
        daily = {date(2016, 4, 1): 5000, date(2016, 4, 8): 7000}   # 사이 날짜 없음
        self.assertEqual(build_history_steps(daily, TARGET), [5000, 7000])

    def test_fewer_than_five_records_are_kept_as_is(self):
        """5개 미만이어도 그대로 돌려준다. 데이터 부족 판정은 AI/ML 이 한다."""
        daily = days_before(TARGET, 3)
        self.assertEqual(build_history_steps(daily, TARGET), [1000, 1001, 1002])
        self.assertEqual(build_history_steps({}, TARGET), [])

    def test_returns_int_list_and_accepts_iso_target(self):
        history = build_history_steps(days_before(TARGET, 5), "2016-04-10")
        self.assertTrue(all(type(value) is int for value in history))

    def test_invalid_inputs(self):
        with self.assertRaises(MLRequestError):
            build_history_steps({}, "2016-4-10")
        with self.assertRaises(MLRequestError):
            build_history_steps({}, "2016-02-30")
        with self.assertRaises(MLRequestError):
            build_history_steps([], TARGET)
        with self.assertRaises(MLRequestError):
            build_history_steps({"2016-04-01": 100}, TARGET)        # 키가 date 가 아님
        with self.assertRaises(MLRequestError):
            build_history_steps({date(2016, 4, 1): "100"}, TARGET)  # 값이 정수가 아님
        with self.assertRaises(MLRequestError):
            build_history_steps({date(2016, 4, 1): True}, TARGET)


class DailyStepsForUserTest(unittest.TestCase):

    def test_only_requested_user_rows(self):
        rows = [
            mapped(USER_ID, "2016-04-08", 8000),
            mapped(OTHER_USER_ID, "2016-04-08", 99999),
            mapped(OTHER_USER_ID, "2016-04-09", 99999),
        ]
        self.assertEqual(daily_steps_for_user(rows, USER_ID), {date(2016, 4, 8): 8000})

    def test_duplicate_dates_follow_dashboard_policy(self):
        """같은 값의 중복은 하나, 서로 다른 값이면 그 날짜 제외. (dashboard_service 정책 재사용)"""
        rows = [
            mapped(USER_ID, "2016-04-07", 7000), mapped(USER_ID, "2016-04-07", 7000),
            mapped(USER_ID, "2016-04-08", 8000), mapped(USER_ID, "2016-04-08", 8100),
        ]
        daily = daily_steps_for_user(rows, USER_ID)
        self.assertEqual(daily, {date(2016, 4, 7): 7000})
        self.assertEqual(build_history_steps(daily, TARGET), [7000])

    def test_invalid_dates_and_values_are_excluded(self):
        rows = [
            mapped(USER_ID, "2016-04-07", None),
            mapped(USER_ID, None, 5000),
            mapped(USER_ID, "2016-04-08", 8000),
        ]
        self.assertEqual(daily_steps_for_user(rows, USER_ID), {date(2016, 4, 8): 8000})

    def test_invalid_user_id(self):
        for user_id in ("u-1001", "", None, "1' OR '1'='1"):
            with self.assertRaises(MLRequestError):
                daily_steps_for_user([], user_id)


# ---------------------------------------------------------------------------
# 요청 JSON
# ---------------------------------------------------------------------------
class BuildDetectionRequestTest(unittest.TestCase):

    # 아래 3개 테스트는 AI/ML 담당자 요청(history_steps 미전달)에 맞춰 기대값을 바꿨다.
    # (이전: 요청에 history_steps 포함 → 현재: 미포함, 과거 기록은 AI/ML 이 Athena 에서 직접 조회)

    def test_request_has_required_fields_and_notify_false(self):
        """요청은 user_id, date, metrics 와 최상위 notify(기본 False)를 담는다 (v0.5)."""
        daily = days_before(TARGET, 6)
        daily[TARGET] = 2100
        request = build_detection_request(USER_ID, TARGET, daily)
        self.assertEqual(request, {
            "user_id": USER_ID,
            "date": "2016-04-10",
            "metrics": {"steps": 2100},
            "notify": False,
        })

    def test_no_other_metrics_or_history_are_created(self):
        """수면·HRV·스트레스 등 없는 지표, context, history_steps 를 넣지 않는다. notify 는 최상위에만."""
        daily = {TARGET: 5000}
        request = build_detection_request(USER_ID, "2016-04-10", daily)
        self.assertEqual(set(request.keys()), {"user_id", "date", "metrics", "notify"})
        self.assertEqual(request["metrics"], {"steps": 5000})
        self.assertIs(request["notify"], False)

    def test_notify_defaults_false_and_accepts_true(self):
        """notify 기본은 False. True 를 명시하면 그대로 전달하고, 재시도해도 값이 유지된다."""
        daily = {TARGET: 5000}
        self.assertIs(build_detection_request(USER_ID, TARGET, daily)["notify"], False)
        r_true = build_detection_request(USER_ID, TARGET, daily, notify=True)
        self.assertIs(r_true["notify"], True)
        # 같은 인자로 다시 만들어도 값이 그대로 유지됨
        self.assertEqual(build_detection_request(USER_ID, TARGET, daily, notify=True), r_true)
        # notify 는 불리언이어야 한다
        with self.assertRaises(MLRequestError):
            build_detection_request(USER_ID, TARGET, daily, notify="false")

    def test_history_is_never_sent_even_with_many_past_records(self):
        """과거 기록이 충분히 있어도 요청에는 기준일 걸음 수만 들어간다."""
        daily = days_before(TARGET, 20)
        daily[TARGET] = 1234
        request = build_detection_request(USER_ID, TARGET, daily)
        self.assertNotIn("history_steps", request)
        self.assertEqual(request["metrics"], {"steps": 1234})
        # 요청 어디에도 과거 기록 값이 들어가지 않는다.
        self.assertNotIn("1019", str(request))

    def test_missing_target_steps_is_not_eligible(self):
        with self.assertRaises(TargetNotEligibleError) as context:
            build_detection_request(USER_ID, TARGET, days_before(TARGET, 7))
        self.assertEqual(context.exception.reason, "missing_steps")

    def test_zero_step_target_is_not_eligible(self):
        """0걸음 기준일은 정상적인 이상 탐지 대상으로 보내지 않는다. (최종 정책 미확정)"""
        daily = days_before(TARGET, 7)
        daily[TARGET] = 0
        with self.assertRaises(TargetNotEligibleError) as context:
            build_detection_request(USER_ID, TARGET, daily)
        self.assertEqual(context.exception.reason, "zero_steps")

    def test_excluded_dates(self):
        """제외 날짜는 호출하는 쪽이 지정한다. 기본값은 비어 있다(불완전한 날 정책 미확정)."""
        daily = {date(2016, 4, 12): 1019}
        request = build_detection_request(USER_ID, "2016-04-12", daily)   # 기본값: 제외 없음
        self.assertEqual(request["date"], "2016-04-12")
        with self.assertRaises(TargetNotEligibleError) as context:
            build_detection_request(USER_ID, "2016-04-12", daily, excluded_dates=["2016-04-12"])
        self.assertEqual(context.exception.reason, "excluded_date")

    def test_invalid_user_and_date(self):
        daily = {TARGET: 5000}
        for user_id in ("demo-user-1", "", None, 1000000001, "1" * 21):
            with self.assertRaises(MLRequestError, msg=repr(user_id)):
                build_detection_request(user_id, TARGET, daily)
        for target in ("2016-4-10", "20160410", "", None, "2016-02-30"):
            with self.assertRaises(MLRequestError, msg=repr(target)):
                build_detection_request(USER_ID, target, daily)
        with self.assertRaises(MLRequestError):
            build_detection_request(USER_ID, TARGET, daily, excluded_dates=["bad"])

    def test_invalid_target_steps_value(self):
        for value in (-1, "5000", 12.5, True):
            with self.assertRaises(MLRequestError, msg=repr(value)):
                build_detection_request(USER_ID, TARGET, {TARGET: value})

    def test_error_messages_do_not_contain_user_input(self):
        with self.assertRaises(MLRequestError) as context:
            build_detection_request("1' OR '1'='1", TARGET, {})
        self.assertNotIn("OR", str(context.exception))


# ---------------------------------------------------------------------------
# tracked_minutes (AI/ML v0.4)
# ---------------------------------------------------------------------------
def item_with_minutes(day, steps, very=None, fairly=None, lightly=None, sedentary=None):
    """collect_daily_tracked_minutes 입력용 가상 활동 항목. (health_service items 형태)"""
    activity = {"totalSteps": steps}
    for key, value in (("veryActiveMinutes", very), ("fairlyActiveMinutes", fairly),
                       ("lightlyActiveMinutes", lightly), ("sedentaryMinutes", sedentary)):
        if value is not None:
            activity[key] = value
    if None not in (very, fairly, lightly, sedentary):
        activity["trackedMinutes"] = very + fairly + lightly + sedentary
    return {"date": day, "activity": activity}


class CollectDailyTrackedMinutesTest(unittest.TestCase):

    def test_sums_when_all_four_present(self):
        items = [item_with_minutes("2016-04-10", 2100, 20, 30, 200, 600)]
        self.assertEqual(collect_daily_tracked_minutes(items), {TARGET: 850})

    def test_valid_zero_is_summed(self):
        items = [item_with_minutes("2016-04-10", 2100, 0, 30, 200, 600)]
        self.assertEqual(collect_daily_tracked_minutes(items), {TARGET: 830})

    def test_missing_minute_excludes_date(self):
        """네 값 중 하나라도 없으면(trackedMinutes 없음) 그 날짜는 결과에 없다."""
        items = [item_with_minutes("2016-04-10", 2100, 20, 30, 200)]  # sedentary 없음
        self.assertEqual(collect_daily_tracked_minutes(items), {})

    def test_conflicting_values_exclude_date(self):
        items = [
            item_with_minutes("2016-04-10", 2100, 20, 30, 200, 600),  # 850
            item_with_minutes("2016-04-10", 2100, 20, 30, 200, 700),  # 870
        ]
        self.assertEqual(collect_daily_tracked_minutes(items), {})

    def test_invalid_items(self):
        with self.assertRaises(ValueError):
            collect_daily_tracked_minutes("not-a-list")
        with self.assertRaises(ValueError):
            collect_daily_tracked_minutes(["not-a-dict"])


class BuildDetectionRequestTrackedMinutesTest(unittest.TestCase):

    def test_tracked_minutes_added_when_available(self):
        daily = {TARGET: 2100}
        request = build_detection_request(USER_ID, TARGET, daily,
                                          daily_tracked_minutes={TARGET: 850})
        self.assertEqual(request["metrics"], {"steps": 2100, "tracked_minutes": 850})

    def test_tracked_minutes_omitted_when_target_missing(self):
        """기준일에 tracked_minutes 가 없으면 생략한다(0 으로 채우지 않음)."""
        daily = {TARGET: 2100}
        request = build_detection_request(USER_ID, TARGET, daily,
                                          daily_tracked_minutes={date(2016, 4, 9): 850})
        self.assertEqual(request["metrics"], {"steps": 2100})

    def test_tracked_minutes_omitted_when_none(self):
        request = build_detection_request(USER_ID, TARGET, {TARGET: 2100},
                                          daily_tracked_minutes=None)
        self.assertEqual(request["metrics"], {"steps": 2100})

    def test_valid_zero_tracked_minutes_is_sent(self):
        request = build_detection_request(USER_ID, TARGET, {TARGET: 2100},
                                          daily_tracked_minutes={TARGET: 0})
        self.assertEqual(request["metrics"], {"steps": 2100, "tracked_minutes": 0})

    def test_799_and_800_are_passed_through_untouched(self):
        """백엔드는 800 분 기준 판정을 하지 않는다. 799/800 모두 그대로 전달한다."""
        for minutes in (799, 800):
            request = build_detection_request(USER_ID, TARGET, {TARGET: 2100},
                                              daily_tracked_minutes={TARGET: minutes})
            self.assertEqual(request["metrics"]["tracked_minutes"], minutes)

    def test_invalid_tracked_minutes_map_type(self):
        with self.assertRaises(MLRequestError):
            build_detection_request(USER_ID, TARGET, {TARGET: 2100},
                                    daily_tracked_minutes=[("x", 1)])

    def test_tracked_minutes_from_collector_end_to_end(self):
        """mappers → collect_daily_tracked_minutes → build_detection_request 흐름."""
        items = [item_with_minutes("2016-04-10", 2100, 10, 10, 100, 679)]  # 합계 799
        request = build_detection_request(
            USER_ID, TARGET, {TARGET: 2100},
            daily_tracked_minutes=collect_daily_tracked_minutes(items),
        )
        self.assertEqual(request["metrics"], {"steps": 2100, "tracked_minutes": 799})


# ---------------------------------------------------------------------------
# 응답 검증 (v0.3)
# ---------------------------------------------------------------------------
class ValidateSamplesTest(unittest.TestCase):

    def test_all_four_samples_are_valid(self):
        for name in SAMPLE_NAMES:
            case = sample(name)
            result = validate_detection_result(
                case["response"],
                expected_user_id=case["request"]["user_id"],
                expected_date=case["request"]["date"],
            )
            self.assertIs(result, case["response"], name)

    def test_response_error_is_503_family(self):
        self.assertTrue(issubclass(MLResponseError, DataSourceUnavailableError))


class ValidateViolationsTest(unittest.TestCase):

    def assert_invalid(self, body, **expected):
        with self.assertRaises(MLResponseError):
            validate_detection_result(body, **expected)

    def anomaly_body(self):
        return sample("activity_drop_high")["response"]

    def test_not_a_dict_or_missing_fields(self):
        self.assert_invalid([])
        self.assert_invalid("text")
        for key in ("user_id", "date", "status", "overall_severity", "anomalies",
                    "anomaly_score", "guide", "model_version"):
            body = self.anomaly_body()
            del body[key]
            self.assert_invalid(body)

    def test_value_sets(self):
        for key, value in (("status", "warning"), ("overall_severity", "danger"),
                           ("anomalies", {}), ("anomaly_score", "0.7"), ("model_version", "")):
            body = self.anomaly_body()
            body[key] = value
            self.assert_invalid(body)

    def test_anomaly_item_fields(self):
        mutations = [
            lambda a: a.pop("type"),
            lambda a: a.update(basis="group"),
            lambda a: a.update(severity="danger"),
            lambda a: a.update(severity="none"),
            lambda a: a.update(value="2100"),
            lambda a: a.update(z_score=True),
            lambda a: a.pop("baseline_mean"),       # personal 필수 필드
            lambda a: a.update(drop_pct=None),
            lambda a: a.update(metric=""),
        ]
        for mutate in mutations:
            body = self.anomaly_body()
            mutate(body["anomalies"][0])
            self.assert_invalid(body)

    def test_population_anomaly_requires_population_mean(self):
        body = sample("sleep_stress_hrv_high")["response"]
        del body["anomalies"][1]["population_mean"]
        self.assert_invalid(body)

    def test_guide_fields(self):
        mutations = [
            lambda g: g.update(text=""),
            lambda g: g.update(lines="한 줄"),
            lambda g: g.update(lines=[]),
            lambda g: g.update(lines=["1", "2", "3", "4"]),
            lambda g: g.update(lines=["1", "", "3"]),
            lambda g: g.update(lines=["1", 2, "3"]),
            lambda g: g.update(warnings=None),
            lambda g: g.update(warnings=[1]),
            lambda g: g.pop("warnings"),
            lambda g: g.update(model_id=""),
            lambda g: g.update(generated_at="2026-10-30T14:40:09"),    # 시간대 없음
            lambda g: g.update(generated_at="어제"),
        ]
        for mutate in mutations:
            body = self.anomaly_body()
            mutate(body["guide"])
            self.assert_invalid(body)

    def test_guide_with_warnings_and_fewer_lines_is_accepted(self):
        """규칙 위반이 남아도 warnings 와 함께 오면 유효하다(명세 8번: 표시는 가능)."""
        body = self.anomaly_body()
        body["guide"]["lines"] = body["guide"]["lines"][:2]
        body["guide"]["warnings"] = ["줄 수 2"]
        validate_detection_result(body)

    def test_optional_top_level_alert_sent_boolean_is_accepted(self):
        """alert_sent(v0.4)는 응답 최상위 선택 필드. true/false 둘 다 유효하고, 없어도 유효하다."""
        for value in (True, False):
            body = self.anomaly_body()
            body["alert_sent"] = value
            validate_detection_result(body)
        body = self.anomaly_body()
        self.assertNotIn("alert_sent", body)  # 커밋된 샘플에는 최상위 필드 없음
        validate_detection_result(body)

    def test_top_level_alert_sent_allowed_when_guide_null(self):
        """guide 가 없어도(이상 아님) 최상위 alert_sent 는 올 수 있다."""
        body = sample("normal")["response"]
        body["alert_sent"] = False
        validate_detection_result(body)

    def test_non_boolean_top_level_alert_sent_is_rejected(self):
        for value in ("true", 1, None):
            body = self.anomaly_body()
            body["alert_sent"] = value
            self.assert_invalid(body)

    def test_optional_top_level_alert_reason_is_accepted(self):
        """alert_reason(v0.5)은 응답 최상위 선택 문자열. 값 집합 내/외 문자열 모두 유효, 없어도 유효."""
        for value in ("sent", "notify_false", "below_threshold", "duplicate", "disabled",
                      "failed", "some_future_reason"):
            body = self.anomaly_body()
            body["alert_reason"] = value
            validate_detection_result(body)
        body = self.anomaly_body()
        self.assertNotIn("alert_reason", body)  # v0.4 처럼 필드 없는 경우
        validate_detection_result(body)

    def test_alert_reason_allowed_when_guide_null(self):
        """guide 가 없어도(이상 아님) 최상위 alert_reason 은 올 수 있다."""
        body = sample("normal")["response"]
        body["alert_sent"] = False
        body["alert_reason"] = "below_threshold"
        validate_detection_result(body)

    def test_non_string_alert_reason_is_rejected(self):
        for value in (1, True, ["sent"], {}):
            body = self.anomaly_body()
            body["alert_reason"] = value
            self.assert_invalid(body)

    def test_consistency_rules(self):
        body = self.anomaly_body()
        body["anomalies"] = []
        self.assert_invalid(body)                       # anomaly 인데 비어 있음

        body = sample("normal")["response"]
        body["anomalies"] = self.anomaly_body()["anomalies"]
        self.assert_invalid(body)                       # normal 인데 anomalies 있음

        body = sample("normal")["response"]
        body["overall_severity"] = "low"
        self.assert_invalid(body)                       # normal 인데 overall 이 none 아님

        body = sample("insufficient_data")["response"]
        body["guide"] = self.anomaly_body()["guide"]
        self.assert_invalid(body)                       # anomaly 가 아닌데 guide 있음

        body = self.anomaly_body()
        body["overall_severity"] = "medium"
        self.assert_invalid(body)                       # overall 이 최고 심각도(high)보다 낮음

    def test_overall_may_be_raised_one_level(self):
        """v0.3 은 지표 2개 이상이면 overall 을 한 단계 올린다 (medium + low×2 → high)."""
        body = sample("sleep_stress_hrv_high")["response"]
        self.assertEqual(body["overall_severity"], "high")
        validate_detection_result(body)

    def test_user_and_date_must_match_request(self):
        body = self.anomaly_body()
        self.assert_invalid(body, expected_user_id="demo-user-9")
        self.assert_invalid(body, expected_date="2026-10-31")

    def test_error_message_does_not_contain_body(self):
        body = self.anomaly_body()
        body["status"] = "secret-status-value"
        with self.assertRaises(MLResponseError) as context:
            validate_detection_result(body)
        self.assertNotIn("secret-status-value", str(context.exception))
        self.assertNotIn("12,271", str(context.exception))


# ---------------------------------------------------------------------------
# 결과 요약 (guide=null 구분)
# ---------------------------------------------------------------------------
class SummarizeDetectionTest(unittest.TestCase):

    def summarize(self, name, mutate=None):
        body = sample(name)["response"]
        if mutate:
            mutate(body)
        return summarize_detection(validate_detection_result(body))

    def test_anomaly_with_guide(self):
        summary = self.summarize("activity_drop_high")
        self.assertEqual(summary, {
            "date": "2026-10-30", "status": "anomaly", "overallSeverity": "high",
            "stepAnomaly": True, "guideState": GUIDE_GENERATED, "guideWarningCount": 0,
            "alertSent": None, "alertReason": None,
        })

    def test_alert_sent_true_false_none_are_distinguished(self):
        """최상위 alert_sent true/false/필드 없음을 각각 True/False/None 으로 구분한다."""
        self.assertIsNone(self.summarize("activity_drop_high")["alertSent"])  # 필드 없음
        true_summary = self.summarize(
            "activity_drop_high", lambda b: b.update(alert_sent=True))
        self.assertIs(true_summary["alertSent"], True)
        false_summary = self.summarize(
            "activity_drop_high", lambda b: b.update(alert_sent=False))
        self.assertIs(false_summary["alertSent"], False)

    def test_alert_sent_preserved_when_guide_null(self):
        """guide 가 null(이상 아님·생성 실패)이어도 최상위 alert_sent 값이 보존된다."""
        # 이상인데 guide 생성 실패 + 알림 발송됨
        missing = self.summarize(
            "activity_drop_high", lambda b: b.update(guide=None, alert_sent=True))
        self.assertEqual(missing["guideState"], GUIDE_MISSING)
        self.assertIs(missing["alertSent"], True)
        # 정상(guide 없음) + 알림 미발송
        normal = self.summarize("normal", lambda b: b.update(alert_sent=False))
        self.assertEqual(normal["guideState"], GUIDE_NOT_APPLICABLE)
        self.assertIs(normal["alertSent"], False)

    def test_alert_reason_is_surfaced_and_preserved(self):
        """alert_reason(v0.5)을 alertReason 으로 그대로 전달한다. 필드 없으면 None, guide null 이어도 보존."""
        self.assertIsNone(self.summarize("activity_drop_high")["alertReason"])  # 필드 없음
        sent = self.summarize("activity_drop_high", lambda b: b.update(alert_sent=True, alert_reason="sent"))
        self.assertEqual(sent["alertReason"], "sent")
        # guide 없음 + 미발송 사유 보존
        normal = self.summarize("normal", lambda b: b.update(alert_sent=False, alert_reason="below_threshold"))
        self.assertIs(normal["alertSent"], False)
        self.assertEqual(normal["alertReason"], "below_threshold")

    def test_anomaly_without_guide_is_distinguished(self):
        """이상이 있는데 guide=null 이면 'missing' (이상 없음의 'not_applicable' 과 구분)."""
        summary = self.summarize("activity_drop_high", lambda b: b.update(guide=None))
        self.assertEqual(summary["status"], "anomaly")
        self.assertEqual(summary["guideState"], GUIDE_MISSING)

    def test_normal_and_insufficient_data(self):
        normal = self.summarize("normal")
        self.assertEqual((normal["status"], normal["guideState"], normal["stepAnomaly"]),
                         ("normal", GUIDE_NOT_APPLICABLE, False))
        insufficient = self.summarize("insufficient_data")
        self.assertEqual((insufficient["status"], insufficient["guideState"]),
                         ("insufficient_data", GUIDE_NOT_APPLICABLE))

    def test_population_only_anomaly_is_not_step_anomaly(self):
        self.assertFalse(self.summarize("sleep_stress_hrv_high")["stepAnomaly"])

    def test_warning_count(self):
        summary = self.summarize(
            "activity_drop_high", lambda b: b["guide"].update(warnings=["줄 수 2", "이모지"])
        )
        self.assertEqual(summary["guideWarningCount"], 2)


class StepAnomalyDatesTest(unittest.TestCase):

    def test_collects_only_step_anomaly_dates(self):
        drop = sample("activity_drop_high")["response"]
        drop["date"] = "2016-04-08"
        population = sample("sleep_stress_hrv_high")["response"]
        population["date"] = "2016-04-09"
        normal = sample("normal")["response"]
        normal["date"] = "2016-04-10"
        dates = step_anomaly_dates([validate_detection_result(b) for b in (drop, population, normal)])
        self.assertEqual(dates, {date(2016, 4, 8)})

    def test_invalid_date_in_result(self):
        drop = sample("activity_drop_high")["response"]
        drop["date"] = "2016/04/08"
        with self.assertRaises(MLResponseError):
            step_anomaly_dates([drop])

    def test_empty(self):
        self.assertEqual(step_anomaly_dates([]), set())


if __name__ == "__main__":
    unittest.main()
