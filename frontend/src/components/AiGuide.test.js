import React from "react";
import { render, screen } from "@testing-library/react";
import AiGuide from "./AiGuide";

test("요약·행동·상담 문장은 각각 한 번만 표시한다", () => {
  render(<AiGuide guide={{ status: "generated", headline: "수면이 부족해요.", text: "수면이 부족해요.\n10분 쉬세요.\n불편하면 상담하세요.", lines: ["수면이 부족해요.", "10분 쉬세요.", "불편하면 상담하세요."], actions: ["10분 쉬세요.", "10분 쉬세요."] }} />);
  expect(screen.getAllByText("수면이 부족해요.")).toHaveLength(1);
  expect(screen.getAllByText("10분 쉬세요.")).toHaveLength(1);
  expect(screen.getAllByText("불편하면 상담하세요.")).toHaveLength(1);
});
