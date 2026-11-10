import React, { useState } from "react";

// 발표용 "가상 이상 시연" 패널.
//
// 역할(표시/조작만, API 호출은 상위 App 이 담당):
//  - 사용자가 "가상 이상 시연" 버튼을 누를 때만 상위의 onRun 을 호출한다.
//  - 요청 중에는 버튼을 비활성화한다(중복 호출·자동 재시도 방지). 상위가 1회만 호출한다.
//  - "가상 입력 · 실제 AI 생성 · 실제 사용자 기록 아님"을 항상 표시한다.
//  - 실패 시 오류 메시지를 표시한다(예시 응답으로 대체하지 않음 — 상위가 보장).
//  - 시연 결과가 떠 있을 때만 "실제 데이터로 돌아가기"로 시연 결과를 해제한다.
//
// props:
//  - onRun():     버튼 클릭 시 호출. 상위가 POST /demo/anomaly 를 1회 호출한다.
//  - onReset():   "실제 데이터로 돌아가기" 클릭 시 호출. 시연 결과만 해제한다.
//  - loading:     요청 진행 중 여부(버튼 비활성화).
//  - active:      시연 결과가 현재 화면에 적용 중인지(해제 버튼 노출).
//  - error:       실패 메시지(문자열) 또는 null.
export default function DemoAnomalyPanel({ onRun, onReset, loading = false, active = false, error = null, onSend, canSend = false, sending = false, delivery = null, persistenceWarning = null }) {
  const [scenario, setScenario] = useState("steps");
  return (
    <section className="card" style={{ padding: 16 }} aria-label="가상 이상 시연">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h3 className="card__title" style={{ margin: 0 }}>가상 이상 시연</h3>
          <p className="ui-note" style={{ margin: "6px 0 0" }}>
            가상 입력 · 실제 AI 생성 · 실제 사용자 기록 아님
          </p>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <label>
            <select aria-label="시연 시나리오" value={scenario} disabled={loading || sending} onChange={(e) => setScenario(e.target.value)}>
              <option value="steps">걸음 수 감소</option>
              <option value="sleep">수면 부족</option>
              <option value="restless">수면 중 움직임 증가</option>
              <option value="hrv">HRV 감소</option>
              <option value="stress">스트레스 증가</option>
              <option value="multi">수면·HRV·스트레스 다중 지표</option>
            </select>
          </label>
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => onRun(scenario)}
            disabled={loading || sending}
          >
            {loading ? "AI 분석 중…" : "가상 이상 시연"}
          </button>

          {active && onSend && (
            <button type="button" className="btn" disabled={!canSend || loading || sending || Boolean(delivery)} onClick={onSend}>
              {sending ? "발송 요청 중…" : delivery ? "발송 요청 처리됨" : "SNS 메일 발송"}
            </button>
          )}
          {active && (
            <button
              type="button"
              className="btn"
              onClick={onReset}
              disabled={loading || sending}
            >
              실제 데이터로 돌아가기
            </button>
          )}
        </div>
      </div>

      {active && !error && (
        <p className="ui-note" role="status" style={{ margin: "12px 0 0" }}>
          아래 이상 탐지와 AI 가이드는 가상 입력에 대한 실제 AI 생성 결과입니다.
          실제 사용자 기록이 아니며, 다른 대시보드 카드는 실제 데이터 그대로입니다.
        </p>
      )}

      {active && <p className="ui-note" style={{ marginTop: 10 }}>분석만으로는 이메일을 보내지 않습니다. SNS 메일 발송 버튼은 기존 SNS 구독 주소로 실제 이메일을 보내며, 같은 결과는 한 번만 발송합니다.</p>}
      {delivery && <p className="ui-note" role="status">{delivery.title}{delivery.status === "accepted" ? " · SNS 접수 결과이며 수신함 도착 확인은 별도입니다." : " · 중복 방지를 위해 다시 보내지 않습니다."}</p>}
      {persistenceWarning && <p className="ui-note" role="status">{persistenceWarning}</p>}
      {error && (
        <p role="alert" style={{ margin: "12px 0 0", color: "var(--color-danger)", fontWeight: 600, fontSize: 13 }}>
          {error}
        </p>
      )}
    </section>
  );
}
