// WearCare Mate - 프로필 로컬 저장소
//
// 사용자 프로필은 데이터베이스를 거치지 않고 브라우저 localStorage에 저장합니다.
// (같은 브라우저에서 새로고침/재방문 시 그대로 유지됩니다.)
//
// 참고: 쿠키 대신 localStorage를 사용합니다.
// - 쿠키는 매 HTTP 요청마다 서버로 전송되지만, 프로필은 서버로 보낼 필요가 없습니다.
// - localStorage는 용량이 넉넉하고 JSON 저장이 간편합니다.

const STORAGE_KEY = "wearcare.profile";

// 브라우저 환경이 아니거나 localStorage 접근이 막힌 경우를 안전하게 처리
function isAvailable() {
  try {
    return typeof window !== "undefined" && !!window.localStorage;
  } catch {
    return false;
  }
}

// 저장된 프로필 읽기 (없으면 null)
export function loadProfile() {
  if (!isAvailable()) return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

// 프로필 저장
export function saveProfile(profile) {
  if (!isAvailable()) return profile;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  } catch {
    // 저장 실패(용량 초과 등)해도 앱 동작은 막지 않음
  }
  return profile;
}

// 프로필 초기화
export function clearProfile() {
  if (!isAvailable()) return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // 무시
  }
}
