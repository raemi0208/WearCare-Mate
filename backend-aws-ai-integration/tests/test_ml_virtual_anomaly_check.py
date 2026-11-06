"""ml_virtual_anomaly_check (콘솔 전용 가상 이상 검증 도구) 테스트.

AWS 에 접속하지 않습니다. Lambda 클라이언트는 가짜를 주입하고,
AI/ML 응답은 AI/ML lambda_handler 와 같은 API Gateway 형식으로 감쌉니다.
"""

import io
import json
import unittest
from unittest import mock

from src import ml_virtual_anomaly_check as probe

ENV = {"ML_FUNCTION_NAME": "wearcare-mate-ml", "ML_REGION": "ap-northeast-2"}


def anomaly_body(guide="default", warnings=None):
    body = {
        "user_id": "test-user", "date": "2026-10-30",
        "anomalies": [{
            "type": "ACTIVITY_DROP", "basis": "personal", "metric": "steps", "value": 1000,
            "baseline_mean": 10083, "baseline_std": 250, "z_score": -18.17,
            "drop_pct": -90.1, "severity": "high",
        }],
        "anomaly_score": None,
        "guide": {
            "text": "오늘 걸음 수가 평소 10,083걸음보다 1,000걸음으로 크게 줄었어요.\n"
                    "오늘 10분 걷기를 해 보세요.\n증상이 지속되거나 불편하면 전문가와 상담해보세요.",
            "lines": ["오늘 걸음 수가 평소 10,083걸음보다 1,000걸음으로 크게 줄었어요.",
                      "오늘 10분 걷기를 해 보세요.",
                      "증상이 지속되거나 불편하면 전문가와 상담해보세요."],
            "model_id": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
            "warnings": warnings or [],
            "generated_at": "2026-10-30T14:40:09+09:00",
        },
        "model_version": "activity-zscore-v0.2+pop-v0.3",
        "overall_severity": "high", "status": "anomaly",
    }
    if guide is None:
        body["guide"] = None
    return body


def normal_body():
    return {"user_id": "test-user", "date": "2026-10-30", "anomalies": [],
            "anomaly_score": None, "guide": None,
            "model_version": "activity-zscore-v0.2+pop-v0.3",
            "overall_severity": "none", "status": "normal"}


class FakeLambda:
    def __init__(self, status_code=200, body=None, error=None, function_error=None):
        self.status_code, self.body, self.error = status_code, body, error
        self.function_error = function_error
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        envelope = {"statusCode": self.status_code, "headers": {},
                    "body": json.dumps(self.body, ensure_ascii=False)}
        response = {"StatusCode": 200, "Payload": io.BytesIO(json.dumps(envelope).encode())}
        if self.function_error:
            response["FunctionError"] = self.function_error
        return response


def run(fake):
    return probe.run_check(lambda_client_factory=lambda config: fake, environ=ENV)


