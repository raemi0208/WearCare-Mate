"""WearCare Mate 백엔드 - 데이터 행(row) → API 응답 형식 매핑 모듈.

이 모듈은 외부 서비스에 접속하지 않는 "순수 함수"만 담습니다.
같은 입력이면 항상 같은 출력을 돌려주므로 AWS 없이 로컬에서 테스트할 수 있습니다.

현재 범위:
    - Fitbit 활동 데이터 1행을 health-data API의 활동 항목 형식으로 변환
    - 수면 데이터는 제외 (사용자 ID·날짜 매핑이 아직 확정되지 않음)

입력 행(row)의 형태:
    - CSV(csv.DictReader) 형식: {"Id": "...", "ActivityDate": "3/25/2016", "TotalSteps": "..."}
    - Athena 결과 형식(소문자 컬럼명): {"id": "...", "activitydate": "...", "totalsteps": "..."}
    두 형식 모두 지원합니다. 값은 문자열 또는 숫자 어느 쪽이어도 됩니다.

설계 원칙 (미확정 사항을 임의로 확정하지 않음):
    - TotalDistance 는 단위(km/mile)가 확정되지 않았으므로 매핑하지 않습니다.
      기존 API 필드명 totalDistanceKm 에 넣으면 "km 단위"라고 확정하는 셈이기 때문입니다.
    - VeryActiveMinutes 는 값이 실제로 제공된 경우에만 결과에 포함합니다.
      (현재 Timestream 적재 스크립트는 이 컬럼을 적재하지 않음)
    - 다른 데이터셋(수면 등)과 사용자 ID가 같다고 가정하지 않습니다.
"""

from datetime import date, datetime

# 날짜 문자열로 허용하는 형식들
# - "%m/%d/%Y": Fitbit CSV 원본 형식 (예: 3/25/2016)
# - "%Y-%m-%d": ISO 형식 / Athena date 타입 문자열 (예: 2016-03-25)
_DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d")


def _normalize_key(key):
    """컬럼명을 비교하기 쉬운 형태로 정규화한다.

    CSV 는 "TotalSteps", Athena 는 "totalsteps"(또는 "total_steps")처럼
    컬럼명 표기가 다를 수 있으므로, 소문자로 바꾸고 영문자·숫자만 남긴다.
    BOM 문자(\\ufeff)나 앞뒤 공백도 함께 제거된다.

    예) "TotalSteps" -> "totalsteps", "total_steps" -> "totalsteps",
        "\\ufeffId" -> "id"
    """
    return "".join(ch for ch in str(key).lower() if ch.isascii() and ch.isalnum())


def _normalize_row(row):
    """행의 모든 컬럼명을 정규화한 새 딕셔너리를 만든다. (원본 행은 바꾸지 않음)"""
    if not isinstance(row, dict):
        raise ValueError("데이터 행은 dict 형식이어야 합니다.")
    return {_normalize_key(key): value for key, value in row.items()}


