import React from "react";

// 가상 이상 시연 중임을 각 화면(대시보드·이상 탐지·AI 가이드)에 일관되게 표시하는 배너.
//
// - "가상 시연 중 · 실제 사용자 기록 아님" 문구를 항상 동일하게 노출한다.
// - 데모 응답의 aiGuide.referenceDate(기준일)가 있으면 함께 표시한다.
//   (UI 에 날짜를 하드코딩하지 않고, 상위에서 받은 referenceDate 만 쓴다.)
// - demoActive 가 false 면 아무것도 렌더링하지 않아 실제 데이터 화면을 그대로 둔다.
//
// props:
//  - demoActive:        가상 시연 결과가 화면에 적용 중인지 여부.
//  - demoReferenceDate: 데모 응답의 기준일(문자열) 또는 null.
export default function DemoBanner({ demoActive = false, demoReferenceDate = null }) {
  if (!demoActive) return null;
  return (
    <div
      className="card"
      role="status"
      aria-label="가상 시연 안내"
      style={{
        padding: "10px 14px",
        borderLeft: "4px solid var(--color-warn, #d97706)",
        background: "var(--color-warn-bg, #fff7ed)",
      }}
    >
      <p style={{ margin: 0, fontWeight: 700, fontSize: 13 }}>
        가상 시연 중 · 실제 사용자 기록 아님
      </p>
      {demoReferenceDate && (
        <p style={{ margin: "4px 0 0", color: "var(--color-muted)", fontSize: 12 }}>
          시연 기준일: {demoReferenceDate}
        </p>
      )}
    </div>
  );
}
