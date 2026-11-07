// B안 인증 모드 api.js 동작 검증
//
// authConfig.isAuthEnabled / apiBase 와 cognitoAuth.getAccessToken 을 mock 해서
// 인증 모드에서의 토큰 첨부·401/403 처리·토큰 없음 차단을 검증한다.

import { fetchDashboard, AuthRequiredError } from "./api";

// CRA jest 기본 resetMocks:true 는 jest.fn(impl) 의 구현도 리셋한다.
// 그래서 mock 은 일반 함수로 선언한다. getAccessToken 만 테스트에서 주입한다.
let mockAccessToken = null;

jest.mock("./authConfig", () => ({
  __esModule: true,
  apiBase: "https://api.example.com",
  isAuthEnabled: () => true,
  authConfig: {},
}));

jest.mock("./cognitoAuth", () => ({
  __esModule: true,
  getAccessToken: () => Promise.resolve(mockAccessToken),
}));

afterEach(() => {
  mockAccessToken = null;
  delete global.fetch;
});

test("유효한 토큰이면 Authorization: Bearer 를 붙여 실제 API 를 호출한다", async () => {
  mockAccessToken = "valid-token";
  const payload = { user: { name: "데모" }, summaryStats: [] };
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => payload,
  });

  const res = await fetchDashboard();

  expect(global.fetch).toHaveBeenCalledTimes(1);
  const [url, options] = global.fetch.mock.calls[0];
  expect(url).toBe("https://api.example.com/dashboard");
  expect(options.headers.Authorization).toBe("Bearer valid-token");
  expect(res.user.name).toBe("데모");
});

test("토큰을 얻지 못하면 네트워크 호출 없이 AuthRequiredError 를 던진다", async () => {
  mockAccessToken = null;
  global.fetch = jest.fn();

  await expect(fetchDashboard()).rejects.toBeInstanceOf(AuthRequiredError);
  expect(global.fetch).not.toHaveBeenCalled();
});

test("401 응답은 AuthRequiredError 로 변환된다", async () => {
  mockAccessToken = "expired-token";
  global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) });

  await expect(fetchDashboard()).rejects.toBeInstanceOf(AuthRequiredError);
});

test("403 응답은 AuthRequiredError 로 변환된다", async () => {
  mockAccessToken = "no-scope-token";
  global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 403, json: async () => ({}) });

  await expect(fetchDashboard()).rejects.toBeInstanceOf(AuthRequiredError);
});
