import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Notifications from "./Notifications";

test("선택한 알림만 삭제 요청하고 실패하면 오류를 표시한다", async () => {
  const hide = jest.fn().mockRejectedValue(new Error("failed"));
  render(<Notifications notifications={[{id:"a",title:"발송 내역",time:"오늘"}]} onHide={hide} />);
  fireEvent.click(screen.getByRole("button", {name:"발송 내역 삭제"}));
  await waitFor(() => expect(hide).toHaveBeenCalledWith("a"));
  expect(await screen.findByRole("alert")).toHaveTextContent("삭제하지 못했습니다");
  expect(screen.getByText("발송 내역")).toBeInTheDocument();
});
