"""health_service 모듈(health-data 응답 조립)에 대한 단위 테스트.

외부 패키지 없이 파이썬 표준 라이브러리 unittest 만 사용합니다.
테스트 데이터는 모두 가상의 값이며, Database 폴더의 실제 CSV 기록을 복사하지 않았습니다.

실행 방법(backend 폴더 기준):
    python -m unittest discover -s tests -v
"""

import copy
import os
import sys
import unittest

# src 패키지를 import 할 수 있도록 backend 폴더를 모듈 검색 경로에 추가합니다.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.health_service import (  # noqa: E402
    build_activity_items,
    build_health_data_response,
)
from src.mappers import map_fitbit_activity_rows  # noqa: E402

USER_A = "1000000001"
USER_B = "1000000002"


def make_mapped_row(user_id=USER_A, row_date="2099-01-02", steps=1234):
    """map_fitbit_activity_row() 결과 형태의 가상 행을 만든다."""
    return {
        "userId": user_id,
        "date": row_date,
        "activity": {"totalSteps": steps, "calories": 1000},
    }


def sample_rows():
    """사용자 2명, 여러 날짜가 섞인 가상 매핑 결과."""
    return [
        make_mapped_row(USER_A, "2099-01-01", 100),
        make_mapped_row(USER_B, "2099-01-01", 200),
        make_mapped_row(USER_A, "2099-01-02", 300),
        make_mapped_row(USER_A, "2099-01-03", 400),
        make_mapped_row(USER_B, "2099-01-03", 500),
    ]


class UserFilterTest(unittest.TestCase):
    """사용자 필터링."""

    def test_only_requested_user_rows(self):
        """요청한 사용자의 행만 포함되어야 한다."""
        items = build_activity_items(sample_rows(), USER_A)
        self.assertEqual([item["activity"]["totalSteps"] for item in items], [100, 300, 400])

    def test_user_id_removed_from_items(self):
        """items[] 각 항목에는 userId 가 없어야 한다."""
        items = build_activity_items(sample_rows(), USER_A)
        for item in items:
            self.assertNotIn("userId", item)
            self.assertEqual(set(item.keys()), {"date", "activity"})

    def test_user_id_compared_as_string(self):
        """숫자로 들어온 ID 도 문자열로 비교해 같은 사용자로 인식해야 한다."""
        rows = [make_mapped_row(1000000001, "2099-01-02")]
        self.assertEqual(len(build_activity_items(rows, "1000000001")), 1)
        self.assertEqual(len(build_activity_items(sample_rows(), 1000000001)), 3)

    def test_similar_user_id_is_not_matched(self):
        """앞자리 0 등 표기가 다른 ID 는 같은 사용자로 보지 않아야 한다."""
        rows = [make_mapped_row("01000000001", "2099-01-02")]
        self.assertEqual(build_activity_items(rows, USER_A), [])

    def test_row_without_user_id_is_excluded(self):
        """userId 가 없는 행은 제외되어야 한다."""
        rows = [{"date": "2099-01-02", "activity": {"totalSteps": 1}}]
        self.assertEqual(build_activity_items(rows, USER_A), [])

    def test_empty_request_user_id_raises(self):
        """요청 사용자 ID 가 비어 있으면 ValueError 가 발생해야 한다."""
        with self.assertRaises(ValueError):
            build_activity_items(sample_rows(), "")
        with self.assertRaises(ValueError):
            build_activity_items(sample_rows(), None)


class DateRangeFilterTest(unittest.TestCase):
    """날짜 범위 필터링."""

    def test_no_range_returns_all_dates(self):
        """from/to 가 없으면 날짜로 거르지 않아야 한다."""
        items = build_activity_items(sample_rows(), USER_A)
        self.assertEqual(
            [item["date"] for item in items], ["2099-01-01", "2099-01-02", "2099-01-03"]
        )

    def test_range_is_inclusive(self):
        """from/to 경계 날짜는 포함되어야 한다."""
        items = build_activity_items(sample_rows(), USER_A, "2099-01-02", "2099-01-03")
        self.assertEqual([item["date"] for item in items], ["2099-01-02", "2099-01-03"])

    def test_from_only(self):
        """from 만 있으면 그 날짜 이후만 포함해야 한다."""
        items = build_activity_items(sample_rows(), USER_A, date_from="2099-01-03")
        self.assertEqual([item["date"] for item in items], ["2099-01-03"])

    def test_to_only(self):
        """to 만 있으면 그 날짜 이전만 포함해야 한다."""
        items = build_activity_items(sample_rows(), USER_A, date_to="2099-01-01")
        self.assertEqual([item["date"] for item in items], ["2099-01-01"])

    def test_from_after_to_returns_empty(self):
        """from 이 to 보다 늦으면 결과가 비어야 한다."""
        items = build_activity_items(sample_rows(), USER_A, "2099-01-03", "2099-01-01")
        self.assertEqual(items, [])


class InvalidDateTest(unittest.TestCase):
    """잘못된 날짜 처리."""

    def test_rows_with_missing_or_invalid_date_are_excluded(self):
        """날짜가 없거나(None) 유효하지 않은 행은 제외되어야 한다."""
        rows = [
            make_mapped_row(USER_A, None),
            make_mapped_row(USER_A, ""),
            make_mapped_row(USER_A, "not-a-date"),
            make_mapped_row(USER_A, "2099-02-30"),
            make_mapped_row(USER_A, "1/2/2099"),
            make_mapped_row(USER_A, "2099-01-02"),
        ]
        items = build_activity_items(rows, USER_A)
        self.assertEqual([item["date"] for item in items], ["2099-01-02"])

    def test_invalid_from_to_are_ignored(self):
        """유효하지 않은 from/to 는 필터에 쓰지 않아야 한다."""
        items = build_activity_items(sample_rows(), USER_A, "2099-1-2", "bad")
        self.assertEqual(len(items), 3)

    def test_invalid_from_with_valid_to(self):
        """from 만 잘못되면 to 경계만 적용되어야 한다."""
        items = build_activity_items(sample_rows(), USER_A, "2099-02-30", "2099-01-02")
        self.assertEqual([item["date"] for item in items], ["2099-01-01", "2099-01-02"])

    def test_non_string_from_is_ignored(self):
        """문자열이 아닌 from 값은 무시되어야 한다."""
        items = build_activity_items(sample_rows(), USER_A, date_from=20990102)
        self.assertEqual(len(items), 3)


