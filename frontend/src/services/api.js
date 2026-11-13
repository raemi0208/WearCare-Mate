// WearCare Mate - API 서비스 레이어
//
// 현재는 목 데이터를 반환합니다. 실제 백엔드가 준비되면
// REACT_APP_API_BASE 환경변수를 설정하고 아래 fetch 분기를 사용하도록
// 전환하면 됩니다. (API Gateway + Lambda REST API)
//
// 각 함수는 Promise를 반환하므로 호출부 코드는 바꿀 필요가 없습니다.

import {
  user,
  summaryStats,
  timeseries,
  sleepStages,
  anomalies,
  aiGuide,
  notifications,
  devices,
  guideHistory,
} from "../data/mockData";
import { loadProfile, saveProfile } from "./profileStorage";
import { apiBase, isAuthEnabled } from "./authConfig";
import { getAccessToken } from "./cognitoAuth";

// 인증 모드에서는 authConfig.apiBase 를, 목/로컬에서는 REACT_APP_API_BASE 를 사용.
// (두 값은 같은 REACT_APP_API_BASE 에서 오지만, 인증 모드 여부로 토큰 첨부를 분기한다.)
// 함수 호출 시점에 계산한다(설정이 런타임에 결정되는 경우/테스트 mock 반영).
function resolveApiBase() {
  return apiBase || (process.env.REACT_APP_API_BASE || "").trim().replace(/\/+$/, "");
}

// 인증이 필요한데 토큰을 얻지 못했을 때 던지는 오류 (호출부에서 로그인 안내로 전환)
export class AuthRequiredError extends Error {
  constructor(message = "로그인이 필요합니다.") {
    super(message);
    this.name = "AuthRequiredError";
    this.authRequired = true;
  }
}

// 기본 사용자 정보에 브라우저에 저장된 프로필을 덮어씀
function resolveUser(baseUser) {
  const saved = loadProfile();
  return saved ? { ...baseUser, ...saved } : baseUser;
}

// 표시용 단위 정규화: 걸음 수 요약 카드의 단위 "보"를 "걸음"으로 표기한다.
// (백엔드 응답은 바꾸지 않고, 프론트 표시 단계에서만 보정)
function normalizeStepsUnit(summaryStats) {
  if (!Array.isArray(summaryStats)) return summaryStats;
  return summaryStats.map((s) =>
    s && s.id === "steps" && s.unit === "보" ? { ...s, unit: "걸음" } : s
  );
}

// 표시용 메타 정규화: 인증 모드(Cognito 로그인)로 실데이터를 조회한 경우에만
// user.meta 의 "인증 미적용" 표기를 "Cognito 로그인 적용"으로 바꾼다.
// - 비인증(로컬 중계/목) 모드에서는 바꾸지 않는다(실제로 인증을 적용하지 않았으므로).
// - 그 외 메타 정보(예: "개발용 데모", "Fitbit 공개 데이터")는 그대로 유지한다.
// - 백엔드 응답 자체는 바꾸지 않고 표시 단계에서만 치환한다.
function normalizeAuthMeta(baseUser) {
  if (!baseUser || typeof baseUser.meta !== "string") return baseUser;
  if (!isAuthEnabled()) return baseUser; // 비인증 모드면 그대로
  if (!baseUser.meta.includes("인증 미적용")) return baseUser;
  return {
    ...baseUser,
    meta: baseUser.meta.replace("인증 미적용", "Cognito 로그인 적용"),
  };
}

// 네트워크 지연을 흉내 내 로딩 상태를 확인할 수 있게 함
function delay(data, ms = 350) {
  return new Promise((resolve) => setTimeout(() => resolve(data), ms));
}

