import React from "react";
import Card from "./ui/Card";
import Badge from "./ui/Badge";

const STATUS_VARIANT = {
  ok: "normal",
  warn: "warn",
  danger: "danger",
};

// Mind + Body + Life 통합 리포트 (다중 도메인 종합)
export default function HealthDomains({ domains = [], dataSources }) {
  return (
    <Card
      title="통합 헬스케어 리포트"
      subtitle="Mind · Body · Life 다중 도메인 종합"
    >
      <div className="domain-grid">
        {domains.map((d) => (
          <div key={d.id} className="domain-card">
            <div className="domain-card__head">
              <span className="domain-card__icon" aria-hidden="true">
                {d.icon}
              </span>
              <Badge variant={STATUS_VARIANT[d.status] || "ghost"}>
                {d.statusLabel}
              </Badge>
            </div>
            <div className="domain-card__title">{d.title}</div>
            <div className="domain-card__subtitle">{d.subtitle}</div>
            <div className="domain-card__metrics">
              {d.metrics.map((m) => (
                <div key={m.label} className="domain-metric">
                  <span className="domain-metric__label">{m.label}</span>
                  <span className="domain-metric__value">{m.value}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {dataSources && (
        <div className="datalake-badge">
          <span className="datalake-badge__tag">AWS Athena</span>
          <span className="datalake-badge__text">{dataSources.note}</span>
        </div>
      )}
    </Card>
  );
}
