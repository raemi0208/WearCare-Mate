import { fetchDashboard } from "./api";
let mockAuthEnabled = false;
jest.mock("./authConfig", () => ({
  apiBase: "https://api.example.com",
  isAuthEnabled: () => mockAuthEnabled,
}));
jest.mock("./cognitoAuth", () => ({
  getAccessToken: async () => "test-token",
}));
beforeEach(() => { mockAuthEnabled = false; localStorage.clear(); });
afterEach(() => { delete global.fetch; });
function serve(meta = "개발용 데모 · 인증 미적용 · Fitbit 공개 데이터", unit = "보") {
  const payload = {
    user: { name: "데모", meta },
    summaryStats: [{ id: "steps", unit }, { id: "sleep", unit: "시간" }],
    sleepDatasetSummary: { sourceLabel: "별도 데이터셋", recordCount: 1000 },
  };
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => payload });
  return payload;
}
test("steps 단위 보를 걸음으로 표시하고 원본과 다른 카드 단위는 보존한다", async () => {
  const original = serve();
  const result = await fetchDashboard();
  expect(result.summaryStats[0].unit).toBe("걸음");
  expect(result.summaryStats[1].unit).toBe("시간");
  expect(original.summaryStats[0].unit).toBe("보");
  expect(result.sleepDatasetSummary).toEqual(original.sleepDatasetSummary);
});
test("이미 걸음인 단위는 유지한다", async () => {
  serve(undefined, "걸음");
  expect((await fetchDashboard()).summaryStats[0].unit).toBe("걸음");
});
test("비인증 중계에서는 인증 미적용 안내를 유지한다", async () => {
  const original = serve();
  const result = await fetchDashboard();
  expect(result.user.meta).toBe(original.user.meta);
  expect(global.fetch.mock.calls[0][1].headers.Authorization).toBeUndefined();
});
test("인증된 조회에서 인증 문구만 바꾸고 원본은 보존한다", async () => {
  mockAuthEnabled = true;
  const original = serve();
  const result = await fetchDashboard();
  expect(result.user.meta).toBe("개발용 데모 · Cognito 로그인 적용 · Fitbit 공개 데이터");
  expect(original.user.meta).toContain("인증 미적용");
  expect(global.fetch.mock.calls[0][1].headers.Authorization).toBe("Bearer test-token");
});
test("다른 메타 문구는 인증 모드에서도 유지한다", async () => {
  mockAuthEnabled = true;
  serve("Fitbit 공개 데이터");
  expect((await fetchDashboard()).user.meta).toBe("Fitbit 공개 데이터");
});
test("메타 정보가 없어도 응답을 유지한다", async () => {
  mockAuthEnabled = true;
  serve(null);
  expect((await fetchDashboard()).user.meta).toBeNull();
});
