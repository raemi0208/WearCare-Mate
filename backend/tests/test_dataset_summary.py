"""dataset_summary 모듈 단위 테스트 (발표용 별도 데이터셋 요약 집계).

- AWS 에 접속하지 않는다. Athena 클라이언트는 가짜(FakeSummaryClient)를 주입한다.
- 집계 SQL 의 테이블/경로 제한, 값 변환, 빈 결과, 개별 실패 격리를 검증한다.
- 상담 원문·개인정보가 쿼리/응답에 들어가지 않는지(COUNT 만) 확인한다.
- 수면 분포(최소·최대·5개 버킷·합계·upperInclusive)와 심박 날짜별 시계열을 검증한다.

⚠ 이 파일의 버킷 건수·최솟값·최댓값·행 수는 모두 '로컬 테스트용' 모조 값이다.
   Athena 실측값이 아니며, 소스의 집계·검증 규칙(합계 일치, 파싱 실패/빈 결과 구분 등)을
   확인하기 위해 서로 일관되게 구성한 값이다.
"""

import os
import sys
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src import dataset_summary  # noqa: E402
from src.dataset_summary import build_dataset_summaries, is_enabled  # noqa: E402

def result_page(columns, values, next_token=None):
    """헤더 행 + 데이터 1행으로 집계 결과 페이지를 만든다."""
    page = {
        "ResultSet": {
            "Rows": [
                {"Data": [{"VarCharValue": c} for c in columns]},
                {"Data": [({} if v is None else {"VarCharValue": v}) for v in values]},
            ],
            "ResultSetMetadata": {
                "ColumnInfo": [{"Name": c, "Type": "varchar"} for c in columns]
            },
        }
    }
    if next_token is not None:
        page["NextToken"] = next_token
    return page

def multi_row_page(columns, rows, include_header=True, next_token=None):
    """여러 데이터 행을 담은 결과 페이지. include_header=False 면 후속 페이지(헤더 없음)."""
    data_rows = []
    if include_header:
        data_rows.append({"Data": [{"VarCharValue": c} for c in columns]})
    for values in rows:
        data_rows.append(
            {"Data": [({} if v is None else {"VarCharValue": v}) for v in values]}
        )
    page = {
        "ResultSet": {
            "Rows": data_rows,
            "ResultSetMetadata": {
                "ColumnInfo": [{"Name": c, "Type": "varchar"} for c in columns]
            },
        }
    }
    if next_token is not None:
        page["NextToken"] = next_token
    return page

def header_only_page(columns):
    """헤더만 있고 데이터 행이 없는 결과(= 집계 데이터 행 자체가 없음 → 잘못된 응답)."""
    return {
        "ResultSet": {
            "Rows": [{"Data": [{"VarCharValue": c} for c in columns]}],
            "ResultSetMetadata": {
                "ColumnInfo": [{"Name": c, "Type": "varchar"} for c in columns]
            },
        }
    }

class FakeSummaryClient:
    """집계 쿼리를 흉내 내는 가짜 Athena 클라이언트.

    responses: SQL 실행 순서대로 돌려줄 결과 '응답'. 각 응답은
        - dict(page): 단일 페이지
        - list[dict]: 페이지네이션(get_query_results 가 순서대로 한 페이지씩 반환)
    fail_on_substring: QueryString 에 이 문자열이 있으면 해당 쿼리만 실패시킨다(개별 격리 테스트용).
    """

    def __init__(self, responses, fail_on_substring=None):
        self._responses = list(responses)
        self._index = 0
        self._page_cursor = 0
        self.fail_on_substring = fail_on_substring
        self.started_sql = []
        self._fail_qids = set()

    def start_query_execution(self, **kwargs):
        sql = kwargs["QueryString"]
        self.started_sql.append(sql)
        qid = f"qid-{len(self.started_sql)}"
        if self.fail_on_substring and self.fail_on_substring in sql:
            self._fail_qids.add(qid)
        return {"QueryExecutionId": qid}

    def get_query_execution(self, **kwargs):
        qid = kwargs["QueryExecutionId"]
        state = "FAILED" if qid in self._fail_qids else "SUCCEEDED"
        return {"QueryExecution": {"Status": {"State": state}}}

    def get_query_results(self, **kwargs):
        current = self._responses[self._index]
        if isinstance(current, list):
            page = current[self._page_cursor]
            self._page_cursor += 1
            if self._page_cursor >= len(current):
                self._index += 1
                self._page_cursor = 0
            return page
        self._index += 1
        return current

