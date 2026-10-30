import React from "react";
import Badge from "./ui/Badge";

export default function Topbar({ user }) {
  return (
    <header className="topbar">
      <div className="topbar__titles">
        <h1>건강 대시보드</h1>
        <p>최근 7일 웨어러블 데이터 분석 · 실시간 모니터링</p>
      </div>

      <div className="topbar__right">
        <Badge variant="normal">● 실시간 동기화</Badge>
        {user && (
          <div className="user-chip">
            <span className="user-chip__avatar">{user.initial}</span>
            <div>
              <div className="user-chip__name">{user.name}</div>
              <div className="user-chip__meta">{user.meta}</div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
