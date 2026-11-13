import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import AiGuide from "./components/AiGuide";
import StatCard from "./components/ui/StatCard";
import { fetchDashboard, fetchAiGuide } from "./services/api";

jest.mock("./services/api", () => ({
  fetchDashboard: jest.fn(), fetchAiGuide: jest.fn(), updateProfile: jest.fn(),
}));

const normalGuide = {
  status: "not_applicable", analysisStatus: "normal", referenceDate: "2016-04-10",
  model: "활동량 분석 · 생성형 가이드 없음", updatedAt: "생성된 가이드 없음",
  headline: "활동량 이상 감소가 감지되지 않았어요.", text: "걸음 수 기준 판정입니다.",
  actions: [], warnings: [],
};
const dashboard = {
  user: { name: "데모 사용자", initial: "데", meta: "공개 데이터" },
  summaryStats: [{ id: "steps", label: "평균 걸음 수", value: "12,369", unit: "보", delta: null }],
  timeseries: { sleep: [], heartRate: [], steps: [{ label: "일", value: 10057, anomaly: false }] },
  sleepStages: { totalLabel: "데이터 없음", segments: [] }, anomalies: [], aiGuide: normalGuide,
  notifications: [], devices: [], guideHistory: [],
  analysis: { referenceDate: "2016-04-10", status: "normal", note: "선택한 날짜의 걸음 수만 판정했습니다." },
};

beforeEach(() => {
  jest.clearAllMocks();
  fetchDashboard.mockResolvedValue(dashboard);
  fetchAiGuide.mockResolvedValue(normalGuide);
});

test("real empty datasets render through all pages without infinite statistics", async () => {
  const { container } = render(<App />);
  await screen.findByText("평균 걸음 수");
  expect(screen.queryByText("● 실시간 동기화")).not.toBeInTheDocument();
  expect(screen.getByText("활동량 판정")).toBeInTheDocument();
  for (const label of ["추이 분석", "이상 탐지", "AI 가이드", "건강 앱 연동", "설정"]) {
    fireEvent.click(screen.getByRole("button", { name: new RegExp(label) }));
    expect(container.textContent).not.toMatch(/Infinity|NaN|undefined/);
  }
});

test("failed regeneration keeps dashboard and displays recoverable error", async () => {
  fetchAiGuide.mockRejectedValue(new Error("network"));
  render(<App />);
  const button = await screen.findByRole("button", { name: "분석 및 가이드 다시 확인" });
  fireEvent.click(button);
  expect(await screen.findByRole("alert")).toHaveTextContent("다시 확인하지 못했습니다");
  await waitFor(() => expect(button).toBeEnabled());
  expect(screen.getByText("평균 걸음 수")).toBeInTheDocument();
});

test.each([
  ["missing", "anomaly", "가이드 생성 실패"],
  ["not_applicable", "insufficient_data", "데이터 부족"],
  ["generated", "anomaly", "생성형 AI"],
])("guide state %s / %s has accurate badge", (status, analysisStatus, label) => {
  render(<AiGuide guide={{ ...normalGuide, status, analysisStatus }} />);
  expect(screen.getByText(label)).toBeInTheDocument();
});

test("generated guide warns when output rules were not met", () => {
  render(<AiGuide guide={{ ...normalGuide, status: "generated", warnings: ["줄 수 2"] }} />);
  expect(screen.getByRole("status")).toHaveTextContent("출력 규칙");
});

test("nullable delta is not shown as zero percent", () => {
  const { container } = render(<StatCard label="걸음" value="1" delta={null} />);
  expect(container).toHaveTextContent("비교 데이터 없음");
  expect(container).not.toHaveTextContent("0%");
});
