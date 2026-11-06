import React, { useEffect, useState, useCallback } from "react";
import "./App.css";

import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";

import DashboardPage from "./pages/DashboardPage";
import TrendsPage from "./pages/TrendsPage";
import AnomalyPage from "./pages/AnomalyPage";
import MindPage from "./pages/MindPage";
import BodyPage from "./pages/BodyPage";
import GuidePage from "./pages/GuidePage";
import DevicesPage from "./pages/DevicesPage";
import SettingsPage from "./pages/SettingsPage";

import { fetchDashboard, fetchAiGuide } from "./services/api";

// 각 페이지의 상단 제목/부제목
const PAGE_META = {
  dashboard: {
    title: "건강 대시보드",
    subtitle: "오늘 기준 건강 상태 요약 (기간별 추이는 추이 분석에서)",
  },
  trends: {
    title: "추이 분석",
    subtitle: "수면 · 심박 · 활동량 시계열 상세 추이",
  },
  anomaly: {
    title: "이상 탐지",
    subtitle: "기록 데이터 기반 이상 패턴 분석",
  },
  mind: {
    title: "심리·스트레스",
    subtitle: "심리상담 점수 기반 정신 건강 상태",
  },
  body: {
    title: "근골격계",
    subtitle: "관절염 메타데이터 기반 통증 현황",
  },
  guide: {
    title: "AI 건강 가이드",
    subtitle: "Amazon Bedrock 생성형 AI 맞춤 가이드",
  },
  devices: {
    title: "기기 연동",
    subtitle: "연결된 웨어러블 기기 및 데이터 수집 상태",
  },
  settings: {
    title: "설정",
    subtitle: "프로필 정보 및 알림 설정",
  },
};

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeNav, setActiveNav] = useState("dashboard");
  const [regenerating, setRegenerating] = useState(false);
  const [guideError, setGuideError] = useState(null);

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
    setGuideError(null);
    setRegenerating(true);
    fetchAiGuide()
      .then((guide) => {
        setData((prev) => (prev ? { ...prev, aiGuide: guide } : prev));
      })
      .catch(() => setGuideError("분석 및 가이드를 다시 확인하지 못했습니다. 잠시 후 다시 시도해 주세요."))
      .finally(() => setRegenerating(false));
  }, []);

  const handleProfileSaved = useCallback((updatedUser) => {
    setData((prev) => (prev ? { ...prev, user: updatedUser } : prev));
  }, []);

  const meta = PAGE_META[activeNav] || PAGE_META.dashboard;

  function renderPage() {
    if (!data) return null;
    const common = { data };
    switch (activeNav) {
      case "trends":
        return <TrendsPage {...common} />;
      case "anomaly":
        return <AnomalyPage {...common} />;
      case "mind":
        return <MindPage {...common} />;
      case "body":
        return <BodyPage {...common} />;
      case "guide":
        return (
          <GuidePage
            {...common}
            onRegenerate={handleRegenerate}
            regenerating={regenerating}
          />
        );
      case "devices":
        return <DevicesPage {...common} />;
      case "settings":
        return (
          <SettingsPage
            user={data.user}
            onProfileSaved={handleProfileSaved}
          />
        );
      case "dashboard":
      default:
        return (
          <DashboardPage
            {...common}
            onRegenerate={handleRegenerate}
            regenerating={regenerating}
          />
        );
    }
  }

  return (
    <div className="app">
      <Sidebar active={activeNav} onSelect={setActiveNav} />

      <div className="main">
        <Topbar
          user={data?.user}
          title={meta.title}
          subtitle={meta.subtitle}
          onProfileClick={() => setActiveNav("settings")}
        />

        <div className="content">
          {guideError && <p role="alert">{guideError}</p>}
          {loading && <LoadingState />}
          {error && <ErrorState message={error} />}
          {data && !loading && !error && renderPage()}
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
