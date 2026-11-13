import React from "react";
import Card from "./ui/Card";
import Badge from "./ui/Badge";

const finite = (value) => typeof value === "number" && Number.isFinite(value);

export default function SleepMetrics({ summary }) {
  const ok = summary?.status === "ok";
  const movementOk = ok && summary.movementStatus === "ok" && finite(summary.averageMovement);
  const note = summary?.status === "error" ? "수면 데이터셋을 조회하지 못했습니다." :
    summary?.status === "empty" ? "조회된 수면 기록이 없습니다." : "수면 관련 집계가 제공되지 않았습니다.";
  return (
    <Card icon="🌙" title="수면 관련 지표" subtitle="수면 시간 · 수면 중 움직임" action={<Badge variant="ghost">{summary ? "공개 데이터셋" : "정보 미제공"}</Badge>}>
      {ok ? (
        <dl style={{display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 16, margin: "0 0 12px"}}>
          <div>
            <dt className="ui-note">데이터셋 평균 수면 시간</dt>
            <dd style={{margin: 0, fontWeight: 700, fontSize: 20}}>{finite(summary.averageHours) ? `${summary.averageHours} 시간` : "—"}</dd>
            <p className="ui-note">{Number.isInteger(summary.recordCount) ? `유효 수면 기록 ${summary.recordCount.toLocaleString()}건` : "건수 미제공"}</p>
          </div>
          <div>
            <dt className="ui-note">데이터셋 평균 수면 중 움직임</dt>
            <dd style={{margin: 0, fontWeight: 700, fontSize: 20}}>{movementOk ? summary.averageMovement : "—"}</dd>
            <p className="ui-note">{movementOk ? `유효 움직임 기록 ${summary.movementRecordCount?.toLocaleString() ?? "—"}건 · 단위 미확인` :
              summary.movementStatus === "error" ? "움직임 집계를 확인하지 못했습니다." : "유효한 움직임 집계가 제공되지 않았습니다."}</p>
          </div>
        </dl>
      ) : <p className="ui-note" role="status">{note}</p>}
      <p className="ui-note">Fitbit 사용자와 연결되지 않은 공개 데이터셋 집계입니다. 움직임은 유효 수면 기록 중 0 이상인 값의 평균이며, 뒤척임 횟수나 수면 단계 비율이 아닙니다.</p>
      <p className="ui-note">현재 데이터셋은 수면 단계 정보를 제공하지 않습니다.</p>
    </Card>
  );
}
