import React from "react";
import Card from "../components/ui/Card";
import AnomalyPanel from "../components/AnomalyPanel";
import DemoBanner from "../components/DemoBanner";

export default function AnomalyPage({ data, demoActive = false, demoReferenceDate = null }) {
  const anomalies = data.anomalies || [];
  const counts = {
    danger: anomalies.filter((a) => a.severity === "danger").length,
    warn: anomalies.filter((a) => a.severity === "warn").length,
    ok: anomalies.filter((a) => a.severity === "ok").length,
  };

  const summary = [
    { id: "danger", label: "위험", value: counts.danger, cls: "is-danger" },
    { id: "warn", label: "주의", value: counts.warn, cls: "is-warn" },
    { id: "ok", label: "정상", value: counts.ok, cls: "is-ok" },
  ];

  // 이상 탐지 화면은 가상 결과(anomalies/aiGuide)를 설명하는 영역이다.
  // 시연 중에는 기준일을 데모 기준일로 표시한다. 실제 data.analysis 는 바꾸지 않는다.
  const displayReferenceDate = demoActive ? demoReferenceDate : data.analysis?.referenceDate;

  return (
    <div className="grid">
      <DemoBanner demoActive={demoActive} demoReferenceDate={demoReferenceDate} />
      <div className="grid grid--stats">
        {summary.map((s) => (
          <div key={s.id} className="card stat">
            <div className="stat__label">{s.label}</div>
            <div className="stat__value">
              {s.value}
              <span className="stat__unit">건</span>
            </div>
            <span className={`anomaly-item__dot ${s.cls}`} style={{ marginTop: 8 }} />
          </div>
        ))}
        <div className="card stat">
          <div className="stat__label">분석 엔진</div>
          <div className="stat__value" style={{ fontSize: 18 }}>
            {demoActive && data.demoScenario && data.demoScenario !== "steps" ? "집단 지표 기준선" : data.analysis ? "활동량 기준선" : "예시 분석"}
          </div>
          <div className="stat__delta is-flat">{displayReferenceDate || "예시 데이터"}</div>
        </div>
      </div>

      <Card
        icon="⚠️" title="이상 패턴 상세 내역"
        subtitle={demoActive ? "가상 시연 입력에 대한 이상 탐지 결과" : (data.analysis?.note || "예시 이상 탐지 내역")}
      >
        <AnomalyPanel
          anomalies={anomalies}
          analysis={data.analysis}
          referenceDateOverride={demoActive ? demoReferenceDate : null}
          embedded
        />
      </Card>
    </div>
  );
}
