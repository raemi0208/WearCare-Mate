"""WearCare Mate 백엔드 - health-data 응답 조립 서비스 계층.

mappers.map_fitbit_activity_rows() 가 만든 "행 단위 매핑 결과"를 받아,
GET /users/{userId}/health-data API 응답 형식으로 조립하는 순수 함수를 담습니다.

이 모듈은 외부 서비스(AWS 등)에 접속하지 않습니다. 데이터를 어디서 읽어 왔는지
(CSV, Athena, Timestream)와 상관없이, 이미 매핑된 행 목록만 다룹니다.

입력(매핑 결과 1행) 형태:
    {"userId": "1000000001", "date": "2099-01-02",
     "activity": {"totalSteps": 1234, "calories": 1000}}

출력(API 응답) 형태 — api-spec.md 4.2절의 필드만 사용:
    {"userId": "1000000001",
     "range": {"from": "2099-01-01", "to": "2099-01-31"},
     "items": [{"date": "2099-01-02", "activity": {...}}]}

설계 원칙:
    - userId 는 응답 최상위에만 두고, items[] 각 항목에서는 제거한다.
    - 사용자 ID 는 문자열로 비교한다. 다른 데이터셋과 ID 가 같다고 가정하지 않는다.
    - 날짜가 없거나 유효하지 않은 행은 날짜를 임의로 만들지 않고 제외한다.
    - from/to 는 유효한 ISO 날짜(YYYY-MM-DD)일 때만 필터에 사용한다.
    - 수면 데이터는 아직 연결하지 않는다. (items[] 에 sleep 키를 넣지 않음)
    - MOCK 표시 필드(mock, _note, requestedRange)는 넣지 않는다.
      이 응답은 실제 필터링을 수행한 결과이기 때문이다.
"""

from datetime import datetime

# ISO 날짜 문자열의 길이 ("YYYY-MM-DD" = 10자)
_ISO_DATE_LENGTH = 10


def _parse_iso_date(value):
    """값이 엄격한 ISO 날짜(YYYY-MM-DD) 문자열이면 date 객체를, 아니면 None 을 돌려준다.

    datetime.strptime 은 "2099-1-2" 처럼 0 이 빠진 값도 허용하므로,
    길이(10자)를 함께 확인해 정확히 YYYY-MM-DD 형식만 받는다.
    존재하지 않는 날짜(2099-02-30)도 None 이다.

    예) "2099-01-02" -> date(2099, 1, 2)
        "2099-1-2", "1/2/2099", "", None, 20990102 -> None
    """
    if not isinstance(value, str) or len(value) != _ISO_DATE_LENGTH:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _validate_user_id(user_id):
    """요청한 사용자 ID 를 비교용 문자열로 만든다. 비어 있으면 ValueError."""
    if user_id is None or isinstance(user_id, bool):
        raise ValueError("요청한 사용자 ID 가 올바르지 않습니다.")
    text = str(user_id)
    if text == "":
        raise ValueError("요청한 사용자 ID 가 비어 있습니다.")
    return text


def build_activity_items(mapped_rows, user_id, date_from=None, date_to=None):
    """매핑된 행 목록에서 조건에 맞는 행만 골라 health-data 의 items[] 를 만든다.

    처리 순서:
        1) 요청한 사용자 ID 와 같은 행만 남긴다. (문자열 비교)
        2) 날짜가 없거나 유효하지 않은 행은 제외한다.
        3) from/to 가 유효한 ISO 날짜이면 그 범위(양 끝 포함)로 거른다.
           유효하지 않은 from/to 는 무시한다(그쪽 경계는 제한 없음).
        4) 각 항목에서 userId 를 빼고 {date, activity} 만 남긴다.

    결과 순서는 입력 순서를 그대로 따른다. (정렬은 데이터 조회 단계에서 결정)
    입력 행과 activity 딕셔너리는 변경하지 않는다(복사본을 만든다).

    Args:
        mapped_rows (list[dict]): map_fitbit_activity_rows() 의 결과.
        user_id (str): 요청 경로의 사용자 ID.
        date_from (str | None): 시작일 (YYYY-MM-DD, 포함).
        date_to (str | None): 종료일 (YYYY-MM-DD, 포함).

    Returns:
        list[dict]: [{"date": "YYYY-MM-DD", "activity": {...}}, ...]
                    조건에 맞는 행이 없으면 빈 리스트.

    Raises:
        ValueError: mapped_rows 가 list/tuple 이 아니거나, 행이 dict 가 아니거나,
                    activity 가 dict 가 아니거나, user_id 가 비어 있을 때.
    """
    if not isinstance(mapped_rows, (list, tuple)):
        raise ValueError("매핑 결과 목록은 list 형식이어야 합니다.")

    target_user_id = _validate_user_id(user_id)
    start = _parse_iso_date(date_from)
    end = _parse_iso_date(date_to)

    items = []
    for row in mapped_rows:
        if not isinstance(row, dict):
            raise ValueError("매핑 결과의 각 행은 dict 형식이어야 합니다.")

        # 1) 사용자 필터: 문자열로 비교
        row_user_id = row.get("userId")
        if row_user_id is None or str(row_user_id) != target_user_id:
            continue

        # 2) 날짜가 없거나 유효하지 않은 행은 제외 (임의로 날짜를 만들지 않음)
        row_date = _parse_iso_date(row.get("date"))
        if row_date is None:
            continue

        # 3) 날짜 범위 필터 (양 끝 포함)
        if start is not None and row_date < start:
            continue
        if end is not None and row_date > end:
            continue

        activity = row.get("activity")
        if not isinstance(activity, dict):
            raise ValueError("매핑 결과의 activity 는 dict 형식이어야 합니다.")

        # 4) userId 를 제외한 {date, activity} 만 담는다 (activity 는 복사본)
        items.append({"date": row_date.isoformat(), "activity": dict(activity)})

    return items


def build_health_data_response(mapped_rows, user_id, date_from=None, date_to=None):
    """health-data API 응답 본문을 조립한다. (api-spec.md 4.2절 필드만 사용)

    range 에는 "실제로 적용된" 날짜 경계만 담는다.
    유효하지 않은 from/to 는 필터에 쓰지 않았으므로 None 으로 표시한다.
    이렇게 하면 프론트가 어떤 범위로 걸러진 결과인지 정확히 알 수 있다.

    Args:
        mapped_rows (list[dict]): map_fitbit_activity_rows() 의 결과.
        user_id (str): 요청 경로의 사용자 ID.
        date_from (str | None): 시작일 (YYYY-MM-DD).
        date_to (str | None): 종료일 (YYYY-MM-DD).

    Returns:
        dict: {"userId": ..., "range": {"from": ..., "to": ...}, "items": [...]}

    Raises:
        ValueError: build_activity_items() 와 같은 조건.
    """
    items = build_activity_items(mapped_rows, user_id, date_from, date_to)
    start = _parse_iso_date(date_from)
    end = _parse_iso_date(date_to)

    return {
        "userId": _validate_user_id(user_id),
        "range": {
            "from": start.isoformat() if start is not None else None,
            "to": end.isoformat() if end is not None else None,
        },
        "items": items,
    }
