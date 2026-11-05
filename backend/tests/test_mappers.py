"""mappers 모듈(Fitbit 활동 데이터 매핑)에 대한 단위 테스트.

외부 패키지 없이 파이썬 표준 라이브러리 unittest 만 사용합니다.
테스트 데이터는 모두 가상의 값이며, Database 폴더의 실제 CSV 기록을 복사하지 않았습니다.

실행 방법(backend 폴더 기준):
    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from datetime import date, datetime

# src 패키지를 import 할 수 있도록 backend 폴더를 모듈 검색 경로에 추가합니다.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.mappers import map_fitbit_activity_row, map_fitbit_activity_rows  # noqa: E402


def make_csv_row(**overrides):
    """CSV(csv.DictReader) 형식의 가상 Fitbit 행을 만든다. 값은 모두 문자열."""
    row = {
        "Id": "1000000001",
        "ActivityDate": "1/2/2099",
        "TotalSteps": "1234",
        "TotalDistance": "0.9",
        "VeryActiveMinutes": "5",
        "SedentaryMinutes": "700",
        "Calories": "1000",
    }
    row.update(overrides)
    return row


class FitbitRowNormalMappingTest(unittest.TestCase):
    """정상 데이터 매핑."""

    def test_csv_row_is_mapped(self):
        """CSV 형식 행이 userId/date/activity 구조로 변환되어야 한다.

        기본 make_csv_row 에는 VeryActive/SedentaryMinutes 만 있고 Fairly/Lightly 가 없으므로
        제공된 활동 시간만 포함되고 trackedMinutes 는 만들어지지 않는다.
        """
        result = map_fitbit_activity_row(make_csv_row())
        self.assertEqual(
            result,
            {
                "userId": "1000000001",
                "date": "2099-01-02",
                "activity": {
                    "totalSteps": 1234,
                    "calories": 1000,
                    "veryActiveMinutes": 5,
                    "sedentaryMinutes": 700,
                },
            },
        )
        self.assertNotIn("trackedMinutes", result["activity"])

    def test_user_id_is_string(self):
        """사용자 ID 는 항상 문자열이어야 한다."""
        result = map_fitbit_activity_row(make_csv_row(Id=1000000001))
        self.assertEqual(result["userId"], "1000000001")
        self.assertIsInstance(result["userId"], str)

    def test_float_user_id_has_no_decimal_suffix(self):
        """정수값을 가진 실수 ID 는 '.0' 없이 문자열로 바뀌어야 한다."""
        result = map_fitbit_activity_row(make_csv_row(Id=1000000001.0))
        self.assertEqual(result["userId"], "1000000001")

    def test_user_id_keeps_leading_zero(self):
        """문자열 ID 의 앞자리 0 은 보존되어야 한다."""
        result = map_fitbit_activity_row(make_csv_row(Id=" 0000000123 "))
        self.assertEqual(result["userId"], "0000000123")

    def test_numeric_values_are_accepted(self):
        """값이 문자열이 아니라 숫자로 들어와도 정수로 변환되어야 한다."""
        result = map_fitbit_activity_row(
            make_csv_row(TotalSteps=2345, Calories=1100.0, VeryActiveMinutes="9.0")
        )
        self.assertEqual(result["activity"]["totalSteps"], 2345)
        self.assertEqual(result["activity"]["calories"], 1100)
        self.assertEqual(result["activity"]["veryActiveMinutes"], 9)

    def test_total_distance_is_not_mapped(self):
        """TotalDistance 는 단위 미확정이므로 결과에 포함되지 않아야 한다."""
        result = map_fitbit_activity_row(make_csv_row())
        self.assertNotIn("totalDistance", result["activity"])
        self.assertNotIn("totalDistanceKm", result["activity"])

    def test_unmapped_columns_are_excluded(self):
        """매핑 대상이 아닌 컬럼(TotalDistance 등)은 결과에 들어가지 않아야 한다."""
        result = map_fitbit_activity_row(make_csv_row())
        self.assertEqual(set(result.keys()), {"userId", "date", "activity"})
        self.assertNotIn("totalDistance", result["activity"])


class FitbitTrackedMinutesTest(unittest.TestCase):
    """AI/ML v0.4 tracked_minutes 근거값: 활동 시간 네 컬럼 매핑과 합계(trackedMinutes)."""

    def all_four(self, **overrides):
        """활동 시간 네 컬럼을 모두 담은 가상 행."""
        row = make_csv_row(
            VeryActiveMinutes="20", FairlyActiveMinutes="30",
            LightlyActiveMinutes="200", SedentaryMinutes="600",
        )
        row.update(overrides)
        return row

    def test_all_four_minutes_are_mapped_and_summed(self):
        """네 활동 시간이 모두 있으면 각 값과 trackedMinutes(합계)를 포함해야 한다."""
        activity = map_fitbit_activity_row(self.all_four())["activity"]
        self.assertEqual(activity["veryActiveMinutes"], 20)
        self.assertEqual(activity["fairlyActiveMinutes"], 30)
        self.assertEqual(activity["lightlyActiveMinutes"], 200)
        self.assertEqual(activity["sedentaryMinutes"], 600)
        self.assertEqual(activity["trackedMinutes"], 850)

    def test_valid_zero_is_summed(self):
        """유효한 0 분은 합계에 포함한다(0 으로 채우는 것과 다름)."""
        activity = map_fitbit_activity_row(self.all_four(VeryActiveMinutes="0"))["activity"]
        self.assertEqual(activity["veryActiveMinutes"], 0)
        self.assertEqual(activity["trackedMinutes"], 830)

    def test_one_missing_minute_omits_tracked_minutes(self):
        """네 값 중 하나라도 없으면 trackedMinutes 를 만들지 않는다. 있는 값은 그대로 둔다."""
        row = self.all_four()
        del row["FairlyActiveMinutes"]
        activity = map_fitbit_activity_row(row)["activity"]
        self.assertNotIn("trackedMinutes", activity)
        self.assertNotIn("fairlyActiveMinutes", activity)
        self.assertEqual(activity["veryActiveMinutes"], 20)

    def test_one_invalid_minute_omits_tracked_minutes(self):
        """네 값 중 하나라도 잘못되면(소수·문자) trackedMinutes 를 만들지 않는다."""
        activity = map_fitbit_activity_row(self.all_four(LightlyActiveMinutes="12.5"))["activity"]
        self.assertNotIn("trackedMinutes", activity)
        self.assertNotIn("lightlyActiveMinutes", activity)

    def test_athena_lowercase_minute_columns(self):
        """Athena 소문자 컬럼명으로도 네 값과 합계가 만들어져야 한다."""
        row = {
            "id": "1000000001", "activitydate": "2099-01-02", "totalsteps": "1234",
            "veryactiveminutes": "10", "fairlyactiveminutes": "10",
            "lightlyactiveminutes": "100", "sedentaryminutes": "679",
        }
        activity = map_fitbit_activity_row(row)["activity"]
        self.assertEqual(activity["trackedMinutes"], 799)

    def test_input_row_is_not_modified(self):
        """매핑 함수는 입력 행을 변경하지 않아야 한다(순수 함수)."""
        row = make_csv_row()
        snapshot = dict(row)
        map_fitbit_activity_row(row)
        self.assertEqual(row, snapshot)


class FitbitColumnNameTest(unittest.TestCase):
    """CSV 형식과 Athena 형식의 컬럼명 차이."""

    def test_athena_lowercase_columns(self):
        """Athena 형식(소문자) 컬럼명도 CSV 형식과 같은 결과를 내야 한다."""
        athena_row = {
            "id": "1000000001",
            "activitydate": "2099-01-02",
            "totalsteps": "1234",
            "veryactiveminutes": "5",
            "sedentaryminutes": "700",
            "calories": "1000",
        }
        self.assertEqual(
            map_fitbit_activity_row(athena_row),
            map_fitbit_activity_row(make_csv_row()),
        )

    def test_snake_case_columns(self):
        """밑줄 표기(total_steps 등)도 같은 컬럼으로 인식해야 한다."""
        row = {
            "id": "1000000001",
            "activity_date": "2099-01-02",
            "total_steps": "1234",
            "calories": "1000",
        }
        result = map_fitbit_activity_row(row)
        self.assertEqual(result["date"], "2099-01-02")
        self.assertEqual(result["activity"]["totalSteps"], 1234)

    def test_bom_in_first_column_name(self):
        """UTF-8 BOM 이 붙은 첫 컬럼명(\\ufeffId)도 Id 로 인식해야 한다."""
        row = make_csv_row()
        row["\ufeffId"] = row.pop("Id")
        result = map_fitbit_activity_row(row)
        self.assertEqual(result["userId"], "1000000001")


class FitbitMissingValueTest(unittest.TestCase):
    """누락된 값 처리."""

    def test_missing_very_active_minutes_is_omitted(self):
        """VeryActiveMinutes 컬럼이 없으면 결과에 키 자체가 없어야 한다."""
        row = make_csv_row()
        del row["VeryActiveMinutes"]
        result = map_fitbit_activity_row(row)
        self.assertNotIn("veryActiveMinutes", result["activity"])

    def test_blank_very_active_minutes_is_omitted(self):
        """VeryActiveMinutes 가 빈 문자열이면 결과에 포함하지 않아야 한다."""
        result = map_fitbit_activity_row(make_csv_row(VeryActiveMinutes="  "))
        self.assertNotIn("veryActiveMinutes", result["activity"])

    def test_zero_very_active_minutes_is_kept(self):
        """VeryActiveMinutes 가 0 이면 '실제로 제공된 값'이므로 포함해야 한다."""
        result = map_fitbit_activity_row(make_csv_row(VeryActiveMinutes="0"))
        self.assertEqual(result["activity"]["veryActiveMinutes"], 0)

    def test_missing_steps_and_calories_become_none(self):
        """TotalSteps/Calories 가 없거나 비어 있으면 None 이어야 한다."""
        row = make_csv_row(Calories="")
        del row["TotalSteps"]
        result = map_fitbit_activity_row(row)
        self.assertIsNone(result["activity"]["totalSteps"])
        self.assertIsNone(result["activity"]["calories"])

    def test_invalid_numbers_become_none(self):
        """숫자가 아니거나 소수인 값은 임의로 변환하지 않고 None 이어야 한다."""
        result = map_fitbit_activity_row(
            make_csv_row(TotalSteps="abc", Calories="12.5", VeryActiveMinutes="x")
        )
        self.assertIsNone(result["activity"]["totalSteps"])
        self.assertIsNone(result["activity"]["calories"])
        self.assertNotIn("veryActiveMinutes", result["activity"])

    def test_missing_user_id_raises(self):
        """사용자 ID 가 없으면 ValueError 가 발생해야 한다."""
        row = make_csv_row()
        del row["Id"]
        with self.assertRaises(ValueError):
            map_fitbit_activity_row(row)

    def test_blank_user_id_raises(self):
        """사용자 ID 가 빈 문자열이면 ValueError 가 발생해야 한다."""
        with self.assertRaises(ValueError):
            map_fitbit_activity_row(make_csv_row(Id="   "))

    def test_non_integer_float_user_id_raises(self):
        """소수점 이하가 있는 실수 ID 는 ValueError 가 발생해야 한다."""
        with self.assertRaises(ValueError):
            map_fitbit_activity_row(make_csv_row(Id=12.5))


class FitbitDateTest(unittest.TestCase):
    """날짜 변환 및 잘못된 날짜 처리."""

    def test_csv_date_format(self):
        """M/D/YYYY 형식은 ISO 형식으로 변환되어야 한다."""
        result = map_fitbit_activity_row(make_csv_row(ActivityDate="12/31/2099"))
        self.assertEqual(result["date"], "2099-12-31")

    def test_iso_date_is_kept(self):
        """이미 ISO 형식이면 그대로 유지되어야 한다."""
        result = map_fitbit_activity_row(make_csv_row(ActivityDate="2099-01-02"))
        self.assertEqual(result["date"], "2099-01-02")

    def test_timestamp_string_uses_date_part(self):
        """날짜 뒤에 시간이 붙은 문자열은 날짜 부분만 사용해야 한다."""
        result = map_fitbit_activity_row(
            make_csv_row(ActivityDate="2099-01-02 00:00:00.000")
        )
        self.assertEqual(result["date"], "2099-01-02")

    def test_date_objects(self):
        """date/datetime 객체도 ISO 문자열로 변환되어야 한다."""
        self.assertEqual(
            map_fitbit_activity_row(make_csv_row(ActivityDate=date(2099, 1, 2)))["date"],
            "2099-01-02",
        )
        self.assertEqual(
            map_fitbit_activity_row(
                make_csv_row(ActivityDate=datetime(2099, 1, 2, 9, 30))
            )["date"],
            "2099-01-02",
        )

    def test_invalid_date_becomes_none(self):
        """해석할 수 없는 날짜 문자열은 None 이어야 한다."""
        result = map_fitbit_activity_row(make_csv_row(ActivityDate="not-a-date"))
        self.assertIsNone(result["date"])

    def test_nonexistent_date_becomes_none(self):
        """존재하지 않는 날짜(2월 30일)는 None 이어야 한다."""
        result = map_fitbit_activity_row(make_csv_row(ActivityDate="2/30/2099"))
        self.assertIsNone(result["date"])

    def test_missing_date_becomes_none(self):
        """날짜가 비어 있으면 None 이어야 한다."""
        result = map_fitbit_activity_row(make_csv_row(ActivityDate=""))
        self.assertIsNone(result["date"])


class FitbitRowsAndInputTypeTest(unittest.TestCase):
    """여러 행 변환과 잘못된 입력 타입."""

    def test_rows_keep_order(self):
        """여러 행을 변환하면 입력 순서가 유지되어야 한다."""
        rows = [
            make_csv_row(ActivityDate="1/1/2099"),
            make_csv_row(ActivityDate="1/2/2099"),
        ]
        result = map_fitbit_activity_rows(rows)
        self.assertEqual([item["date"] for item in result], ["2099-01-01", "2099-01-02"])

    def test_empty_rows(self):
        """빈 목록은 빈 목록으로 변환되어야 한다."""
        self.assertEqual(map_fitbit_activity_rows([]), [])

    def test_non_dict_row_raises(self):
        """dict 가 아닌 행은 ValueError 가 발생해야 한다."""
        with self.assertRaises(ValueError):
            map_fitbit_activity_row(["not", "a", "dict"])

    def test_non_list_rows_raises(self):
        """행 목록이 list 가 아니면 ValueError 가 발생해야 한다."""
        with self.assertRaises(ValueError):
            map_fitbit_activity_rows("not-a-list")


if __name__ == "__main__":
    unittest.main()
