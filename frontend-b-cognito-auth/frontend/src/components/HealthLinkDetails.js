import React from "react";
import { LINK_DATA_ITEMS } from "../services/healthLinkStorage";
import { timeseries as sampleTimeseries } from "../data/mockData";

// 시계열의 마지막 값(없으면 null)
function lastValue(series) {
  if (!Array.isArray(series) || series.length === 0) return null;
  const v = series[series.length - 1]?.value;
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

// 항목별 예시 값 문자열 (timeseries 마지막 값 → mockData 마지막 값 → 항목 기본 예시)
function sampleText(item, timeseries) {
  let value = null;
  if (item.source) {
    value = lastValue(timeseries?.[item.source]) ?? lastValue(sampleTimeseries[item.source]);
  } else {
    value = item.sample;
  }
  if (value == null) return "—";
  const digits = item.id === "sleep" ? 1 : 0;
  return `${value.toLocaleString("ko-KR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}${item.unit}`;
}

// 건강 앱 연동 상세: 가져오는 데이터 항목, 필요한 권한, 개인정보·데이터 이용 안내
export default function HealthLinkDetails({ timeseries }) {
  return (
    <div className="health-link-details">
      <section aria-label="가져오는 데이터 항목">
        <h4 className="health-link-details__title">가져오는 데이터</h4>
        <ul className="health-link-items">
          {LINK_DATA_ITEMS.map((item) => (
            <li key={item.id} className="health-link-item">
              <span className="health-link-item__icon" aria-hidden="true">{item.icon}</span>
              <span className="health-link-item__text">
                <span className="health-link-item__label">{item.label}</span>
                <span className="health-link-item__desc">{item.desc}</span>
              </span>
              <span className="health-link-item__value">
                {sampleText(item, timeseries)}
                <span className="health-link-item__sample">예시 값</span>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="필요한 권한">
        <h4 className="health-link-details__title">필요한 권한</h4>
        <ul className="health-link-notes">
          <li>건강 앱의 걸음수·수면·심박·활동·칼로리 기록을 읽기 전용으로 조회하는 권한</li>
          <li>기록을 수정하거나 삭제하는 권한은 요청하지 않습니다.</li>
          <li>연동 해제 시 권한은 언제든 건강 앱 설정에서 다시 끌 수 있습니다.</li>
        </ul>
      </section>

      <section aria-label="개인정보 및 데이터 이용 안내">
        <h4 className="health-link-details__title">개인정보·데이터 이용 안내</h4>
        <ul className="health-link-notes">
          <li>가져온 기록은 걸음수·수면 분석, 일일 리포트, AI 건강 가이드 표시에만 사용됩니다.</li>
          <li>이 화면의 연동 상태는 이 브라우저에만 저장되며 다른 기기와 공유되지 않습니다.</li>
          <li>시연용 연동이므로 실제 건강 데이터를 가져오거나 외부로 전송하지 않습니다.</li>
        </ul>
      </section>
    </div>
  );
}
