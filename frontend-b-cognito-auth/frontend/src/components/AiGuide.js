import React from "react";
import YesterdayCompare from "./YesterdayCompare";

// detailed=true 이면 AI 가이드 페이지용 상세 보기(섹션 구분·안내 문구 추가)로 표시합니다.
// comparison/comparisonNote 는 detailed 일 때만 '어제와 비교' 섹션으로 표시됩니다.
export default function AiGuide({ guide, onRegenerate, regenerating = false, detailed = false, comparison = null, comparisonNote = "" }) {
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

  const normalize = (text) => (text || "").trim().replace(/\s+/g, " ");
  const actions = [...new Set((guide.actions || []).filter(Boolean))];
  const shown = new Set([normalize(guide.headline), ...actions.map(normalize)]);
  const uniqueBodyLines = bodyLines.filter((line) => {
    const key = normalize(line);
    if (!key || shown.has(key)) return false;
    shown.add(key);
    return true;
  });

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
        {detailed && <p className="ai-guide__section">오늘의 요약</p>}
        <p className="ai-guide__headline">{guide.headline}</p>
        {detailed && actions.length > 0 && (
          <p className="ai-guide__section">실천 항목 {actions.length}개</p>
        )}
        <div className="ai-guide__actions">
          {actions.map((action, i) => (
            <div key={i} className="ai-guide__action">
              <span className="ai-guide__action-check" aria-hidden="true">
                {i + 1}
              </span>
              <span className="ai-guide__action-text">{action}</span>
            </div>
          ))}
        </div>

        {detailed && uniqueBodyLines.length > 0 && (
          <p className="ai-guide__section">상세 설명</p>
        )}
        <div className="ai-guide__text">
          {uniqueBodyLines.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>

        {detailed && (comparison || comparisonNote) && (
          <YesterdayCompare comparison={comparison} note={comparisonNote} />
        )}

        {detailed && (
          <div className="ai-guide__notice">
            <p className="ai-guide__notice-title">이렇게 활용하세요</p>
            <ul>
              <li>실천 항목은 오늘 하루 부담 없는 범위에서 하나씩 시도해 보세요.</li>
              <li>하단의 다시 확인 버튼으로 최신 데이터 기준 가이드를 받을 수 있어요.</li>
              <li>과거 가이드는 오른쪽 히스토리에서 비교해 볼 수 있어요.</li>
            </ul>
            <p className="ai-guide__notice-foot">
              본 안내는 일반적인 생활 습관 권고이며, 의학적 진단이나 치료를 대체하지 않습니다.
              불편함이 계속되면 전문가와 상담하세요.
            </p>
          </div>
        )}

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
