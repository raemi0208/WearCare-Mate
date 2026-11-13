import React from "react";

const NAV = [
  { id: "dashboard", icon: "▦", label: "대시보드" },
  { id: "trends", icon: "📈", label: "추이 분석" },
  { id: "anomaly", icon: "⚠", label: "이상 탐지" },
  { id: "guide", icon: "💬", label: "AI 가이드" },
  { id: "devices", icon: "⌚", label: "건강 앱 연동" },
  { id: "settings", icon: "⚙", label: "설정" },
];

export default function Sidebar({ active = "dashboard", onSelect = () => {} }) {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__logo">W</div>
        <div>
          <div className="sidebar__title">WearCare Mate</div>
          <div className="sidebar__subtitle">AI 건강 주치의</div>
        </div>
      </div>

      <nav className="sidebar__nav">
        {NAV.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`sidebar__nav-item ${
              active === item.id ? "is-active" : ""
            }`.trim()}
            onClick={() => onSelect(item.id)}
          >
            <span className="sidebar__nav-icon" aria-hidden="true">
              {item.icon}
            </span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="sidebar__footer">
        웨어러블 시계열 데이터 기반
        <br />
        생성형 AI 건강 행동 가이드
      </div>
    </aside>
  );
}
