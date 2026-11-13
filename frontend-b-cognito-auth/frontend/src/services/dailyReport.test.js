import {
  buildDailyReport,
  formatReportMessage,
  formatScheduleSummary,
  shouldShowReport,
} from "./dailyReport";
import { loadReportSettings } from "./reportSettingsStorage";

const series = (values) => values.map((value, i) => ({ label: String(i), value }));

const settings = (patch = {}) => ({
  enabled: true,
  time: "08:00",
  stepGoal: 10000,
  lastShownDate: "",
  days: [0, 1, 2, 3, 4, 5, 6],
  include: { steps: true, sleep: true, heartRate: false },
  ...patch,
});

test("요일 필터: 선택하지 않은 요일에는 표시하지 않는다", () => {
  const monday = new Date(2024, 0, 8, 8, 1); // 2024-01-08 월요일
  expect(shouldShowReport(settings({ days: [1] }), monday)).toBe(true);
  expect(shouldShowReport(settings({ days: [2, 3] }), monday)).toBe(false);
  // days 가 없는 예전 설정은 매일로 취급
  const legacy = settings();
  delete legacy.days;
  expect(shouldShowReport(legacy, monday)).toBe(true);
});

test("수신 시간 요약 문구", () => {
  expect(formatScheduleSummary(settings())).toBe("매일 오전 8:00에 받아요");
  expect(formatScheduleSummary(settings({ days: [1, 2, 3, 4, 5], time: "21:00" }))).toBe("평일 오후 9:00에 받아요");
  expect(formatScheduleSummary(settings({ days: [0, 6] }))).toBe("주말 오전 8:00에 받아요");
  expect(formatScheduleSummary(settings({ days: [1, 3, 5], time: "21:00" }))).toBe("월·수·금 오후 9:00에 받아요");
  expect(formatScheduleSummary(settings({ enabled: false }))).toBe("리포트 알림이 꺼져 있어요");
});

test("남은 걸음, 수면 평가, 어제 대비를 계산한다", () => {
  const ts = { steps: series([8000, 7200]), sleep: series([7, 5.5]), heartRate: series([60, 62]) };
  const r = buildDailyReport(ts, 10000);
  expect(r.remaining).toBe(2800);
  expect(r.sleepVerdict).toBe("부족");
  expect(r.stepsDelta.text).toBe("−800걸음");
  expect(r.sleepDelta.verdict).toBe("worse");
  expect(r.heartRate).toBe(62);
  expect(r.comment).toMatch(/남았어요|산책/);
  expect(buildDailyReport({ steps: series([12000]), sleep: series([8.5]) }, 10000).remaining).toBe(0);
});

test("데이터가 없으면 예시 데이터로 대체하고 isSample 로 표시한다", () => {
  const r = buildDailyReport({ sleep: [], heartRate: [], steps: [] }, 10000);
  expect(r.isSample).toBe(true);
  expect(Number.isFinite(r.steps)).toBe(true);
  expect(r.stepsDelta).toBeNull();
  expect(r.sourceLabel).toBeNull();
  expect(buildDailyReport(null, 10000, { sourceLabel: "삼성 헬스" }).sourceLabel).toBe("삼성 헬스");
});

test("formatReportMessage: include 생략 시 기존 문자열과 같고, 선택 항목만 포함한다", () => {
  const r = buildDailyReport({ steps: series([7200]), sleep: series([7.2]), heartRate: series([61]) }, 10000);
  expect(formatReportMessage(r)).toBe("오늘 걸음수 7,200 / 10,000걸음 (72%) · 수면 7시간 12분");
  expect(formatReportMessage(r, { steps: false, sleep: true, heartRate: true })).toBe("수면 7시간 12분 · 안정 시 심박 61bpm");
});

test("저장 설정 불러오기: 예전 저장값은 기본 요일·항목과 병합된다", () => {
  localStorage.setItem("wearcare.dailyReport", JSON.stringify({ enabled: true, time: "09:30" }));
  const s = loadReportSettings();
  expect(s.days).toEqual([0, 1, 2, 3, 4, 5, 6]);
  expect(s.include).toEqual({ steps: true, sleep: true, heartRate: false });
  localStorage.setItem("wearcare.dailyReport", JSON.stringify({ days: [9, "x"], include: { steps: false, sleep: false, heartRate: false } }));
  const bad = loadReportSettings();
  expect(bad.days).toHaveLength(7);
  expect(bad.include.steps).toBe(true);
  localStorage.clear();
});
