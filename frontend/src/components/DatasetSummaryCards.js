import React from "react";
import Card from "./ui/Card";
import Badge from "./ui/Badge";

function number(value) {
  return typeof value === "number" ? value.toLocaleString() : null;
}

// status 가 ok 가 아닐 때의 공통 안내 문구 (0 으로 표시하지 않음)
function statusNote(status) {
  if (status === "empty") return "집계 대상 데이터가 없습니다.";
  if (status === "error") return "집계를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.";
  return null;
}

function CardShell({ title, icon, summary, children }) {
  const note = summary ? statusNote(summary.status) : "집계 정보를 사용할 수 없습니다.";
  return (
    <Card title={title} icon={icon} action={<Badge variant="ghost">공개 데이터셋</Badge>}>
      {note ? (
        <p className="ui-note" style={{ margin: 0 }}>{note}</p>
      ) : (
        children
      )}
    </Card>
  );
}

function SleepCard({ summary }) {
  const ok = summary && summary.status === "ok";
  return (
    <CardShell icon="🌙" title="수면 데이터셋" summary={summary}>
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
  const excludesZero = summary?.averageBasis === "positive";
  return (
    <CardShell icon="❤️" title="심박 데이터셋" summary={summary}>
      {summary?.status === "ok" && (
        <div className="dataset-summary">
          <div className="dataset-summary__metric">
            <span className="ui-note">{excludesZero ? "평균 심박수" : "전체 평균 심박수"}</span>
            <strong>{number(summary.averageValue) ?? "—"}{summary.averageValue != null && summary.unit ? " " + summary.unit : ""}</strong>
          </div>
          {summary.totalRows != null && (
            <p className="ui-note">전체 기록 {number(summary.totalRows)}건</p>
          )}
          {excludesZero && summary.positiveRows != null && (
            <p className="ui-note">0보다 큰 기록 {number(summary.positiveRows)}건으로 평균을 계산했어요.</p>
          )}
        </div>
      )}
    </CardShell>
  );
}

const psychologyLabels = {
  integrated: "모아서 정리한 자료",
  validation: "검증용 자료",
};

function PsychologyCard({ summary }) {
  return (
    <CardShell icon="💬" title="심리상담 데이터셋" summary={summary}>
      {summary?.status === "ok" && (
        <div className="dataset-summary">
          {summary.files?.map((file) => (
            <div key={file.id} className="dataset-summary__metric">
              <span className="ui-note">{psychologyLabels[file.id] ?? file.label}</span>
              <strong>{file.rowCount == null ? "—" : number(file.rowCount) + "건"}</strong>
            </div>
          ))}
          <p className="ui-note">공개 자료의 항목 수를 보여줘요.</p>
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
    <div className="grid grid--datasets" aria-label="공개 데이터셋 요약">
      <SleepCard summary={sleep} />
      <HeartRateCard summary={heart} />
      <PsychologyCard summary={psychology} />
    </div>
  );
}
