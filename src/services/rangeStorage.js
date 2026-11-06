// WearCare Mate - 추이 분석 기간 선택 저장소
//
// 사용자가 마지막으로 본 기간(일간/주간/월간)을 브라우저 localStorage에 저장해,
// 다시 방문했을 때 같은 기간으로 보여줍니다. (측정 데이터가 아닌 "뷰 설정"만 저장)

const STORAGE_KEY = "wearcare.trendRange";
const VALID = ["daily", "weekly", "monthly"];
const DEFAULT_RANGE = "weekly";

function isAvailable() {
  try {
    return typeof window !== "undefined" && !!window.localStorage;
  } catch {
    return false;
  }
}

// 저장된 기간 읽기 (없거나 잘못된 값이면 기본값)
export function loadRange() {
  if (!isAvailable()) return DEFAULT_RANGE;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return VALID.includes(raw) ? raw : DEFAULT_RANGE;
  } catch {
    return DEFAULT_RANGE;
  }
}

// 기간 저장
export function saveRange(range) {
  if (!isAvailable() || !VALID.includes(range)) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, range);
  } catch {
    // 저장 실패해도 앱 동작은 막지 않음
  }
}

export { DEFAULT_RANGE };
