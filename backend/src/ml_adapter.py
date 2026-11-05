"""WearCare Mate 백엔드 - AI/ML(이상 탐지) 요청 생성과 응답 검증 (순수 함수).

기준 자료 (읽기 전용 확인, origin/ai-ml @ 1956156a, 2026-11-03):
    - docs/ml-interface-spec.md v0.4 (GitHub origin/ai-ml, 다운로드본과 내용 동일 확인)
    - AI_ML/lambda_handler.py, AI_ML/detector.py
    - docs/sample_responses.json

AI/ML v0.4 반영 (명세 v0.4 기준):
    - 요청 metrics 에 tracked_minutes(기준일 활동 시간 네 값의 합)를 선택 전달. 네 값이 모두
      유효할 때만 보내고, 누락·오류면 생략한다(0 으로 채우지 않음).
      800 분 미만이면 AI/ML 이 "걸음 수 판정"만 건너뛴다(detector.personal_check → insufficient_data).
      다른 지표(수면·HRV·스트레스)는 그대로 판정한다. 백엔드는 합계만 전달한다.
    - 응답 guide 의 lines 배열을 그대로 보존한다.
    - alert_sent 는 **응답 최상위** 선택 필드다(명세 7번, 핸들러 out["alert_sent"]=send_alert(out)).
      guide 와 형제이며, guide 가 null 이어도(이상 아님·생성 실패) true/false 가 올 수 있다.
      true/false/필드 없음을 구분한다. SNS 발송은 AI/ML(wearcare-mate-ml)이 담당한다(주제 wearcare-mate-alert).
    ⚠️ 커밋된 sample_responses.json 에는 아직 alert_sent 가 없어, 검증에서는 최상위 선택 필드로 둔다.
       실제 응답은 항상 alert_sent 를 포함한다.

현재 범위:
    - API(/dashboard, /ai-guide)는 ai_service.py를 통해 이 모듈을 사용한다.
    - 프론트엔드 형식(danger/warn/ok, headline/actions/text)으로의 변환은
      ai_service.py에 구현되어 있다. 최종 화면 계약은 팀 검토 대상이다.

요청 (AI/ML 담당자 요청 반영: history_steps 를 보내지 않음):
    {"user_id": "<숫자 문자열>", "date": "YYYY-MM-DD", "metrics": {"steps": <정수>}}
    - user_id, date, metrics(dict) 는 v0.3 lambda_handler 의 필수 필드다.
    - 기준일 걸음 수(metrics.steps)는 계속 보낸다. v0.3 명세 6번은 "과거 기록만" AI/ML 이 Athena 에서
      읽는다고 하며, 기준일 값은 입력 metrics 로 받는다.
    - 걸음 수 외 지표(수면, HRV, 스트레스)는 데이터가 없으므로 보내지 않는다. 임의로 만들지 않는다.
    - AI/ML Lambda의 최신 배포에서 Athena 직접 조회와 normal 판정을 확인했다.
      과거 구현(3dc9a94)의 빈 기록 반환 설명은 현재 배포 상태가 아니다.
      AI_SOURCE=real은 ai_service.py의 테스트 조건을 통과해야 사용한다.
    - AI/ML 이 직접 조회하므로 user_id 는 Athena 의 실제 사용자 ID(id 컬럼) 그대로여야 한다.

호환성 코드 — build_history_steps (현재 요청에는 사용하지 않음):
    v0.3 lambda_handler 는 요청에 history_steps 가 있으면 Athena 조회 대신 그 값을 쓴다.
    AI/ML 측 조회가 준비되기 전 임시 확인이나, 팀 결정으로 다시 전달하게 될 때를 위해 남겨 둔다.
    아래 규칙은 v0.3 detector.personal_check 와 맞춘 것이다.

history_steps 규칙 (호환성 코드, v0.3 detector.personal_check 와 맞춤):
    - 기준일 당일 제외, 기준일 이전 기록만
    - 걸음 수 0 이하 제외 (AI/ML 은 0걸음을 기기 미착용으로 보고 제외 — 명세상 "가정, 확인 필요")
    - 날짜 오래된 순, 마지막(최근) 최대 14개
    - 날짜 누락은 0 으로 채우지 않는다. (빠진 날은 목록에 없음)
    - 같은 날짜 중복: dashboard_service.collect_daily_steps 정책 재사용
      (같은 값은 하나, 서로 다른 값이면 그 날짜 제외)
    - 5개 미만이어도 그대로 보낸다. 데이터 부족 판정은 AI/ML 이 한다.

미확정 정책 (문서화만, 자동 처리하지 않음):
    - 기준일 걸음 수가 0 인 경우: v0.3 코드는 기준일 0걸음을 제외하지 않아 high 이상으로 판정될 수 있다.
      최종 정책이 정해지기 전까지 이 모듈은 0걸음 기준일의 요청을 만들지 않는다(TargetNotEligibleError).
    - ai_service.py는 불완전한 2016-04-12를 판정일에서 제외한다.
    - Fitbit ActivityDate 오류(385/457행): 재적재 대상. 이 모듈은 날짜를 임의 규칙으로 보정하지 않는다.
"""

