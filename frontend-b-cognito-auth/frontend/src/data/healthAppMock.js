// WearCare Mate - 건강 앱별 mock 데이터 (시연용)
//
// 1) 앱별 블루투스 연결 기기 목록
// 2) 삼성 헬스 / 애플 건강 두 앱의 서로 다른 측정 데이터셋
// 실제 앱에서 가져온 값이 아니라 화면 시연을 위한 예시 값입니다.

// 블루투스 연결 상태: connected(연결됨) | disconnected(연결 끊김)
export const BLUETOOTH_DEVICES = {
  apple: [
    { id: "apple-watch", name: "Apple Watch Series 9", type: "스마트워치", icon: "⌚", status: "connected", metrics: ["심박", "수면", "걸음수"] },
    { id: "airpods-pro", name: "AirPods Pro", type: "오디오", icon: "🎧", status: "connected", metrics: ["청력 소음"] },
  ],
  samsung: [
    { id: "galaxy-watch", name: "Galaxy Watch 6", type: "스마트워치", icon: "⌚", status: "connected", metrics: ["심박", "수면", "걸음수"] },
    { id: "galaxy-ring", name: "Galaxy Ring", type: "스마트링", icon: "💍", status: "connected", metrics: ["수면", "심박"] },
    { id: "galaxy-buds", name: "Galaxy Buds", type: "오디오", icon: "🎧", status: "disconnected", metrics: ["청력 소음"] },
  ],
  healthconnect: [
    { id: "hc-band", name: "스마트 밴드", type: "스마트밴드", icon: "⌚", status: "connected", metrics: ["걸음수", "심박"] },
  ],
  fitbit: [
    { id: "fitbit-charge6", name: "Fitbit Charge 6", type: "스마트밴드", icon: "⌚", status: "connected", metrics: ["걸음수", "심박", "수면"] },
  ],
  garmin: [
    { id: "garmin-watch", name: "Garmin Forerunner", type: "스마트워치", icon: "⌚", status: "connected", metrics: ["걸음수", "심박", "활동 시간"] },
  ],
  xiaomi: [
    { id: "mi-band", name: "Mi Smart Band", type: "스마트밴드", icon: "⌚", status: "disconnected", metrics: ["걸음수", "수면"] },
  ],
  huawei: [
    { id: "huawei-watch", name: "Huawei Watch", type: "스마트워치", icon: "⌚", status: "connected", metrics: ["심박", "수면"] },
  ],
  oura: [
    { id: "oura-ring", name: "Oura Ring", type: "스마트링", icon: "💍", status: "connected", metrics: ["수면", "심박"] },
  ],
};

const DAYS = ["월", "화", "수", "목", "금", "토", "일"];

function series(values, anomalyIndex) {
  return DAYS.map((label, i) => ({ label, value: values[i], anomaly: anomalyIndex === i }));
}

// 메인 앱별 측정 데이터셋 (두 앱의 값이 서로 확실히 다르다)
// 애플 건강: 오늘 모든 지표가 어제보다 좋아진 예시 / 삼성 헬스: 오늘 모든 지표가 어제보다 나빠진 예시
export const MAIN_APP_DATASETS = {
  apple: {
    label: "애플 건강",
    timeseries: {
      steps: series([7400, 8100, 9300, 6900, 10400, 9800, 11600], null),
      sleep: series([7.6, 7.1, 7.4, 6.9, 7.8, 7.2, 7.9], null),
      heartRate: series([58, 59, 57, 60, 58, 59, 57], null),
    },
    healthScore: 88,
    sleepStages: {
      totalLabel: "7시간 54분",
      segments: [
        { id: "deep", label: "깊은 수면", pct: 24, color: "#141414" },
        { id: "light", label: "얕은 수면", pct: 46, color: "#71717a" },
        { id: "rem", label: "REM", pct: 24, color: "#a1a1aa" },
        { id: "awake", label: "깨어남", pct: 6, color: "#d6d6db" },
      ],
    },
  },
  samsung: {
    label: "삼성 헬스",
    timeseries: {
      steps: series([6100, 5400, 7200, 4800, 6600, 8900, 7350], 3),
      sleep: series([6.4, 6.9, 6.2, 5.8, 6.6, 7.4, 6.1], 3),
      heartRate: series([66, 68, 65, 70, 67, 63, 69], 3),
    },
    healthScore: 74,
    sleepStages: {
      totalLabel: "6시간 6분",
      segments: [
        { id: "deep", label: "깊은 수면", pct: 18, color: "#141414" },
        { id: "light", label: "얕은 수면", pct: 52, color: "#71717a" },
        { id: "rem", label: "REM", pct: 19, color: "#a1a1aa" },
        { id: "awake", label: "깨어남", pct: 11, color: "#d6d6db" },
      ],
    },
  },
};

const avg = (list) => list.reduce((sum, p) => sum + p.value, 0) / list.length;

// 시계열 평균으로 대시보드 요약 카드(summaryStats)를 만든다.
function buildSummaryStats(dataset) {
  const { timeseries } = dataset;
  return [
    { id: "sleep", icon: "🌙", label: "평균 수면", value: avg(timeseries.sleep).toFixed(1), unit: "시간", delta: 0, deltaLabel: "메인 앱 예시 기준" },
    { id: "hr", icon: "❤️", label: "안정 시 심박", value: String(Math.round(avg(timeseries.heartRate))), unit: "bpm", delta: 0, deltaLabel: "메인 앱 예시 기준" },
    { id: "steps", icon: "👟", label: "평균 걸음 수", value: Math.round(avg(timeseries.steps)).toLocaleString("ko-KR"), unit: "걸음", delta: 0, deltaLabel: "메인 앱 예시 기준" },
    { id: "score", icon: "🩺", label: "건강 점수", value: String(dataset.healthScore), unit: "/100", delta: 0, deltaLabel: "메인 앱 예시 기준" },
  ];
}

// 메인 앱이 삼성/애플이면 화면용 data 를 예시 데이터로 덮어 반환한다(원본 data 는 바꾸지 않는다).
// 그 외(기타 앱/미연동)는 원본 data 를 그대로 반환한다. 백엔드 응답 스키마는 건드리지 않고
// 화면에서 쓰는 timeseries / summaryStats / sleepStages 만 바꾼다.
export function applyMainAppData(data, mainProvider) {
  const dataset = MAIN_APP_DATASETS[mainProvider];
  if (!data || !dataset) return data;
  return {
    ...data,
    timeseries: dataset.timeseries,
    summaryStats: buildSummaryStats(dataset),
    sleepStages: dataset.sleepStages,
    mainAppSample: { provider: mainProvider, label: dataset.label },
  };
}
