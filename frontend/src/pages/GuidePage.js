import React from "react";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import AiGuide from "../components/AiGuide";
import DemoBanner from "../components/DemoBanner";

export default function GuidePage({ data, onRegenerate, regenerating, demoActive = false, demoReferenceDate = null, onLoadMore, historyLoading = false }) {
  const history = data.guideHistory || [];

  return (
    // 배너는 2열 그리드 밖에서 페이지 전체 너비로 표시한다(그리드 열에 끼어들지 않게).
    // 아래 grid--main 은 기존대로 좌 AI 가이드 · 우 히스토리 2열(작은 화면에서는 1열로 접힘).
    <div className="grid">
      <DemoBanner demoActive={demoActive} demoReferenceDate={demoReferenceDate} />
      <div className="grid grid--main">
        <AiGuide
          guide={data.aiGuide}
          onRegenerate={onRegenerate}
          regenerating={regenerating}
        />

        <Card
          title="가이드 히스토리"
          subtitle="Amazon Bedrock이 생성한 과거 가이드"
        >
          <p className="ui-note">로그인 계정별로 저장된 가이드입니다. 가상 시연 결과에는 별도 표시가 붙습니다.</p>
          <div className="history-list">
            {history.length === 0 && <p className="ui-note">저장된 가이드 내역이 없습니다.</p>}
            {history.map((h) => (
              <div key={h.id} className="history-item">
                <div className="history-item__top">
                  <span className="history-item__date">{h.date}</span>
                  <Badge variant="ghost">{h.tag}</Badge>
                </div>
                <p className="history-item__headline">{h.headline}</p>
                {h.text && <p className="ui-note" style={{ whiteSpace: "pre-line" }}>{h.text}</p>}
              </div>
            ))}
          </div>
          {data.nextCursor && onLoadMore && <button className="btn" disabled={historyLoading} onClick={() => onLoadMore(data.nextCursor)}>{historyLoading ? "불러오는 중…" : "이전 내역 더 보기"}</button>}
        </Card>
      </div>
    </div>
  );
}