class VirtualAnomalyCheckTest(unittest.TestCase):

    def test_sends_virtual_request_matching_ml_interface(self):
        fake = FakeLambda(body=anomaly_body())
        run(fake)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0]["FunctionName"], "wearcare-mate-ml")
        self.assertEqual(fake.calls[0]["InvocationType"], "RequestResponse")
        self.assertEqual(json.loads(fake.calls[0]["Payload"].decode("utf-8")), {
            "user_id": "test-user", "date": "2026-10-30", "metrics": {"steps": 1000},
            "history_steps": [10000, 10500, 9800, 10200, 10100, 9900],
            "notify": False,
        })

    def test_pass_uses_existing_screen_conversion(self):
        result = run(FakeLambda(body=anomaly_body()))
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["inputKind"], "virtual")
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["ml"]["overallSeverity"], "high")
        self.assertTrue(result["ml"]["guideGenerated"])
        guide = result["screen"]["aiGuide"]
        expected = probe.guide_for_frontend(anomaly_body())
        self.assertEqual(guide, expected)                       # 기존 변환 결과 그대로
        self.assertEqual(guide["status"], "generated")
        self.assertTrue(guide["model"].startswith("Amazon Bedrock"))
        self.assertNotIn("MOCK", guide["model"])
        self.assertEqual(guide["actions"], ["오늘 10분 걷기를 해 보세요."])
        self.assertEqual(result["screen"]["anomalies"][0]["severity"], "danger")

    def test_warnings_are_reported(self):
        result = run(FakeLambda(body=anomaly_body(warnings=["줄 수 2"])))
        self.assertEqual(result["verdict"], "PASS_WITH_WARNINGS")
        self.assertEqual(result["ml"]["guideWarnings"], ["줄 수 2"])

    def test_missing_guide_is_failure_not_mock(self):
        result = run(FakeLambda(body=anomaly_body(guide=None)))
        self.assertEqual(result["verdict"], "FAIL")
        self.assertFalse(result["checks"]["guideGenerated"])
        self.assertEqual(result["screen"]["aiGuide"]["status"], "missing")
        self.assertNotIn("MOCK", json.dumps(result, ensure_ascii=False))

    def test_normal_result_is_failure(self):
        result = run(FakeLambda(body=normal_body()))
        self.assertEqual(result["verdict"], "FAIL")
        self.assertFalse(result["checks"]["statusIsAnomaly"])

    def test_ml_error_response_is_failure(self):
        fake = FakeLambda(status_code=500, body={"error": {"code": "MODEL_ERROR", "message": "x"}})
        result = run(fake)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["mlErrorCode"], "MODEL_ERROR")
        self.assertNotIn("screen", result)

    def test_invoke_exception_and_function_error_are_failures(self):
        for fake in (FakeLambda(error=TimeoutError("t")),
                     FakeLambda(body=anomaly_body(), function_error="Unhandled")):
            result = run(fake)
            self.assertEqual(result["verdict"], "FAIL")
            self.assertEqual(result["stage"], "invoke_or_validate")

    def test_missing_config_is_failure_without_invoke(self):
        fake = FakeLambda(body=anomaly_body())
        result = probe.run_check(lambda_client_factory=lambda config: fake, environ={})
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["stage"], "config")
        self.assertEqual(fake.calls, [])

    def test_api_gateway_event_is_refused_without_invoke(self):
        with mock.patch.object(probe, "run_check") as run_check:
            response = probe.lambda_handler({"requestContext": {"http": {"method": "GET"}}}, None)
        self.assertEqual(response["verdict"], "REFUSED")
        run_check.assert_not_called()


# ---------------------------------------------------------------------------
# 기록 시간(tracked_minutes) 경계 검증 (AI/ML v0.4)
# ---------------------------------------------------------------------------
class TrackedMinutesRequestTest(unittest.TestCase):
    """요청에 799/800 이 그대로 실리는지(백엔드는 전달만)."""

    def test_builds_request_with_only_tracked_minutes_changed(self):
        for minutes in (probe.TRACKED_MINUTES_BELOW, probe.TRACKED_MINUTES_AT):
            request = probe.build_tracked_minutes_request(minutes)
            self.assertEqual(request["user_id"], probe.VIRTUAL_REQUEST["user_id"])
            self.assertEqual(request["date"], probe.VIRTUAL_REQUEST["date"])
            self.assertEqual(request["history_steps"], probe.VIRTUAL_REQUEST["history_steps"])
            self.assertEqual(request["metrics"], {"steps": 1000, "tracked_minutes": minutes})
            # v0.5: 두 경계 요청 모두 notify=False 를 그대로 싣는다.
            self.assertIs(request["notify"], False)

    def test_does_not_mutate_virtual_request(self):
        probe.build_tracked_minutes_request(799)
        self.assertEqual(probe.VIRTUAL_REQUEST["metrics"], {"steps": 1000})
        self.assertNotIn("tracked_minutes", probe.VIRTUAL_REQUEST["metrics"])

    def test_cases_cover_799_and_800(self):
        values = [c["trackedMinutes"] for c in probe.TRACKED_MINUTES_CASES]
        self.assertEqual(values, [799, 800])


