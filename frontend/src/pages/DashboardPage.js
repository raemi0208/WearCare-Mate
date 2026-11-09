import React from "react";
import StatCard from "../components/ui/StatCard";
import TrendChart from "../components/TrendChart";
import SleepStages from "../components/SleepStages";
import AnomalyPanel from "../components/AnomalyPanel";
import AiGuide from "../components/AiGuide";
import Notifications from "../components/Notifications";
import DatasetSummaryCards from "../components/DatasetSummaryCards";
import DemoBanner from "../components/DemoBanner";

export default function DashboardPage({ data, onRegenerate, regenerating, demoActive = false, demoReferenceDate = null, onHideNotification }) {
  // 분석 기준일/이상 탐지 카드는 가상 결과(anomalies)를 설명하는 영역이다.
  // 시연 중에는 데모 기준일을 표시하되, 실제 data.analysis 는 바꾸지 않는다.
  // (상단 통계·추이 차트 등 실제 집계의 2016년 값은 그대로 유지한다.)
  const displayReferenceDate = demoActive ? demoReferenceDate : data.analysis?.referenceDate;
  return (
    <>
      <DemoBanner demoActive={demoActive} demoReferenceDate={demoReferenceDate} />
      {data.analysis && (
        <div className="card" style={{ padding: 16 }}>
          <p>분석 기준일: {displayReferenceDate}</p>
          <p className="ui-note">{demoActive ? "가상 시연 입력에 대한 이상 탐지 결과입니다." : data.analysis.note}</p>
        </div>
      )}
      <div className="grid grid--stats">
        {data.summaryStats.map((s) => (
          <StatCard key={s.id} {...s} />
        ))}
      </div>

      <DatasetSummaryCards data={data} />

      <div className="grid grid--main">
        <div className="grid">
          <TrendChart timeseries={data.timeseries} />
          <SleepStages sleepStages={data.sleepStages} />
          <AnomalyPanel
            anomalies={data.anomalies}
            analysis={data.analysis}
            referenceDateOverride={demoActive ? demoReferenceDate : null}
          />
        </div>

        <div className="grid">
          <AiGuide
            guide={data.aiGuide}
            onRegenerate={onRegenerate}
            regenerating={regenerating}
          />
          <Notifications notifications={data.notifications} onHide={onHideNotification} />
        </div>
      </div>
    </>
  );
}