from datetime import date, datetime

from src.athena_repository import AthenaQueryValidationError, validate_user_id
from src.dashboard_service import collect_daily_steps
from src.data_source import DataSourceUnavailableError
from src.health_service import build_activity_items

HISTORY_MAX_RECORDS = 14

# v0.3 출력 값 집합
STATUSES = ("normal", "anomaly", "insufficient_data")
OVERALL_SEVERITIES = ("none", "low", "medium", "high")
ANOMALY_SEVERITIES = ("low", "medium", "high")
BASES = ("personal", "population")
_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}

STEP_ANOMALY_TYPE = "ACTIVITY_DROP"
STEP_METRIC = "steps"

# guide 상태 구분 (summarize_detection)
GUIDE_GENERATED = "generated"            # status=anomaly, guide 있음
GUIDE_MISSING = "missing"                # status=anomaly, guide=null (생성 실패 또는 AI/ML 측 비활성)
GUIDE_NOT_APPLICABLE = "not_applicable"  # status=normal/insufficient_data → 원래 guide 없음


class MLRequestError(Exception):
    """AI/ML 요청을 만들 수 없을 때 (사용자 ID·날짜·입력 형식 오류). 사용자 입력값은 메시지에 넣지 않는다."""


class TargetNotEligibleError(Exception):
    """기준일이 이상 탐지 대상이 아닐 때. reason 으로 사유를 구분한다.

    reason:
        "missing_steps": 기준일 걸음 수 기록이 없음
        "zero_steps":    기준일 걸음 수가 0 (기기 미착용 가능성. 최종 정책 미확정)
        "excluded_date": 호출한 쪽이 제외 날짜로 지정함 (예: 불완전한 날 — 정책 미확정)
    """

    def __init__(self, reason):
        super().__init__(f"기준일이 이상 탐지 대상이 아닙니다: {reason}")
        self.reason = reason


class MLResponseError(DataSourceUnavailableError):
    """AI/ML 응답 형식이 v0.3 과 다를 때. (503) 응답 원문은 메시지에 넣지 않는다."""


# ---------------------------------------------------------------------------
# 입력 준비
# ---------------------------------------------------------------------------
def _parse_iso_date(value):
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _require_user_id(user_id):
    try:
        return validate_user_id(user_id)
    except AthenaQueryValidationError:
        raise MLRequestError("user_id 는 숫자 1~20자여야 합니다.") from None


def _require_date(value, name="date"):
    parsed = _parse_iso_date(value)
    if parsed is None:
        raise MLRequestError(f"{name} 는 YYYY-MM-DD 형식의 유효한 날짜여야 합니다.")
    return parsed


def daily_steps_for_user(mapped_rows, user_id):
    """매핑된 행(mappers.map_fitbit_activity_rows 결과)에서 해당 사용자의 날짜별 걸음 수를 만든다.

    - health_service.build_activity_items 로 요청 사용자 행만 남긴다. (다른 사용자 데이터 혼합 방지)
    - dashboard_service.collect_daily_steps 정책을 그대로 쓴다.
      (0 이상 정수만, 잘못된 날짜 제외, 같은 날짜의 서로 다른 값은 제외)

    Returns:
        dict[date, int]
    """
    user_id = _require_user_id(user_id)
    return collect_daily_steps(build_activity_items(mapped_rows, user_id))