class RequestAwareFakeLambda:
    """tracked_minutes 값에 따라 다른 AI/ML 응답을 돌려주는 가짜.

    실제 v0.5 Lambda 동작을 로컬에서 흉내 낸 것이다. (실제 응답 아님)
    - 799(<800): 걸음 수 판정 건너뜀 → insufficient_data, guide=null
    - 800(>=800): 걸음 수 판정 → anomaly + guide
    - 두 경우 모두 요청 notify=False 라 alert_sent=false, alert_reason="notify_false" 로 흉내 낸다.
      (실제로 799 에서 below_threshold/notify_false 중 어느 쪽이 우선인지는 배포·실제 응답으로 확인)
    """

    def __init__(self):
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        request = json.loads(kwargs["Payload"].decode("utf-8"))
        tracked = request["metrics"].get("tracked_minutes")
        notify = request.get("notify", True)
        body = anomaly_body() if (tracked is not None and tracked >= 800) else insufficient_body()
        # v0.5 최상위 알림 필드. notify=False 면 발송 안 함.
        body["alert_sent"] = False if not notify else body.get("alert_sent", False)
        body["alert_reason"] = "notify_false" if not notify else body.get("alert_reason", "sent")
        envelope = {"statusCode": 200, "headers": {},
                    "body": json.dumps(body, ensure_ascii=False)}
        return {"StatusCode": 200, "Payload": io.BytesIO(json.dumps(envelope).encode())}


def insufficient_body():
    return {"user_id": "test-user", "date": "2026-10-30", "anomalies": [],
            "anomaly_score": None, "guide": None,
            "model_version": "activity-zscore-v0.2+pop-v0.3",
            "overall_severity": "none", "status": "insufficient_data"}


def run_boundary(fake):
    return probe.run_tracked_minutes_boundary_check(
        lambda_client_factory=lambda config: fake, environ=ENV)


class TrackedMinutesBoundaryObserveTest(unittest.TestCase):
    """경계 관찰 러너: 걸음 수 판정 여부만 보고, 가이드/SNS 를 통과 조건으로 삼지 않는다.

    아래 기대 결과는 RequestAwareFakeLambda 로 v0.4 동작을 흉내 낸 로컬 관찰이다.
    실제 판정은 AI/ML 책임이며 실제 v0.4 응답으로 재확인해야 한다.
    """

    def test_two_cases_pass_through_799_and_800_with_notify_false(self):
        fake = RequestAwareFakeLambda()
        result = run_boundary(fake)
        payloads = [json.loads(c["Payload"].decode("utf-8")) for c in fake.calls]
        sent = [p["metrics"]["tracked_minutes"] for p in payloads]
        self.assertEqual(sent, [799, 800])  # 두 값이 그대로 전달됨
        self.assertEqual([p["notify"] for p in payloads], [False, False])  # v0.5 notify=False 전달
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual([c["trackedMinutes"] for c in result["cases"]], [799, 800])
        self.assertEqual([c["notify"] for c in result["cases"]], [False, False])

    def test_both_cases_observe_alert_sent_false(self):
        """두 경계 모두 notify=False 라 alert_sent=false 를 관찰하고, alert_reason(실제 값)을 기록한다."""
        result = run_boundary(RequestAwareFakeLambda())
        for case in result["cases"]:
            self.assertIs(case["alertSent"], False)
            self.assertTrue(case["alertSentMatchesExpectation"])
            self.assertEqual(case["alertReason"], "notify_false")  # 이 fake 가 흉내 낸 값

    def test_observed_step_judgment_matches_expectation(self):
        result = run_boundary(RequestAwareFakeLambda())
        below, at = result["cases"]
        # 799: 걸음 수 판정 건너뜀
        self.assertFalse(below["stepAnomalyJudged"])
        self.assertEqual(below["mlStatus"], "insufficient_data")
        self.assertTrue(below["matchesExpectation"])
        # 800: 걸음 수 판정 대상
        self.assertTrue(at["stepAnomalyJudged"])
        self.assertEqual(at["mlStatus"], "anomaly")
        self.assertTrue(at["matchesExpectation"])

    def test_guide_is_not_a_pass_condition(self):
        """800 경계에서 가이드가 없어도(guide=null) 걸음 수 판정 관찰은 유지된다."""
        class NoGuideAt800(RequestAwareFakeLambda):
            def invoke(self, **kwargs):
                self.calls.append(kwargs)
                request = json.loads(kwargs["Payload"].decode("utf-8"))
                tracked = request["metrics"].get("tracked_minutes")
                body = anomaly_body(guide=None) if (tracked and tracked >= 800) else insufficient_body()
                envelope = {"statusCode": 200, "headers": {},
                            "body": json.dumps(body, ensure_ascii=False)}
                return {"StatusCode": 200, "Payload": io.BytesIO(json.dumps(envelope).encode())}

        result = run_boundary(NoGuideAt800())
        at = result["cases"][1]
        self.assertTrue(at["stepAnomalyJudged"])        # 가이드 없어도 판정은 관찰됨
        self.assertEqual(at["guideState"], "missing")
        self.assertTrue(at["matchesExpectation"])

    def test_config_error_without_invoke(self):
        fake = RequestAwareFakeLambda()
        result = probe.run_tracked_minutes_boundary_check(
            lambda_client_factory=lambda config: fake, environ={})
        self.assertEqual(result["stage"], "config")
        self.assertEqual(fake.calls, [])


