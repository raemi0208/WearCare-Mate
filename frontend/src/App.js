import React, { useEffect, useState, useCallback } from "react";
import "./App.css";

import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";

import DashboardPage from "./pages/DashboardPage";
import TrendsPage from "./pages/TrendsPage";
import AnomalyPage from "./pages/AnomalyPage";
import GuidePage from "./pages/GuidePage";
import DevicesPage from "./pages/DevicesPage";
import SettingsPage from "./pages/SettingsPage";

import { fetchDashboard, fetchAiGuide } from "./services/api";
import { isAuthEnabled } from "./services/authConfig";
import { login, logout } from "./services/cognitoAuth";

// 각 페이지의 상단 제목/부제목
const PAGE_META = {
  dashboard: {
    title: "건강 대시보드",
    subtitle: "웨어러블 기록 데이터 분석",
  },
  trends: {
    title: "추이 분석",
    subtitle: "수면 · 심박 · 활동량 시계열 상세 추이",
  },
  anomaly: {
    title: "이상 탐지",
    subtitle: "기록 데이터 기반 이상 패턴 분석",
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
  const [authError, setAuthError] = useState(false);

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
          if (err && err.authRequired) {
            // 토큰 없음/만료/권한 없음: 실제 데이터 요청을 막고 로그인 안내로 전환
            setAuthError(true);
          } else {
            setError(err.message || "데이터를 불러오지 못했습니다.");
          }
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
      .catch((err) => {
        if (err && err.authRequired) {
          setAuthError(true);
        } else {
          setGuideError("분석 및 가이드를 다시 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.");
        }
      })
      .finally(() => setRegenerating(false));
  }, []);

  const handleProfileSaved = useCallback((updatedUser) => {
    setData((prev) => (prev ? { ...prev, user: updatedUser } : prev));
  }, []);

  const meta = PAGE_META[activeNav] || PAGE_META.dashboard;

  // 인증 모드에서 토큰 없음/만료/권한 없음: 실제 데이터 대신 로그인 안내 화면
  if (authError) {
    return <AuthGate />;
  }

  function renderPage() {
    if (!data) return null;
    const common = { data };
    switch (activeNav) {
      case "trends":
        return <TrendsPage {...common} />;
      case "anomaly":
        return <AnomalyPage {...common} />;
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
          {isAuthEnabled() && (
            <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
              <button className="btn" onClick={() => logout()}>
                로그아웃
              </button>
            </div>
          )}
          {guideError && <p role="alert">{guideError}</p>}
          {loading && <LoadingState />}
          {error && <ErrorState message={error} />}
          {data && !loading && !error && renderPage()}
        </div>
      </div>
    </div>
  );
}

// 인증 필요 안내 화면 (실제 데이터 요청을 막고 로그인으로 유도)
function AuthGate() {
  return (
    <div
      className="app"
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
      }}
    >
      <div className="card" style={{ padding: "40px", textAlign: "center", maxWidth: 420 }}>
        <p style={{ fontSize: 18, fontWeight: 800, margin: "0 0 8px" }}>로그인이 필요합니다</p>
        <p style={{ color: "var(--color-muted)", margin: "0 0 20px" }}>
          실제 건강 데이터는 승인된 시연 계정으로 로그인한 경우에만 표시됩니다.
        </p>
        <button className="btn btn--primary" onClick={() => login()}>
          로그인하기
        </button>
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