# ---- 소스의 현재 SQL 별칭 순서와 일치시킨다 (로컬 테스트용 모조 컬럼) ----
SLEEP_COLS = [
    "record_count", "average_hours", "minimum_hours", "maximum_hours",
    "bucket_0", "bucket_1", "bucket_2", "bucket_3", "bucket_4",
]
HEART_SUMMARY_COLS = [
    "total_rows", "numeric_rows", "zero_rows", "positive_rows",
    "avg_all", "avg_positive", "invalid_date_rows",
]
HEART_DAILY_COLS = ["day", "avg_positive", "included_rows"]
PSY_COLS = ["cnt"]

# ---- 로컬 테스트용 모조 값 (Athena 실측값 아님) ----
# 수면: record_count=1000, 버킷 합=1000(20+120+600+230+30). min/max 는 임의.
SLEEP_OK_VALUES = ["1000", "7.47", "3.2", "11.8", "20", "120", "600", "230", "30"]
SLEEP_BUCKET_COUNTS = [20, 120, 600, 230, 30]

# 심박(정상): 소규모·일관. totalRows=1616, positiveRows=1610, zeroRows=6, invalidDateRows=0.
# dailySeries 양수 합 = 800+810+0 = 1610 == positiveRows. (마지막 날짜는 양수 없음)
HEART_SUMMARY_OK = ["1616", "1616", "6", "1610", "79.3", "79.9", "0"]
HEART_DAILY_ROWS = [
    ["2025-10-15", "78.5", "800"],
    ["2025-10-16", "80.1", "810"],
    ["2025-11-20", None, "0"],  # 유효 날짜지만 양수 없음 → averageValue=None, includedRows=0
]
HEART_DAILY_POSITIVE_SUM = 1610  # == positiveRows (invalidDateRows=0 이므로 일치)

def ok_responses():
    """세 집계가 모두 성공하는 응답 순서:
    sleep, heart(요약), heart(날짜별), psy_integrated, psy_validation."""
    return [
        result_page(SLEEP_COLS, SLEEP_OK_VALUES),
        result_page(HEART_SUMMARY_COLS, HEART_SUMMARY_OK),
        multi_row_page(HEART_DAILY_COLS, HEART_DAILY_ROWS),
        result_page(PSY_COLS, ["1328"]),
        result_page(PSY_COLS, ["175"]),
    ]

ENV = {"ENABLE_DATASET_SUMMARY": "true"}

