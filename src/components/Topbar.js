import React from "react";
import Badge from "./ui/Badge";

export default function Topbar({ user, title, subtitle, onProfileClick }) {
  return (
    <header className="topbar">
      <div className="topbar__titles">
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>

      <div className="topbar__right">
        <Badge variant="normal">● 실시간 동기화</Badge>
        {user && (
          <button
            type="button"
            className="user-chip user-chip--button"
            onClick={onProfileClick}
            title="프로필 정보 변경"
          >
            <span className="user-chip__avatar">{user.initial}</span>
            <div style={{ textAlign: "left" }}>
              <div className="user-chip__name">{user.name}</div>
              <div className="user-chip__meta">{user.meta}</div>
            </div>
            <span className="user-chip__caret" aria-hidden="true">
              ▾
            </span>
          </button>
        )}
      </div>
    </header>
  );
}