def _valid_minutes(value):
    """활동 시간으로 쓸 수 있는 0 이상의 정수면 그 값, 아니면 None. (유효한 0 은 그대로 둔다)"""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def collect_daily_tracked_minutes(items):
    """items 에서 날짜별 기록 시간 합계(tracked_minutes)를 만든다. (AI/ML v0.4 metrics.tracked_minutes)

    activity.trackedMinutes 는 mappers 가 네 활동 시간(very/fairly/lightly/sedentary)이 모두
    유효할 때만 넣는 값이다. 하나라도 누락·오류면 그 날짜는 결과에 넣지 않는다. (0 으로 채우지 않음)

    - 유효한 0 은 그대로 쓴다. (활동 시간 0 분도 유효한 값)
    - 같은 날짜에 서로 다른 trackedMinutes 가 있으면 어느 값이 맞는지 알 수 없으므로 그 날짜를 제외한다.
      (collect_daily_steps 와 같은 정책)

    Returns:
        dict[date, int]: 네 활동 시간이 모두 유효한 날짜 → 합계.

    Raises:
        ValueError: items 가 list/tuple 이 아니거나 항목이 dict 가 아닐 때.
    """
    if not isinstance(items, (list, tuple)):
        raise ValueError("activity items 는 list 형식이어야 합니다.")

    values_by_date = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("activity item 은 dict 형식이어야 합니다.")
        day = _parse_iso_date(item.get("date"))
        activity = item.get("activity")
        minutes = _valid_minutes(activity.get("trackedMinutes")) if isinstance(activity, dict) else None
        if day is None or minutes is None:
            continue
        values_by_date.setdefault(day, set()).add(minutes)

    return {day: next(iter(values)) for day, values in values_by_date.items() if len(values) == 1}


def build_history_steps(daily_steps, target_date):
    """기준일 직전 걸음 수 기록(history_steps)을 만든다.

    ⚠️ 호환성 코드: AI/ML 담당자 요청으로 build_detection_request() 는 더 이상 history_steps 를
       보내지 않는다. 이 함수는 실제 API 요청 경로에서 사용하지 않는다. (모듈 설명 참고)

    Args:
        daily_steps (dict[date, int]): 날짜별 걸음 수 (한 사용자). daily_steps_for_user 결과.
        target_date (date | str): 기준일.

    Returns:
        list[int]: 기준일 이전, 0 초과, 오래된 순, 최근 최대 14개. 5개 미만이어도 그대로 돌려준다.
    """
    target = _require_date(target_date, "target_date")
    if not isinstance(daily_steps, dict):
        raise MLRequestError("daily_steps 는 날짜별 걸음 수 dict 여야 합니다.")

    history = []
    for day, steps in daily_steps.items():
        if not isinstance(day, date) or isinstance(day, datetime):
            raise MLRequestError("daily_steps 의 키는 날짜여야 합니다.")
        if isinstance(steps, bool) or not isinstance(steps, int):
            raise MLRequestError("daily_steps 의 값은 정수여야 합니다.")
        if day < target and steps > 0:
            history.append((day, steps))

    history.sort()
    return [steps for _day, steps in history[-HISTORY_MAX_RECORDS:]]


