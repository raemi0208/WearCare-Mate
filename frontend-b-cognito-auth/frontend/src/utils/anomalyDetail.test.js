import { describeAnomaly, formatDiffPct } from "./anomalyDetail";

describe("describeAnomaly", () => {
  it("실제 백엔드 desc 형식을 파싱한다", () => {
    const d = describeAnomaly({
      id: "x", severity: "warn", title: "활동량 급감", time: "일요일",
      desc: "기준일 걸음 수 4,000걸음 · 과거 기록 평균 10,000걸음",
    });
    expect(d.metricLabel).toBe("걸음 수");
    expect(d.measured).toBe("4,000걸음");
    expect(d.baseline).toBe("10,000걸음");
    expect(d.diffPct).toBe(-60);
    expect(d.basis).toBe("personal");
    expect(formatDiffPct(d.diffPct)).toBe("−60%");
  });

  it("목 문장(심박 범위, 수면 권장)을 파싱한다", () => {
    const hr = describeAnomaly({ severity: "danger", title: "안정 시 심박 급등", desc: "평소 패턴(58~64bpm) 대비 78bpm으로 상승." });
    expect(hr.measured).toBe("78 bpm");
    expect(hr.baseline).toBe("61 bpm");
    const sl = describeAnomaly({ severity: "warn", title: "수면 시간 부족", desc: "수면 5.4시간으로 권장(7시간) 미달." });
    expect(sl.measured).toBe("5.4시간");
    expect(sl.diffPct).toBe(-23);
    expect(sl.basis).toBe("population");
  });

  it("퍼센트만 있으면 차이%만 채운다", () => {
    const d = describeAnomaly({ severity: "warn", title: "활동량 급감", desc: "주간 평균 대비 걸음 수 60% 감소." });
    expect(d.diffPct).toBe(-60);
    expect(d.measured).toBeNull();
  });

  it("필드가 없어도 안전하다", () => {
    const d = describeAnomaly({});
    expect(d.measured).toBeNull();
    expect(d.diffPct).toBeNull();
    expect(d.basisLabel).toBe("비교 기준 정보 없음");
    expect(JSON.stringify(d)).not.toMatch(/NaN|undefined|Infinity/);
    expect(formatDiffPct(null)).toBeNull();
  });

  it("평소값이 0이면 차이%는 null", () => {
    const d = describeAnomaly({ severity: "warn", title: "걸음", desc: "기준일 걸음 수 100걸음 · 과거 기록 평균 0걸음" });
    expect(d.diffPct).toBeNull();
  });
});
