// WearCare Mate - 목(mock) 데이터
// 추후 실제 백엔드(API Gateway + Lambda, Timestream, SageMaker, Bedrock) 연동 시
// src/services/api.js 에서 이 데이터를 fetch 결과로 교체하면 됩니다.

export const user = {
  name: "김웨어",
  meta: "33세 · 일반 사용자",
  initial: "웨",
};

// 최근 7일 라벨
const days = ["월", "화", "수", "목", "금", "토", "일"];

// 시계열(일별) - 수면시간(시간), 안정시심박(bpm), 활동량(걸음수)
export const timeseries = {
  sleep: days.map((d, i) => ({
    label: d,
    value: [7.2, 6.8, 7.5, 5.4, 6.1, 8.0, 7.3][i],
  })),
  heartRate: days.map((d, i) => ({
    label: d,
    value: [62, 64, 61, 78, 70, 59, 63][i],
    // 목요일 안정 심박 급등 → 이상치
    anomaly: i === 3,
  })),
  steps: days.map((d, i) => ({
    label: d,
    value: [8200, 9100, 7600, 3200, 6800, 11200, 9400][i],
    // 목요일 활동량 급감 → 이상치
    anomaly: i === 3,
  })),
};

// 상단 요약 통계
export const summaryStats = [
  {
    id: "sleep",
    icon: "🌙",
    label: "평균 수면",
    value: "6.9",
    unit: "시간",
    delta: -4,
    deltaLabel: "지난주 대비",
  },
  {
    id: "hr",
    icon: "❤️",
    label: "안정 시 심박",
    value: "65",
    unit: "bpm",
    delta: 3,
    deltaLabel: "지난주 대비",
  },
  {
    id: "steps",
    icon: "👟",
    label: "평균 걸음 수",
    value: "7,929",
    unit: "보",
    delta: -2,
    deltaLabel: "지난주 대비",
  },
  {
    id: "score",
    icon: "🩺",
    label: "건강 점수",
    value: "82",
    unit: "/100",
    delta: 0,
    deltaLabel: "변동 없음",
  },
];

// 수면 단계 (오늘 밤)
export const sleepStages = {
  totalLabel: "7시간 18분",
  segments: [
    { id: "deep", label: "깊은 수면", pct: 22, color: "#141414" },
    { id: "light", label: "얕은 수면", pct: 48, color: "#71717a" },
    { id: "rem", label: "REM", pct: 22, color: "#a1a1aa" },
    { id: "awake", label: "깨어남", pct: 8, color: "#d6d6db" },
  ],
};

// SageMaker 이상 패턴 탐지 결과
export const anomalies = [
  {
    id: "a1",
    severity: "danger",
    title: "안정 시 심박 급등 감지",
    time: "목요일 · 오전 3:20",
    desc: "평소 패턴(58~64bpm) 대비 78bpm으로 상승. 수면 중 이상 징후로 분류되었습니다.",
  },
  {
    id: "a2",
    severity: "warn",
    title: "활동량 급감",
    time: "목요일 · 하루 종일",
    desc: "주간 평균 대비 걸음 수 60% 감소. 컨디션 저하 가능성이 있습니다.",
  },
  {
    id: "a3",
    severity: "warn",
    title: "수면 시간 부족",
    time: "목요일 · 밤",
    desc: "수면 5.4시간으로 권장(7시간) 미달. 연속 패턴 여부를 관찰 중입니다.",
  },
  {
    id: "a4",
    severity: "ok",
    title: "주말 회복 패턴 정상",
    time: "토요일 · 밤",
    desc: "수면·심박·활동량 모두 평소 정상 범위로 복귀했습니다.",
  },
];

// Bedrock 생성형 AI 맞춤 가이드
export const aiGuide = {
  model: "Amazon Bedrock · Claude",
  updatedAt: "방금 전 생성됨",
  headline: "목요일에 나타난 수면·심박 이상 징후, 가벼운 회복 루틴으로 돌봐보세요.",
  text:
    "최근 안정 시 심박이 평소보다 올라가고 수면이 부족했어요. 급성 질환보다는 피로 누적 신호일 가능성이 높아요. 오늘은 무리한 운동 대신 회복에 집중하는 하루를 권해요.",
  actions: [
    "오늘 밤은 평소보다 30분 일찍, 11시 전에 잠자리에 들어보기",
    "자기 전 1시간은 카페인·화면 사용을 줄이고 스트레칭하기",
    "낮에 가벼운 20분 산책으로 활동량 회복하기",
    "내일도 안정 시 심박이 70bpm 이상이면 휴식을 더 길게 가지기",
  ],
};

// SNS 푸시 알림
export const notifications = [
  {
    id: "n1",
    icon: "🔔",
    title: "새로운 AI 건강 가이드가 도착했어요.",
    time: "방금 전",
  },
  {
    id: "n2",
    icon: "⚠️",
    title: "심박 이상 패턴이 감지되었습니다.",
    time: "오늘 오전 3:25",
  },
  {
    id: "n3",
    icon: "📉",
    title: "활동량이 평소보다 크게 줄었어요.",
    time: "어제 오후 9:00",
  },
  {
    id: "n4",
    icon: "✅",
    title: "주간 건강 리포트가 준비됐어요.",
    time: "2일 전",
  },
];
