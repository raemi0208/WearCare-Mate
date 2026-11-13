import { applyMainAppData } from "./healthAppMock";
import { timeseries as baseTimeseries } from "./mockData";
import { buildDailyReport } from "../services/dailyReport";
import { compareYesterday } from "../utils/compareYesterday";

const base = { timeseries: baseTimeseries, summaryStats: [], user: { name: "x" } };

test("메인 앱이 삼성/애플이면 리포트·어제와 비교 수치가 서로 다르다", () => {
  const samsung = applyMainAppData(base, "samsung");
  const apple = applyMainAppData(base, "apple");
  expect(buildDailyReport(samsung.timeseries, 10000).steps).not.toBe(buildDailyReport(apple.timeseries, 10000).steps);
  expect(compareYesterday(samsung.timeseries).worsened.length).toBe(3);
  expect(compareYesterday(apple.timeseries).improved.length).toBe(3);
  expect(samsung.summaryStats[2].value).not.toBe(apple.summaryStats[2].value);
  expect(samsung.mainAppSample.label).toBe("삼성 헬스");
});

test("기타 앱/미연동이면 원본 data 를 그대로 사용하고 원본은 바뀌지 않는다", () => {
  expect(applyMainAppData(base, "fitbit")).toBe(base);
  expect(applyMainAppData(base, null)).toBe(base);
  applyMainAppData(base, "apple");
  expect(base.timeseries).toBe(baseTimeseries);
  expect(base.mainAppSample).toBeUndefined();
});
