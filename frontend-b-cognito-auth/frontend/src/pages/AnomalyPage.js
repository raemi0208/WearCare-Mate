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
        title="이상 패턴 상세 내역"
        subtitle={demoActive ? "가상 시연 입력에 대한 이상 탐지 결과" : (data.analysis?.note || "예시 이상 탐지 내역")}
      >
        <AnomalyPanel
          anomalies={anomalies}
          analysis={data.analysis}
          referenceDateOverride={demoActive ? demoReferenceDate : null}
          timeseries={data.timeseries}
          detailed
          embedded
        />
      </Card>

      <Card title="심각도 기준 안내" subtitle="배지가 의미하는 정도">
        <ul className="anomaly-detail-guide">
          <li><strong>주의</strong> 평소와 차이가 있어 지켜볼 필요가 있는 단계입니다. (분석 결과 낮음·중간)</li>
          <li><strong>위험</strong> 평소와 크게 달라 먼저 확인해 보면 좋은 단계입니다. (분석 결과 높음)</li>
          <li><strong>정상</strong> 이상이 감지되지 않았거나 평소 범위로 돌아온 상태입니다.</li>
        </ul>
      </Card>

      <Card title="탐지 방식 설명" subtitle="무엇과 비교하나요?">
        <ul className="anomaly-detail-guide">
          <li><strong>개인 기준선</strong> 내 과거 기록의 평균과 비교해 평소보다 얼마나 달라졌는지 봅니다.</li>
          <li><strong>집단 평균</strong> 전체 사용자 평균이나 권장 기준과 비교합니다. 개인 기록이 부족할 때 쓰입니다.</li>
          <li>항목에 비교 수치가 없으면 &apos;정보 없음&apos;으로 표시하며, 값을 추정해 채우지 않습니다.</li>
        </ul>
        <p className="ui-note">이 결과는 참고용이며 의학적 진단이 아닙니다. 불편한 증상이 계속되면 의료 전문가와 상담하세요.</p>
      </Card>
    </div>
  );
}
