// WearCare Mate - 헬스 앱 연동 상태 로컬 저장소
//
// 여러 건강 앱을 동시에 연동하고, 그중 하나를 '메인 앱'으로 지정한 상태를 브라우저 localStorage에 저장합니다.
// 저장 형태: { links: [{ provider, linkedAt, lastSyncAt }], mainProvider }
// (예전 단일 저장 형태 { provider, linkedAt } 도 읽을 때 자동으로 변환합니다.)
// 실제 Apple HealthKit / Samsung Health SDK 연동이 아닌 시연용 mock 연동입니다.

const STORAGE_KEY = "wearcare.healthLink";
// 같은 탭의 다른 컴포넌트(App 등)가 연동 변경을 바로 알 수 있도록 보내는 이벤트 이름
export const HEALTH_LINK_EVENT = "wearcare:healthLinkChanged";

// 기본 헬스 앱 (앱 선택 화면 첫 단계에 표시)
export const MAIN_PROVIDERS = {
  apple: { id: "apple", name: "애플 건강 (Apple Health)", device: "아이폰", icon: "🍎" },
  samsung: { id: "samsung", name: "삼성 헬스 (Samsung Health)", device: "삼성 갤럭시", icon: "💙" },
};

// 기타(Other) 웨어러블 앱 (앱 선택 화면에서 '기타'를 누르면 표시)
export const OTHER_PROVIDERS = {
  healthconnect: { id: "healthconnect", name: "헬스 커넥트 (Health Connect)", device: "안드로이드", icon: "🟢" },
  fitbit: { id: "fitbit", name: "핏빗 (Fitbit)", device: "Fitbit 기기", icon: "⌚" },
  garmin: { id: "garmin", name: "가민 커넥트 (Garmin Connect)", device: "Garmin 기기", icon: "🧭" },
  xiaomi: { id: "xiaomi", name: "미 피트니스 (Mi Fitness)", device: "샤오미 밴드/워치", icon: "🟠" },
  huawei: { id: "huawei", name: "화웨이 헬스 (Huawei Health)", device: "화웨이 기기", icon: "🔴" },
  oura: { id: "oura", name: "오우라 (Oura)", device: "Oura 링", icon: "💍" },
};

// 연동 가능한 전체 헬스 앱 목록 (저장된 연동 상태 검증/표시에 사용)
export const HEALTH_PROVIDERS = { ...MAIN_PROVIDERS, ...OTHER_PROVIDERS };

// 연동 시 가져오는 데이터 항목 (예시 값은 timeseries 마지막 값 또는 mock 값)
export const LINK_DATA_ITEMS = [
  { id: "steps", label: "걸음수", icon: "👟", desc: "하루 동안 걸은 걸음 수", unit: "걸음", source: "steps" },
  { id: "sleep", label: "수면", icon: "🌙", desc: "총 수면 시간과 수면 단계", unit: "시간", source: "sleep" },
  { id: "heartRate", label: "심박", icon: "❤️", desc: "안정 시 심박수", unit: "bpm", source: "heartRate" },
  { id: "activeMinutes", label: "활동 시간", icon: "🏃", desc: "움직인 시간(분)", unit: "분", source: null, sample: 48 },
  { id: "calories", label: "칼로리", icon: "🔥", desc: "하루 활동 소모 칼로리", unit: "kcal", source: null, sample: 2150 },
];

// 연동 진행 4단계 (단계당 약 0.5초, 총 약 2초)
export const LINK_STEPS = ["앱 확인", "권한 요청", "데이터 불러오기", "완료"];

// 브라우저 환경이 아니거나 localStorage 접근이 막힌 경우를 안전하게 처리
function isAvailable() {
  try {
    return typeof window !== "undefined" && !!window.localStorage;
  } catch {
    return false;
  }
}

const EMPTY = () => ({ links: [], mainProvider: null });

// 저장값을 올바른 { links, mainProvider } 로 정리 (예전 단일 형태 변환 포함)
function normalize(parsed) {
  if (!parsed || typeof parsed !== "object") return EMPTY();
  let rawLinks = [];
  let main = null;
  if (Array.isArray(parsed.links)) {
    rawLinks = parsed.links;
    main = parsed.mainProvider;
  } else if (parsed.provider) {
    // 예전 단일 저장값 { provider, linkedAt } → links 1개 + 메인
    rawLinks = [parsed];
    main = parsed.provider;
  }
  const seen = new Set();
  const links = [];
  rawLinks.forEach((l) => {
    if (!l || !HEALTH_PROVIDERS[l.provider] || seen.has(l.provider)) return;
    seen.add(l.provider);
    const linkedAt = typeof l.linkedAt === "string" ? l.linkedAt : new Date().toISOString();
    links.push({ provider: l.provider, linkedAt, lastSyncAt: typeof l.lastSyncAt === "string" ? l.lastSyncAt : linkedAt });
  });
  const mainProvider = links.some((l) => l.provider === main) ? main : links.length > 0 ? links[0].provider : null;
  return { links, mainProvider };
}

// 저장 + 변경 알림
function persist(state) {
  if (isAvailable()) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // 저장 실패해도 앱 동작은 막지 않음
    }
    try {
      window.dispatchEvent(new Event(HEALTH_LINK_EVENT));
    } catch {
      // 무시
    }
  }
  return state;
}

// 저장된 연동 상태 읽기 (없거나 올바르지 않으면 빈 상태)
export function loadHealthLinks() {
  if (!isAvailable()) return EMPTY();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return normalize(raw ? JSON.parse(raw) : null);
  } catch {
    return EMPTY();
  }
}

// 앱 연동 추가 (이미 연동된 앱이면 그대로, 첫 연동 앱은 자동으로 메인)
export function addHealthLink(provider) {
  const state = loadHealthLinks();
  if (!HEALTH_PROVIDERS[provider] || state.links.some((l) => l.provider === provider)) return state;
  const now = new Date().toISOString();
  const links = [...state.links, { provider, linkedAt: now, lastSyncAt: now }];
  return persist({ links, mainProvider: state.mainProvider || provider });
}

// 앱 연동 해제 (메인을 해제하면 남은 첫 앱이 메인, 없으면 null)
export function removeHealthLink(provider) {
  const state = loadHealthLinks();
  const links = state.links.filter((l) => l.provider !== provider);
  let mainProvider = state.mainProvider;
  if (mainProvider === provider) mainProvider = links.length > 0 ? links[0].provider : null;
  return persist({ links, mainProvider });
}

// 메인 측정 앱 변경 (연동된 앱만 가능)
export function setMainProvider(provider) {
  const state = loadHealthLinks();
  if (!state.links.some((l) => l.provider === provider)) return state;
  return persist({ ...state, mainProvider: provider });
}

// 마지막 동기화 시각 갱신 (다시 동기화)
export function touchLastSync(provider) {
  const state = loadHealthLinks();
  if (!state.links.some((l) => l.provider === provider)) return state;
  const now = new Date().toISOString();
  const links = state.links.map((l) => (l.provider === provider ? { ...l, lastSyncAt: now } : l));
  return persist({ ...state, links });
}
