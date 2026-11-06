import React from "react";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";

const STATUS = {
  connected: { label: "연결됨", variant: "normal" },
  syncing: { label: "동기화 중", variant: "ghost" },
  disconnected: { label: "연결 끊김", variant: "warn" },
};

export default function DevicesPage({ data }) {
  const devices = data.devices || [];
  const connected = devices.filter((d) => d.status === "connected").length;

  return (
    <div className="grid">
      <Card
        title="연결된 기기"
        subtitle="웨어러블 기기에서 데이터를 수집합니다"
        action={<Badge variant="ghost">{connected} / {devices.length} 연결</Badge>}
      >
        <div className="device-list">
          {devices.length === 0 && <p>연결된 기기 정보가 없습니다.</p>}
          {devices.map((d) => {
            const st = STATUS[d.status] || STATUS.disconnected;
            return (
              <div key={d.id} className="device-item">
                <span className="device-item__icon" aria-hidden="true">
                  {d.icon}
                </span>
                <div className="device-item__body">
                  <div className="device-item__name">
                    {d.name}
                    <Badge variant={st.variant}>{st.label}</Badge>
                  </div>
                  <div className="device-item__meta">
                    {d.type} · 마지막 동기화 {d.lastSync}
                    {d.battery != null && ` · 배터리 ${d.battery}%`}
                  </div>
                  <div className="device-item__metrics">
                    {d.metrics.map((m) => (
                      <span key={m} className="device-item__chip">
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
                <button type="button" className="chart__tab">
                  {d.status === "disconnected" ? "다시 연결" : "관리"}
                </button>
              </div>
            );
          })}
        </div>
      </Card>

      <Card title="새 기기 추가" subtitle="지원되는 웨어러블 기기를 연결하세요">
        <button type="button" className="add-device-btn">
          + 기기 연결하기
        </button>
      </Card>
    </div>
  );
}
