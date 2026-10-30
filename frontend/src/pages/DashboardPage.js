import React from "react";
import StatCard from "../components/ui/StatCard";
import TrendChart from "../components/TrendChart";
import SleepStages from "../components/SleepStages";
import AnomalyPanel from "../components/AnomalyPanel";
import AiGuide from "../components/AiGuide";
import Notifications from "../components/Notifications";

export default function DashboardPage({ data, onRegenerate, regenerating }) {
  return (
    <>
      <div className="grid grid--stats">
        {data.summaryStats.map((s) => (
          <StatCard key={s.id} {...s} />
        ))}
      </div>

      <div className="grid grid--main">
        <div className="grid">
          <TrendChart timeseries={data.timeseries} />
          <SleepStages sleepStages={data.sleepStages} />
          <AnomalyPanel anomalies={data.anomalies} />
        </div>

        <div className="grid">
          <AiGuide
            guide={data.aiGuide}
            onRegenerate={onRegenerate}
            regenerating={regenerating}
          />
          <Notifications notifications={data.notifications} />
        </div>
      </div>
    </>
  );
}