class DatasetSummarySuccessTest(unittest.TestCase):
    def setUp(self):
        self.client = FakeSummaryClient(ok_responses())
        self.summaries = build_dataset_summaries(
            client_factory=lambda region: self.client, environ=ENV
        )

    def test_sleep_summary_values(self):
        s = self.summaries["sleepDatasetSummary"]
        self.assertEqual(s["status"], "ok")
        self.assertEqual(s["sourceLabel"], "별도 데이터셋")
        self.assertEqual(s["recordCount"], 1000)
        self.assertEqual(s["averageHours"], 7.47)

    def test_sleep_min_max_are_local_test_values(self):
        # 로컬 테스트용 최솟값/최댓값 (실측 아님)
        s = self.summaries["sleepDatasetSummary"]
        self.assertEqual(s["minimumHours"], 3.2)
        self.assertEqual(s["maximumHours"], 11.8)

    def test_sleep_distribution_sum_equals_record_count(self):
        s = self.summaries["sleepDatasetSummary"]
        dist = s["distribution"]
        self.assertEqual(len(dist), 5)
        self.assertEqual([b["count"] for b in dist], SLEEP_BUCKET_COUNTS)
        self.assertEqual(sum(b["count"] for b in dist), s["recordCount"])

    def test_sleep_distribution_upper_inclusive_flags(self):
        """앞 네 구간은 상한 미포함(False), 마지막 구간([10,24])만 포함(True)."""
        dist = self.summaries["sleepDatasetSummary"]["distribution"]
        self.assertEqual([b["upperInclusive"] for b in dist],
                         [False, False, False, False, True])
        self.assertEqual(dist[-1]["lowerHours"], 10)
        self.assertEqual(dist[-1]["upperHours"], 24)

    def test_sleep_last_bucket_sql_includes_upper_bound(self):
        """마지막 구간만 <= 24, 중간 구간은 < 로 상한 미포함."""
        sleep_sql = self.client.started_sql[0]
        self.assertIn("<= 24", sleep_sql)
        self.assertIn("< 4", sleep_sql)

    def test_heart_rate_summary_values(self):
        h = self.summaries["heartRateDatasetSummary"]
        self.assertEqual(h["status"], "ok")
        self.assertEqual(h["totalRows"], 1616)
        self.assertEqual(h["zeroRows"], 6)
        self.assertEqual(h["positiveRows"], 1610)
        # 0 값이 존재하므로 대표값은 양수 평균(결측 추정 제외) — 기존 정책 보존
        self.assertEqual(h["averageBasis"], "positive")
        self.assertEqual(h["averageValue"], 79.9)

    def test_heart_unit_is_unconfirmed(self):
        h = self.summaries["heartRateDatasetSummary"]
        self.assertIsNone(h["unit"])
        self.assertEqual(h["unitBasis"], "unconfirmed")

    def test_heart_daily_series_consistent_with_positive_rows(self):
        """invalidDateRows=0 이면 dailySeries 의 includedRows 합 == positiveRows."""
        h = self.summaries["heartRateDatasetSummary"]
        self.assertEqual(h["invalidDateRows"], 0)
        series = h["dailySeries"]
        self.assertEqual([d["date"] for d in series],
                         ["2025-10-15", "2025-10-16", "2025-11-20"])
        self.assertEqual(sum(d["includedRows"] for d in series), h["positiveRows"])
        self.assertEqual(series[0]["averageValue"], 78.5)
        self.assertEqual(series[0]["includedRows"], 800)
        # 양수 없는 날짜: averageValue=None, includedRows=0 (0 으로 채우지 않음)
        self.assertIsNone(series[2]["averageValue"])
        self.assertEqual(series[2]["includedRows"], 0)

    def test_psychology_summary_is_per_file_counts(self):
        p = self.summaries["psychologyDatasetSummary"]
        self.assertEqual(p["status"], "ok")
        self.assertEqual(p["unit"], "데이터 행 수")
        by_id = {f["id"]: f["rowCount"] for f in p["files"]}
        self.assertEqual(by_id, {"integrated": 1328, "validation": 175})

    def test_sleep_query_restricts_table_and_path(self):
        sleep_sql = self.client.started_sql[0]
        self.assertIn("wearable_sleep_table_fixed", sleep_sql)
        self.assertIn(dataset_summary.SLEEP_PATH, sleep_sql)
        self.assertIn('"$path"', sleep_sql)
        self.assertIn("BETWEEN 0 AND 24", sleep_sql)

    def test_psychology_queries_only_count_no_pii(self):
        """심리상담 SQL 은 COUNT 만. 원문/점수/ID 컬럼을 선택하지 않는다."""
        psy_sqls = [s for s in self.client.started_sql if "psychology_csv_check" in s]
        self.assertEqual(len(psy_sqls), 2)
        for sql in psy_sqls:
            self.assertIn("COUNT(*)", sql)
            for forbidden in ("consult_text", "depression", "anxiety", "addiction",
                              "userid", "age", "gender"):
                self.assertNotIn(forbidden, sql)
        self.assertTrue(any(dataset_summary.PSYCHOLOGY_INTEGRATED_PATH in s for s in psy_sqls))
        self.assertTrue(any(dataset_summary.PSYCHOLOGY_VALIDATION_PATH in s for s in psy_sqls))

