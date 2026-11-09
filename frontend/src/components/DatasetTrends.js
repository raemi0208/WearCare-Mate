import React, { useState } from "react";
import Card from "./ui/Card";
import Badge from "./ui/Badge";
import LineChart from "./ui/LineChart";

// 발표용 "별도 데이터셋" 추이 (추이 분석 페이지의 실제 모드 전용).
//
// ⚠ 이 영역은 Fitbit 시연 사용자(걸음 수·가상 이상 시연)와 "연결되지 않은" 별도 데이터셋이다.
//   개인별 timeseries.sleep / heartRate 를 채우지 않고, 데이터셋 집계(dataset_summary)만 표시한다.
//
// props:
//  - sleepSummary: data.sleepDatasetSummary (없거나 status 로 상태 구분)
//  - heartSummary: data.heartRateDatasetSummary
//
// 상태 구분: status 없음/empty/error 는 안내만, ok 라도 확장 필드(distribution/dailySeries)가
//   없으면 '확장 집계 미제공'으로 안내한다(이전 배포 API 호환). 목 데이터로 대체하지 않는다.

const DATASET_BADGE = "별도 데이터셋";
const DATASET_DESC = "Fitbit 시연 사용자 기록과 연결되지 않은 별도 데이터셋입니다.";

// status 기반 공통 안내(ok 면 null). 확장 필드 유무는 각 섹션에서 별도로 판단한다.
function statusMessage(summary) {
  if (!summary || !summary.status) return "데이터셋 요약이 제공되지 않았습니다.";
  if (summary.status === "empty") return "조회된 데이터가 없습니다.";
  if (summary.status === "error") return "데이터셋을 조회하지 못했습니다.";
  return null; // ok
}

const isNonNegativeInt = (v) =>
  typeof v === "number" && Number.isInteger(v) && v >= 0;

const isFiniteNumber = (v) => typeof v === "number" && Number.isFinite(v);

const datasetBadge = <Badge variant="ghost">{DATASET_BADGE}</Badge>;

// ---------------------------------------------------------------------------
// 막대차트 레이아웃 (외부 CSS 없이 인라인 스타일로 완성)
// ---------------------------------------------------------------------------
const BAR_TRACK_HEIGHT = 140;

const barStyles = {
  // 구간을 가로로 배치. 좁은 화면에서는 가로 스크롤로 라벨·건수가 잘리지 않게 한다.
  row: {
    display: "flex",
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
    overflowX: "auto",
    paddingBottom: 4,
  },
  col: {
    flex: "1 0 72px",   // 최소 폭 확보(좁은 화면에서 스크롤)
    minWidth: 72,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 4,
  },
  // 트랙: 고정 높이. 내부 막대는 아래쪽 정렬(flex-end).
  track: {
    width: "100%",
    height: BAR_TRACK_HEIGHT,
    display: "flex",
    alignItems: "flex-end",
    justifyContent: "center",
    background: "var(--color-panel, #ededf0)",
    borderRadius: "var(--radius-sm, 8px)",
  },
  fill: {
    width: "70%",
    background: "var(--color-ink, #141414)",
    borderRadius: "8px 8px 0 0",
    minHeight: 0, // 0 건이어도 바닥에 얇게 보이도록
  },
  count: { fontSize: 12, fontWeight: 700 },
  label: {
    fontSize: 11,
    color: "var(--color-muted, #71717a)",
    textAlign: "center",
    lineHeight: 1.3,
    wordBreak: "keep-all",
  },
};

