// Cognito 콜백 state 검증 및 진단 수집 테스트
//
// 목적:
// 1) 로그인 시작 origin 과 콜백 origin 이 다르면 state 가 유실되어 "로그인 상태 검증 실패"가 나는 상황 재현.
// 2) 오류에 담기는 진단 요약이 민감정보(state/verifier/code/token) 원문을 포함하지 않고
//    존재 여부/일치 여부/origin/횟수만 담는지 검증.
// 3) 정상 흐름(같은 origin, state 일치)에서는 토큰 교환이 수행되는지 검증.

import {
  handleRedirectCallback,
  getLastAuthDiagnostics,
  login,
  prepareLogin,
  proceedToAuthorize,
  getLastLoginStartDiagnostics,
} from "./cognitoAuth";

jest.mock("./authConfig", () => ({
  __esModule: true,
  authConfig: {
    domain: "https://wearcare-mate-demo.auth.ap-northeast-2.amazoncognito.com",
    clientId: "test-client",
    redirectUri: "https://wearcare-mate-dxqh.vercel.app/",
    scope: "openid wearcare-demo/read",
  },
  apiBase: "https://api.example.com",
  isAuthEnabled: () => true,
}));

const STATE_KEY = "wearcare.pkce.state";
const VERIFIER_KEY = "wearcare.pkce.verifier";
const START_ORIGIN_KEY = "wearcare.pkce.startOrigin";

// jsdom 의 location 을 원하는 콜백 URL 로 바꾼다. (쿼리에 code/state 포함)
function setLocation(href) {
  delete window.location;
  // URL 로부터 origin/href/pathname 을 제공하는 최소 stub
  const u = new URL(href);
  window.location = {
    href: u.href,
    origin: u.origin,
    pathname: u.pathname,
    search: u.search,
    assign: jest.fn(),
  };
  // history.replaceState(cleanUrl) 호출을 무해화
  window.history.replaceState = jest.fn();
}

afterEach(() => {
  sessionStorage.clear();
  delete global.fetch;
  jest.clearAllMocks();
});

test("콜백 origin 이 시작 origin 과 다르면 state 가 없어 '상태 검증 실패'를 던진다", async () => {
  // 시작 origin 은 배포별 preview 주소였고, state/verifier 는 그 origin 의 sessionStorage 에 저장됨.
  // 콜백은 고정 발표 도메인으로 복귀 → 현재 sessionStorage 에는 state/verifier 가 없다.
  // (테스트에서는 '콜백 origin' 의 저장소에 state 가 없는 상태로 재현)
  sessionStorage.setItem(START_ORIGIN_KEY, "https://preview-hash.vercel.app");
  setLocation(
    "https://wearcare-mate-dxqh.vercel.app/?code=abc123&state=returned-state-xyz"
  );

  await expect(handleRedirectCallback()).rejects.toThrow("로그인 상태 검증에 실패");

  const d = getLastAuthDiagnostics();
  expect(d.savedStatePresent).toBe(false); // 콜백 origin 저장소에 state 없음
  expect(d.returnedStatePresent).toBe(true); // URL 에는 state 가 옴
  expect(d.stateMatches).toBe(false);
  expect(d.originMatches).toBe(false); // 시작 != 콜백
});

test("시작 origin 을 알 수 없으면 originMatches 는 false 가 아니라 null(unknown)이다", async () => {
  // startOrigin 미저장(예: sessionStorage 유실/첫 진입) → 불일치로 단정하지 않는다.
  sessionStorage.setItem(STATE_KEY, "saved-state");
  sessionStorage.setItem(VERIFIER_KEY, "verifier-value");
  // START_ORIGIN_KEY 는 설정하지 않음
  setLocation(
    "https://wearcare-mate-dxqh.vercel.app/?code=abc&state=different-returned"
  );

  await expect(handleRedirectCallback()).rejects.toThrow("로그인 상태 검증에 실패");

  const d = getLastAuthDiagnostics();
  expect(d.startOrigin).toBeNull();
  expect(d.originMatches).toBeNull(); // false 가 아니라 null
});

test("진단 요약은 state/verifier/code 원문을 포함하지 않는다", async () => {
  sessionStorage.setItem(STATE_KEY, "saved-state-value");
  sessionStorage.setItem(VERIFIER_KEY, "verifier-value");
  sessionStorage.setItem(START_ORIGIN_KEY, "https://wearcare-mate-dxqh.vercel.app");
  setLocation(
    "https://wearcare-mate-dxqh.vercel.app/?code=secret-code&state=different-returned"
  );

  await expect(handleRedirectCallback()).rejects.toThrow("로그인 상태 검증에 실패");

  const serialized = JSON.stringify(getLastAuthDiagnostics());
  expect(serialized).not.toContain("saved-state-value");
  expect(serialized).not.toContain("verifier-value");
  expect(serialized).not.toContain("secret-code");
  expect(serialized).not.toContain("different-returned");
});

