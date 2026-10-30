import React, { useEffect, useState, useCallback } from "react";
import "./App.css";

import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import StatCard from "./components/ui/StatCard";
import TrendChart from "./components/TrendChart";
import SleepStages from "./components/SleepStages";
import AnomalyPanel from "./components/AnomalyPanel";
import AiGuide from "./components/AiGuide";
import Notifications from "./components/Notifications";

import { fetchDashboard, fetchAiGuide } from "./services/api";

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeNav, setActiveNav] = useState("dashboard");
  const [regenerating, setRegenerating] = useState(false);

  useEffect(() => {
    let mounted = true;
    fetchDashboard()
      .then((res) => {
        if (mounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message || "데이터를 불러오지 못했습니다.");
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const handleRegenerate = useCallback(() => {
    setRegenerating(true);
    fetchAiGuide()
      .then((guide) => {
        setData((prev) => (prev ? { ...prev, aiGuide: guide } : prev));
      })
      .finally(() => setRegenerating(false));
  }, []);

  return (
    <div className="app">
      <Sidebar active={activeNav} onSelect={setActiveNav} />

      <div className="main">
        <Topbar user={data?.user} />

        <div className="content">
          {loading && <LoadingState />}
          {error && <ErrorState message={error} />}

          {data && !loading && !error && (
            <>
              {/* 요약 통계 */}
              <div className="grid grid--stats">
                {data.summaryStats.map((s) => (
                  <StatCard key={s.id} {...s} />
                ))}
              </div>

              {/* 메인: 좌측 차트/이상탐지, 우측 AI가이드/알림 */}
              <div className="grid grid--main">
                <div className="grid">
                  <TrendChart timeseries={data.timeseries} />
                  <SleepStages sleepStages={data.sleepStages} />
                  <AnomalyPanel anomalies={data.anomalies} />
                </div>

                <div className="grid">
                  <AiGuide
                    guide={data.aiGuide}
                    onRegenerate={handleRegenerate}
                    regenerating={regenerating}
                  />
                  <Notifications notifications={data.notifications} />
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="card" style={{ padding: "48px", textAlign: "center" }}>
      <p style={{ color: "var(--color-muted)" }}>건강 데이터를 불러오는 중…</p>
    </div>
  );
}

function ErrorState({ message }) {
  return (
    <div className="card" style={{ padding: "48px", textAlign: "center" }}>
      <p style={{ color: "var(--color-danger)", fontWeight: 600 }}>
        데이터를 불러오지 못했습니다.
      </p>
      <p style={{ color: "var(--color-muted)", marginTop: "8px" }}>{message}</p>
    </div>
  );
}

export default App;
