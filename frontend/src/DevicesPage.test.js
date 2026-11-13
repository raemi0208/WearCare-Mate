import React from "react";
import { render, screen } from "@testing-library/react";
import DevicesPage from "./pages/DevicesPage";

// 실제 기기 데이터가 들어와도 웨어러블 기기 목록은 표시하지 않는다.
const realData = {
  devices: [
    { id: "d1", name: "Galaxy Watch 6", type: "스마트워치", icon: "⌚", status: "connected", battery: 82, lastSync: "2분 전", metrics: ["심박", "수면"] },
  ],
};

beforeEach(() => localStorage.clear());

test("기기 연동 화면에는 건강 앱 연동만 표시한다", () => {
  render(<DevicesPage data={realData} />);
  expect(screen.getByRole("heading", { name: "기기 연동 미리보기" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "건강 앱 연동하기" })).toBeInTheDocument();
});

test("웨어러블 기기 목록(연결된 기기/시연용 기기)은 표시하지 않는다", () => {
  const { container } = render(<DevicesPage data={realData} />);
  expect(screen.queryByText("연결된 기기")).not.toBeInTheDocument();
  expect(screen.queryByText("시연용 기기")).not.toBeInTheDocument();
  expect(screen.queryByText("Galaxy Watch 6")).not.toBeInTheDocument();
  expect(container.textContent).not.toMatch(/배터리/);
});
