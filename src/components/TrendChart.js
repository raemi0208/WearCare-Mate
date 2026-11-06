import React, { useState } from "react";
import Card from "./ui/Card";
import LineChart from "./ui/LineChart";

const TABS = [
  { id: "sleep", label: "수면", unit: "시간" },
  { id: "heartRate", label: "심박", unit: "bpm" },
  { id: "steps", label: "활동량", unit: "걸음" },
];

export default function TrendChart({ timeseries }) {
  const [tab, setTab] = useState(() => TABS.find((t) => timeseries[t.id]?.length)?.id || "steps");
  const current = TABS.find((t) => t.id === tab);
  const data = timeseries[tab] || [];
  const hasAnomaly = data.some((d) => d.anomaly);

  const tabs = (
    <div className="chart__tabs">
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`chart__tab ${tab === t.id ? "is-active" : ""}`.trim()}
          onClick={() => setTab(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );

  return (
    <Card
      title="최근 7일 추이"
      subtitle={`${current.label} 기록 (단위: ${current.unit}) · 일/주/월 비교는 추이 분석에서`}
      action={tabs}
    >
      <div className="chart__legend">
        <span className="chart__legend-item">
          <span className="chart__swatch" style={{ background: "#141414" }} />
          일별 측정값
        </span>
        {hasAnomaly && (
          <span className="chart__legend-item">
            <span className="chart__swatch" style={{ background: "#9b2c2c" }} />
            이상 패턴 (AI/ML 판정)
          </span>
        )}
      </div>
      <LineChart data={data} />
    </Card>
  );
}
