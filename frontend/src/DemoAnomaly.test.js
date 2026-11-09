import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "./App";
import { fetchDashboard, fetchAiGuide, fetchDemoAnomaly } from "./services/api";

jest.mock("./services/api", () => ({
  fetchDashboard: jest.fn(),
  fetchAiGuide: jest.fn(),
  fetchDemoAnomaly: jest.fn(),
  updateProfile: jest.fn(),
}));

// 인증 모드로 고정(데모 패널은 인증 모드에서만 노출). login/logout 은 호출만 막는다.
jest.mock("./services/authConfig", () => ({
  isAuthEnabled: () => true,
  apiBase: "https://tirb2qdtj8.example.com",
}));
jest.mock("./services/cognitoAuth", () => ({
  login: jest.fn(),
  logout: jest.fn(),
}));

// 실제(정상 판정) 대시보드 데이터
const realGuide = {
  status: "not_applicable",
  analysisStatus: "normal",
  referenceDate: "2016-04-10",
  model: "활동량 분석 · 생성형 가이드 없음",
  updatedAt: "생성된 가이드 없음",
  headline: "활동량 이상 감소가 감지되지 않았어요.",
  text: "걸음 수 기준 판정입니다.",
  actions: [],
  warnings: [],
};
const dashboard = {
  user: { name: "데모 사용자", initial: "데", meta: "Cognito 로그인 적용" },
  summaryStats: [{ id: "steps", label: "평균 걸음 수", value: "12,369", unit: "걸음", delta: null }],
  timeseries: { sleep: [], heartRate: [], steps: [{ label: "일", value: 10057, anomaly: false }] },
  sleepStages: { totalLabel: "데이터 없음", segments: [] },
  anomalies: [],
  aiGuide: realGuide,
  notifications: [],
  devices: [],
  guideHistory: [],
  analysis: { referenceDate: "2016-04-10", status: "normal", note: "선택한 날짜의 걸음 수만 판정했습니다." },
};

// 데모(가상 이상) 응답: /ai-guide 와 같은 스키마 + anomalies 배열
const demoResponse = {
  inputKind: "virtual",
  referenceDate: "2026-10-30",
  analysisStatus: "anomaly",
  overallSeverity: "high",
  aiGuide: {
    status: "generated",
    analysisStatus: "anomaly",
    referenceDate: "2026-10-30",
    model: "Amazon Bedrock · claude-haiku",
    updatedAt: "2026-10-30T14:40:09+09:00",
    headline: "오늘 걸음 수가 평소보다 크게 줄었어요.",
    text: "오늘 10분 걷기를 해 보세요.",
    actions: ["오늘 10분 걷기를 해 보세요."],
    lines: ["오늘 걸음 수가 평소보다 크게 줄었어요.", "오늘 10분 걷기를 해 보세요."],
    warnings: [],
  },
  anomalies: [
    { id: "2026-10-30-0", severity: "danger", title: "평소 대비 걸음 수 감소", time: "2026-10-30",
      desc: "기준일 걸음 수 1,000걸음 · 과거 기록 평균 10,083걸음" },
  ],
};

beforeEach(() => {
  jest.clearAllMocks();
  fetchDashboard.mockResolvedValue(dashboard);
  fetchAiGuide.mockResolvedValue(realGuide);
});

test("시연 패널은 가상/실제AI/실제기록아님 안내와 버튼을 보여준다", async () => {
  render(<App />);
  await screen.findByText("평균 걸음 수");
  expect(screen.getByText(/가상 입력 · 실제 AI 생성 · 실제 사용자 기록 아님/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "가상 이상 시연" })).toBeInTheDocument();
  // 초기에는 해제 버튼이 없다(시연 결과 없음).
  expect(screen.queryByRole("button", { name: "실제 데이터로 돌아가기" })).not.toBeInTheDocument();
});

test("버튼 클릭 시 1회 호출하고, 성공하면 가상 가이드/이상을 표시한다", async () => {
  fetchDemoAnomaly.mockResolvedValue(demoResponse);
  render(<App />);
  await screen.findByText("평균 걸음 수");

  // 클릭 전에는 호출하지 않는다.
  expect(fetchDemoAnomaly).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: "가상 이상 시연" }));

  // 가상 가이드(생성형 AI 배지)와 이상 항목이 표시된다.
  expect(await screen.findByText("생성형 AI")).toBeInTheDocument();
  expect(screen.getByText("평소 대비 걸음 수 감소")).toBeInTheDocument();
  expect(fetchDemoAnomaly).toHaveBeenCalledTimes(1); // 자동 재시도 없음

  // 실제 데이터 카드(걸음 수)는 보존된다.
  expect(screen.getByText("평균 걸음 수")).toBeInTheDocument();
  expect(screen.getByText("12,369")).toBeInTheDocument();
});

test("요청 중에는 버튼이 비활성화된다", async () => {
  let resolve;
  fetchDemoAnomaly.mockReturnValue(new Promise((r) => { resolve = r; }));
  render(<App />);
  await screen.findByText("평균 걸음 수");

  const button = screen.getByRole("button", { name: "가상 이상 시연" });
  fireEvent.click(button);

  // 진행 중: 비활성 + 라벨 변경
  await waitFor(() => expect(screen.getByRole("button", { name: "AI 분석 중…" })).toBeDisabled());

  resolve(demoResponse);
  await screen.findByText("생성형 AI");
});

