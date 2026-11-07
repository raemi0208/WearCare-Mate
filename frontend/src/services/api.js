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

// 네트워크 지연을 흉내 내 로딩 상태를 확인할 수 있게 함
function delay(data, ms = 350) {
  return new Promise((resolve) => setTimeout(() => resolve(data), ms));
}

async function request(path, fallback) {
  const base = resolveApiBase();
  // 실제 백엔드가 연결되지 않은 경우 목 데이터 반환 (A안 로컬/목 모드)
  if (!base) {
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

  const res = await fetch(`${base}${path}`, { headers });

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
  return { ...res, user: resolveUser(res.user) };
}

export function fetchAiGuide() {
  // Bedrock 재생성 트리거용 (현재는 목)
  return request("/ai-guide", aiGuide);
}

// 프로필 정보 업데이트
// 데이터베이스를 거치지 않고 브라우저 localStorage에 저장합니다.
export function updateProfile(profile) {
  saveProfile(profile);
  return delay(profile, 300);
}