def run_single(fake, minutes):
    return probe.run_single_boundary_case(
        minutes, lambda_client_factory=lambda config: fake, environ=ENV)


class SingleBoundaryCaseTest(unittest.TestCase):
    """콘솔 단일 케이스 실행: ML 한 번 호출, notify=False, 799/800 성공 조건.

    RequestAwareFakeLambda 는 v0.5 동작을 흉내 낸다(799→insufficient, 800→anomaly,
    notify=False → alert_sent=false, alert_reason="notify_false"). 실제 응답은 AI/ML 책임.
    """

    def test_799_passes_when_no_step_anomaly_and_not_sent(self):
        fake = RequestAwareFakeLambda()
        result = run_single(fake, 799)
        self.assertEqual(len(fake.calls), 1)  # ML 한 번만 호출
        payload = json.loads(fake.calls[0]["Payload"].decode("utf-8"))
        self.assertEqual(payload["metrics"], {"steps": 1000, "tracked_minutes": 799})
        self.assertIs(payload["notify"], False)  # 최상위 notify=False
        self.assertEqual(result["verdict"], "PASS")
        self.assertFalse(result["stepAnomalyJudged"])      # ACTIVITY_DROP 없음
        self.assertIs(result["alertSent"], False)
        self.assertEqual(result["alertReason"], "notify_false")  # 원문 기록
        self.assertTrue(all(result["checks"].values()))

    def test_800_passes_when_step_anomaly_and_not_sent(self):
        fake = RequestAwareFakeLambda()
        result = run_single(fake, 800)
        self.assertEqual(len(fake.calls), 1)
        payload = json.loads(fake.calls[0]["Payload"].decode("utf-8"))
        self.assertEqual(payload["metrics"], {"steps": 1000, "tracked_minutes": 800})
        self.assertIs(payload["notify"], False)
        self.assertEqual(result["verdict"], "PASS")
        self.assertTrue(result["stepAnomalyJudged"])       # ACTIVITY_DROP 감지
        self.assertIs(result["alertSent"], False)

    def test_sent_is_not_a_success_condition(self):
        """alert_sent=true(발송됨)면 notify=False 위반이므로 FAIL. 'sent' 는 성공 조건이 아니다."""
        class SentFake(RequestAwareFakeLambda):
            def invoke(self, **kwargs):
                self.calls.append(kwargs)
                request = json.loads(kwargs["Payload"].decode("utf-8"))
                body = anomaly_body()
                body["alert_sent"] = True          # 발송됨(테스트가 금지하는 상황)
                body["alert_reason"] = "sent"
                envelope = {"statusCode": 200, "headers": {},
                            "body": json.dumps(body, ensure_ascii=False)}
                return {"StatusCode": 200, "Payload": io.BytesIO(json.dumps(envelope).encode())}

        result = run_single(SentFake(), 800)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertFalse(result["checks"]["alertNotSent"])
        self.assertIs(result["alertSent"], True)
        self.assertEqual(result["alertReason"], "sent")

    def test_799_fails_if_step_anomaly_present(self):
        """799 인데 ACTIVITY_DROP 이 감지되면(규칙 위반) FAIL."""
        class DropAt799(RequestAwareFakeLambda):
            def invoke(self, **kwargs):
                self.calls.append(kwargs)
                body = anomaly_body()
                body["alert_sent"] = False
                body["alert_reason"] = "notify_false"
                envelope = {"statusCode": 200, "headers": {},
                            "body": json.dumps(body, ensure_ascii=False)}
                return {"StatusCode": 200, "Payload": io.BytesIO(json.dumps(envelope).encode())}

        result = run_single(DropAt799(), 799)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertFalse(result["checks"]["stepAnomalyMatches"])

    def test_unsupported_value_rejected_before_invoke(self):
        for minutes in (700, 801, 0, None, "799", 799.0):
            fake = RequestAwareFakeLambda()
            result = probe.run_single_boundary_case(
                minutes, lambda_client_factory=lambda config: fake, environ=ENV)
            self.assertEqual(result["verdict"], "REJECTED", repr(minutes))
            self.assertEqual(result["statusCode"], 400)
            self.assertFalse(result["mlInvoked"])
            self.assertEqual(fake.calls, [])  # ML 미호출

    def test_config_error_without_invoke(self):
        fake = RequestAwareFakeLambda()
        result = probe.run_single_boundary_case(
            799, lambda_client_factory=lambda config: fake, environ={})
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["stage"], "config")
        self.assertEqual(fake.calls, [])


