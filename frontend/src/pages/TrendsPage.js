import React from "react";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import LineChart from "../components/ui/LineChart";
import DatasetTrends from "../components/DatasetTrends";

const SERIES = [
  { key: "sleep", title: "수면 시간", unit: "시간", icon: "🌙" },
  { key: "heartRate", title: "안정 시 심박", unit: "bpm", icon: "❤️" },
  { key: "steps", title: "활동량", unit: "걸음", icon: "👟" },
];

function isValidPoint(point) {
  return (
    point != null &&
    typeof point.value === "number" &&
    Number.isFinite(point.value)
  );
}

export default function TrendsPage({ data }) {
  const timeseries = data.timeseries || {};

  const hasDatasetSummaries =
    data.sleepDatasetSummary !== undefined ||
    data.heartRateDatasetSummary !== undefined;

  // 별도 데이터셋이 있으면 개인별 수면·심박 카드와 중복하지 않는다.
  // 목 모드에서는 기존 세 차트를 유지한다.
  const visibleSeries = hasDatasetSummaries
    ? SERIES.filter((series) => series.key === "steps")
    : SERIES;

  return (
    <div className="grid">
      {visibleSeries.map((seriesConfig) => {
        const rawSeries = timeseries[seriesConfig.key];
        const series = Array.isArray(rawSeries) ? rawSeries : [];
        const validPoints = series.filter(isValidPoint);
        const values = validPoints.map((point) => point.value);

        const average = values.length
          ? values.reduce((sum, value) => sum + value, 0) / values.length
          : null;

        const maximum = values.length ? Math.max(...values) : null;
        const minimum = values.length ? Math.min(...values) : null;
        const anomalyCount = validPoints.filter(
          (point) => point.anomaly
        ).length;

        return (
          <Card
            key={seriesConfig.key}
            icon={seriesConfig.icon} title={seriesConfig.title}
            subtitle={`조회된 기준 주의 기록 (단위: ${seriesConfig.unit})`}
            action={
              anomalyCount > 0 ? (
                <Badge variant="danger">
                  이상 {anomalyCount}건
                </Badge>
              ) : (
                <Badge variant="ghost">
                  {values.length ? "강조된 이상 없음" : "데이터 없음"}
                </Badge>
              )
            }
          >
            <div className="trend-stats">
              <div className="trend-stat">
                <span className="trend-stat__label">평균</span>
                <span className="trend-stat__value">
                  {average !== null
                    ? average.toFixed(
                        seriesConfig.key === "steps" ? 0 : 1
                      )
                    : "—"}
                  <span className="trend-stat__unit">
                    {seriesConfig.unit}
                  </span>
                </span>
              </div>

              <div className="trend-stat">
                <span className="trend-stat__label">최고</span>
                <span className="trend-stat__value">
                  {maximum ?? "—"}
                  <span className="trend-stat__unit">
                    {seriesConfig.unit}
                  </span>
                </span>
              </div>

              <div className="trend-stat">
                <span className="trend-stat__label">최저</span>
                <span className="trend-stat__value">
                  {minimum ?? "—"}
                  <span className="trend-stat__unit">
                    {seriesConfig.unit}
                  </span>
                </span>
              </div>
            </div>

            <LineChart data={series} />
          </Card>
        );
      })}

      {hasDatasetSummaries && (
        <DatasetTrends
          sleepSummary={data.sleepDatasetSummary}
          heartSummary={data.heartRateDatasetSummary}
        />
      )}
    </div>
  );
}