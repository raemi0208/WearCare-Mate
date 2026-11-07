// WearCare Mate - Cognito Authorization Code + PKCE 클라이언트 (B안)
//
// 외부 라이브러리 없이 브라우저 표준 API(crypto.subtle, fetch)로 PKCE 흐름을 구현합니다.
// - 공개 앱 클라이언트(시크릿 없음)에 맞춰 token 교환 시 code_verifier 를 사용합니다.
// - 액세스 토큰은 메모리에 보관하고, 만료 시 refresh_token 으로 조용히 갱신합니다.
//   (refresh_token 은 sessionStorage 에만 저장: 탭을 닫으면 사라지는 시연용 수명.)
// - AWS 자격 증명/시크릿/비밀번호는 다루지 않습니다. 토큰 값은 로그로 남기지 않습니다.

import { authConfig } from "./authConfig";

const PKCE_VERIFIER_KEY = "wearcare.pkce.verifier";
const PKCE_STATE_KEY = "wearcare.pkce.state";
const REFRESH_KEY = "wearcare.auth.refresh";

// 메모리 토큰 캐시 (새로고침되면 사라지고 refresh_token 으로 재획득)
let accessToken = null;
let accessTokenExpiry = 0; // epoch ms

// ---------- 저수준 유틸 ----------

function base64UrlEncode(bytes) {
  let str = "";
  const arr = new Uint8Array(bytes);
  for (let i = 0; i < arr.length; i += 1) str += String.fromCharCode(arr[i]);
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomString(byteLength = 32) {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

async function sha256(input) {
  const data = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return base64UrlEncode(digest);
}

function tokenEndpoint() {
  return `${authConfig.domain}/oauth2/token`;
}

function authorizeEndpoint() {
  return `${authConfig.domain}/oauth2/authorize`;
}

function logoutEndpoint() {
  return `${authConfig.domain}/logout`;
}

// ---------- 로그인 시작 (authorize 로 리다이렉트) ----------

export async function login() {
  const verifier = randomString(32);
  const challenge = await sha256(verifier);
  const state = randomString(16);

  sessionStorage.setItem(PKCE_VERIFIER_KEY, verifier);
  sessionStorage.setItem(PKCE_STATE_KEY, state);

  const params = new URLSearchParams({
    response_type: "code",
    client_id: authConfig.clientId,
    redirect_uri: authConfig.redirectUri,
    scope: authConfig.scope,
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
  });
  window.location.assign(`${authorizeEndpoint()}?${params.toString()}`);
}

// ---------- 콜백 처리 (authorize → redirect_uri?code=...&state=...) ----------

// URL 에 code 가 있으면 토큰으로 교환합니다. 성공 시 true, 콜백이 아니면 false.
export async function handleRedirectCallback() {
  const url = new URL(window.location.href);
  const code = url.searchParams.get("code");
  const returnedState = url.searchParams.get("state");
  const errorParam = url.searchParams.get("error");

  if (errorParam) {
    cleanUrl();
    throw new Error(`로그인에 실패했습니다 (${errorParam}).`);
  }
  if (!code) return false;

  const savedState = sessionStorage.getItem(PKCE_STATE_KEY);
  const verifier = sessionStorage.getItem(PKCE_VERIFIER_KEY);
  sessionStorage.removeItem(PKCE_STATE_KEY);
  sessionStorage.removeItem(PKCE_VERIFIER_KEY);

  if (!savedState || savedState !== returnedState) {
    cleanUrl();
    throw new Error("로그인 상태 검증에 실패했습니다. 다시 시도해 주세요.");
  }
  if (!verifier) {
    cleanUrl();
    throw new Error("로그인 세션이 만료되었습니다. 다시 시도해 주세요.");
  }

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: authConfig.clientId,
    code,
    redirect_uri: authConfig.redirectUri,
    code_verifier: verifier,
  });
  const res = await fetch(tokenEndpoint(), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) {
    cleanUrl();
    throw new Error("토큰 교환에 실패했습니다. 다시 로그인해 주세요.");
  }
  const tokens = await res.json();
  storeTokens(tokens);
  cleanUrl();
  return true;
}

function storeTokens(tokens) {
  if (tokens.access_token) {
    accessToken = tokens.access_token;
    const expiresInMs = (Number(tokens.expires_in) || 3600) * 1000;
    // 만료 60초 전에 미리 갱신하도록 여유를 둠
    accessTokenExpiry = Date.now() + expiresInMs - 60 * 1000;
  }
  if (tokens.refresh_token) {
    try {
      sessionStorage.setItem(REFRESH_KEY, tokens.refresh_token);
    } catch (e) {
      // 저장 실패해도 메모리 토큰으로는 동작
    }
  }
}

// 콜백 쿼리스트링(code, state)을 주소창에서 제거
function cleanUrl() {
  const base = window.location.origin + window.location.pathname;
  window.history.replaceState({}, document.title, base);
}

// ---------- 토큰 조회/갱신 ----------

async function refreshWithToken() {
  const refreshToken = sessionStorage.getItem(REFRESH_KEY);
  if (!refreshToken) return false;
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: authConfig.clientId,
    refresh_token: refreshToken,
  });
  const res = await fetch(tokenEndpoint(), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) {
    clearTokens();
    return false;
  }
  const tokens = await res.json();
  storeTokens(tokens);
  return Boolean(accessToken);
}

// 유효한 액세스 토큰을 돌려줍니다. 없거나 만료면 refresh 를 시도하고, 그래도 없으면 null.
export async function getAccessToken() {
  if (accessToken && Date.now() < accessTokenExpiry) return accessToken;
  const refreshed = await refreshWithToken();
  return refreshed ? accessToken : null;
}

export function isAuthenticated() {
  if (accessToken && Date.now() < accessTokenExpiry) return true;
  return Boolean(sessionStorage.getItem(REFRESH_KEY));
}

function clearTokens() {
  accessToken = null;
  accessTokenExpiry = 0;
  try {
    sessionStorage.removeItem(REFRESH_KEY);
  } catch (e) {
    // noop
  }
}

// ---------- 로그아웃 (Cognito 세션까지 종료) ----------

export function logout() {
  clearTokens();
  const params = new URLSearchParams({
    client_id: authConfig.clientId,
    logout_uri: authConfig.logoutUri,
  });
  window.location.assign(`${logoutEndpoint()}?${params.toString()}`);
}
