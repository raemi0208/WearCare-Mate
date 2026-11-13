// WearCare Mate - 일일 리포트 계산 유틸
import { timeseries as sampleTimeseries } from "../data/mockData";
import { compareYesterday } from "../utils/compareYesterday";

// 수면 목표(시간)
const SLEEP_GOAL_HOURS = 7;

// 요일 라벨(0=일 ~ 6=토)
export const DAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

// 시계열의 마지막(가장 최근) 값을 읽는다.
function lastValue(series) {
  if (!Array.isArray(series) || series.length === 0) return null;
  const v = series[series.length - 1]?.value;
  return typeof v === "number" ? v : null;
}

// 수면 평가: 6시간 미만 부족 / 6~8시간 적정 / 8시간 초과 충분
function sleepVerdictOf(hours) {
  if (hours < SLEEP_GOAL_HOURS - 1) return "부족";
  if (hours > SLEEP_GOAL_HOURS + 1) return "충분";
  return "적정";
}

// 달성률과 수면 평가를 조합한 한 줄 코멘트(규칙 기반 템플릿)
function buildComment(percent, remaining, verdict) {
  let steps;
  if (percent >= 100) steps = "목표 걸음을 달성했어요.";
  else if (percent >= 70) steps = `목표까지 ${remaining.toLocaleString("ko-KR")}걸음 남았어요.`;
  else steps = "오늘은 가벼운 산책으로 활동량을 채워 보세요.";
  let sleep;
  if (verdict === "부족") sleep = "수면이 부족했으니 오늘은 일찍 쉬어 보세요.";
  else if (verdict === "충분") sleep = "잠을 충분히 잤어요.";
  else sleep = "수면은 적정해요.";
  return `${steps} ${sleep}`;
}

// 걸음수/수면 리포트 계산. 데이터가 없으면 예시 데이터로 대체하고 isSample 로 표시한다.
// options.sourceLabel: 리포트 기준 앱 이름(예: "삼성 헬스")
export function buildDailyReport(timeseries, stepGoal, options = {}) {
  const steps = lastValue(timeseries?.steps);
  const sleep = lastValue(timeseries?.sleep);
  const isSample = steps == null || sleep == null;
  const s = steps ?? lastValue(sampleTimeseries.steps);
  const sl = sleep ?? lastValue(sampleTimeseries.sleep);
  const goal = Number(stepGoal) > 0 ? Number(stepGoal) : 10000;
  const percent = Math.round((s / goal) * 100);
  const remaining = Math.max(goal - s, 0);
  const verdict = sleepVerdictOf(sl);

  // 어제 대비(해당 지표에 어제 값이 없으면 null)
  const compare = compareYesterday(timeseries);
  const find = (id) => compare.items.find((i) => i.id === id) || null;
  const stepsItem = find("steps");
  const sleepItem = find("sleep");

  return {
    steps: s,
    goal,
    percent,
    sleepHours: sl,
    isSample,
    remaining,
    sleepGoal: SLEEP_GOAL_HOURS,
    sleepVerdict: verdict,
    stepsDelta: stepsItem ? { text: stepsItem.text, verdict: stepsItem.verdict } : null,
    sleepDelta: sleepItem ? { text: sleepItem.text, verdict: sleepItem.verdict } : null,
    heartRate: lastValue(timeseries?.heartRate),
    comment: buildComment(percent, remaining, verdict),
    sourceLabel: options.sourceLabel || null,
  };
}

// "오늘 걸음수 7,200 / 10,000걸음 (72%) · 수면 7시간 12분" 형태의 문자열
export function formatSleep(hours) {
  const total = Math.round(hours * 60);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return m === 0 ? `${h}시간` : `${h}시간 ${m}분`;
}

// include 를 생략하면 걸음수·수면 두 항목(기존 형식)을 모두 포함한다.
export function formatReportMessage(report, include = { steps: true, sleep: true, heartRate: false }) {
  const parts = [];
  if (include.steps) {
    parts.push(`오늘 걸음수 ${report.steps.toLocaleString("ko-KR")} / ${report.goal.toLocaleString("ko-KR")}걸음 (${report.percent}%)`);
  }
  if (include.sleep) parts.push(`수면 ${formatSleep(report.sleepHours)}`);
  if (include.heartRate && report.heartRate != null) parts.push(`안정 시 심박 ${report.heartRate}bpm`);
  return parts.join(" · ");
}

// 로컬 시간대 기준 YYYY-MM-DD
export function todayString(now = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

// 리포트를 지금 표시해야 하는지 판단: ON, 오늘 요일 선택됨, 오늘 아직 안 보여줌, 설정 시각 이후 5분 이내
export function shouldShowReport(settings, now = new Date()) {
  if (!settings.enabled) return false;
  if (Array.isArray(settings.days) && !settings.days.includes(now.getDay())) return false;
  if (settings.lastShownDate === todayString(now)) return false;
  const [h, m] = settings.time.split(":").map(Number);
  const target = new Date(now.getFullYear(), now.getMonth(), now.getDate(), h, m, 0, 0);
  const diff = now.getTime() - target.getTime();
  return diff >= 0 && diff <= 5 * 60 * 1000;
}

// "HH:MM" → "오전 8:00" / "오후 9:00"
function formatClock(time) {
  const [h, m] = String(time).split(":").map(Number);
  const period = h < 12 ? "오전" : "오후";
  const hour12 = h % 12 === 0 ? 12 : h % 12;
  return `${period} ${hour12}:${String(m).padStart(2, "0")}`;
}

// 수신 일정 요약 문구: "매일 오전 8:00에 받아요", "평일 …", "주말 …", "월·수·금 오후 9:00에 받아요"
export function formatScheduleSummary(settings) {
  if (!settings.enabled) return "리포트 알림이 꺼져 있어요";
  const days = Array.isArray(settings.days) ? [...new Set(settings.days)].sort((a, b) => a - b) : [0, 1, 2, 3, 4, 5, 6];
  if (days.length === 0) return "수신 요일이 선택되지 않았어요";
  const same = (target) => days.length === target.length && target.every((d) => days.includes(d));
  let dayText;
  if (days.length === 7) dayText = "매일";
  else if (same([1, 2, 3, 4, 5])) dayText = "평일";
  else if (same([0, 6])) dayText = "주말";
  else dayText = [1, 2, 3, 4, 5, 6, 0].filter((d) => days.includes(d)).map((d) => DAY_LABELS[d]).join("·");
  return `${dayText} ${formatClock(settings.time)}에 받아요`;
}
