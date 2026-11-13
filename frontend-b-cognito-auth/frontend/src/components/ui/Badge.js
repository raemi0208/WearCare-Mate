import React from "react";

// 상태 배지 (variant: normal | warn | danger | ghost)
export default function Badge({ variant = "ghost", children }) {
  return <span className={`badge badge--${variant}`}>{children}</span>;
}
