import React from "react";
import { render, screen, fireEvent, act, within } from "@testing-library/react";
import HealthAppLinkCard from "./components/HealthAppLinkCard";
import { loadHealthLinks } from "./services/healthLinkStorage";

beforeEach(() => {
  localStorage.clear();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

// 앱 선택 모달을 열어 앱을 고르고 연동이 끝날 때까지 시간을 진행한다.
function linkApp(name, { other = false } = {}) {
  const trigger = screen.queryByRole("button", { name: "건강 앱 연동하기" }) || screen.getByRole("button", { name: "다른 앱 추가 연동" });
  fireEvent.click(trigger);
  if (other) fireEvent.click(screen.getByRole("button", { name: /기타 \(Other\)/ }));
  fireEvent.click(screen.getByRole("button", { name: new RegExp(name) }));
  act(() => {
    jest.advanceTimersByTime(2000);
  });
}

test("기타(Other) 앱 연동: 4단계가 순서대로 보이고 약 2초 후 완료된다", () => {
  render(<HealthAppLinkCard />);
  fireEvent.click(screen.getByRole("button", { name: "건강 앱 연동하기" }));
  fireEvent.click(screen.getByRole("button", { name: /기타 \(Other\)/ }));
  fireEvent.click(screen.getByRole("button", { name: /핏빗/ }));
  expect(screen.getByText(/1단계 · 앱 확인/)).toHaveAttribute("aria-current", "step");
  act(() => {
    jest.advanceTimersByTime(500);
  });
  expect(screen.getByText(/2단계 · 권한 요청/)).toHaveAttribute("aria-current", "step");
  act(() => {
    jest.advanceTimersByTime(500);
  });
  expect(screen.getByText(/3단계 · 데이터 불러오기/)).toHaveAttribute("aria-current", "step");
  act(() => {
    jest.advanceTimersByTime(500);
  });
  expect(screen.getByText(/4단계 · 완료/)).toHaveAttribute("aria-current", "step");
  act(() => {
    jest.advanceTimersByTime(500);
  });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByText("핏빗 (Fitbit)")).toBeInTheDocument();
  expect(loadHealthLinks().links).toHaveLength(1);
});

test("연동 해제는 확인 후에만 실행된다", () => {
  render(<HealthAppLinkCard />);
  linkApp("핏빗", { other: true });
  fireEvent.click(screen.getByRole("button", { name: "핏빗 연동 해제" }));
  const dialog = screen.getByRole("alertdialog");
  fireEvent.click(within(dialog).getByRole("button", { name: "취소" }));
  expect(screen.getByText("핏빗 (Fitbit)")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "핏빗 연동 해제" }));
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "해제" }));
  expect(screen.queryByText("핏빗 (Fitbit)")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "건강 앱 연동하기" })).toBeInTheDocument();
});

test("재렌더 후에도 연동 상태와 마지막 동기화가 유지되고 다시 동기화로 갱신된다", () => {
  const { unmount } = render(<HealthAppLinkCard />);
  linkApp("삼성 헬스");
  const before = loadHealthLinks().links[0].lastSyncAt;
  unmount();
  render(<HealthAppLinkCard />);
  expect(screen.getByText("삼성 헬스 (Samsung Health)")).toBeInTheDocument();

  jest.setSystemTime(new Date(Date.now() + 60 * 1000));
  fireEvent.click(screen.getByRole("button", { name: "삼성 헬스 다시 동기화" }));
  expect(screen.getByRole("button", { name: "삼성 헬스 다시 동기화" })).toBeDisabled();
  act(() => {
    jest.advanceTimersByTime(1000);
  });
  expect(loadHealthLinks().links[0].lastSyncAt).not.toBe(before);
});

test("두 앱을 연동하고 메인 앱을 바꿀 수 있다", () => {
  render(<HealthAppLinkCard />);
  linkApp("삼성 헬스");
  linkApp("애플 건강");
  expect(loadHealthLinks().mainProvider).toBe("samsung");
  // 이미 연동된 앱은 선택 모달에서 비활성화된다
  fireEvent.click(screen.getByRole("button", { name: "다른 앱 추가 연동" }));
  const modal = screen.getByRole("dialog");
  expect(within(modal).getByRole("button", { name: /삼성 헬스/ })).toBeDisabled();
  fireEvent.click(within(modal).getByRole("button", { name: "취소" }));

  fireEvent.click(screen.getByRole("button", { name: "애플 건강을(를) 메인 앱으로 설정" }));
  expect(loadHealthLinks().mainProvider).toBe("apple");
  expect(screen.getByRole("button", { name: "삼성 헬스을(를) 메인 앱으로 설정" })).toBeInTheDocument();
});

test("블루투스로 연결된 기기 목록을 볼 수 있다", () => {
  render(<HealthAppLinkCard />);
  linkApp("삼성 헬스");
  fireEvent.click(screen.getByRole("button", { name: "삼성 헬스 블루투스 기기 보기" }));
  expect(screen.getByText("Galaxy Watch 6")).toBeInTheDocument();
  expect(screen.getByText("Galaxy Ring")).toBeInTheDocument();
  expect(screen.getAllByText("연결됨").length).toBeGreaterThan(0);
  expect(screen.getByText("연결 끊김")).toBeInTheDocument();
});

test("메인 앱을 해제하면 남은 앱이 메인을 승계한다", () => {
  render(<HealthAppLinkCard />);
  linkApp("삼성 헬스");
  linkApp("애플 건강");
  fireEvent.click(screen.getByRole("button", { name: "삼성 헬스 연동 해제" }));
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "해제" }));
  expect(loadHealthLinks().mainProvider).toBe("apple");
});

test("기존 단일 저장값은 links 1개 + 메인으로 변환된다", () => {
  localStorage.setItem("wearcare.healthLink", JSON.stringify({ provider: "apple", linkedAt: "2024-01-01T00:00:00.000Z" }));
  const state = loadHealthLinks();
  expect(state.links).toHaveLength(1);
  expect(state.links[0]).toMatchObject({ provider: "apple", lastSyncAt: "2024-01-01T00:00:00.000Z" });
  expect(state.mainProvider).toBe("apple");
  render(<HealthAppLinkCard />);
  expect(screen.getByText("애플 건강 (Apple Health)")).toBeInTheDocument();
});