class DatasetSummaryEmptyVsErrorTest(unittest.TestCase):
    """수면: '데이터 행 자체 없음' = error, 'COUNT=0' = empty 로 구분한다."""

    def test_sleep_no_rows_is_error(self):
        """집계 결과에 데이터 행이 아예 없으면(헤더만) 잘못된 응답 → error."""
        client = FakeSummaryClient([
            header_only_page(SLEEP_COLS),  # 데이터 행 없음
            result_page(HEART_SUMMARY_COLS, HEART_SUMMARY_OK),
            multi_row_page(HEART_DAILY_COLS, HEART_DAILY_ROWS),
            result_page(PSY_COLS, ["1328"]),
            result_page(PSY_COLS, ["175"]),
        ])
        summaries = build_dataset_summaries(client_factory=lambda r: client, environ=ENV)
        s = summaries["sleepDatasetSummary"]
        self.assertEqual(s["status"], "error")

    def test_sleep_count_zero_is_empty(self):
        """COUNT=0 인 집계 응답만 empty. 평균/분포는 비운다(0 으로 채우지 않음)."""
        client = FakeSummaryClient([
            result_page(SLEEP_COLS, ["0", None, None, None, "0", "0", "0", "0", "0"]),
            result_page(HEART_SUMMARY_COLS, HEART_SUMMARY_OK),
            multi_row_page(HEART_DAILY_COLS, HEART_DAILY_ROWS),
            result_page(PSY_COLS, ["1328"]),
            result_page(PSY_COLS, ["175"]),
        ])
        summaries = build_dataset_summaries(client_factory=lambda r: client, environ=ENV)
        s = summaries["sleepDatasetSummary"]
        self.assertEqual(s["status"], "empty")
        self.assertIsNone(s["averageHours"])
        self.assertEqual(s["distribution"], [])

    def test_heart_count_zero_is_empty(self):
        """심박 totalRows=0 이면 empty. 날짜별 쿼리는 실행되지 않는다."""
        client = FakeSummaryClient([
            result_page(SLEEP_COLS, SLEEP_OK_VALUES),
            result_page(HEART_SUMMARY_COLS, ["0", "0", "0", "0", None, None, "0"]),
            result_page(PSY_COLS, ["1328"]),
            result_page(PSY_COLS, ["175"]),
        ])
        summaries = build_dataset_summaries(client_factory=lambda r: client, environ=ENV)
        self.assertEqual(summaries["heartRateDatasetSummary"]["status"], "empty")
        self.assertEqual(summaries["heartRateDatasetSummary"]["dailySeries"], [])
        self.assertEqual(summaries["psychologyDatasetSummary"]["files"][0]["rowCount"], 1328)

