import React from "react";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";

const LEVEL = {
  normal: { label: "정상", variant: "normal" },
  warn: { label: "주의", variant: "warn" },
  high: { label: "높음", variant: "danger" },
};

export default function MindPage({ data }) {
  const mental = data.mentalState;

  if (!mental) {
    return (
      <Card title="심리·스트레스">
        <p>심리 상태 데이터가 없습니다.</p>
      </Card>
    );
  }

  return (
    <div className="grid">
      <Card
        title="심리·스트레스 상태"
        subtitle={`심리상담 점수 기반 · ${mental.updatedAt}`}
        action={<Badge variant="ghost">Mind</Badge>}
      >
        <p className="section-summary">{mental.summary}</p>

        <div className="gauge-list">
          {mental.scores.map((s) => {
            const lv = LEVEL[s.level] || LEVEL.normal;
            return (
              <div key={s.id} className="gauge">
                <div className="gauge__head">
                  <span className="gauge__label">{s.label}</span>
                  <span className="gauge__value">
                    {s.value}
                    <span className="gauge__max"> / 100</span>
                  </span>
                </div>
                <div className="gauge__track">
                  <div
                    className={`gauge__fill is-${s.level}`}
                    style={{ width: `${s.value}%` }}
                  />
                </div>
                <div className="gauge__foot">
                  <Badge variant={lv.variant}>{lv.label}</Badge>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <Card
        title="종합 해석"
        subtitle="Amazon Bedrock 기반 심리 상태 요약"
      >
        <p className="section-summary">
          스트레스와 불안 지표가 평소보다 높게 나타났습니다. 수면 부족과 함께
          나타나는 경우가 많아, 충분한 휴식과 이완 활동이 도움이 됩니다. 증상이
          2주 이상 지속되면 전문 상담을 권장합니다.
        </p>
        <div className="ai-guide__actions" style={{ marginTop: 0 }}>
          <div className="info-action">🧘 하루 10분 호흡 명상으로 긴장 완화</div>
          <div className="info-action">☕ 오후 카페인 섭취 줄이기</div>
          <div className="info-action">🚶 가벼운 산책으로 기분 전환</div>
        </div>
        <p className="chat__disclaimer" style={{ marginTop: 16 }}>
          심리 점수는 자가 설문 기반 참고 지표이며 의학적 진단을 대체하지 않습니다.
        </p>
      </Card>
    </div>
  );
}