test("실패 시 오류를 표시하고 예시로 대체하지 않는다(실제 가이드 유지)", async () => {
  fetchDemoAnomaly.mockRejectedValue(new Error("network"));
  render(<App />);
  await screen.findByText("평균 걸음 수");

  fireEvent.click(screen.getByRole("button", { name: "가상 이상 시연" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("예시로 대체하지 않습니다");
  // 실제 가이드 상태(활동량 판정 배지)가 그대로 유지된다. 가상 생성형 AI 배지는 없다.
  expect(screen.getByText("활동량 판정")).toBeInTheDocument();
  expect(screen.queryByText("생성형 AI")).not.toBeInTheDocument();
  // 버튼은 다시 활성화된다(사용자가 원하면 다시 시도). 자동 재시도는 하지 않았다.
  await waitFor(() => expect(screen.getByRole("button", { name: "가상 이상 시연" })).toBeEnabled());
  expect(fetchDemoAnomaly).toHaveBeenCalledTimes(1);
});

test("시연 중에는 '분석 및 가이드 다시 확인'이 사라져 실제 재조회와 섞이지 않는다", async () => {
  fetchDemoAnomaly.mockResolvedValue(demoResponse);
  render(<App />);
  await screen.findByText("평균 걸음 수");

  // 시연 전에는 실제 가이드 재확인 버튼이 있다.
  expect(screen.getByRole("button", { name: "분석 및 가이드 다시 확인" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "가상 이상 시연" }));
  await screen.findByText("생성형 AI");

  // 시연 결과 표시 중에는 재확인 버튼이 없다(실제 /ai-guide 요청 차단).
  expect(screen.queryByRole("button", { name: "분석 및 가이드 다시 확인" })).not.toBeInTheDocument();
  expect(fetchAiGuide).not.toHaveBeenCalled();

  // 돌아가면 다시 나타난다.
  fireEvent.click(screen.getByRole("button", { name: "실제 데이터로 돌아가기" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "분석 및 가이드 다시 확인" })).toBeInTheDocument()
  );
});

test("실제 데이터로 돌아가기는 시연 결과만 해제한다", async () => {
  fetchDemoAnomaly.mockResolvedValue(demoResponse);
  render(<App />);
  await screen.findByText("평균 걸음 수");

  fireEvent.click(screen.getByRole("button", { name: "가상 이상 시연" }));
  await screen.findByText("생성형 AI");

  fireEvent.click(screen.getByRole("button", { name: "실제 데이터로 돌아가기" }));

  // 실제(정상) 가이드 상태로 복원된다. 가상 이상 항목은 사라진다.
  await waitFor(() => expect(screen.getByText("활동량 판정")).toBeInTheDocument());
  expect(screen.queryByText("생성형 AI")).not.toBeInTheDocument();
  expect(screen.queryByText("평소 대비 걸음 수 감소")).not.toBeInTheDocument();
  // 실제 데이터 카드는 그대로.
  expect(screen.getByText("12,369")).toBeInTheDocument();
});

test("시연 기준일 전환과 실제 집계·차트 보존을 확인한다", async () => {
  fetchDemoAnomaly.mockResolvedValue(demoResponse);
  render(<App />);
  await screen.findByText("평균 걸음 수");

  const dateCard = () =>
    screen.getByText(
      /^(선택한 날짜의 걸음 수만 판정했습니다\.|가상 시연 입력에 대한 이상 탐지 결과입니다\.)$/
    ).closest(".card");

  const guideCard = () =>
    screen.getByText("AI 맞춤 건강 가이드").closest(".ai-guide");

  const checkDate = (date) => {
    expect(
      within(dateCard()).getByText(`분석 기준일: ${date}`)
    ).toBeInTheDocument();
    expect(
      within(guideCard()).getByText(`분석 기준일: ${date}`)
    ).toBeInTheDocument();
  };

  const chart = screen.getByLabelText("시계열 추이 라인 차트");
  const originalChart = chart.outerHTML;
  const originalTimeseries = JSON.stringify(dashboard.timeseries);

  checkDate("2016-04-10");

  fireEvent.click(
    screen.getByRole("button", { name: "가상 이상 시연" })
  );
  await screen.findByText("생성형 AI");

  checkDate("2026-10-30");
  expect(
    screen.queryByText("분석 기준일: 2016-04-10")
  ).not.toBeInTheDocument();
  expect(screen.getByText("12,369")).toBeInTheDocument();
  expect(
    screen.getByLabelText("시계열 추이 라인 차트").outerHTML
  ).toBe(originalChart);
  expect(JSON.stringify(dashboard.timeseries)).toBe(originalTimeseries);
  expect(dashboard.analysis.referenceDate).toBe("2016-04-10");

  fireEvent.click(
    screen.getByRole("button", { name: "실제 데이터로 돌아가기" })
  );

  await waitFor(() => checkDate("2016-04-10"));

  expect(
    screen.queryByText("분석 기준일: 2026-10-30")
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText("가상 시연 중 · 실제 사용자 기록 아님")
  ).not.toBeInTheDocument();
  expect(screen.getByText("12,369")).toBeInTheDocument();
  expect(
    screen.getByLabelText("시계열 추이 라인 차트").outerHTML
  ).toBe(originalChart);
});
