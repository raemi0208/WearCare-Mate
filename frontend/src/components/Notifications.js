import React from "react";
import Card from "./ui/Card";

export default function Notifications({ notifications = [] }) {
  return (
    <Card title="알림" subtitle="Amazon SNS 푸시 내역">
      <div className="notif-list">
        {notifications.map((n) => (
          <div key={n.id} className="notif-item">
            <span className="notif-item__icon" aria-hidden="true">
              {n.icon}
            </span>
            <div>
              <div className="notif-item__title">{n.title}</div>
              <div className="notif-item__time">{n.time}</div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
