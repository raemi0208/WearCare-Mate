import React from "react";
import Card from "./ui/Card";

const formatNumber = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 });

export default function PersonalReportHistory({ records = [], loading, error }) {
  const entries = [...records].sort((a, b) => b.date.localeCompare(a.date));
  const latest = entries[0];
  const showBars = entries.length >= 2;

  return (
    <Card icon="📋" title="내 건강 기록" subtitle="최근 30일 · 오늘의 건강 리포트에서 직접 입력한 기록">
      {error ? <p role="alert">내 기록을 불러오지 못했습니다.</p>
        : loading ? <p role="status">내 기록을 불러오는 중이에요.</p>
        : !latest ? <p>오늘의 건강 리포트에 기록을 입력하면 여기에 표시돼요.</p>
        : (
          <>
            <div className="personal-history__summary">
              <p>최근 기록 · <time dateTime={latest.date}>{latest.date}</time></p>
              <div className="trend-stats">
                <div className="trend-stat">
                  <span className="trend-stat__label">걸음 수</span>
                  <strong>{formatNumber.format(latest.steps)} / {formatNumber.format(latest.goal)}걸음</strong>
                </div>
                <div className="trend-stat">
                  <span className="trend-stat__label">목표 달성률</span>
                  <strong>{Math.round(latest.steps / latest.goal * 100)}%</strong>
                </div>
                <div className="trend-stat">
                  <span className="trend-stat__label">수면 시간</span>
                  <strong>{Number.isFinite(latest.sleep) ? formatNumber.format(latest.sleep) + "시간" : "기록 없음"}</strong>
                </div>
              </div>
            </div>
            <div className="personal-history__table">
              <table>
                <caption>날짜별 기록</caption>
                <thead>
                  <tr>
                    <th scope="col">날짜</th>
                    <th scope="col">걸음 수 / 목표</th>
                    <th scope="col">목표 달성률</th>
                    <th scope="col">수면 시간</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map(({ date, steps, goal, sleep }) => {
                    const percentage = Math.round(steps / goal * 100);
                    const hasSleep = Number.isFinite(sleep);
                    return (
                      <tr key={date}>
                        <th scope="row"><time dateTime={date}>{date}</time></th>
                        <td>{formatNumber.format(steps)} / {formatNumber.format(goal)}걸음</td>
                        <td>
                          <span>{percentage}%</span>
                          {showBars && <span aria-hidden="true" className="personal-history__bar"><span style={{ width: Math.min(percentage, 100) + "%" }} /></span>}
                        </td>
                        <td>
                          <span>{hasSleep ? formatNumber.format(sleep) + "시간" : "기록 없음"}</span>
                          {showBars && hasSleep && <span aria-hidden="true" className="personal-history__bar"><span style={{ width: (sleep / 24) * 100 + "%" }} /></span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
    </Card>
  );
}
