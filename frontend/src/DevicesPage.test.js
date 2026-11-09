import React from "react";
import { render, screen, within } from "@testing-library/react";
import DevicesPage from "./pages/DevicesPage";
import { devices as sampleDevices } from "./data/mockData";

// 실제 연결 기기 2대(connected) + 연결 끊김 1대(disconnected).
const realData = {
  devices: [
    { id: "d1", name: "Galaxy Watch 6", type: "스마트워치", icon: "⌚", status: "connected", battery: 82, lastSync: "2분 전", metrics: ["심박", "수면"] },
    { id: "d2", name: "Galaxy Ring", type: "스마트링", icon: "💍", status: "connected", battery: 45, lastSync: "10분 전", metrics: ["수면"] },
    { id: "d3", name: "Withings Scale", type: "체성분계", icon: "⚖️", status: "disconnected", battery: null, lastSync: "3일 전", metrics: ["체중"] },
  ],
};

describe("실제 기기가 있을 때", () => {
  test("기존 실제 기기 목록과 연결 건수를 유지한다", () => {
    render(<DevicesPage data={realData} />);
    // 연결됨 2대 / 전체 3대.
    expect(screen.getByText("연결된 기기")).toBeInTheDocument();
    expect(screen.getByText("2 / 3 연결")).toBeInTheDocument();
    // 실제 기기 카드가 표시된다(배터리/동기화 메타 포함).
    expect(screen.getByText(/배터리 82%/)).toBeInTheDocument();
    expect(screen.getByText(/마지막 동기화 2분 전/)).toBeInTheDocument();
  });

  test("실제 기기가 있으면 '시연용 기기' 예시 영역은 표시하지 않는다", () => {
    render(<DevicesPage data={realData} />);
    expect(screen.queryByText("시연용 기기")).not.toBeInTheDocument();
    expect(screen.queryByText(/예시 표시/)).not.toBeInTheDocument();
    expect(screen.queryByText("예시 · 실제 연결 아님")).not.toBeInTheDocument();
  });
});

describe("실제 기기가 없을 때", () => {
  test("'시연용 기기' 제목과 '실제 연결 0대 · 예시 표시' 배지를 표시한다", () => {
    render(<DevicesPage data={{ devices: [] }} />);
    expect(screen.getByText("시연용 기기")).toBeInTheDocument();
    expect(screen.getByText("실제 연결 0대 · 예시 표시")).toBeInTheDocument();
    // 실제 연결 기기 집계 카드(연결된 기기)는 노출되지 않는다.
    expect(screen.queryByText("연결된 기기")).not.toBeInTheDocument();
  });

  test("예시 카드는 mockData 모델명만 쓰고 각 카드에 '예시 · 실제 연결 아님'을 표시한다", () => {
    render(<DevicesPage data={{ devices: [] }} />);
    // 기존 예시 모델명만 사용한다.
    for (const d of sampleDevices) {
      expect(screen.getByText(d.name)).toBeInTheDocument();
    }
    // 예시 카드 수만큼 '예시 · 실제 연결 아님' 배지가 있다.
    expect(screen.getAllByText("예시 · 실제 연결 아님")).toHaveLength(sampleDevices.length);
  });

  test("가상의 배터리·최근 동기화 시간과 실제 수집 문구는 표시하지 않는다", () => {
    const { container } = render(<DevicesPage data={{ devices: [] }} />);
    expect(container.textContent).not.toMatch(/배터리/);
    expect(container.textContent).not.toMatch(/마지막 동기화/);
    expect(container.textContent).not.toMatch(/데이터를 수집합니다/);
  });

  test("예시 기기는 실제 연결 건수에 포함되지 않는다('연결됨/전체' 집계 미노출)", () => {
    render(<DevicesPage data={{ devices: [] }} />);
    // "N / M 연결" 형태의 실제 연결 집계 배지가 없다.
    expect(screen.queryByText(/\d+ \/ \d+ 연결/)).not.toBeInTheDocument();
  });
});
