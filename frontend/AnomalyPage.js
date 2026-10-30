import React from "react";
import Card from "../components/ui/Card";
import AnomalyPanel from "../components/AnomalyPanel";

export default function AnomalyPage({ data }) {
  const anomalies = data.anomalies || [];
  const counts = {
    danger: anomalies.filter((a) => a.severity === "danger").length,
    warn: anomalies.filter((a) => a.severity === "warn").length,
    ok: anomalies.filter((a) => a.severity === "ok").length,
  };

  const summary = [
    { id: "danger", label: "위험", value: counts.danger, cls: "is-danger" },
    { id: "warn", label: "주의", value: counts.warn, cls: "is-warn" },
    { id: "ok", label: "정상", value: counts.ok, cls: "is-ok" },
  ];

  return (
    <div className="grid">
      <div className="grid grid--stats">
        {summary.map((s) => (
          <div key={s.id} className="card stat">
            <div className="stat__label">{s.label}</div>
            <div className="stat__value">
              {s.value}
              <span className="stat__unit">건</span>
            </div>
            <span className={`anomaly-item__dot ${s.cls}`} style={{ marginTop: 8 }} />
          </div>
        ))}
        <div className="card stat">
          <div className="stat__label">분석 엔진</div>
          <div className="stat__value" style={{ fontSize: 18 }}>
            {data.analysis ? "활동량 기준선" : "예시 분석"}
          </div>
          <div className="stat__delta is-flat">{data.analysis?.referenceDate || "예시 데이터"}</div>
        </div>
      </div>

      <Card
        title="이상 패턴 상세 내역"
        subtitle={data.analysis?.note || "예시 이상 탐지 내역"}
      >
        <AnomalyPanel anomalies={anomalies} analysis={data.analysis} embedded />
      </Card>
    </div>
  );
}
