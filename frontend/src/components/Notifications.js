import React, { useState } from "react";
import Card from "./ui/Card";

export default function Notifications({ notifications = [], onHide, onClear, historyLoading }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const hide = async (id) => {
    if (id === null && !window.confirm("SNS 알림 내역을 모두 삭제할까요?")) return;
    setBusy(id ?? "all");
    setError(null);
    try {
      if (id === null) await onClear("notifications");
      else await onHide(id);
    }
    catch { setError("알림을 삭제하지 못했습니다. 다시 시도해 주세요."); }
    finally { setBusy(null); }
  };
  return (
    <Card icon="🔔" title="알림" subtitle="SNS 이메일 발송 요청 내역"
      action={onClear && (
        <button type="button" className="btn" disabled={busy !== null || historyLoading}
          onClick={() => hide(null)}>{busy === "all" ? "삭제 중…" : "전체 삭제"}</button>
      )}>
      {onHide && notifications.length > 0 && <p className="ui-note">삭제하면 목록에서 숨겨집니다. 보낸 메일과 중복 발송 방지 기록은 유지됩니다.</p>}
      {error && <p className="ui-note" role="alert">{error}</p>}
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
            {onHide && <button type="button" className="chart__tab" disabled={busy !== null} onClick={() => hide(n.id)} aria-label={`${n.title} 삭제`}>{busy === n.id ? "삭제 중…" : "삭제"}</button>}
          </div>
        ))}
      </div>
    </Card>
  );
}
