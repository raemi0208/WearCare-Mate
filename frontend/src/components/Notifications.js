import React from "react";
import Card from "./ui/Card";

export default function Notifications({ notifications = [] }) {
  return (
    <Card title="알림" subtitle="SNS 이메일 발송 요청 내역">
      <div className="notif-list">
        {notifications.length === 0 && <p className="ui-note">표시할 알림 내역이 없습니다.</p>}
        {notifications.map((n) => (
          <div key={n.id} className="notif-item">
            <span className="notif-item__icon" aria-hidden="true">
              {n.icon || "•"}
            </span>
            <div>
              <div className="notif-item__title">{n.title}</div>
              <div className="notif-item__time">{n.time}</div>
              {n.status && <p className="ui-note">{n.status === "accepted" ? "SNS 접수 완료 · 이메일 도착 확인은 별도" : "발송 결과 확인 필요 · 자동 재발송하지 않음"}</p>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
