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

// 시계열(일별, 최근 7일) - 수면시간(시간), 안정시심박(bpm), 활동량(걸음수)
// 기존 코드 호환용으로 유지 (= 주간 데이터)
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

// 기간별 시계열 (추이 분석 페이지: 일간 / 주간 / 월간)
// - daily: 오늘 하루를 3시간 간격으로
// - weekly: 최근 7일 (= timeseries와 동일)
// - monthly: 최근 4주 주차별 평균
const hours = ["00시", "03시", "06시", "09시", "12시", "15시", "18시", "21시"];
const weeks = ["1주차", "2주차", "3주차", "4주차"];

export const timeseriesByRange = {
  daily: {
    sleep: hours.map((h, i) => ({
      // 수면은 새벽 구간에만 값이 있다고 가정
      label: h,
      value: [1.2, 1.1, 0.8, 0, 0, 0, 0, 0.3][i],
    })),
    heartRate: hours.map((h, i) => ({
      label: h,
      value: [58, 56, 61, 72, 75, 70, 68, 63][i],
      anomaly: i === 3, // 오전 9시 급등
    })),
    steps: hours.map((h, i) => ({
      label: h,
      value: [0, 50, 420, 1800, 2600, 3100, 900, 300][i],
    })),
  },
  weekly: {
    sleep: timeseries.sleep,
    heartRate: timeseries.heartRate,
    steps: timeseries.steps,
  },
  monthly: {
    sleep: weeks.map((w, i) => ({
      label: w,
      value: [7.1, 6.9, 7.3, 6.5][i],
      anomaly: i === 3,
    })),
    heartRate: weeks.map((w, i) => ({
      label: w,
      value: [63, 64, 62, 68][i],
    })),
    steps: weeks.map((w, i) => ({
      label: w,
      value: [8900, 9200, 8100, 6700][i],
      anomaly: i === 3,
    })),
  },
};

