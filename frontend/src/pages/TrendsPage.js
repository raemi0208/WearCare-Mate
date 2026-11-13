import React, { useEffect, useState } from "react";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import LineChart from "../components/ui/LineChart";
import { isAuthEnabled } from "../services/authConfig";
import { getDailyReport } from "../services/api";
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

export default function TrendsPage({ data, initialPersonal = false }) {
  const authenticated = isAuthEnabled();
  const [personal, setPersonal] = useState(initialPersonal);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!personal || !authenticated) return undefined;
    let active = true;
    getDailyReport().then((value) => {
      if (active) { setReport(value); setError(false); }
    }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [personal, authenticated]);

  const points = report?.records?.filter((entry) => Number.isFinite(entry.sleep))
    .map((entry) => ({ label: entry.date.slice(5), value: entry.sleep })) || [];

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
      {authenticated && (
        <div className="chart__tabs" aria-label="기록 출처">
          <button type="button" className={`chart__tab ${personal ? "" : "is-active"}`}
            aria-pressed={!personal} onClick={() => setPersonal(false)}>공개 데이터</button>
          <button type="button" className={`chart__tab ${personal ? "is-active" : ""}`}
            aria-pressed={personal} onClick={() => setPersonal(true)}>내 기록</button>
        </div>
      )}
      {personal && authenticated ? (
        <Card icon="🌙" title="내 수면 기록" subtitle="최근 30일 · 직접 입력 · 단위 시간">
          {error ? <p role="alert">내 기록을 불러오지 못했습니다.</p>
            : !report ? <p role="status">내 기록을 불러오는 중이에요.</p>
            : points.length ? <LineChart data={points} />
            : <p>오늘의 건강 리포트에서 수면 시간을 입력해 주세요.</p>}
        </Card>
      ) : <>
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
      </>}
    </div>
  );
}