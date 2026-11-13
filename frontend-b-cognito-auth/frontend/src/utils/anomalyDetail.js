// 이상 탐지 항목 상세 정규화 (순수 함수)
// 백엔드가 주는 필드는 {id, severity, title, time, desc} 뿐이므로
// 수치는 desc 문장 파싱으로만 얻고, 못 구하면 null 로 둔다(수치를 지어내지 않는다).

const SEVERITY_INFO = {
  danger: { label: "위험", meaning: "평소와 크게 달라 먼저 확인해 보면 좋아요." },
  warn: { label: "주의", meaning: "평소와 차이가 있어 지켜볼 필요가 있어요." },
  ok: { label: "정상", meaning: "평소 범위 안에 있어요." },
};

const METRICS = {
  steps: {
    label: "걸음 수",
    unit: "걸음",
    hint: "일시적인 활동 감소, 컨디션 저하, 기기 미착용 등이 영향을 줄 수 있어요.",
    action: "가벼운 산책으로 활동량을 조금씩 회복해 보세요.",
  },
  sleep: {
    label: "수면 시간",
    unit: "시간",
    hint: "늦은 취침, 수면 환경 변화, 일시적인 피로 등이 영향을 줄 수 있어요.",
    action: "취침·기상 시각을 일정하게 지키고 충분히 쉬어 보세요.",
  },
  heartRate: {
    label: "심박수",
    unit: "bpm",
    hint: "스트레스, 카페인, 수면 부족, 운동 직후 측정 등이 영향을 줄 수 있어요.",
    action: "충분히 쉬고 수분을 섭취한 뒤 다시 확인해 보세요.",
  },
  hrv: {
    label: "심박 변이도(HRV)",
    unit: "ms",
    hint: "피로 누적이나 스트레스 상태가 영향을 줄 수 있어요.",
    action: "휴식과 수면을 우선하고 컨디션 변화를 관찰해 보세요.",
  },
  stress: {
    label: "스트레스 지수",
    unit: "",
    hint: "업무량, 수면 부족, 생활 리듬 변화 등이 영향을 줄 수 있어요.",
    action: "짧은 호흡 운동이나 가벼운 스트레칭을 해 보세요.",
  },
};

const DEFAULT_METRIC = {
  label: "건강 지표",
  unit: "",
  hint: "일시적인 컨디션 변화나 측정 환경이 영향을 줄 수 있어요.",
  action: "생활 패턴을 살피며 며칠 더 관찰해 보세요.",
};

