import React from "react";

// 어제와 비교 섹션: 좋아진 점(초록 ▲), 나빠진 점(주황 ▼)을 색·기호·텍스트로 함께 표시합니다.
function Row({ item, kind }) {
  const symbol = kind === "better" ? "▲" : kind === "worse" ? "▼" : "＝";
  const word = kind === "better" ? "좋아졌어요" : kind === "worse" ? "나빠졌어요" : "비슷해요";
  return (
    <li className={`compare-item compare-item--${kind}`}>
      <span className="compare-item__symbol" aria-hidden="true">{symbol}</span>
      <span className="compare-item__label">{item.label}</span>
      <span className="compare-item__change">
        {kind === "same" ? word : `${item.text} · ${word}`}
      </span>
    </li>
  );
}

function Group({ title, items, kind }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="compare-group">
      <p className={`compare-group__title compare-group__title--${kind}`}>{title}</p>
      <ul className="compare-list">
        {items.map((item) => (
          <Row key={item.id} item={item} kind={kind} />
        ))}
      </ul>
    </div>
  );
}

export default function YesterdayCompare({ comparison, note }) {
  return (
    <div className="compare">
      <p className="ai-guide__section">어제와 비교</p>
      {!note && (
        <p className="ui-note">생성형 AI 문장이 아니라 오늘·어제 기록 값을 단순 비교한 결과입니다.</p>
      )}
      {note ? (
        <p className="ui-note">{note}</p>
      ) : !comparison || !comparison.hasData ? (
        <p className="ui-note">비교할 어제 데이터가 없습니다.</p>
      ) : (
        <>
          <Group title="어제보다 좋아진 점" items={comparison.improved} kind="better" />
          <Group title="어제보다 나빠진 점" items={comparison.worsened} kind="worse" />
          <Group title="어제와 비슷한 점" items={comparison.same} kind="same" />
        </>
      )}
    </div>
  );
}
