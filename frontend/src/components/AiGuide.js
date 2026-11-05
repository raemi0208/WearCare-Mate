import React from "react";

export default function AiGuide({ guide, onRegenerate, regenerating = false }) {
  if (!guide) return null;

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
        <span className="ai-guide__badge">✦ 생성형 AI</span>
      </header>

      <div className="card__body">
        <p className="ai-guide__headline">{guide.headline}</p>
        <div className="ai-guide__text">
          {bodyLines.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>

        <div className="ai-guide__actions">
          {guide.actions.map((action, i) => (
            <div key={i} className="ai-guide__action">
              <span className="ai-guide__action-check" aria-hidden="true">
                {i + 1}
              </span>
              <span className="ai-guide__action-text">{action}</span>
            </div>
          ))}
        </div>

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
            {regenerating ? "생성 중…" : "가이드 다시 생성"}
          </button>
        )}
      </div>
    </section>
  );
}
