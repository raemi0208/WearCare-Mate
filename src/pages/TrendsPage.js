import React, { useState } from "react";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import LineChart from "../components/ui/LineChart";
import { loadRange, saveRange } from "../services/rangeStorage";

const SERIES = [
  { key: "sleep", title: "수면 시간", unit: "시간", icon: "🌙", decimals: 1 },
  { key: "heartRate", title: "안정 시 심박", unit: "bpm", icon: "❤️", decimals: 0 },
  { key: "steps", title: "활동량", unit: "걸음", icon: "👟", decimals: 0 },
];

const RANGES = [
  { id: "daily", label: "일간", desc: "오늘 하루 3시간 간격" },
  { id: "weekly", label: "주간", desc: "최근 7일 일별" },
  { id: "monthly", label: "월간", desc: "최근 4주 주차별" },
];

function avg(arr) {
  if (!arr.length) return 0;
  return arr.reduce((s, d) => s + d.value, 0) / arr.length;
}

function fmt(v, decimals) {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return v.toLocaleString("ko-KR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export default function TrendsPage({ data }) {
  // 마지막으로 본 기간을 localStorage에서 복원
  const [range, setRange] = useState(() => loadRange());

  const byRange = data.timeseriesByRange || {};
  // 선택 기간 데이터, 없으면 기존 주간(timeseries)로 폴백
  const timeseries = byRange[range] || data.timeseries || {};
  const activeRange = RANGES.find((r) => r.id === range) || RANGES[1];

  const changeRange = (id) => {
    setRange(id);
    saveRange(id); // 선택 상태 localStorage에 저장
  };

  const stats = SERIES.map((s) => {
    const series = timeseries[s.key] || [];
    const values = series.map((d) => d.value);
    return {
      ...s,
      series,
      count: series.length,
      average: avg(series),
      max: values.length ? Math.max(...values) : null,
      min: values.length ? Math.min(...values) : null,
      anomalies: series.filter((d) => d.anomaly),
    };
  });

  return (
    <div className="grid">
      {/* 기간 토글 */}
      <div className="range-switch">
        <div className="range-switch__tabs">
          {RANGES.map((r) => (
            <button
              key={r.id}
              type="button"
              className={`range-switch__tab ${range === r.id ? "is-active" : ""
                }`.trim()}
              onClick={() => changeRange(r.id)}
            >
              {r.label}
            </button>
          ))}
        </div>
        <span className="range-switch__desc">{activeRange.desc}</span>
      </div>

      {/* 상단: 세 지표 한눈에 비교 */}
      <div className="grid grid--stats">
        {stats.map((s) => (
          <div key={s.key} className="card stat">
            <div className="stat__top">
              <span className="stat__icon" aria-hidden="true">
                {s.icon}
              </span>
              {s.anomalies.length > 0 ? (
                <Badge variant="danger">이상 {s.anomalies.length}</Badge>
              ) : (
                <Badge variant="normal">정상</Badge>
              )}
            </div>
            <div className="stat__label">
              {activeRange.label} {s.title} 평균
            </div>
            <div className="stat__value">
              {s.count ? fmt(s.average, s.decimals) : "—"}
              <span className="stat__unit">{s.unit}</span>
            </div>
            <div className="stat__delta is-flat">
              최고 {s.max != null ? fmt(s.max, s.decimals) : "—"} · 최저{" "}
              {s.min != null ? fmt(s.min, s.decimals) : "—"}
            </div>
          </div>
        ))}
        <div className="card stat">
          <div className="stat__top">
            <span className="stat__icon" aria-hidden="true">
              🔎
            </span>
          </div>
          <div className="stat__label">감지된 이상</div>
          <div className="stat__value">
            {stats.reduce((n, s) => n + s.anomalies.length, 0)}
            <span className="stat__unit">건</span>
          </div>
          <div className="stat__delta is-flat">SageMaker 분석</div>
        </div>
      </div>

      {/* 개별 상세 차트 */}
      {stats.map((s) => (
        <Card
          key={s.key}
          title={`${s.icon} ${s.title}`}
          subtitle={`${activeRange.label} 기록 (단위: ${s.unit})`}
          action={
            s.anomalies.length > 0 ? (
              <Badge variant="danger">이상 {s.anomalies.length}건</Badge>
            ) : (
              <Badge variant="ghost">
                {s.count ? "강조된 이상 없음" : "데이터 없음"}
              </Badge>
            )
          }
        >
          <LineChart
            data={s.series}
            showValues
            showYAxis
            valueFormatter={(v) => fmt(v, s.decimals)}
          />

          {s.anomalies.length > 0 && (
            <div className="trend-anomaly-note">
              <span className="anomaly-item__dot is-danger" />
              <span>
                이상 감지: {s.anomalies.map((a) => a.label).join(", ")} — 평소
                패턴과 다른 값이 확인되었습니다.
              </span>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}