class EmptyResultTest(unittest.TestCase):
    """빈 결과."""

    def test_empty_input(self):
        """입력이 비어 있으면 빈 items[] 를 반환해야 한다."""
        self.assertEqual(build_activity_items([], USER_A), [])

    def test_unknown_user(self):
        """해당 사용자의 데이터가 없으면 빈 items[] 를 반환해야 한다."""
        self.assertEqual(build_activity_items(sample_rows(), "9999999999"), [])

    def test_response_with_no_items(self):
        """응답 조립 시에도 결과가 없으면 items 는 빈 리스트여야 한다."""
        response = build_health_data_response(sample_rows(), "9999999999")
        self.assertEqual(response["items"], [])
        self.assertEqual(response["userId"], "9999999999")


class ResponseShapeTest(unittest.TestCase):
    """전체 응답 구조."""

    def test_response_fields_follow_spec(self):
        """응답은 api-spec 4.2절의 userId/range/items 만 가져야 한다."""
        response = build_health_data_response(
            sample_rows(), USER_A, "2099-01-01", "2099-01-02"
        )
        self.assertEqual(set(response.keys()), {"userId", "range", "items"})
        self.assertEqual(response["userId"], USER_A)
        self.assertEqual(response["range"], {"from": "2099-01-01", "to": "2099-01-02"})
        self.assertEqual(len(response["items"]), 2)

    def test_response_has_no_mock_markers(self):
        """실제 필터링 결과이므로 MOCK 표시 필드가 없어야 한다."""
        response = build_health_data_response(sample_rows(), USER_A)
        for field in ("mock", "_note", "requestedRange"):
            self.assertNotIn(field, response)

    def test_items_have_no_sleep_key(self):
        """수면 데이터는 아직 연결하지 않으므로 sleep 키가 없어야 한다."""
        response = build_health_data_response(sample_rows(), USER_A)
        for item in response["items"]:
            self.assertNotIn("sleep", item)

    def test_range_shows_only_applied_bounds(self):
        """유효하지 않은 from/to 는 range 에 None 으로 표시되어야 한다."""
        response = build_health_data_response(sample_rows(), USER_A, "bad", "2099-01-02")
        self.assertEqual(response["range"], {"from": None, "to": "2099-01-02"})

    def test_range_is_none_without_query(self):
        """from/to 가 없으면 range 의 양쪽 모두 None 이어야 한다."""
        response = build_health_data_response(sample_rows(), USER_A)
        self.assertEqual(response["range"], {"from": None, "to": None})


class InputSafetyTest(unittest.TestCase):
    """입력 보존 및 잘못된 입력 타입."""

    def test_input_rows_are_not_modified(self):
        """입력 행과 activity 는 변경되지 않아야 한다."""
        rows = sample_rows()
        snapshot = copy.deepcopy(rows)
        items = build_activity_items(rows, USER_A)
        items[0]["activity"]["totalSteps"] = -1
        self.assertEqual(rows, snapshot)

    def test_non_list_rows_raises(self):
        """행 목록이 list 가 아니면 ValueError 가 발생해야 한다."""
        with self.assertRaises(ValueError):
            build_activity_items("not-a-list", USER_A)

    def test_non_dict_row_raises(self):
        """dict 가 아닌 행은 ValueError 가 발생해야 한다."""
        with self.assertRaises(ValueError):
            build_activity_items(["not-a-dict"], USER_A)

    def test_non_dict_activity_raises(self):
        """activity 가 dict 가 아니면 ValueError 가 발생해야 한다."""
        rows = [{"userId": USER_A, "date": "2099-01-02", "activity": "bad"}]
        with self.assertRaises(ValueError):
            build_activity_items(rows, USER_A)


class MapperIntegrationTest(unittest.TestCase):
    """mappers 결과와 연결했을 때의 동작 (CSV 형식 가상 행 사용)."""

    def test_csv_rows_to_response(self):
        """CSV 형식 가상 행 → 매핑 → 응답 조립이 끝까지 이어져야 한다."""
        csv_rows = [
            {"Id": USER_A, "ActivityDate": "1/1/2099", "TotalSteps": "100", "Calories": "900"},
            {"Id": USER_B, "ActivityDate": "1/1/2099", "TotalSteps": "200", "Calories": "950"},
            {"Id": USER_A, "ActivityDate": "bad-date", "TotalSteps": "300", "Calories": "990"},
            {"Id": USER_A, "ActivityDate": "1/2/2099", "TotalSteps": "400",
             "Calories": "1000", "VeryActiveMinutes": "7"},
        ]
        response = build_health_data_response(
            map_fitbit_activity_rows(csv_rows), USER_A, "2099-01-01", "2099-01-31"
        )
        self.assertEqual(
            response["items"],
            [
                {"date": "2099-01-01", "activity": {"totalSteps": 100, "calories": 900}},
                {"date": "2099-01-02",
                 "activity": {"totalSteps": 400, "calories": 1000, "veryActiveMinutes": 7}},
            ],
        )


if __name__ == "__main__":
    unittest.main()
