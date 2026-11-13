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

import DemoAnomalyPanel from "./components/DemoAnomalyPanel";

import { fetchDashboard, fetchAiGuide, fetchDemoAnomaly, sendDemoEmail, fetchHistory, hideNotification } from "./services/api";
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
  // 가상 이상 시연 상태. demoResult 가 있으면 화면의 aiGuide/anomalies 만 이 값으로 덮어 표시한다.
  // (원본 data 는 그대로 보존한다. "실제 데이터로 돌아가기"로 demoResult 만 비우면 복원된다.)
  const [demoResult, setDemoResult] = useState(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState(null);
  const [sending, setSending] = useState(false);
  const [delivery, setDelivery] = useState(null);
  const [persistenceWarning, setPersistenceWarning] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const applyHistory = useCallback((res) => {
    if (res.historyStatus === "unavailable") setData((prev) => prev ? { ...prev, historyStatus: "unavailable" } : prev);
    if (res.historyStatus === "ok") setData((prev) => prev ? { ...prev,
      guideHistory: res.guideHistory, notifications: res.notifications, nextCursor: res.nextCursor, historyStatus: "ok" } : prev);
  }, []);
  const loadMoreHistory = useCallback(async (cursor) => {
    setHistoryLoading(true);
    try {
      const res = await fetchHistory(cursor);
      setData((prev) => ({ ...prev, historyStatus: "ok", nextCursor: res.nextCursor,
        guideHistory: [...new Map([...(prev.guideHistory || []), ...res.guideHistory].map((h) => [h.id, h])).values()],
        notifications: [...new Map([...(prev.notifications || []), ...res.notifications].map((h) => [h.id, h])).values()] }));
    } catch (err) {
      if (err.authRequired) setAuthError(true);
      else setPersistenceWarning("과거 내역을 불러오지 못했습니다. 다시 시도해 주세요.");
    } finally { setHistoryLoading(false); }
  }, []);

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
      .then(async (guide) => {
        setData((prev) => (prev ? { ...prev, aiGuide: guide } : prev));
        if (guide.persistenceStatus === "unavailable") setPersistenceWarning("생성된 가이드를 영구 저장하지 못했습니다.");
        if (isAuthEnabled() && guide.status === "generated") {
          try { applyHistory(await fetchHistory()); }
          catch { setPersistenceWarning("저장된 가이드 목록을 새로 불러오지 못했습니다."); }
        }
      })
      .catch((err) => {
        if (err && err.authRequired) {
          setAuthError(true);
        } else {
          setGuideError("분석 및 가이드를 다시 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.");
        }
      })
      .finally(() => setRegenerating(false));
  }, [applyHistory]);

  const handleHideNotification = useCallback(async (id) => {
    try { await hideNotification(id); }
    catch (err) { if (err.authRequired) setAuthError(true); throw err; }
    setData((prev) => prev ? { ...prev, notifications: (prev.notifications || []).filter((item) => item.id !== id) } : prev);
  }, []);

  const handleProfileSaved = useCallback((updatedUser) => {
    setData((prev) => (prev ? { ...prev, user: updatedUser } : prev));
  }, []);

  // 가상 이상 시연 실행: 버튼 클릭 시에만 POST /demo/anomaly 를 "1회" 호출한다.
  // 자동 재시도는 하지 않는다. 실패 시 오류만 표시하고 예시 응답으로 대체하지 않는다.
  const handleRunDemo = useCallback((scenario) => {
    setDelivery(null);
    setPersistenceWarning(null);
    setDemoError(null);
    setDemoLoading(true);
    fetchDemoAnomaly(scenario)
      .then((res) => {
        applyHistory(res);
        if (res.persistenceStatus === "unavailable") setPersistenceWarning("분석 결과를 영구 저장하지 못했습니다. 이메일 발송은 비활성화됩니다.");
        // 기존 실제 데이터는 보존한다.
        setDemoResult({
          eventId: res.eventId, scenario: res.scenario,
          aiGuide: res.aiGuide,
          anomalies: Array.isArray(res.anomalies) ? res.anomalies : [],
        });
      })
      .catch((err) => {
        if (err && err.authRequired) {
          // 토큰 없음/만료/권한 없음: 로그인 안내로 전환(예시 대체 없음)
          setAuthError(true);
        } else {
          setDemoError(
            "가상 이상 시연을 실행하지 못했습니다. 예시로 대체하지 않습니다. 잠시 후 다시 시도해 주세요."
          );
        }
      })
      .finally(() => setDemoLoading(false));
  }, [applyHistory]);

  const handleSendDemo = useCallback(async () => {
    if (!demoResult?.eventId || sending || delivery) return;
    setSending(true);
    setDemoError(null);
    try {
      const res = await sendDemoEmail(demoResult.eventId);
      setDelivery(res.notification || { title: "발송 결과 확인 필요", status: "unknown" });
      applyHistory(res);
      if (res.persistenceStatus === "unavailable") setPersistenceWarning("발송 요청 후 기록 저장을 확인하지 못했습니다. 중복 발송을 피하려면 재발송하지 마세요.");
    } catch (err) {
      if (err.authRequired) setAuthError(true);
      else {
        setDelivery({ title: "발송 결과 확인 필요", status: "unknown" });
        setDemoError("발송 응답을 확인하지 못했습니다. 새로고침 후 알림 내역을 확인해 주세요. 자동 재발송하지 않습니다.");
      }
    } finally { setSending(false); }
  }, [demoResult, sending, delivery, applyHistory]);

  // 시연 결과만 해제한다(실제 데이터·기존 가이드 상태는 건드리지 않는다).
  const handleResetDemo = useCallback(() => {
    setDemoResult(null);
    setDemoError(null);
    setDelivery(null);
    setPersistenceWarning(null);
  }, []);

  const meta = PAGE_META[activeNav] || PAGE_META.dashboard;

  // 인증 모드에서 토큰 없음/만료/권한 없음: 실제 데이터 대신 로그인 안내 화면
  if (authError) {
    return <AuthGate />;
  }

  function renderPage() {
    if (!data) return null;
    // 시연 결과가 있으면 화면용으로 aiGuide/anomalies 만 덮는다. 원본 data 는 보존한다.
    const demoActive = Boolean(demoResult);
    const viewData = demoActive
      ? { ...data, aiGuide: demoResult.aiGuide, anomalies: demoResult.anomalies, demoScenario: demoResult.scenario }
      : data;
    // 가상 시연 중 표시용 기준일. 실제 data.analysis(2016-04-10)는 건드리지 않고,
    // 화면에는 데모 응답의 aiGuide.referenceDate 만 쓴다. (UI 에 날짜를 하드코딩하지 않는다)
    const demoReferenceDate = demoActive
      ? (demoResult.aiGuide && demoResult.aiGuide.referenceDate) || null
      : null;
    // 가상 시연 안내/날짜를 각 페이지가 일관되게 쓰도록 공통 prop 으로 전달한다.
    const common = { data: viewData, demoActive, demoReferenceDate, onLoadMore: loadMoreHistory, historyLoading, onHideNotification: handleHideNotification };
    // 시연 결과를 보는 동안에는 "분석 및 가이드 다시 확인"(실제 /ai-guide 재조회)을 숨긴다.
    // 시연(가상 가이드) 표시 중에 실제 데이터 요청이 섞여 data.aiGuide 를 덮어쓰는 것을 막기 위함이다.
    // 실제 데이터로 돌아간 뒤에는 다시 재확인 버튼이 나타난다.
    const regenerateHandler = demoActive ? undefined : handleRegenerate;
    switch (activeNav) {
      case "trends":
        return <TrendsPage {...common} />;
      case "anomaly":
        return <AnomalyPage {...common} />;
      case "guide":
        return (
          <GuidePage
            {...common}
            onRegenerate={regenerateHandler}
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
            onRegenerate={regenerateHandler}
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
          onLogout={isAuthEnabled() ? () => logout() : undefined}
        />

        <div className="content">
          {data?.historyStatus === "unavailable" && <p className="ui-note" role="status">저장된 내역을 불러오지 못했습니다. 빈 내역으로 확정된 상태는 아닙니다.</p>}
          {persistenceWarning && activeNav !== "dashboard" && <p className="ui-note" role="status">{persistenceWarning}</p>}
          {guideError && <p role="alert">{guideError}</p>}
          {/* 가상 이상 시연: 인증 모드에서 대시보드 탭일 때만 노출(토큰 첨부 경로가 유효한 경우) */}
          {isAuthEnabled() && activeNav === "dashboard" && data && !loading && !error && (
            <div style={{ marginBottom: 16 }}>
              <DemoAnomalyPanel
                onRun={handleRunDemo}
                onReset={handleResetDemo}
                loading={demoLoading}
                active={Boolean(demoResult)}
                error={demoError}
                onSend={handleSendDemo}
                canSend={Boolean(demoResult?.eventId)}
                sending={sending}
                delivery={delivery}
                persistenceWarning={persistenceWarning}
              />
            </div>
          )}
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
