import React from "react";
import Card from "./ui/Card";
import LineChart from "./ui/LineChart";

export default function TrendChart({ steps = [] }) {
  const hasAnomaly = steps.some((point) => point.anomaly);

  return (
    <Card icon="📈" title="시계열 추이" subtitle="조회된 기준 주의 활동량 기록 (단위: 걸음)">
      <div className="chart__legend">
        <span className="chart__legend-item">
          <span className="chart__swatch" style={{ background: "#141414" }} />
          일별 걸음 수
        </span>
        {hasAnomaly && (
          <span className="chart__legend-item">
            <span className="chart__swatch" style={{ background: "#9b2c2c" }} />
            이상 패턴 (AI/ML 판정)
          </span>
        )}
      </div>
      <LineChart data={steps} />
    </Card>
  );
}