class DatasetSummaryBadResponseTest(unittest.TestCase):
    """잘못된 응답(버킷 합 불일치·음수·파싱 실패)은 error 로 처리한다(검증 약화 금지)."""

    def _sleep_summary_for(self, sleep_values):
        client = FakeSummaryClient([
            result_page(SLEEP_COLS, sleep_values),
            result_page(HEART_SUMMARY_COLS, HEART_SUMMARY_OK),
            multi_row_page(HEART_DAILY_COLS, HEART_DAILY_ROWS),
            result_page(PSY_COLS, ["1328"]),
            result_page(PSY_COLS, ["175"]),
        ])
        return build_dataset_summaries(
            client_factory=lambda r: client, environ=ENV)["sleepDatasetSummary"]

    def test_bucket_sum_mismatch_is_error(self):
        # 합계 999 ≠ record_count 1000
        bad = ["1000", "7.47", "3.2", "11.8", "20", "120", "600", "230", "29"]
        self.assertEqual(self._sleep_summary_for(bad)["status"], "error")

    def test_negative_bucket_is_error(self):
        bad = ["1000", "7.47", "3.2", "11.8", "-1", "121", "600", "230", "50"]
        self.assertEqual(self._sleep_summary_for(bad)["status"], "error")

    def test_unparsable_bucket_is_error(self):
        bad = ["1000", "7.47", "3.2", "11.8", "x", "120", "600", "230", "30"]
        self.assertEqual(self._sleep_summary_for(bad)["status"], "error")

    def test_heart_positive_count_without_avg_is_error(self):
        """날짜별: 양수 건수(included_rows>0)인데 평균 파싱 실패면 error."""
        client = FakeSummaryClient([
            result_page(SLEEP_COLS, SLEEP_OK_VALUES),
            result_page(HEART_SUMMARY_COLS, HEART_SUMMARY_OK),
            multi_row_page(HEART_DAILY_COLS, [["2025-10-15", None, "800"]]),
            result_page(PSY_COLS, ["1328"]),
            result_page(PSY_COLS, ["175"]),
        ])
        summaries = build_dataset_summaries(client_factory=lambda r: client, environ=ENV)
        self.assertEqual(summaries["heartRateDatasetSummary"]["status"], "error")

class DatasetSummaryInvalidDatesTest(unittest.TestCase):
    """날짜 파싱 실패 행(invalidDateRows)과 날짜별 집계의 일관성(소규모 데이터)."""

    def test_invalid_date_rows_consistent_with_totals(self):
        # 소규모 일관 데이터:
        #   totalRows=1628, positiveRows=1610, zeroRows=6, invalidDateRows=12
        #   유효 날짜 양수 합 = 800 + 810 = 1610 == positiveRows
        #   (invalidDateRows=12 는 날짜 파싱이 안 된 행 수. 양수/0 여부와 무관하게 '날짜' 기준)
        heart_summary = ["1628", "1628", "6", "1610", "79.3", "79.9", "12"]
        daily = [
            ["2025-10-15", "78.5", "800"],
            ["2025-10-16", "80.1", "810"],
        ]
        client = FakeSummaryClient([
            result_page(SLEEP_COLS, SLEEP_OK_VALUES),
            result_page(HEART_SUMMARY_COLS, heart_summary),
            multi_row_page(HEART_DAILY_COLS, daily),
            result_page(PSY_COLS, ["1328"]),
            result_page(PSY_COLS, ["175"]),
        ])
        h = build_dataset_summaries(
            client_factory=lambda r: client, environ=ENV)["heartRateDatasetSummary"]
        self.assertEqual(h["status"], "ok")
        self.assertEqual(h["invalidDateRows"], 12)
        self.assertEqual(h["positiveRows"], 1610)
        # 날짜별 포함 건수 합이 양수 행 수와 일치(빠진 양수 행은 최대 invalidDateRows 범위)
        self.assertEqual(sum(d["includedRows"] for d in h["dailySeries"]), h["positiveRows"])

class DatasetSummaryPaginationTest(unittest.TestCase):
    """다중 행 결과의 페이지네이션(NextToken)과 헤더 1회 제거를 검증한다."""

    def test_daily_series_spans_multiple_pages(self):
        # 날짜별 결과를 2페이지로 나눠 반환. 첫 페이지에만 헤더. 합계는 positiveRows 와 일치.
        daily_pages = [
            multi_row_page(HEART_DAILY_COLS, [["2025-10-15", "78.5", "800"]],
                           include_header=True, next_token="t1"),
            multi_row_page(HEART_DAILY_COLS, [["2025-10-16", "80.1", "810"]],
                           include_header=False),
        ]
        client = FakeSummaryClient([
            result_page(SLEEP_COLS, SLEEP_OK_VALUES),
            result_page(HEART_SUMMARY_COLS, HEART_SUMMARY_OK),  # positiveRows=1610
            daily_pages,
            result_page(PSY_COLS, ["1328"]),
            result_page(PSY_COLS, ["175"]),
        ])
        h = build_dataset_summaries(
            client_factory=lambda r: client, environ=ENV)["heartRateDatasetSummary"]
        series = h["dailySeries"]
        # 두 페이지가 합쳐지고, 첫 데이터 행이 헤더로 오인돼 유실되지 않아야 한다.
        self.assertEqual([d["date"] for d in series], ["2025-10-15", "2025-10-16"])
        self.assertEqual([d["includedRows"] for d in series], [800, 810])
        self.assertEqual(sum(d["includedRows"] for d in series), h["positiveRows"])

