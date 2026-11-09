import React from "react";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import { devices as sampleDevices } from "../data/mockData";

const STATUS = {
  connected: { label: "연결됨", variant: "normal" },
  syncing: { label: "동기화 중", variant: "ghost" },
  disconnected: { label: "연결 끊김", variant: "warn" },
};

export default function DevicesPage({ data }) {
  const devices = data.devices || [];
  const hasRealDevices = devices.length > 0;
  const connected = devices.filter((d) => d.status === "connected").length;

  // 실제 기기가 없으면 "시연용 기기" 영역에 기존 예시 기기 카드를 보여준다.
  // 예시 기기는 실제 연결 건수에 포함하지 않으며, 가상의 배터리/동기화 시간은 표시하지 않는다.
  return (
    <div className="grid">
      {hasRealDevices ? (
        <Card
          title="연결된 기기"
          subtitle="웨어러블 기기에서 데이터를 수집합니다"
          action={<Badge variant="ghost">{connected} / {devices.length} 연결</Badge>}
        >
          <div className="device-list">
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
      ) : (
        // 실제 연결 기기가 없을 때: 빈 영역 대신 예시 기기 카드를 디자인 그대로 활용.
        // 실제 연결은 0대이며, 아래 카드는 모두 예시(실제 연결 아님)임을 명확히 한다.
        <Card
          title="시연용 기기"
          subtitle="UI 미리보기용 예시 기기입니다. 실제 기기 연결이나 데이터 수집은 이루어지지 않습니다."
          action={<Badge variant="warn">실제 연결 0대 · 예시 표시</Badge>}
        >
          <div className="device-list">
            {sampleDevices.map((d) => (
              <div key={d.id} className="device-item" style={{ borderLeft: "4px solid var(--color-warn, #d97706)" }}>
                <span className="device-item__icon" aria-hidden="true">
                  {d.icon}
                </span>
                <div className="device-item__body">
                  <div className="device-item__name">
                    {d.name}
                    <Badge variant="warn">예시 · 실제 연결 아님</Badge>
                  </div>
                  {/* 가상의 배터리·최근 동기화 시간은 표시하지 않는다(기기 종류만 표시). */}
                  <div className="device-item__meta">{d.type}</div>
                  <div className="device-item__metrics">
                    {d.metrics.map((m) => (
                      <span key={m} className="device-item__chip">
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card title="새 기기 추가" subtitle="지원되는 웨어러블 기기를 연결하세요">
        <button type="button" className="add-device-btn">
          + 기기 연결하기
        </button>
      </Card>
    </div>
  );
}
