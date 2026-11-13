import React from "react";

// 발표용 "별도 데이터셋" 요약 카드 3개 (수면 · 심박 · 심리상담)
//
// - 각 카드는 실제 API 가 반환한 집계값만 사용한다. 집계 누락/실패를 0 으로 표시하지 않는다.
// - status: "ok"(값 있음) / "empty"(대상 없음) / "error"(조회 실패) 를 구분해 안내한다.
// - sourceLabel("별도 데이터셋") 배지를 붙여, 사용자별 걸음 수/심박 차트와 다른 출처임을 표시한다.
// - 세 필드가 응답에 없으면(집계 비활성) 카드를 렌더하지 않는다.

function Badge({ label }) {
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        color: "var(--color-muted)",
        border: "1px solid var(--color-border)",
        borderRadius: 999,
        padding: "2px 8px",
      }}
    >
      {label || "별도 데이터셋"}
    </span>
  );
}

function number(value) {
  return typeof value === "number" ? value.toLocaleString() : null;
}

// status 가 ok 가 아닐 때의 공통 안내 문구 (0 으로 표시하지 않음)
function statusNote(status) {
  if (status === "empty") return "집계 대상 데이터가 없습니다.";
  if (status === "error") return "집계를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.";
  return null;
}

function CardShell({ title, summary, children }) {
  const note = summary ? statusNote(summary.status) : "집계 정보를 사용할 수 없습니다.";
  return (
    <div className="card" style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <strong>{title}</strong>
        <Badge label={summary && summary.sourceLabel} />
      </div>
      {note ? (
        <p className="ui-note" style={{ margin: 0 }}>{note}</p>
      ) : (
        children
      )}
    </div>
  );
}

function SleepCard({ summary }) {
  const ok = summary && summary.status === "ok";
  return (
    <CardShell title="수면 데이터셋" summary={summary}>
      {ok && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ fontSize: 22, fontWeight: 800 }}>
            {summary.averageHours != null ? `${summary.averageHours}시간` : "—"}
            <span style={{ fontSize: 12, fontWeight: 500, color: "var(--color-muted)", marginLeft: 6 }}>
              평균 수면 시간
            </span>
          </div>
          <div style={{ fontSize: 13, color: "var(--color-muted)" }}>
            집계 기록 수 {number(summary.recordCount) ?? "—"}건
          </div>
        </div>
      )}
    </CardShell>
  );
}

function HeartRateCard({ summary }) {
  const ok = summary && summary.status === "ok";
  // 단위/행 의미의 명시적 문서 근거가 약하므로, 확인된 집계(전체/양수 행 수)를 중심으로 표시한다.
  // 평균은 averageBasis 에 따라 라벨을 보수적으로 붙인다(positive=양수 값 평균 / all=전체 평균).
  const avgLabel =
    summary && summary.averageBasis === "positive"
      ? "양수 값 평균"
      : "전체 평균";
  return (
    <CardShell title="심박 데이터셋" summary={summary}>
      {ok && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ fontSize: 13 }}>
            전체 기록 <strong>{number(summary.totalRows) ?? "—"}</strong>행
          </div>
          <div style={{ fontSize: 13 }}>
            양수 값 <strong>{number(summary.positiveRows) ?? "—"}</strong>행
            {summary.zeroRows != null && (
              <span style={{ color: "var(--color-muted)" }}> · 0값 {number(summary.zeroRows)}행</span>
            )}
          </div>
          {summary.averageValue != null && (
            <div style={{ fontSize: 13, color: "var(--color-muted)" }}>
              {avgLabel} {summary.averageValue}
              {summary.unit ? ` ${summary.unit}` : ""}
            </div>
          )}
        </div>
      )}
    </CardShell>
  );
}

function PsychologyCard({ summary }) {
  const ok = summary && summary.status === "ok" && summary.files && summary.files.length > 0;
  return (
    <CardShell title="심리상담 데이터셋" summary={summary}>
      {ok && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {summary.files.map((f) => (
            <div key={f.id} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
              <span>{f.label}</span>
              <strong>
                {number(f.rowCount) ?? "—"}
                <span style={{ fontWeight: 500, color: "var(--color-muted)", marginLeft: 4 }}>
                  {summary.unit || "데이터 행 수"}
                </span>
              </strong>
            </div>
          ))}
        </div>
      )}
    </CardShell>
  );
}

export default function DatasetSummaryCards({ data }) {
  const sleep = data.sleepDatasetSummary;
  const heart = data.heartRateDatasetSummary;
  const psychology = data.psychologyDatasetSummary;

  // 세 필드가 모두 없으면(집계 비활성/목 모드 일부) 섹션을 렌더하지 않는다.
  if (!sleep && !heart && !psychology) return null;

  return (
    <div className="grid grid--datasets" aria-label="별도 데이터셋 요약">
      <SleepCard summary={sleep} />
      <HeartRateCard summary={heart} />
      <PsychologyCard summary={psychology} />
    </div>
  );
}
