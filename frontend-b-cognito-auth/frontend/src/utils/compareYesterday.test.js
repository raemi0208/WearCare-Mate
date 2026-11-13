import { compareYesterday } from "./compareYesterday";

const series = (...values) => values.map((value, i) => ({ label: String(i), value }));

test("목 데이터: 걸음·수면·심박 모두 나빠진 점", () => {
  const r = compareYesterday({
    steps: series(11200, 9400),
    sleep: series(8.0, 7.3),
    heartRate: series(59, 63),
  });
  expect(r.hasData).toBe(true);
  expect(r.worsened.map((i) => i.id)).toEqual(["steps", "sleep", "heartRate"]);
  expect(r.improved).toHaveLength(0);
  expect(r.items[0].text).toBe("−1,800걸음");
  expect(r.items[1].text).toBe("−0.7시간(−42분)");
  expect(r.items[2].text).toBe("+4bpm");
});

test("개선: 걸음·수면 증가, 심박 감소는 좋아진 점이고 임계 미만은 비슷함", () => {
  const r = compareYesterday({
    steps: series(5000, 6240),
    sleep: series(6.0, 6.05),
    heartRate: series(70, 66),
  });
  expect(r.improved.map((i) => i.id)).toEqual(["steps", "heartRate"]);
  expect(r.same.map((i) => i.id)).toEqual(["sleep"]);
  expect(r.worsened).toHaveLength(0);
});

test("데이터가 부족하면 hasData=false", () => {
  expect(compareYesterday(undefined).hasData).toBe(false);
  expect(compareYesterday({ steps: series(100), sleep: [], heartRate: [] }).hasData).toBe(false);
});

test("유한하지 않은 값은 건너뛴다", () => {
  const r = compareYesterday({
    steps: series(NaN, 100),
    sleep: series(7, Infinity),
    heartRate: series(60, 58),
  });
  expect(r.items.map((i) => i.id)).toEqual(["heartRate"]);
  expect(JSON.stringify(r)).not.toMatch(/NaN|Infinity|undefined/);
});
