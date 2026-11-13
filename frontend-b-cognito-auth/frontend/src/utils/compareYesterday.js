// 오늘·어제 기록 값을 단순 비교하는 순수 함수(생성형 AI 문장이 아님).
// timeseries 각 지표의 마지막 두 값(어제 → 오늘)을 비교합니다.

const METRICS = [
  { id: "steps", key: "steps", label: "걸음 수", unit: "걸음", higherIsBetter: true, digits: 0 },
  { id: "sleep", key: "sleep", label: "수면 시간", unit: "시간", higherIsBetter: true, digits: 1 },
  { id: "heartRate", key: "heartRate", label: "안정시 심박", unit: "bpm", higherIsBetter: false, digits: 0 },
];

const isNum = (v) => typeof v === "number" && Number.isFinite(v);

// 지표별 '비슷해요' 판단 임계값(절대 변화량 기준)
function isSame(metric, today, yesterday, delta) {
  if (metric.id === "steps") return Math.abs(delta) < Math.abs(yesterday) * 0.01 || delta === 0;
  if (metric.id === "sleep") return Math.abs(delta) < 0.1;
  return Math.abs(delta) < 1;
}

function fmtNumber(value, digits) {
  return Math.abs(value).toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function buildText(metric, delta) {
  const sign = delta > 0 ? "+" : delta < 0 ? "−" : "";
  let text = `${sign}${fmtNumber(delta, metric.digits)}${metric.unit}`;
  if (metric.id === "sleep") {
    const minutes = Math.round(Math.abs(delta) * 60);
    text += `(${sign}${minutes}분)`;
  }
  return text;
}

export function compareYesterday(timeseries) {
  const items = [];
  METRICS.forEach((metric) => {
    const series = timeseries && Array.isArray(timeseries[metric.key]) ? timeseries[metric.key] : [];
    if (series.length < 2) return;
    const yesterday = series[series.length - 2]?.value;
    const today = series[series.length - 1]?.value;
    if (!isNum(yesterday) || !isNum(today)) return;

    const delta = today - yesterday;
    const same = isSame(metric, today, yesterday, delta);
    const verdict = same ? "same" : (delta > 0) === metric.higherIsBetter ? "better" : "worse";
    items.push({
      id: metric.id,
      label: metric.label,
      unit: metric.unit,
      today,
      yesterday,
      delta,
      deltaPct: yesterday !== 0 ? Math.round((delta / yesterday) * 100) : null,
      direction: same ? "same" : delta > 0 ? "up" : "down",
      verdict,
      text: same ? "비슷해요" : buildText(metric, delta),
    });
  });

  return {
    hasData: items.length > 0,
    items,
    improved: items.filter((i) => i.verdict === "better"),
    worsened: items.filter((i) => i.verdict === "worse"),
    same: items.filter((i) => i.verdict === "same"),
  };
}
