// WearCare Mate - API 서비스 레이어
//
// 현재는 목 데이터를 반환합니다. 실제 백엔드가 준비되면
// REACT_APP_API_BASE 환경변수를 설정하고 아래 fetch 분기를 사용하도록
// 전환하면 됩니다. (API Gateway + Lambda REST API)
//
// 각 함수는 Promise를 반환하므로 호출부 코드는 바꿀 필요가 없습니다.

import {
  user,
  summaryStats,
  timeseries,
  timeseriesByRange,
  sleepStages,
  anomalies,
  aiGuide,
  notifications,
  devices,
  guideHistory,
  mentalState,
  musculoskeletal,
  healthDomains,
  dataSources,
  feedbackRules,
  feedbackFallback,
} from "../data/mockData";
import { loadProfile, saveProfile } from "./profileStorage";

const API_BASE = (process.env.REACT_APP_API_BASE || "").trim().replace(/\/+$/, "");

// 기본 사용자 정보에 브라우저에 저장된 프로필을 덮어씀
function resolveUser(baseUser) {
  const saved = loadProfile();
  return saved ? { ...baseUser, ...saved } : baseUser;
}

// 네트워크 지연을 흉내 내 로딩 상태를 확인할 수 있게 함
function delay(data, ms = 350) {
  return new Promise((resolve) => setTimeout(() => resolve(data), ms));
}

async function request(path, fallback) {
  // 실제 백엔드가 연결되지 않은 경우 목 데이터 반환
  if (!API_BASE) {
    return delay(fallback);
  }
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API 요청 실패: ${res.status}`);
  }
  return res.json();
}

export async function fetchDashboard() {
  // 실제로는 /dashboard 같은 단일 엔드포인트로 합칠 수 있음
  const res = await request("/dashboard", {
    user,
    summaryStats,
    timeseries,
    timeseriesByRange,
    sleepStages,
    anomalies,
    aiGuide,
    notifications,
    devices,
    guideHistory,
    mentalState,
    musculoskeletal,
    healthDomains,
    dataSources,
  });
  // 프로필은 DB가 아닌 브라우저 localStorage 값을 우선 반영
  return { ...res, user: resolveUser(res.user) };
}

// 인터랙티브 컨디션 피드백
// 사용자가 입력한 현재 컨디션 문장에 대해 AI 피드백을 반환합니다.
// 실제 연동 시 Bedrock 프롬프트로 전달하고 생성 결과를 받습니다.
export function sendConditionFeedback(message) {
  if (API_BASE) {
    return fetch(`${API_BASE}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    }).then((res) => {
      if (!res.ok) throw new Error(`피드백 요청 실패: ${res.status}`);
      return res.json();
    });
  }
  // 목: 키워드 룰 기반 즉답
  const text = (message || "").toLowerCase();
  const matched = feedbackRules.find((rule) =>
    rule.keywords.some((k) => (message || "").includes(k) || text.includes(k))
  );
  return delay({ reply: matched ? matched.reply : feedbackFallback }, 600);
}

export function fetchAiGuide() {
  // Bedrock 재생성 트리거용 (현재는 목)
  return request("/ai-guide", aiGuide);
}

// 프로필 정보 업데이트
// 데이터베이스를 거치지 않고 브라우저 localStorage에 저장합니다.
export function updateProfile(profile) {
  saveProfile(profile);
  return delay(profile, 300);
}
