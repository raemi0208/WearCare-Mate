import React from "react";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import AiGuide from "../components/AiGuide";
import ConditionChat from "../components/ConditionChat";

export default function GuidePage({ data, onRegenerate, regenerating }) {
  const history = data.guideHistory || [];

  return (
    <div className="grid">
      <div className="grid grid--main">
        <AiGuide
          guide={data.aiGuide}
          onRegenerate={onRegenerate}
          regenerating={regenerating}
        />
        <ConditionChat />
      </div>

      <Card
        title="가이드 히스토리"
        subtitle="Amazon Bedrock이 생성한 과거 가이드"
      >
        <div className="history-list">
          {history.length === 0 && <p>저장된 가이드 내역이 없습니다.</p>}
          {history.map((h) => (
            <div key={h.id} className="history-item">
              <div className="history-item__top">
                <span className="history-item__date">{h.date}</span>
                <Badge variant="ghost">{h.tag}</Badge>
              </div>
              <p className="history-item__headline">{h.headline}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
