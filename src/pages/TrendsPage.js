import React from "react";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import LineChart from "../components/ui/LineChart";

const SERIES = [
  { key: "sleep", title: "수면 시간", unit: "시간", icon: "🌙" },
  { key: "heartRate", title: "안정 시 심박", unit: "bpm", icon: "❤️" },
  { key: "steps", title: "활동량", unit: "보", icon: "👟" },
];

function avg(arr) {
  if (!arr.length) return 0;
  return arr.reduce((s, d) => s + d.value, 0) / arr.length;
}

export default function TrendsPage({ data }) {
  const { timeseries } = data;

  return (
    <div className="grid">
      {SERIES.map((s) => {
        const series = timeseries[s.key] || [];
        const values = series.map((d) => d.value);
        const average = avg(series);
        const max = Math.max(...values);
        const min = Math.min(...values);
        const anomalyCount = series.filter((d) => d.anomaly).length;

        return (
          <Card
            key={s.key}
            title={`${s.icon} ${s.title}`}
            subtitle={`최근 7일 추이 (단위: ${s.unit})`}
            action={
              anomalyCount > 0 ? (
                <Badge variant="danger">이상 {anomalyCount}건</Badge>
              ) : (
                <Badge variant="normal">정상</Badge>
              )
            }
          >
            <div className="trend-stats">
              <div className="trend-stat">
                <span className="trend-stat__label">평균</span>
                <span className="trend-stat__value">
                  {average.toFixed(s.key === "steps" ? 0 : 1)}
                  <span className="trend-stat__unit">{s.unit}</span>
                </span>
              </div>
              <div className="trend-stat">
                <span className="trend-stat__label">최고</span>
                <span className="trend-stat__value">
                  {max}
                  <span className="trend-stat__unit">{s.unit}</span>
                </span>
              </div>
              <div className="trend-stat">
                <span className="trend-stat__label">최저</span>
                <span className="trend-stat__value">
                  {min}
                  <span className="trend-stat__unit">{s.unit}</span>
                </span>
              </div>
            </div>
            <LineChart data={series} />
          </Card>
        );
      })}
    </div>
  );
}
