import React from "react";
import { render, screen } from "@testing-library/react";
import AiGuide from "./AiGuide";
import { compareYesterday } from "../utils/compareYesterday";

test("요약·행동·상담 문장은 각각 한 번만 표시한다", () => {
  render(<AiGuide guide={{ status: "generated", headline: "수면이 부족해요.", text: "수면이 부족해요.\n10분 쉬세요.\n불편하면 상담하세요.", lines: ["수면이 부족해요.", "10분 쉬세요.", "불편하면 상담하세요."], actions: ["10분 쉬세요.", "10분 쉬세요."] }} />);
  expect(screen.getAllByText("수면이 부족해요.")).toHaveLength(1);
  expect(screen.getAllByText("10분 쉬세요.")).toHaveLength(1);
  expect(screen.getAllByText("불편하면 상담하세요.")).toHaveLength(1);
});

describe("어제와 비교", () => {
  const guide = { status: "generated", headline: "요약", lines: ["요약"], actions: [] };
  const sample = (steps, sleep, hr) => ({ steps, sleep, heartRate: hr });
  const s = (...v) => v.map((value, i) => ({ label: String(i), value }));

  test("detailed에서 개선/악화 라벨을 표시한다", () => {
    const comparison = compareYesterday(sample(s(9000, 9500), s(7, 6.3), s(60, 64)));
    render(<AiGuide guide={guide} detailed comparison={comparison} />);
    expect(screen.getByText("어제와 비교")).toBeInTheDocument();
    expect(screen.getByText("어제보다 좋아진 점")).toBeInTheDocument();
    expect(screen.getByText("어제보다 나빠진 점")).toBeInTheDocument();
    expect(screen.getByText(/단순 비교한 결과/)).toBeInTheDocument();
  });

  test("데이터가 없으면 안내 문구를 표시한다", () => {
    render(<AiGuide guide={guide} detailed comparison={compareYesterday({ steps: s(1), sleep: [], heartRate: [] })} />);
    expect(screen.getByText("비교할 어제 데이터가 없습니다.")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/NaN|undefined|Infinity/);
  });

  test("detailed가 아니면 표시하지 않는다", () => {
    const comparison = compareYesterday(sample(s(9000, 9500), [], []));
    render(<AiGuide guide={guide} comparison={comparison} />);
    expect(screen.queryByText("어제와 비교")).not.toBeInTheDocument();
  });
});

