import React from "react";
import {render, screen} from "@testing-library/react";
import SleepMetrics from "./SleepMetrics";

test("실제 수면·움직임 집계만 표시하고 수면 단계와 구분한다", () => {
  render(<SleepMetrics summary={{status:"ok", averageHours:7.47, recordCount:1000, movementStatus:"ok", averageMovement:2.013, movementRecordCount:970}} />);
  expect(screen.getByText("수면 관련 지표")).toBeInTheDocument();
  expect(screen.getByText("7.47 시간")).toBeInTheDocument();
  expect(screen.getByText("2.013")).toBeInTheDocument();
  expect(screen.getByText(/단위 미확인/)).toBeInTheDocument();
  expect(screen.queryByText("수면 단계 분석")).not.toBeInTheDocument();
});

test("누락된 움직임 값을 0으로 만들거나 가상 값으로 채우지 않는다", () => {
  render(<SleepMetrics summary={{status:"ok", averageHours:7.47, recordCount:1000}} />);
  expect(screen.getByText("—")).toBeInTheDocument();
  expect(screen.getByText("유효한 움직임 집계가 제공되지 않았습니다.")).toBeInTheDocument();
});