const toNum = (s) => {
  if (s == null) return null;
  const n = Number(String(s).replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
};

// 제목/설명 키워드로 지표 추정
function detectMetric(text) {
  if (/걸음|활동/.test(text)) return "steps";
  if (/수면/.test(text)) return "sleep";
  if (/HRV|변이도/i.test(text)) return "hrv";
  if (/스트레스/.test(text)) return "stress";
  if (/심박|bpm/i.test(text)) return "heartRate";
  return null;
}

const fmt = (value, unit) => {
  if (value == null || !Number.isFinite(value)) return null;
  const text = Number.isInteger(value) ? value.toLocaleString("ko-KR") : String(Math.round(value * 10) / 10);
  if (!unit) return text;
  return unit === "bpm" || unit === "ms" ? `${text} ${unit}` : `${text}${unit}`;
};

export function describeAnomaly(anomaly, { timeseries } = {}) {
  const a = anomaly || {};
  const title = String(a.title || "");
  const desc = String(a.desc || "");
  const text = `${title} ${desc}`;
  const severity = SEVERITY_INFO[a.severity] ? a.severity : "ok";
  const sevInfo = SEVERITY_INFO[severity];

  let metricKey = detectMetric(text);
  let measured = null;
  let baseline = null;
  let diffPct = null;
  let basis = null;

  // 1) 실제 백엔드 형식: 기준일 걸음 수 X걸음 · 과거 기록 평균 Y걸음 (개인 기준선)
  const real = desc.match(/걸음\s*수\s*([\d,]+(?:\.\d+)?)\s*걸음\s*[·,]\s*과거\s*기록\s*평균\s*([\d,]+(?:\.\d+)?)\s*걸음/);
  if (real) {
    metricKey = "steps";
    measured = toNum(real[1]);
    baseline = toNum(real[2]);
    basis = "personal";
  } else {
    // 2) 목 문장: "평소 패턴(58~64bpm) 대비 78bpm"
    const range = desc.match(/평소[^()]*\((\d+(?:\.\d+)?)\s*[~-]\s*(\d+(?:\.\d+)?)\s*(bpm|시간|걸음)?\)\s*대비\s*(\d+(?:\.\d+)?)\s*(bpm|시간|걸음)?/i);
    // 3) "수면 5.4시간으로 권장(7시간) 미달"
    const rec = desc.match(/(\d+(?:\.\d+)?)\s*시간[^()]*권장\s*\((\d+(?:\.\d+)?)\s*시간\)/);
    // 4) "평균 대비 걸음 수 60% 감소"
    const pct = desc.match(/평균\s*대비[^\d]*(\d+(?:\.\d+)?)\s*%\s*(감소|증가|하락|상승)/);
    if (range) {
      const lo = toNum(range[1]);
      const hi = toNum(range[2]);
      measured = toNum(range[4]);
      baseline = lo != null && hi != null ? (lo + hi) / 2 : null;
      basis = "personal";
    } else if (rec) {
      measured = toNum(rec[1]);
      baseline = toNum(rec[2]);
      metricKey = "sleep";
      basis = "population";
    } else if (pct) {
      const p = toNum(pct[1]);
      if (p != null) diffPct = /감소|하락/.test(pct[2]) ? -Math.round(p) : Math.round(p);
      basis = "personal";
      // 걸음 시계열이 있으면 평균으로 보강
      if (metricKey === "steps" && timeseries && Array.isArray(timeseries.steps)) {
        const vals = timeseries.steps.map((x) => Number(x && x.value)).filter(Number.isFinite);
        if (vals.length >= 2) {
          baseline = Math.round(vals.slice(0, -1).reduce((s, v) => s + v, 0) / (vals.length - 1));
          measured = vals[vals.length - 1];
        }
      }
    } else if (/집단|전체\s*사용자|평균/.test(text)) {
      basis = "population";
    }
  }

  if (diffPct == null && measured != null && baseline != null && baseline !== 0) {
    diffPct = Math.round(((measured - baseline) / baseline) * 100);
  }
  if (!Number.isFinite(diffPct)) diffPct = null;

  const metric = METRICS[metricKey] || DEFAULT_METRIC;
  const basisLabel =
    basis === "personal" ? "내 평소 기록과 비교"
      : basis === "population" ? "전체 사용자 평균·권장 기준과 비교"
        : "비교 기준 정보 없음";

  const missing = [];
  if (measured == null) missing.push("measured");
  if (baseline == null) missing.push("baseline");
  if (diffPct == null) missing.push("diffPct");

  return {
    id: a.id,
    title,
    metricKey,
    metricLabel: metric.label,
    measured: fmt(measured, metric.unit),
    baseline: fmt(baseline, metric.unit),
    diffPct,
    basis,
    basisLabel,
    severity,
    severityLabel: sevInfo.label,
    severityMeaning: sevInfo.meaning,
    detectedAt: a.time ? String(a.time) : null,
    hint: metric.hint,
    action: metric.action,
    missing,
  };
}

export function formatDiffPct(diffPct) {
  if (diffPct == null || !Number.isFinite(diffPct)) return null;
  if (diffPct === 0) return "0%";
  return `${diffPct > 0 ? "+" : "−"}${Math.abs(diffPct)}%`;
}
