import React from "react";
import { render, screen, within } from "@testing-library/react";
import DatasetSummaryCards from "./components/DatasetSummaryCards";

const okData = {
  sleepDatasetSummary: {
    status: "ok", sourceLabel: "별도 데이터셋", averageHours: 7.47, recordCount: 1000,
  },
  heartRateDatasetSummary: {
    status: "ok", sourceLabel: "별도 데이터셋", totalRows: 30000, numericRows: 30000,
    zeroRows: 206, positiveRows: 29794, averageValue: 79.9, averageBasis: "positive", unit: "bpm",
  },
  psychologyDatasetSummary: {
    status: "ok", sourceLabel: "별도 데이터셋", unit: "데이터 행 수",
    files: [
      { id: "integrated", label: "통합 데이터셋", rowCount: 1328 },
      { id: "validation", label: "검증 데이터셋", rowCount: 175 },
    ],
  },
};

test("세 데이터셋 카드가 실제 집계값과 별도 데이터셋 배지를 표시한다", () => {
  render(<DatasetSummaryCards data={okData} />);
  // 수면
  expect(screen.getByText("수면 데이터셋")).toBeInTheDocument();
  expect(screen.getByText("7.47시간")).toBeInTheDocument();
  expect(screen.getByText(/집계 기록 수 1,000건/)).toBeInTheDocument();
  // 심박: 행 수 중심
  expect(screen.getByText("심박 데이터셋")).toBeInTheDocument();
  expect(screen.getByText("30,000")).toBeInTheDocument();
  expect(screen.getByText("29,794")).toBeInTheDocument();
  expect(screen.getByText(/양수 값 평균 79.9 bpm/)).toBeInTheDocument();
  // 심리상담: 파일별 행 수
  expect(screen.getByText("심리상담 데이터셋")).toBeInTheDocument();
  expect(screen.getByText("통합 데이터셋")).toBeInTheDocument();
  expect(screen.getByText("1,328")).toBeInTheDocument();
  expect(screen.getByText("175")).toBeInTheDocument();
  // 별도 데이터셋 배지 3개
  expect(screen.getAllByText("별도 데이터셋")).toHaveLength(3);
});

test("실패/빈 결과는 0 이 아니라 안내 문구로 표시된다", () => {
  const data = {
    sleepDatasetSummary: { status: "error", sourceLabel: "별도 데이터셋", averageHours: null, recordCount: null },
    heartRateDatasetSummary: { status: "empty", sourceLabel: "별도 데이터셋", totalRows: 0 },
    psychologyDatasetSummary: {
      status: "ok", sourceLabel: "별도 데이터셋", unit: "데이터 행 수",
      files: [{ id: "integrated", label: "통합 데이터셋", rowCount: 1328 }],
    },
  };
  const { container } = render(<DatasetSummaryCards data={data} />);
  expect(screen.getByText(/불러오지 못했습니다/)).toBeInTheDocument();
  expect(screen.getByText(/집계 대상 데이터가 없습니다/)).toBeInTheDocument();
  // 실패/빈 카드에 0 을 숫자로 표시하지 않는다
  expect(container.textContent).not.toMatch(/0시간/);
  expect(container.textContent).not.toMatch(/전체 기록 0행/);
  // 정상인 심리상담은 계속 표시
  expect(screen.getByText("1,328")).toBeInTheDocument();
});

test("세 필드가 모두 없으면 섹션을 렌더하지 않는다", () => {
  const { container } = render(<DatasetSummaryCards data={{}} />);
  expect(container.firstChild).toBeNull();
});

test("심박 평균 근거가 전체 평균이면 라벨이 바뀐다", () => {
  const data = {
    heartRateDatasetSummary: {
      status: "ok", sourceLabel: "별도 데이터셋", totalRows: 100, positiveRows: 100,
      zeroRows: 0, averageValue: 70.1, averageBasis: "all", unit: "bpm",
    },
  };
  render(<DatasetSummaryCards data={data} />);
  const card = screen.getByText("심박 데이터셋").closest(".card");
  expect(within(card).getByText(/전체 평균 70.1 bpm/)).toBeInTheDocument();
});
