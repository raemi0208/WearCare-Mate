import React from "react";
import Card from "./ui/Card";
import Badge from "./ui/Badge";

export default function SleepStages({ sleepStages }) {
  const { totalLabel, segments } = sleepStages;

  if (segments.length === 0) {
    return (
      <Card title="수면 단계 분석" action={<Badge variant="ghost">정보 미제공</Badge>}>
        <p role="status">현재 데이터셋은 수면 단계 정보를 제공하지 않습니다.</p>
      </Card>
    );
  }

  return (
    <Card
      title="수면 단계 분석"
      subtitle={segments.length ? "수면 구조" : "수면 단계 데이터가 연결되지 않았습니다"}
      action={<Badge variant="ghost">총 {totalLabel}</Badge>}
    >
      <div className="sleep-stages">
        {segments.map((s) => (
          <div
            key={s.id}
            className="sleep-stages__seg"
            style={{ width: `${s.pct}%`, background: s.color }}
            title={`${s.label} ${s.pct}%`}
          />
        ))}
      </div>
      <div className="sleep-legend">
        {segments.map((s) => (
          <div key={s.id} className="sleep-legend__item">
            <span
              className="sleep-legend__swatch"
              style={{ background: s.color }}
            />
            {s.label} · {s.pct}%
          </div>
        ))}
      </div>
    </Card>
  );
}