class BoundaryEventDispatchTest(unittest.TestCase):
    """lambda_handler 이벤트 분기: 경계 이벤트 / {} / API Gateway."""

    def test_boundary_event_runs_single_case_once(self):
        for minutes in (799, 800):
            with mock.patch.object(probe, "run_single_boundary_case",
                                   return_value={"verdict": "PASS"}) as single, \
                 mock.patch.object(probe, "run_check") as full:
                event = {"check": "tracked_minutes_boundary", "tracked_minutes": minutes}
                probe.lambda_handler(event, None)
                single.assert_called_once_with(minutes)
                full.assert_not_called()

    def test_empty_event_still_runs_full_check(self):
        with mock.patch.object(probe, "run_check", return_value={"verdict": "PASS"}) as full, \
             mock.patch.object(probe, "run_single_boundary_case") as single:
            probe.lambda_handler({}, None)
            full.assert_called_once()
            single.assert_not_called()

    def test_api_gateway_event_refused_without_any_run(self):
        with mock.patch.object(probe, "run_check") as full, \
             mock.patch.object(probe, "run_single_boundary_case") as single:
            # 경계 필드가 있어도 API Gateway 형식이면 거절이 우선한다.
            event = {"requestContext": {"http": {"method": "GET"}},
                     "check": "tracked_minutes_boundary", "tracked_minutes": 799}
            response = probe.lambda_handler(event, None)
            self.assertEqual(response["verdict"], "REFUSED")
            full.assert_not_called()
            single.assert_not_called()

    def test_unknown_check_falls_back_to_full(self):
        with mock.patch.object(probe, "run_check", return_value={"verdict": "PASS"}) as full:
            probe.lambda_handler({"check": "something_else"}, None)
            full.assert_called_once()


if __name__ == "__main__":
    unittest.main()