test("같은 origin + state 일치면 토큰 교환을 수행한다", async () => {
  sessionStorage.setItem(STATE_KEY, "matching-state");
  sessionStorage.setItem(VERIFIER_KEY, "verifier-value");
  sessionStorage.setItem(START_ORIGIN_KEY, "https://wearcare-mate-dxqh.vercel.app");
  setLocation(
    "https://wearcare-mate-dxqh.vercel.app/?code=good-code&state=matching-state"
  );

  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ access_token: "a", expires_in: 3600, refresh_token: "r" }),
  });

  const result = await handleRedirectCallback();
  expect(result).toBe(true);
  expect(global.fetch).toHaveBeenCalledTimes(1);

  const d = getLastAuthDiagnostics();
  expect(d.stateMatches).toBe(true);
  expect(d.originMatches).toBe(true);
  expect(d.verifierPresent).toBe(true);
});

test("code 가 없으면 콜백이 아니므로 false 를 반환한다", async () => {
  setLocation("https://wearcare-mate-dxqh.vercel.app/");
  const result = await handleRedirectCallback();
  expect(result).toBe(false);
});

// ---------- login() 저장·write-verify 진단 ----------

// jsdom 에는 crypto.subtle 이 없을 수 있어 최소 모킹을 둔다. (값은 테스트용 더미)
function mockCrypto() {
  global.crypto = {
    getRandomValues: (arr) => {
      for (let i = 0; i < arr.length; i += 1) arr[i] = (i * 7 + 3) % 256;
      return arr;
    },
    subtle: {
      digest: async () => new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]).buffer,
    },
  };
  global.TextEncoder =
    global.TextEncoder ||
    class {
      encode(s) {
        return new Uint8Array([...String(s)].map((c) => c.charCodeAt(0)));
      }
    };
}

test("prepareLogin() 은 저장+즉시 되읽기로 writeVerified=true, 이동은 하지 않는다", async () => {
  mockCrypto();
  setLocation("https://wearcare-mate-dxqh.vercel.app/");

  const d = await prepareLogin();

  expect(d.startOrigin).toBe("https://wearcare-mate-dxqh.vercel.app");
  expect(d.redirectUri).toBe("https://wearcare-mate-dxqh.vercel.app/");
  expect(d.redirectOrigin).toBe("https://wearcare-mate-dxqh.vercel.app");
  expect(d.startMatchesRedirect).toBe(true);
  expect(d.writeVerified).toBe(true);
  expect(d.loginCount).toBe(1);
  // 준비만 하고 이동하지 않는다
  expect(window.location.assign).not.toHaveBeenCalled();
  // 저장 실제 확인
  expect(sessionStorage.getItem(STATE_KEY)).toBeTruthy();
  expect(sessionStorage.getItem(VERIFIER_KEY)).toBeTruthy();
});

test("proceedToAuthorize() 는 준비된 동일 요청으로 이동하며 state/verifier 를 재생성하지 않는다", async () => {
  mockCrypto();
  setLocation("https://wearcare-mate-dxqh.vercel.app/");

  await prepareLogin();
  const stateAfterPrepare = sessionStorage.getItem(STATE_KEY);
  const verifierAfterPrepare = sessionStorage.getItem(VERIFIER_KEY);

  const moved = proceedToAuthorize();
  expect(moved).toBe(true);
  expect(window.location.assign).toHaveBeenCalledTimes(1);
  // 이동 시 state/verifier 가 바뀌지 않아야 한다(동일 요청 재사용)
  expect(sessionStorage.getItem(STATE_KEY)).toBe(stateAfterPrepare);
  expect(sessionStorage.getItem(VERIFIER_KEY)).toBe(verifierAfterPrepare);
});

test("저장 검증 실패면 preparedUrl 이 없어 proceedToAuthorize() 가 이동하지 않는다", async () => {
  mockCrypto();
  setLocation("https://wearcare-mate-dxqh.vercel.app/");
  // setItem 을 실패시켜 writeVerified=false 유도
  const orig = Storage.prototype.setItem;
  Storage.prototype.setItem = jest.fn(() => {
    throw new Error("blocked");
  });

  const d = await prepareLogin();
  Storage.prototype.setItem = orig; // 복구

  expect(d.writeVerified).toBe(false);
  const moved = proceedToAuthorize();
  expect(moved).toBe(false);
  expect(window.location.assign).not.toHaveBeenCalled();
});

test("login() 기본 모드: 준비 후 즉시 이동", async () => {
  mockCrypto();
  setLocation("https://wearcare-mate-dxqh.vercel.app/");

  await login();
  expect(window.location.assign).toHaveBeenCalledTimes(1);
  expect(getLastLoginStartDiagnostics().writeVerified).toBe(true);
});

test("로그인 시작 진단은 state/verifier 원문을 포함하지 않는다", async () => {
  mockCrypto();
  setLocation("https://wearcare-mate-dxqh.vercel.app/");

  await prepareLogin();

  const serialized = JSON.stringify(getLastLoginStartDiagnostics());
  const savedState = sessionStorage.getItem(STATE_KEY);
  const savedVerifier = sessionStorage.getItem(VERIFIER_KEY);
  if (savedState) expect(serialized).not.toContain(savedState);
  if (savedVerifier) expect(serialized).not.toContain(savedVerifier);
});
