// WearCare Mate - 일일 리포트 알림 설정 로컬 저장소
//
// 알림 ON/OFF, 수신 시간, 목표 걸음수, 마지막 표시 날짜를 브라우저 localStorage에 저장합니다.

const STORAGE_KEY = "wearcare.dailyReport";

export const DEFAULT_REPORT_SETTINGS = {
  enabled: false,
  time: "21:00",
  stepGoal: 10000,
  lastShownDate: "",
  // 수신 요일(0=일 ~ 6=토). 기본은 매일
  days: [0, 1, 2, 3, 4, 5, 6],
  // 리포트에 포함할 항목
  include: { steps: true, sleep: true, heartRate: false },
};

// 브라우저 환경이 아니거나 localStorage 접근이 막힌 경우를 안전하게 처리
function isAvailable() {
  try {
    return typeof window !== "undefined" && !!window.localStorage;
  } catch {
    return false;
  }
}

// 저장값과 기본값을 병합해 읽기 (잘못된 형식은 기본값으로 대체)
export function loadReportSettings() {
  if (!isAvailable()) return { ...DEFAULT_REPORT_SETTINGS };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const saved = raw ? JSON.parse(raw) : {};
    const merged = {
      ...DEFAULT_REPORT_SETTINGS,
      ...saved,
      include: { ...DEFAULT_REPORT_SETTINGS.include, ...(saved && typeof saved.include === "object" ? saved.include : {}) },
    };
    // 요일: 0~6 정수만 남기고 중복 제거. 비었거나 잘못되면 매일
    const days = Array.isArray(merged.days)
      ? [...new Set(merged.days.filter((d) => Number.isInteger(d) && d >= 0 && d <= 6))].sort((a, b) => a - b)
      : [];
    merged.days = days.length > 0 ? days : [...DEFAULT_REPORT_SETTINGS.days];
    // 포함 항목은 불리언으로 정리하고, 걸음수는 최소 1개 유지를 위해 모두 꺼져 있으면 걸음수를 켠다
    merged.include = {
      steps: merged.include.steps === true,
      sleep: merged.include.sleep === true,
      heartRate: merged.include.heartRate === true,
    };
    if (!merged.include.steps && !merged.include.sleep && !merged.include.heartRate) merged.include.steps = true;
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(merged.time)) merged.time = DEFAULT_REPORT_SETTINGS.time;
    if (!(Number(merged.stepGoal) > 0)) merged.stepGoal = DEFAULT_REPORT_SETTINGS.stepGoal;
    merged.enabled = merged.enabled === true;
    return merged;
  } catch {
    return { ...DEFAULT_REPORT_SETTINGS };
  }
}

// 설정 저장
export function saveReportSettings(next) {
  if (!isAvailable()) return next;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // 저장 실패해도 앱 동작은 막지 않음
  }
  return next;
}
