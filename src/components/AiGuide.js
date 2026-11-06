import React from "react";

export default function AiGuide({ guide, onRegenerate, regenerating = false }) {
  if (!guide) return null;
  const generated = guide.status === "generated";
  const isMock = !guide.status;
  const badge = isMock ? "예시 가이드" : generated ? "생성형 AI" :
    guide.status === "missing" ? "가이드 생성 실패" :
      guide.analysisStatus === "insufficient_data" ? "데이터 부족" : "활동량 판정";

  // 본문은 lines 배열을 우선 사용해 줄별로 표시하고,
  // lines가 없거나 비어있으면 text의 줄바꿈(\n)을 유지해 표시합니다.
  const bodyLines =
    Array.isArray(guide.lines) && guide.lines.length > 0
      ? guide.lines
      : (guide.text || "").split("\n");

  return (
    <section className="card ai-guide">
      <header className="card__header">
        <div>
          <h3 className="card__title">AI 맞춤 건강 가이드</h3>
        </div>
        <span className="ai-guide__badge">{badge}</span>
      </header>

      <div className="card__body">
        {guide.referenceDate && <p>분석 기준일: {guide.referenceDate}</p>}
        <p className="ai-guide__headline">{guide.headline}</p>

        {guide.sources?.length > 0 && (
          <div className="ai-guide__sources">
            <span className="ai-guide__sources-label">종합 분석 데이터</span>
            <div className="ai-guide__sources-chips">
              {guide.sources.map((s) => (
                <span key={s.id} className="ai-guide__source-chip">
                  <span aria-hidden="true">{s.icon}</span>
                  {s.label}
                </span>
              ))}
            </div>
          </div>
        )}
        <div className="ai-guide__text">
          {bodyLines.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>

        <div className="ai-guide__actions">
          {(guide.actions || []).map((action, i) => (
            <div key={i} className="ai-guide__action">
              <span className="ai-guide__action-check" aria-hidden="true">
                {i + 1}
              </span>
              <span className="ai-guide__action-text">{action}</span>
            </div>
          ))}
        </div>

        {guide.warnings?.length > 0 && (
          <p role="status">생성 가이드가 일부 출력 규칙을 충족하지 못했습니다. 내용을 확인해 주세요.</p>
        )}

        <div className="ai-guide__footer">
          <span>⟳</span>
          {guide.model} · {regenerating ? "가이드 재생성 중…" : guide.updatedAt}
        </div>

        {onRegenerate && (
          <button
            type="button"
            className="chart__tab"
            style={{ marginTop: "16px" }}
            onClick={onRegenerate}
            disabled={regenerating}
          >
            {regenerating ? "확인 중…" : "분석 및 가이드 다시 확인"}
          </button>
        )}
      </div>
    </section>
  );
}