def build_detection_request(user_id, target_date, daily_steps, excluded_dates=(),
                            daily_tracked_minutes=None):
    """AI/ML Lambda 요청 JSON 을 만든다. (걸음 수 기반 개인 기준선만, history_steps 미포함)

    과거 기록(history)은 AI/ML Lambda 가 Athena 에서 직접 읽는다(담당자 요청).
    과거 기록은 최신 AI/ML Lambda의 Athena 직접 조회로 채운다.

    Args:
        user_id (str): 숫자 문자열 사용자 ID (REAL 모드에서는 DASHBOARD_USER_ID).
            AI/ML 이 Athena 를 직접 조회하므로 실제 id 컬럼 값이어야 한다.
        target_date (date | str): 기준일.
        daily_steps (dict[date, int]): 그 사용자의 날짜별 걸음 수. 기준일 걸음 수를 꺼내는 데만 쓴다.
        excluded_dates (Iterable[date | str]): 기준일로 쓰지 않을 날짜. 기본값은 비어 있다.
            ⚠️ 2016-04-12 같은 불완전한 날의 제외 정책은 미확정이므로 기본값에 넣지 않았다.
        daily_tracked_minutes (dict[date, int] | None): 날짜별 기록 시간 합계
            (collect_daily_tracked_minutes 결과). AI/ML v0.4 의 metrics.tracked_minutes 근거값이다.
            기준일 값이 있으면 metrics.tracked_minutes 로 전달하고, 없으면 생략한다.
            (네 활동 시간 중 하나라도 누락·오류면 그 날짜는 여기에 들어 있지 않으므로 자동으로 생략된다.
            누락값을 0 으로 채우지 않는다. 800 분 미만 판정 제외는 AI/ML 쪽 규칙이므로 백엔드는 합계만 보낸다.)

    Returns:
        dict: {"user_id", "date", "metrics": {"steps"[, "tracked_minutes"]}}

    Raises:
        MLRequestError: 사용자 ID·날짜·입력 형식 오류
        TargetNotEligibleError: 기준일 걸음 수 없음 / 0걸음 / 제외 날짜
    """
    user_id = _require_user_id(user_id)
    target = _require_date(target_date, "target_date")
    excluded = {_require_date(value, "excluded_dates") for value in excluded_dates}

    if not isinstance(daily_steps, dict):
        raise MLRequestError("daily_steps 는 날짜별 걸음 수 dict 여야 합니다.")
    if daily_tracked_minutes is not None and not isinstance(daily_tracked_minutes, dict):
        raise MLRequestError("daily_tracked_minutes 는 날짜별 기록 시간 dict 여야 합니다.")
    if target in excluded:
        raise TargetNotEligibleError("excluded_date")

    steps = daily_steps.get(target)
    if steps is None:
        raise TargetNotEligibleError("missing_steps")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
        raise MLRequestError("기준일 걸음 수는 0 이상의 정수여야 합니다.")
    if steps == 0:
        # v0.3 코드는 기준일 0걸음을 제외하지 않는다 → 정책 확정 전까지 요청을 만들지 않는다.
        raise TargetNotEligibleError("zero_steps")

    metrics = {"steps": steps}
    if daily_tracked_minutes is not None:
        tracked = daily_tracked_minutes.get(target)
        if tracked is not None:
            # collect_daily_tracked_minutes 가 이미 네 값이 모두 유효할 때만 넣으므로 0 이상의 정수다.
            if isinstance(tracked, bool) or not isinstance(tracked, int) or tracked < 0:
                raise MLRequestError("기준일 기록 시간은 0 이상의 정수여야 합니다.")
            metrics["tracked_minutes"] = tracked

    # history_steps 는 넣지 않는다. (AI/ML Lambda 가 Athena 에서 직접 조회)
    return {
        "user_id": user_id,
        "date": target.isoformat(),
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# 응답 검증 (v0.3 출력, API Gateway 래핑을 푼 body)
# ---------------------------------------------------------------------------
def _fail(message):
    raise MLResponseError(message)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_keys(obj, keys, where):
    if not isinstance(obj, dict):
        _fail(f"{where} 형식이 올바르지 않습니다.")
    missing = [key for key in keys if key not in obj]
    if missing:
        _fail(f"{where} 에 필수 필드가 없습니다: {', '.join(missing)}")


def _validate_anomaly(anomaly, index):
    where = f"anomalies[{index}]"
    _require_keys(anomaly, ("type", "basis", "metric", "value", "z_score", "severity"), where)
    if not isinstance(anomaly["type"], str) or not anomaly["type"]:
        _fail(f"{where}.type 이 올바르지 않습니다.")
    if anomaly["basis"] not in BASES:
        _fail(f"{where}.basis 값이 올바르지 않습니다.")
    if not isinstance(anomaly["metric"], str) or not anomaly["metric"]:
        _fail(f"{where}.metric 이 올바르지 않습니다.")
    if anomaly["severity"] not in ANOMALY_SEVERITIES:
        _fail(f"{where}.severity 값이 올바르지 않습니다.")
    for key in ("value", "z_score"):
        if not _is_number(anomaly[key]):
            _fail(f"{where}.{key} 는 숫자여야 합니다.")
    if anomaly["basis"] == "personal":
        extra = ("baseline_mean", "baseline_std", "drop_pct")
    else:
        extra = ("population_mean",)
    _require_keys(anomaly, extra, where)
    for key in extra:
        if not _is_number(anomaly[key]):
            _fail(f"{where}.{key} 는 숫자여야 합니다.")


def _validate_guide(guide):
    _require_keys(guide, ("text", "lines", "model_id", "warnings", "generated_at"), "guide")
    if not isinstance(guide["text"], str) or not guide["text"].strip():
        _fail("guide.text 가 올바르지 않습니다.")
    lines = guide["lines"]
    # v0.3 split_lines 는 최대 3줄. 규칙 위반이 남으면 3줄 미만일 수 있다(warnings 에 사유).
    if not isinstance(lines, list) or not 1 <= len(lines) <= 3:
        _fail("guide.lines 는 1~3개의 문자열 목록이어야 합니다.")
    if any(not isinstance(line, str) or not line.strip() for line in lines):
        _fail("guide.lines 에 빈 줄이나 문자열이 아닌 값이 있습니다.")
    if not isinstance(guide["model_id"], str) or not guide["model_id"]:
        _fail("guide.model_id 가 올바르지 않습니다.")
    warnings = guide["warnings"]
    if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
        _fail("guide.warnings 는 문자열 목록이어야 합니다.")
    generated_at = guide["generated_at"]
    try:
        parsed = datetime.fromisoformat(generated_at) if isinstance(generated_at, str) else None
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None:
        _fail("guide.generated_at 은 시간대가 포함된 ISO 시각이어야 합니다.")


def validate_detection_result(body, expected_user_id=None, expected_date=None):
    """AI/ML 응답 body 가 v0.3 출력 구조인지 검증한다. 통과하면 body 를 그대로 돌려준다.

    검증 항목:
        - 필수 필드: user_id, date, status, overall_severity, anomalies, anomaly_score, guide, model_version
        - 값 집합: status, overall_severity, anomalies[].severity/basis
        - anomalies[] 필드와 숫자 타입 (personal/population 별 추가 필드)
        - guide: null 또는 {text, lines(1~3), model_id, warnings[], generated_at(시간대 포함)}
        - 일관성: anomaly ⇔ anomalies 비어 있지 않음, guide 는 anomaly 일 때만,
                  overall_severity 는 anomalies 의 최고 심각도 이상 (v0.3 은 지표 2개 이상이면 한 단계 올림)
        - 요청과 같은 user_id/date 인지 (다른 사용자·날짜의 결과가 섞이지 않게)

    Raises:
        MLResponseError: 형식이 다를 때 (503)
    """
    _require_keys(
        body,
        ("user_id", "date", "status", "overall_severity", "anomalies",
         "anomaly_score", "guide", "model_version"),
        "AI/ML 응답",
    )
    if expected_user_id is not None and body["user_id"] != expected_user_id:
        _fail("AI/ML 응답의 사용자가 요청과 다릅니다.")
    if expected_date is not None and body["date"] != expected_date:
        _fail("AI/ML 응답의 날짜가 요청과 다릅니다.")

    status = body["status"]
    overall = body["overall_severity"]
    anomalies = body["anomalies"]
    if status not in STATUSES:
        _fail("status 값이 올바르지 않습니다.")
    if overall not in OVERALL_SEVERITIES:
        _fail("overall_severity 값이 올바르지 않습니다.")
    if not isinstance(anomalies, list):
        _fail("anomalies 는 목록이어야 합니다.")
    for index, anomaly in enumerate(anomalies):
        _validate_anomaly(anomaly, index)
    if body["anomaly_score"] is not None and not _is_number(body["anomaly_score"]):
        _fail("anomaly_score 는 숫자 또는 null 이어야 합니다.")
    if not isinstance(body["model_version"], str) or not body["model_version"]:
        _fail("model_version 이 올바르지 않습니다.")
    # alert_sent 는 응답 최상위의 선택 필드(v0.4 명세 7번, origin/ai-ml @ 1956156a). guide 와 형제다.
    # 실제 AI/ML 핸들러는 항상 넣지만(true/false), 커밋된 sample_responses.json 에는 아직 없어 선택으로 둔다.
    # 있으면 불리언이어야 하며, guide 가 null 이어도(status=anomaly 가 아니어도) 올 수 있다.
    if "alert_sent" in body and not isinstance(body["alert_sent"], bool):
        _fail("alert_sent 는 불리언이어야 합니다.")

    if status == "anomaly":
        if not anomalies:
            _fail("status=anomaly 인데 anomalies 가 비어 있습니다.")
        top = max(_RANK[anomaly["severity"]] for anomaly in anomalies)
        if _RANK[overall] < top:
            _fail("overall_severity 가 anomalies 의 심각도보다 낮습니다.")
    else:
        if anomalies:
            _fail(f"status={status} 인데 anomalies 가 있습니다.")
        if overall != "none":
            _fail(f"status={status} 인데 overall_severity 가 none 이 아닙니다.")

    guide = body["guide"]
    if guide is not None:
        if status != "anomaly":
            _fail("guide 는 status=anomaly 일 때만 있을 수 있습니다.")
        _validate_guide(guide)
    return body


def summarize_detection(result):
    """검증된 결과를 백엔드가 다루기 쉬운 요약으로 만든다. (API 형식 변환 아님)

    Returns:
        dict: {
            "date": "YYYY-MM-DD",
            "status": "normal" | "anomaly" | "insufficient_data",
            "overallSeverity": "none" | "low" | "medium" | "high",
            "stepAnomaly": bool,          # ACTIVITY_DROP(걸음 수) 이상 여부
            "guideState": "generated" | "missing" | "not_applicable",
            "guideWarningCount": int,     # 프론트 표시는 가능, 로그 수집용 (명세 8번)
            "alertSent": True | False | None,  # 응답 최상위 alert_sent (v0.4, 선택). 필드 없으면 None
        }
        guideState 로 "이상이 없어 가이드가 없음"과 "이상이 있는데 가이드가 없음(생성 실패 등)"을 구분한다.
        alertSent 는 AI/ML(wearcare-mate-ml)이 SNS 를 발송했는지 알려 주는 응답 최상위 선택 필드다.
        True(발송함) / False(발송 안 함) / None(필드 없음 = 알 수 없음)을 구분한다.
        guide 가 null(이상 아님·생성 실패)이어도 발송 결과는 보존한다.
        백엔드는 SNS 를 직접 발송하지 않으며, 이 값은 표시·로그용으로만 전달한다.
    """
    status = result["status"]
    guide = result["guide"]
    if status != "anomaly":
        guide_state = GUIDE_NOT_APPLICABLE
    elif guide is None:
        guide_state = GUIDE_MISSING
    else:
        guide_state = GUIDE_GENERATED
    return {
        "date": result["date"],
        "status": status,
        "overallSeverity": result["overall_severity"],
        "stepAnomaly": any(
            anomaly["type"] == STEP_ANOMALY_TYPE and anomaly["metric"] == STEP_METRIC
            for anomaly in result["anomalies"]
        ),
        "guideState": guide_state,
        "guideWarningCount": len(guide["warnings"]) if guide else 0,
        # 응답 최상위 alert_sent 를 읽는다(v0.4). guide 유무와 무관하게 true/false 를 보존하고,
        # 필드가 없으면 None. (기존 프론트엔드용 alertSent 계약: True/False/None)
        "alertSent": result.get("alert_sent"),
    }


def step_anomaly_dates(results):
    """검증된 결과 목록에서 걸음 수 이상(ACTIVITY_DROP) 날짜를 모은다.

    dashboard_service.build_steps_timeseries(stats, anomaly_dates=...) 에 넘길 수 있는 형태(date 집합).
    ⚠️ 아직 /dashboard 에 연결하지 않았다.
    """
    dates = set()
    for result in results:
        if summarize_detection(result)["stepAnomaly"]:
            parsed = _parse_iso_date(result["date"])
            if parsed is None:
                _fail("AI/ML 응답의 날짜 형식이 올바르지 않습니다.")
            dates.add(parsed)
    return dates
