import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import DemoAnomalyPanel from "./DemoAnomalyPanel";

test("선택은 분석을 자동 호출하지 않으며 다중 지표 선택 후 버튼에서만 실행한다", () => {
  const run = jest.fn();
  render(<DemoAnomalyPanel onRun={run} />);
  fireEvent.change(screen.getByLabelText("시연 시나리오"), { target: { value: "multi" } });
  expect(run).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "가상 이상 시연" }));
  expect(run).toHaveBeenCalledTimes(1);
  expect(run).toHaveBeenCalledWith("multi");
});

test("저장 결과가 있어야 발송 가능하며 불확실한 발송도 재요청하지 않는다", () => {
  const send = jest.fn();
  const { rerender } = render(<DemoAnomalyPanel active onSend={send} canSend={false} />);
  expect(screen.getByRole("button", { name: "SNS 메일 발송" })).toBeDisabled();
  rerender(<DemoAnomalyPanel active onSend={send} canSend />);
  fireEvent.click(screen.getByRole("button", { name: "SNS 메일 발송" }));
  expect(send).toHaveBeenCalledTimes(1);
  rerender(<DemoAnomalyPanel active onSend={send} canSend delivery={{status: "unknown", title: "결과 확인 필요"}} />);
  expect(screen.getByRole("button", { name: "발송 요청 처리됨" })).toBeDisabled();
});

test("선택 상자의 접근성 이름은 유지하고 앞의 가시 문구는 숨긴다", () => {
  render(<DemoAnomalyPanel />);
  expect(screen.getByLabelText("시연 시나리오")).toBeInTheDocument();
  expect(screen.queryByText("시연 시나리오")).not.toBeInTheDocument();
});
