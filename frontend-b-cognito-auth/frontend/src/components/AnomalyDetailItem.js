import React from "react";
import Badge from "./ui/Badge";
import { describeAnomaly, formatDiffPct } from "../utils/anomalyDetail";

const BADGE_VARIANT = { danger: "danger", warn: "warn", ok: "normal" };
const NO_INFO = "정보 없음";

// 이상 탐지 항목 1건의 상세 표시 (측정값·평소값·차이·기준·원인·권장 행동)
export default function AnomalyDetailItem({ anomaly, timeseries }) {
  const d = describeAnomaly(anomaly, { timeseries });
  const diff = formatDiffPct(d.diffPct);

  return (
    <div className="anomaly-detail-item">
      <div className="anomaly-detail-item__head">
        <span className={`anomaly-item__dot is-${d.severity}`} />
        <strong className="anomaly-detail-item__title">{d.title || "이상 탐지 항목"}</strong>
        <Badge variant={BADGE_VARIANT[d.severity]}>{d.severityLabel}</Badge>
      </div>
      <p className="ui-note">{d.severityMeaning}</p>
      <dl className="anomaly-detail-item__grid">
        <div><dt>지표</dt><dd>{d.metricLabel}</dd></div>
        <div><dt>측정값</dt><dd>{d.measured || NO_INFO}</dd></div>
        <div><dt>평소(평균)값</dt><dd>{d.baseline || NO_INFO}</dd></div>
        <div><dt>차이</dt><dd>{diff || NO_INFO}</dd></div>
        <div><dt>비교 기준</dt><dd>{d.basisLabel}</dd></div>
        <div><dt>탐지 시각</dt><dd>{d.detectedAt || NO_INFO}</dd></div>
      </dl>
      {anomaly && anomaly.desc ? <p className="anomaly-item__desc">{anomaly.desc}</p> : null}
      {d.severity !== "ok" && (
        <div className="anomaly-detail-item__tips">
          <p><strong>가능한 원인(참고)</strong> {d.hint}</p>
          <p><strong>권장 행동</strong> {d.action}</p>
        </div>
      )}
    </div>
  );
}