def _is_missing(value):
    """값이 '없음'인지 판단한다. None, 빈 문자열, 공백 문자열을 없음으로 본다."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _to_user_id(value):
    """사용자 ID를 문자열로 변환한다.

    - 문자열이면 앞뒤 공백만 제거한다. (앞자리 0 등 원래 표기를 보존)
    - 정수면 그대로 문자열로 바꾼다.
    - 1503960366.0 처럼 정수값을 가진 실수면 ".0" 이 붙지 않게 정수로 바꾼 뒤 문자열로 만든다.
    - 값이 없으면 어느 사용자의 데이터인지 알 수 없으므로 ValueError 를 던진다.
    """
    if _is_missing(value):
        raise ValueError("사용자 ID(Id) 값이 없습니다.")
    if isinstance(value, bool):
        raise ValueError("사용자 ID(Id) 형식이 올바르지 않습니다.")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("사용자 ID(Id) 형식이 올바르지 않습니다.")
        return str(int(value))
    return str(value).strip()


def _to_iso_date(value):
    """날짜 값을 ISO "YYYY-MM-DD" 문자열로 변환한다.

    지원하는 입력:
        - "3/25/2016" (Fitbit CSV 형식)
        - "2016-03-25" (ISO / Athena date)
        - "2016-03-25 00:00:00.000" 처럼 날짜 뒤에 시간이 붙은 문자열
          → 앞의 날짜 부분만 사용 (시간대 변환은 하지 않음)
        - datetime.date / datetime.datetime 객체

    변환할 수 없는 값(없음, 형식 오류, 존재하지 않는 날짜 2/30/2016 등)은 None 을 돌려준다.
    잘못된 날짜를 그럴듯한 값으로 바꿔 넣지 않기 위함이다.
    """
    if _is_missing(value):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    # "2016-03-25 00:00:00" / "2016-03-25T00:00:00" → 날짜 부분만 사용
    if len(text) > 10 and text[10] in (" ", "T"):
        text = text[:10]

    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _to_int(value):
    """숫자 값을 정수로 변환한다. 변환할 수 없으면 None 을 돌려준다.

    - "11004", 11004, "11004.0", 11004.0 → 11004
    - 소수점 이하가 있는 값("12.5")은 임의로 반올림하지 않고 None 처리한다.
    - None, 빈 문자열, 숫자가 아닌 문자열, bool 값은 None 처리한다.
    """
    if _is_missing(value) or isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    if number != number or not number.is_integer():
        # NaN 이거나 정수가 아닌 값
        return None
    return int(number)


def map_fitbit_activity_row(row):
    """Fitbit 활동 데이터 1행을 health-data API 의 활동 항목 형식으로 변환한다.

    매핑 규칙:
        Id                → userId               (문자열, 필수)
        ActivityDate      → date                 (ISO YYYY-MM-DD, 변환 불가 시 None)
        TotalSteps        → activity.totalSteps  (정수, 없으면 None)
        Calories          → activity.calories    (정수, 없으면 None)
        VeryActiveMinutes → activity.veryActiveMinutes (값이 있을 때만 포함)

    매핑하지 않는 컬럼:
        TotalDistance (단위 미확정), 그 외 Fitbit 컬럼, 수면 관련 컬럼

    Args:
        row (dict): CSV 또는 Athena 결과의 한 행. 컬럼명 대소문자/밑줄 차이는 무시한다.

    Returns:
        dict: 예) {"userId": "1000000001", "date": "2099-01-01",
                   "activity": {"totalSteps": 1234, "calories": 1000}}

    Raises:
        ValueError: row 가 dict 가 아니거나, 사용자 ID 가 없거나 형식이 잘못된 경우.
    """
    normalized = _normalize_row(row)

    activity = {
        "totalSteps": _to_int(normalized.get("totalsteps")),
        "calories": _to_int(normalized.get("calories")),
    }

    # VeryActiveMinutes 는 실제 값이 제공된 경우에만 포함한다.
    very_active_minutes = _to_int(normalized.get("veryactiveminutes"))
    if very_active_minutes is not None:
        activity["veryActiveMinutes"] = very_active_minutes

    return {
        "userId": _to_user_id(normalized.get("id")),
        "date": _to_iso_date(normalized.get("activitydate")),
        "activity": activity,
    }


def map_fitbit_activity_rows(rows):
    """여러 Fitbit 행을 한 번에 변환한다. 입력 순서를 그대로 유지한다.

    Args:
        rows (list[dict]): 데이터 행 목록.

    Returns:
        list[dict]: map_fitbit_activity_row 결과 목록.

    Raises:
        ValueError: rows 가 list/tuple 이 아니거나, 행 중 하나라도 변환에 실패한 경우.
    """
    if not isinstance(rows, (list, tuple)):
        raise ValueError("데이터 행 목록은 list 형식이어야 합니다.")
    return [map_fitbit_activity_row(row) for row in rows]