// ---------------------------------------------------------------------------
// 수면 시간 분포
// ---------------------------------------------------------------------------
function SleepDistribution({ sleepSummary }) {
  const msg = statusMessage(sleepSummary);
  if (msg) {
    return (
      <Card title="수면 시간 분포" action={datasetBadge}>
        <p role="status">{msg}</p>
        <p style={{ fontSize: 12, color: "var(--color-muted)", margin: "8px 0 0" }}>
          {DATASET_DESC}
        </p>
      </Card>
    );
  }

  const distribution = sleepSummary.distribution;
  // ok 라도 확장 필드가 없으면 호환 안내(이전 배포 API).
  if (!Array.isArray(distribution)) {
    return (
      <Card title="수면 시간 분포" action={datasetBadge}>
        <p role="status">확장 집계가 제공되지 않았습니다.</p>
        <p style={{ fontSize: 12, color: "var(--color-muted)", margin: "8px 0 0" }}>
          {DATASET_DESC}
        </p>
      </Card>
    );
  }

  // 버킷 count 검증: 음수가 아닌 정수여야 한다. 누락·비정상은 0 으로 대체하지 않는다.
  const invalidBucket = distribution.some((b) => !b || !isNonNegativeInt(b.count));
  const bucketTotal = invalidBucket
    ? null
    : distribution.reduce((sum, b) => sum + b.count, 0);
  const recordCount = sleepSummary.recordCount;
  // 합계가 recordCount 와 다르면 차트를 그리지 않고 집계 오류를 안내한다.
  const sumMismatch =
    isNonNegativeInt(recordCount) && bucketTotal !== null && bucketTotal !== recordCount;

  const fmt = (v, suffix = "시간") => (isFiniteNumber(v) ? `${v}${suffix}` : "—");

if (
  !isNonNegativeInt(recordCount) ||
  distribution.length === 0 ||
  invalidBucket ||
  sumMismatch
) {
     return (
      <Card title="수면 시간 분포" action={datasetBadge}>
        <p role="alert">수면 분포 집계가 올바르지 않아 차트를 표시하지 않습니다.</p>
        <p style={{ fontSize: 12, color: "var(--color-muted)", margin: "8px 0 0" }}>
          {invalidBucket
            ? "구간 건수 값이 비정상입니다."
            : `구간 합계(${bucketTotal?.toLocaleString?.() ?? bucketTotal})가 전체 건수(${
                isNonNegativeInt(recordCount) ? recordCount.toLocaleString() : "—"
              })와 일치하지 않습니다.`}
          {" "}
          {DATASET_DESC}
        </p>
      </Card>
    );
  }

  const counts = distribution.map((b) => b.count);
  const maxCount = counts.length ? Math.max(...counts) : 0;

  return (
    <Card title="수면 시간 분포" action={datasetBadge}>
      <div className="trend-stats">
        <div className="trend-stat">
          <span className="trend-stat__label">평균</span>
          <span className="trend-stat__value">{fmt(sleepSummary.averageHours)}</span>
        </div>
        <div className="trend-stat">
          <span className="trend-stat__label">최소</span>
          <span className="trend-stat__value">{fmt(sleepSummary.minimumHours)}</span>
        </div>
        <div className="trend-stat">
          <span className="trend-stat__label">최대</span>
          <span className="trend-stat__value">{fmt(sleepSummary.maximumHours)}</span>
        </div>
        <div className="trend-stat">
          <span className="trend-stat__label">유효 건수</span>
          <span className="trend-stat__value">
            {isNonNegativeInt(recordCount) ? recordCount.toLocaleString() : "—"}
            <span className="trend-stat__unit">건</span>
          </span>
        </div>
      </div>

      <div style={barStyles.row} role="img" aria-label="수면 시간 구간별 건수 막대차트">
        {distribution.map((b, i) => {
          const pct = maxCount > 0 ? Math.round((b.count / maxCount) * 100) : 0;
          return (
            <div key={b.label || i} style={barStyles.col}>
              <div style={barStyles.track}>
                <div
                  style={{ ...barStyles.fill, height: `${pct}%` }}
                  title={`${b.label}: ${b.count.toLocaleString()}건`}
                />
              </div>
              <div style={barStyles.count}>{b.count.toLocaleString()}</div>
              <div style={barStyles.label}>{b.label}</div>
            </div>
          );
        })}
      </div>

      <p style={{ fontSize: 12, color: "var(--color-muted)", margin: "12px 0 0" }}>
        {DATASET_DESC}
      </p>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// 날짜별 평균 심박
// ---------------------------------------------------------------------------
function HeartDaily({ heartSummary }) {
  const [showRows, setShowRows] = useState(false);
  const msg = statusMessage(heartSummary);

  if (msg) {
    return (
      <Card title="날짜별 평균 심박" action={datasetBadge}>
        <p role="status">{msg}</p>
        <p style={{ fontSize: 12, color: "var(--color-muted)", margin: "8px 0 0" }}>
          {DATASET_DESC}
        </p>
      </Card>
    );
  }

  const dailySeries = heartSummary.dailySeries;
  if (!Array.isArray(dailySeries)) {
    return (
      <Card title="날짜별 평균 심박" action={datasetBadge}>
        <p role="status">확장 집계가 제공되지 않았습니다.</p>
        <p style={{ fontSize: 12, color: "var(--color-muted)", margin: "8px 0 0" }}>
          {DATASET_DESC}
        </p>
      </Card>
    );
  }

  // LineChart 매핑: label=date, value=averageValue, includedRows 그대로 전달.
  // averageValue=null 은 null 그대로 둔다(0 변환 금지 → 차트가 결측으로 끊음).
  const chartData = dailySeries.map((d) => ({
    label: d.date,
    value: d.averageValue,
    includedRows: d.includedRows,
  }));

  // 단위 미확인(unit=null)이면 bpm 등을 붙이지 않는다.
  const hasUnit = typeof heartSummary.unit === "string" && heartSummary.unit.length > 0;
  const unitText = hasUnit ? heartSummary.unit : "";
  const unitSuffix = hasUnit ? ` ${heartSummary.unit}` : "";

  const overall = isFiniteNumber(heartSummary.averageValue)
    ? heartSummary.averageValue
    : null;
  const basisText =
    heartSummary.averageBasis === "positive"
      ? "0 이하 값 제외(양수 heart_rate 행 평균)"
      : heartSummary.averageBasis === "all"
      ? "전체 행 평균"
      : "기준 미상";

  return (
    <Card title="날짜별 평균 심박" action={datasetBadge}>
      <div className="trend-stats">
        <div className="trend-stat">
          <span className="trend-stat__label">전체 대표 평균</span>
          <span className="trend-stat__value">
            {overall != null ? `${overall}${unitSuffix}` : "—"}
          </span>
        </div>
        <div className="trend-stat">
          <span className="trend-stat__label">양수 행 수</span>
          <span className="trend-stat__value">
            {isNonNegativeInt(heartSummary.positiveRows)
              ? heartSummary.positiveRows.toLocaleString()
              : "—"}
            <span className="trend-stat__unit">행</span>
          </span>
        </div>
        <div className="trend-stat">
          <span className="trend-stat__label">날짜 파싱 실패</span>
          <span className="trend-stat__value">
            {isNonNegativeInt(heartSummary.invalidDateRows)
              ? heartSummary.invalidDateRows.toLocaleString()
              : "—"}
            <span className="trend-stat__unit">행</span>
          </span>
        </div>
      </div>

      <p style={{ fontSize: 12, color: "var(--color-muted)", margin: "0 0 8px" }}>
        {DATASET_DESC} 전체 대표 평균은 {basisText} 기준이고, 아래 날짜별 평균은 날짜마다
        heart_rate > 0 인 행만 평균한 값이라 집계 기준이 다를 수 있습니다.
        {!hasUnit && " 단위 미확인이라 수치만 표시합니다."}
      </p>

      <LineChart data={chartData} />

      <button
        type="button"
        className="chart__tab"
        style={{ marginTop: 12 }}
        onClick={() => setShowRows((v) => !v)}
        aria-expanded={showRows}
      >
        {showRows ? "날짜별 포함 건수 접기" : "날짜별 포함 건수 보기"}
      </button>

      {showRows && (
        <div style={{ marginTop: 8, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: "6px 8px" }}>날짜</th>
                <th style={{ textAlign: "right", padding: "6px 8px" }}>
                  평균{unitText ? ` (${unitText})` : ""}
                </th>
                <th style={{ textAlign: "right", padding: "6px 8px" }}>포함 건수</th>
              </tr>
            </thead>
            <tbody>
              {dailySeries.map((d) => (
                <tr key={d.date}>
                  <td style={{ padding: "6px 8px" }}>{d.date}</td>
                  <td style={{ textAlign: "right", padding: "6px 8px" }}>
                    {isFiniteNumber(d.averageValue) ? d.averageValue : "—"}
                  </td>
                  <td style={{ textAlign: "right", padding: "6px 8px" }}>
                    {isNonNegativeInt(d.includedRows)
                      ? d.includedRows.toLocaleString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// 묶음: 수면 분포 + 심박 날짜별 + 수면 단계 미제공 안내
// ---------------------------------------------------------------------------
export default function DatasetTrends({ sleepSummary, heartSummary }) {
  return (
    <div className="grid">
      <SleepDistribution sleepSummary={sleepSummary} />
      <HeartDaily heartSummary={heartSummary} />

      <Card title="수면 단계 분석" action={datasetBadge}>
        <p role="status">현재 데이터셋은 수면 단계 정보를 제공하지 않습니다.</p>
      </Card>
    </div>
  );
}
