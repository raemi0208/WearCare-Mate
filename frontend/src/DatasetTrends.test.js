import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import DatasetTrends from "./components/DatasetTrends";
import LineChart from "./components/ui/LineChart";
import TrendsPage from "./pages/TrendsPage";

const sleep = {
  status: "ok", averageHours: 7.47, minimumHours: 3, maximumHours: 12,
  recordCount: 3,
  distribution: [
    { label: "0 이상 4 미만", count: 1 },
    { label: "4 이상 6 미만", count: 0 },
    { label: "6 이상 8 미만", count: 2 },
  ],
};
const heart = {
  status: "ok", averageValue: 80, averageBasis: "positive", unit: null,
  positiveRows: 3, invalidDateRows: 0,
  dailySeries: [
    { date: "2025-10-15", averageValue: 78, includedRows: 1 },
    { date: "2025-10-16", averageValue: null, includedRows: 0 },
    { date: "2025-10-17", averageValue: 81, includedRows: 2 },
  ],
};

test("dataset charts show actual supplied aggregates and omit unconfirmed units", () => {
  render(<DatasetTrends sleepSummary={sleep} heartSummary={heart} />);
  expect(screen.getByText("7.47시간")).toBeInTheDocument();
  expect(screen.getByRole("img", {name: "수면 시간 구간별 건수 막대차트"})).toBeInTheDocument();
  expect(screen.queryByText(/bpm/i)).not.toBeInTheDocument();
  const button = screen.getByRole("button", {name: "날짜별 포함 건수 보기"});
  expect(button).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(button);
  expect(button).toHaveAttribute("aria-expanded", "true");
  const table = screen.getByRole("table");
  expect(within(table).getByText("2025-10-16")).toBeInTheDocument();
  expect(within(table).getByText("—")).toBeInTheDocument();

});

test("missing extension, empty and failed datasets have distinct notices", () => {
  const {rerender} = render(<DatasetTrends sleepSummary={{status: "ok"}} heartSummary={{status: "error"}} />);
  expect(screen.getByText("확장 집계가 제공되지 않았습니다.")).toBeInTheDocument();
  expect(screen.getByText("데이터셋을 조회하지 못했습니다.")).toBeInTheDocument();
  rerender(<DatasetTrends sleepSummary={{status: "empty"}} />);
  expect(screen.getByText("조회된 데이터가 없습니다.")).toBeInTheDocument();
  expect(screen.getByText("데이터셋 요약이 제공되지 않았습니다.")).toBeInTheDocument();
});

test.each([
  {...sleep, recordCount: 99},
  {...sleep, recordCount: null},
  {...sleep, distribution: []},
  {...sleep, distribution: [{label: "invalid", count: null}]},
])("invalid sleep aggregates are not drawn as zero counts", (summary) => {
  render(<DatasetTrends sleepSummary={summary} heartSummary={{status: "empty"}} />);
  expect(screen.getByRole("alert")).toHaveTextContent("수면 분포 집계가 올바르지 않아");
  expect(screen.queryByRole("img", {name: "수면 시간 구간별 건수 막대차트"})).not.toBeInTheDocument();
});

test("line chart separates missing values and preserves point counts", () => {
  const {container} = render(<LineChart data={[
    {label: "a", value: 1}, {label: "b", value: 2},
    {label: "c", value: null},
    {label: "d", value: 3}, {label: "e", value: 4, includedRows: 8},
  ]} />);
  expect(container.querySelectorAll("polyline")).toHaveLength(2);
  expect(container.querySelectorAll("circle")).toHaveLength(4);
  expect(container.querySelectorAll("polygon")).toHaveLength(2);
  expect(container.textContent).toContain("포함 8건");
  expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
});

test("line chart handles all missing, single, and constant values", () => {
  const {container, rerender} = render(<LineChart data={[{label: "a", value: null}]} />);
  expect(screen.getByText("표시할 값이 없습니다.")).toBeInTheDocument();
  rerender(<LineChart data={[{label: "a", value: 5, anomaly: true}]} />);
  expect(container.querySelectorAll("circle")).toHaveLength(2);
  expect(container.querySelector("polyline")).toBeNull();
  rerender(<LineChart data={[{label: "a", value: 5}, {label: "b", value: 5}]} />);
  expect(container.querySelectorAll("polyline")).toHaveLength(1);
  expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
});

test("real dataset mode replaces empty personal cards and keeps activity", () => {
  render(<TrendsPage data={{
    timeseries: {sleep: [], heartRate: [], steps: [{label: "일", value: 10057}]},
    sleepDatasetSummary: sleep, heartRateDatasetSummary: heart,
  }} />);
  expect(screen.getByText(/활동량/)).toBeInTheDocument();
  expect(screen.getByText("날짜별 평균 심박")).toBeInTheDocument();
  expect(screen.queryByText(/안정 시 심박/)).not.toBeInTheDocument();
  expect(screen.getByText("현재 데이터셋은 수면 단계 정보를 제공하지 않습니다.")).toBeInTheDocument();
});
test("dashboard sleep stages show a notice instead of an empty bar", () => {
  const SleepStages = require("./components/SleepStages").default;
  const {container, rerender} = render(<SleepStages sleepStages={{totalLabel: "데이터 없음", segments: []}} />);
  expect(screen.getByText("현재 데이터셋은 수면 단계 정보를 제공하지 않습니다.")).toBeInTheDocument();
  expect(container.querySelector(".sleep-stages")).toBeNull();
  rerender(<SleepStages sleepStages={{totalLabel: "예시", segments: [{id: "deep", label: "깊은 수면", pct: 30, color: "black"}]}} />);
  expect(container.querySelector(".sleep-stages__seg")).toHaveStyle({width: "30%"});
});