// 상단 요약 통계 (대시보드 = 오늘 기준 스냅샷)
export const summaryStats = [
  {
    id: "sleep",
    icon: "🌙",
    label: "오늘 수면",
    value: "7.3",
    unit: "시간",
    delta: 6,
    deltaLabel: "어제 대비",
  },
  {
    id: "hr",
    icon: "❤️",
    label: "오늘 안정 시 심박",
    value: "63",
    unit: "bpm",
    delta: -2,
    deltaLabel: "어제 대비",
  },
  {
    id: "steps",
    icon: "👟",
    label: "오늘 걸음 수",
    value: "9,400",
    unit: "걸음",
    delta: 8,
    deltaLabel: "어제 대비",
  },
  {
    id: "score",
    icon: "🩺",
    label: "오늘 건강 점수",
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

// Bedrock 생성형 AI 맞춤 가이드 (다중 도메인 종합 판단)
// sources: 이 가이드가 어떤 도메인 데이터를 근거로 생성되었는지 표시 (멀티모달 어필)
export const aiGuide = {
  model: "Amazon Bedrock · Claude",
  updatedAt: "방금 전 생성됨",
  // 어떤 도메인을 종합했는지 근거 태그
  sources: [
    { id: "body", icon: "⌚", label: "활동량·수면" },
    { id: "mind", icon: "🧠", label: "심리상담 점수" },
    { id: "joint", icon: "🦵", label: "관절염 메타데이터" },
  ],
  headline:
    "수면 부족·스트레스 지수가 높고 우측 무릎 통증 이력이 있어, 오늘은 회복 중심 루틴을 권해요.",
  text:
    "활동 데이터상 수면이 부족하고 안정 시 심박이 올라가 있어요. 심리상담 점수에서는 스트레스·불안 지표가 평소보다 높게 나타났고, 근골격계 기록에는 우측 무릎 통증 이력이 있습니다. 세 영역을 종합하면 고강도 하체 운동은 무릎에 부담을 줄 수 있어, 오늘은 심신 안정과 가벼운 회복에 집중하는 편이 좋습니다.",
  actions: [
    "고강도 하체 운동 대신 무릎에 무리 없는 가벼운 스트레칭 10분",
    "스트레스 완화를 위한 10분 명상 또는 호흡 이완",
    "오늘 밤은 11시 전 취침으로 수면 부족 회복하기",
    "우측 무릎 통증이 심해지면 활동을 멈추고 휴식하기",
  ],
};

// 심리 상태 (심리상담 점수 도메인 - Mind)
export const mentalState = {
  summary: "스트레스·불안 지표가 평소보다 높아요",
  updatedAt: "오늘 오전 설문 기준",
  scores: [
    { id: "stress", label: "스트레스", value: 72, level: "high" }, // 0~100
    { id: "anxiety", label: "불안", value: 64, level: "high" },
    { id: "depression", label: "우울", value: 38, level: "normal" },
    { id: "mood", label: "기분", value: 55, level: "warn" },
  ],
};

// 근골격계 상태 (관절염 메타데이터 도메인 - Body)
export const musculoskeletal = {
  summary: "우측 무릎에 경도 통증 이력이 있어요",
  condition: "경도 관절염 (무릎)",
  painPoints: [
    { id: "knee_r", label: "우측 무릎", level: "warn", note: "뻐근함 · 계단 시 불편" },
    { id: "lower_back", label: "허리", level: "ok", note: "특이사항 없음" },
    { id: "shoulder_l", label: "좌측 어깨", level: "ok", note: "특이사항 없음" },
  ],
};

// 통합 리포트 3영역 요약 (Mind + Body + Life)
export const healthDomains = [
  {
    id: "life",
    icon: "⌚",
    title: "일상 생체 신호",
    subtitle: "활동량 · 수면",
    status: "warn",
    statusLabel: "주의",
    metrics: [
      { label: "걸음 수", value: "3,200보" },
      { label: "수면", value: "5.4시간" },
      { label: "칼로리", value: "1,680kcal" },
    ],
  },
  {
    id: "body",
    icon: "🦵",
    title: "근골격계 상태",
    subtitle: "관절염 메타데이터",
    status: "warn",
    statusLabel: "통증 이력",
    metrics: [
      { label: "주요 부위", value: "우측 무릎" },
      { label: "상태", value: "경도 관절염" },
      { label: "최근 통증", value: "계단 이용 시" },
    ],
  },
  {
    id: "mind",
    icon: "🧠",
    title: "심리·스트레스",
    subtitle: "심리상담 점수",
    status: "danger",
    statusLabel: "높음",
    metrics: [
      { label: "스트레스", value: "72 / 100" },
      { label: "불안", value: "64 / 100" },
      { label: "우울", value: "38 / 100" },
    ],
  },
];

// 데이터 소스 / 아키텍처 어필 메타 (Athena 데이터레이크)
export const dataSources = {
  note: "본 리포트는 Amazon S3 데이터 레이크에 적재된 다중 도메인 원본 데이터를 AWS Athena로 실시간 쿼리하여 생성되었습니다.",
  lastQueried: "방금 전 · AWS Athena",
  items: ["활동·수면", "심리상담 점수", "관절염 메타데이터"],
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

// 연결된 웨어러블 기기 (기기 연동 페이지)
export const devices = [
  {
    id: "d1",
    name: "Galaxy Watch 6",
    type: "스마트워치",
    icon: "⌚",
    status: "connected", // connected | syncing | disconnected
    battery: 82,
    lastSync: "2분 전",
    metrics: ["심박", "수면", "활동량", "SpO2"],
  },
  {
    id: "d2",
    name: "Galaxy Ring",
    type: "스마트링",
    icon: "💍",
    status: "connected",
    battery: 45,
    lastSync: "10분 전",
    metrics: ["수면", "심박", "체온"],
  },
  {
    id: "d3",
    name: "Withings Scale",
    type: "체성분계",
    icon: "⚖️",
    status: "disconnected",
    battery: null,
    lastSync: "3일 전",
    metrics: ["체중", "체지방"],
  },
];

// AI 가이드 생성 히스토리 (AI 가이드 페이지)
export const guideHistory = [
  {
    id: "g1",
    date: "오늘 · 오전 9:12",
    headline: "수면·심박 이상 징후, 가벼운 회복 루틴으로 돌봐보세요.",
    tag: "회복 권장",
  },
  {
    id: "g2",
    date: "어제 · 오전 8:40",
    headline: "활동량이 꾸준해요. 수분 섭취만 조금 더 신경 써보세요.",
    tag: "유지",
  },
  {
    id: "g3",
    date: "2일 전 · 오전 8:55",
    headline: "주말 수면 패턴이 흐트러졌어요. 기상 시간을 일정하게 맞춰보세요.",
    tag: "수면 관리",
  },
];

// 인터랙티브 피드백 - 사용자 컨디션 입력에 대한 룰 기반 즉답 (목)
// 실제로는 Bedrock에 프롬프트로 전달해 생성합니다.
export const feedbackRules = [
  {
    keywords: ["무릎", "관절", "다리"],
    reply:
      "우측 무릎 통증 이력이 있어 오늘은 하체에 부담을 주는 운동은 피하는 게 좋아요. 앉아서 하는 가벼운 스트레칭과 냉찜질을 권하고, 통증이 지속되면 무리하지 마세요.",
  },
  {
    keywords: ["스트레스", "불안", "우울", "힘들", "예민"],
    reply:
      "심리상담 점수에서 스트레스·불안 지표가 높게 나와 있어요. 10분 호흡 명상이나 가벼운 산책으로 긴장을 풀어보고, 카페인 섭취를 줄여보는 걸 추천해요.",
  },
  {
    keywords: ["피곤", "졸", "잠", "수면"],
    reply:
      "최근 수면이 부족했어요. 오늘은 평소보다 일찍 잠자리에 들고, 자기 전 화면 사용을 줄이면 회복에 도움이 돼요.",
  },
  {
    keywords: ["운동", "뛰", "헬스"],
    reply:
      "오늘은 컨디션 지표가 회복이 필요한 상태예요. 고강도 운동보다는 20분 내외의 가벼운 유산소나 스트레칭을 권해요.",
  },
];

// 매칭되는 규칙이 없을 때의 기본 응답
export const feedbackFallback =
  "입력을 종합 건강 데이터와 함께 분석했어요. 현재는 수면 부족·스트레스 지표가 높아 전반적으로 회복에 집중하는 하루를 권합니다. 증상이 지속되면 전문가 상담을 권장해요.";
