import React from "react";

// 상단 요약 통계 카드
export default function StatCard({ icon, label, value, unit, delta = 0, deltaLabel }) {
  const dir = delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  const arrow = delta > 0 ? "▲" : delta < 0 ? "▼" : "–";
  const deltaText =
    delta === 0 ? deltaLabel : `${arrow} ${Math.abs(delta)}% · ${deltaLabel}`;

  return (
    <div className="card stat">
      <div className="stat__top">
        <span className="stat__icon" aria-hidden="true">
          {icon}
        </span>
      </div>
      <div className="stat__label">{label}</div>
      <div className="stat__value">
        {value}
        {unit && <span className="stat__unit">{unit}</span>}
      </div>
      <div className={`stat__delta is-${dir}`}>{deltaText}</div>
    </div>
  );
}
