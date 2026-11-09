// fetchDemoAnomaly (POST /demo/anomaly) 서비스 레이어 테스트.
//
// - POST 메서드로 호출하고, 인증 모드에서는 액세스 토큰을 Authorization: Bearer 로 붙인다.
// - 401/403 은 AuthRequiredError(authRequired=true)로 전환한다.
// - 실패(네트워크·비연결·오류 상태)는 예시로 대체하지 않고 오류를 던진다.
import { fetchDemoAnomaly, AuthRequiredError } from "./api";

let mockAuthEnabled = true;
let mockApiBase = "https://api.example.com";
jest.mock("./authConfig", () => ({
  get apiBase() {
    return mockApiBase;
  },
  isAuthEnabled: () => mockAuthEnabled,
}));
jest.mock("./cognitoAuth", () => ({
  getAccessToken: async () => "demo-token",
}));

beforeEach(() => {
  mockAuthEnabled = true;
  mockApiBase = "https://api.example.com";
});
afterEach(() => {
  delete global.fetch;
  jest.clearAllMocks();
});

function okResponse(body) {
  return { ok: true, status: 200, json: async () => body };
}

const DEMO_BODY = {
  inputKind: "virtual",
  referenceDate: "2026-10-30",
  analysisStatus: "anomaly",
  overallSeverity: "high",
  aiGuide: { status: "generated", headline: "가상 가이드" },
  anomalies: [{ id: "2026-10-30-0", severity: "danger", title: "평소 대비 걸음 수 감소" }],
};

test("POST 메서드로 호출하고 토큰을 Authorization 헤더에 붙인다", async () => {
  global.fetch = jest.fn().mockResolvedValue(okResponse(DEMO_BODY));
  const result = await fetchDemoAnomaly();

  expect(global.fetch).toHaveBeenCalledTimes(1);
  const [url, opts] = global.fetch.mock.calls[0];
  expect(url).toBe("https://api.example.com/demo/anomaly");
  expect(opts.method).toBe("POST");
  expect(opts.headers.Authorization).toBe("Bearer demo-token");
  expect(result.inputKind).toBe("virtual");
  expect(result.aiGuide.status).toBe("generated");
  expect(result.anomalies[0].severity).toBe("danger");
});

test("요청 본문을 보내지 않는다(서버가 입력 고정)", async () => {
  global.fetch = jest.fn().mockResolvedValue(okResponse(DEMO_BODY));
  await fetchDemoAnomaly();
  const [, opts] = global.fetch.mock.calls[0];
  expect(opts.body).toBeUndefined();
});

test("401/403 은 AuthRequiredError 로 전환한다", async () => {
  for (const status of [401, 403]) {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status, json: async () => ({}) });
    await expect(fetchDemoAnomaly()).rejects.toBeInstanceOf(AuthRequiredError);
  }
});

test("5xx 오류는 예시로 대체하지 않고 오류를 던진다", async () => {
  global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 502, json: async () => ({}) });
  await expect(fetchDemoAnomaly()).rejects.toThrow(/실패/);
});

test("API_BASE 가 없으면 예시로 대체하지 않고 오류를 던진다", async () => {
  mockApiBase = "";
  mockAuthEnabled = false;
  global.fetch = jest.fn();
  await expect(fetchDemoAnomaly()).rejects.toThrow(/연결/);
  expect(global.fetch).not.toHaveBeenCalled(); // 실제 호출 없음
});
