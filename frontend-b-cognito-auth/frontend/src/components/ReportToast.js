import React from "react";
import { formatSleep } from "../services/dailyReport";

// 일일 리포트 앱 내 알림 배너 (자동으로 닫히지 않는다)
// include 를 생략하면 걸음수·수면을 표시한다.
export default function ReportToast({ report, onClose, include = { steps: true, sleep: true, heartRate: false } }) {
  return (
    <div className="report-toast" role="status">
      <div className="report-toast__head">
        <strong>오늘의 건강 리포트</strong>
        <button type="button" className="btn" onClick={onClose}>
          닫기
        </button>
      </div>
      {report.sourceLabel && <p className="report-toast__line">기준 앱: {report.sourceLabel}</p>}
      {include.steps && (
        <>
          <p className="report-toast__line">
            걸음수 {report.steps.toLocaleString("ko-KR")} / 목표 {report.goal.toLocaleString("ko-KR")}걸음 · 달성률 {report.percent}%
          </p>
          <p className="report-toast__line">
            {report.remaining > 0 ? `남은 걸음 ${report.remaining.toLocaleString("ko-KR")}걸음` : "목표 걸음을 달성했어요"}
            {report.stepsDelta && ` · 어제 대비 ${report.stepsDelta.text}`}
          </p>
        </>
      )}
      {include.sleep && (
        <p className="report-toast__line">
          수면시간 {formatSleep(report.sleepHours)} · 수면 평가 {report.sleepVerdict}
          {report.sleepDelta && ` · 어제 대비 ${report.sleepDelta.text}`}
        </p>
      )}
      {include.heartRate && report.heartRate != null && (
        <p className="report-toast__line">안정 시 심박 {report.heartRate}bpm</p>
      )}
      {report.comment && <p className="report-toast__line report-toast__comment">{report.comment}</p>}
      {report.isSample && <p className="ui-note" style={{ margin: 0 }}>예시 데이터입니다.</p>}
    </div>
  );
}