// path 로 실제 API 를 호출한다. 기존 GET 호출은 request(path, fallback) 그대로 동작한다.
// options 로 POST 등 다른 메서드를 쓸 수 있다.
//   - method: 기본 "GET"
//   - fallbackOnly: true 면 API_BASE 가 없을 때(목/비연결) fallback 을 쓰지 않고 오류를 던진다.
//     (데모 호출처럼 "실제 호출이 아니면 예시로 대체하지 않아야" 하는 경우에 사용)
async function request(path, fallback, options = {}) {
  const { method = "GET", fallbackOnly = false, body } = options;
  const base = resolveApiBase();
  // 실제 백엔드가 연결되지 않은 경우 목 데이터 반환 (A안 로컬/목 모드)
  if (!base) {
    if (fallbackOnly) {
      // 예시로 대체하면 안 되는 호출(데모). API_BASE 가 없으면 명확히 오류를 던진다.
      throw new Error("실제 API 가 연결되어 있지 않습니다.");
    }
    return delay(fallback);
  }

  const headers = { Accept: "application/json" };

  // 인증 모드: 액세스 토큰을 Authorization: Bearer 로 첨부. 토큰이 없으면 실제 요청을 막는다.
  if (isAuthEnabled()) {
    const token = await getAccessToken();
    if (!token) {
      throw new AuthRequiredError();
    }
    headers.Authorization = `Bearer ${token}`;
  }

  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`${base}${path}`, { method, headers, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) });

  // 토큰 없음/잘못됨/만료: 오소라이저가 401/403 으로 거절 → 로그인 안내로 전환
  if (res.status === 401 || res.status === 403) {
    throw new AuthRequiredError("세션이 만료되었거나 접근 권한이 없습니다. 다시 로그인해 주세요.");
  }
  if (!res.ok) {
    throw new Error(`API 요청 실패: ${res.status}`);
  }
  return res.json();
}

export async function fetchDashboard() {
  // 실제로는 /dashboard 같은 단일 엔드포인트로 합칠 수 있음
  const res = await request("/dashboard", {
    user,
    summaryStats,
    timeseries,
    sleepStages,
    anomalies,
    aiGuide,
    notifications,
    devices,
    guideHistory,
  });
  // 프로필은 DB가 아닌 브라우저 localStorage 값을 우선 반영
  // 걸음 수 단위("보")는 표시용으로 "걸음"으로 정규화
  return {
    ...res,
    user: normalizeAuthMeta(resolveUser(res.user)),
    summaryStats: normalizeStepsUnit(res.summaryStats),
  };
}

export function fetchAiGuide() {
  // Bedrock 재생성 트리거용 (현재는 목)
  return request("/ai-guide", aiGuide);
}

// 발표용 가상 이상 시연: POST /demo/anomaly.
// - 사용자가 버튼을 누를 때만 호출한다(이 함수는 자동 재시도를 하지 않는다. 호출부가 1회만 호출).
// - 시나리오 식별자만 보낸다. 지표 값은 서버에서 고정한다.
// - 인증 모드에서는 Cognito 액세스 토큰을 Authorization: Bearer 로 첨부한다(request 가 처리).
// - 실패 시 예시(mock) 가이드로 대체하지 않는다. fallbackOnly:true 로 "실제 호출이 아니면 오류"로 만든다.
// - 응답 스키마는 /ai-guide 와 동일한 aiGuide + anomalies 배열 + inputKind="virtual".
export function fetchDemoAnomaly(scenario) {
  return request("/demo/anomaly", null, { method: "POST", fallbackOnly: true,
    ...(scenario ? { body: { scenario } } : {}) });
}

export function sendDemoEmail(eventId) {
  return request("/demo/anomaly", null, { method: "POST", fallbackOnly: true,
    body: { action: "send", eventId } });
}

export function fetchHistory(cursor) {
  return request(`/history${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`, null, { fallbackOnly: true });
}

// 프로필 정보 업데이트
// 데이터베이스를 거치지 않고 브라우저 localStorage에 저장합니다.
export function updateProfile(profile) {
  saveProfile(profile);
  return delay(profile, 300);
}

// 목록에서만 숨긴다. 실제 메일과 중복 발송 방지 기록은 유지된다.
export function hideNotification(eventId) {
  return request("/demo/anomaly", null, { method: "POST", fallbackOnly: true,
    body: { action: "hide_notification", eventId } });
}

export function getDailyReport() {
  return request("/daily-report", null, { fallbackOnly: true });
}

export function saveDailyReport(body) {
  return request("/daily-report", null, { method: "POST", fallbackOnly: true, body });
}
export function hideGuide(eventId) {
  return request("/demo/anomaly", null, { method: "POST", fallbackOnly: true,
    body: { action: "hide_guide", eventId } });
}