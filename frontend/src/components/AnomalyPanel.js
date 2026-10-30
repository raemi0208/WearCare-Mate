import React from "react";
import Card from "./ui/Card";
import Badge from "./ui/Badge";

const SEVERITY_LABEL = {
  danger: "위험",
  warn: "주의",
  ok: "정상",
};

export default function AnomalyPanel({ anomalies = [], embedded = false }) {
  const alertCount = anomalies.filter((a) => a.severity !== "ok").length;

  const list = (
    <div className="anomaly-list">
      {anomalies.map((a) => (
        <div key={a.id} className="anomaly-item">
          <span className={`anomaly-item__dot is-${a.severity}`} />
          <div className="anomaly-item__body">
            <div className="anomaly-item__title">
              <span>{a.title}</span>
              <span className="anomaly-item__time">{a.time}</span>
            </div>
            <p className="anomaly-item__desc">{a.desc}</p>
          </div>
        </div>
      ))}
    </div>
  );

  // 다른 Card 안에 삽입될 때는 리스트만 렌더
  if (embedded) {
    return list;
  }

  return (
    <Card
      title="이상 패턴 탐지"
      subtitle="Amazon SageMaker 기반 분석"
      action={
        <Badge variant={alertCount > 0 ? "danger" : "normal"}>
          {alertCount > 0 ? `${alertCount}건 감지` : "이상 없음"}
        </Badge>
      }
    >
      {list}
    </Card>
  );
}

export { SEVERITY_LABEL };