class DatasetSummaryIsolationTest(unittest.TestCase):
    def test_one_query_failure_does_not_break_others(self):
        """심박 집계만 실패해도 수면·심리상담은 정상 반환된다."""
        client = FakeSummaryClient(
            [
                result_page(SLEEP_COLS, SLEEP_OK_VALUES),
                # heart 쿼리는 fail_on_substring 으로 실패 → 날짜별 쿼리는 실행되지 않음
                result_page(PSY_COLS, ["1328"]),
                result_page(PSY_COLS, ["175"]),
            ],
            fail_on_substring="heart_rate_table",
        )
        summaries = build_dataset_summaries(client_factory=lambda r: client, environ=ENV)
        self.assertEqual(summaries["sleepDatasetSummary"]["status"], "ok")
        self.assertEqual(summaries["heartRateDatasetSummary"]["status"], "error")
        self.assertIsNone(summaries["heartRateDatasetSummary"]["totalRows"])
        self.assertEqual(summaries["psychologyDatasetSummary"]["status"], "ok")

    def test_setup_failure_marks_all_error(self):
        """클라이언트 생성 실패 시 세 필드 모두 error, 값은 None."""
        def boom(region):
            raise RuntimeError("no client")
        summaries = build_dataset_summaries(client_factory=boom, environ=ENV)
        for key in ("sleepDatasetSummary", "heartRateDatasetSummary", "psychologyDatasetSummary"):
            self.assertEqual(summaries[key]["status"], "error")

class DatasetSummaryEnableTest(unittest.TestCase):
    def test_is_enabled_switch(self):
        self.assertTrue(is_enabled({"ENABLE_DATASET_SUMMARY": "true"}))
        self.assertTrue(is_enabled({"ENABLE_DATASET_SUMMARY": "TRUE"}))
        self.assertFalse(is_enabled({"ENABLE_DATASET_SUMMARY": "false"}))
        self.assertFalse(is_enabled({}))

if __name__ == "__main__":
    unittest.main()


class SleepMovementSummaryTest(unittest.TestCase):
    def summary(self, count, average):
        columns = SLEEP_COLS + ["movement_count", "average_movement"]
        client = FakeSummaryClient([result_page(columns, SLEEP_OK_VALUES + [count, average])])
        result = dataset_summary._sleep_summary(client, dataset_summary._summary_config(ENV))
        self.assertIn("TRY_CAST(movement_during_sleep AS double) >= 0", client.started_sql[0])
        self.assertIn(dataset_summary.SLEEP_PATH, client.started_sql[0])
        return result

    def test_movement_average_and_count_come_from_query(self):
        result = self.summary("970", "2.01346")
        self.assertEqual(result["averageMovement"], 2.013)
        self.assertEqual(result["movementRecordCount"], 970)
        self.assertEqual(result["movementStatus"], "ok")
        self.assertIsNone(result["movementUnit"])

    def test_no_movement_records_is_not_zero_average(self):
        result = self.summary("0", None)
        self.assertIsNone(result["averageMovement"])
        self.assertEqual(result["movementStatus"], "empty")
        self.assertEqual(result["status"], "ok")

    def test_invalid_movement_does_not_destroy_valid_sleep_duration(self):
        for count, average in [("1001", "2"), ("2", "NaN"), ("2", "-1")]:
            result = self.summary(count, average)
            self.assertEqual(result["movementStatus"], "error")
            self.assertIsNone(result["averageMovement"])
            self.assertEqual(result["averageHours"], 7.47)
