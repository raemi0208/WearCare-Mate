import React from "react";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";

const LEVEL = {
  ok: { label: "정상", variant: "normal" },
  warn: { label: "주의", variant: "warn" },
  danger: { label: "통증", variant: "danger" },
};

export default function BodyPage({ data }) {
  const ms = data.musculoskeletal;

  if (!ms) {
    return (
      <Card title="근골격계">
        <p>근골격계 데이터가 없습니다.</p>
      </Card>
    );
  }

  return (
    <div className="grid">
      <div className="grid grid--stats">
        <div className="card stat">
          <div className="stat__label">주요 상태</div>
          <div className="stat__value" style={{ fontSize: 20 }}>
            {ms.condition}
          </div>
          <div className="stat__delta is-flat">관절염 메타데이터</div>
        </div>
        <div className="card stat">
          <div className="stat__label">통증 관찰 부위</div>
          <div className="stat__value">
            {ms.painPoints.filter((p) => p.level !== "ok").length}
            <span className="stat__unit">곳</span>
          </div>
          <div className="stat__delta is-flat">주의 이상 등급</div>
        </div>
        <div className="card stat">
          <div className="stat__label">정상 부위</div>
          <div className="stat__value">
            {ms.painPoints.filter((p) => p.level === "ok").length}
            <span className="stat__unit">곳</span>
          </div>
          <div className="stat__delta is-flat">특이사항 없음</div>
        </div>
        <div className="card stat">
          <div className="stat__label">데이터 소스</div>
          <div className="stat__value" style={{ fontSize: 18 }}>
            관절염 DB
          </div>
          <div className="stat__delta is-flat">S3 데이터 레이크</div>
        </div>
      </div>

      <Card
        title="근골격계 상태"
        subtitle="관절염 메타데이터 기반 부위별 통증 현황"
        action={<Badge variant="ghost">Body</Badge>}
      >
        <p className="section-summary">{ms.summary}</p>

        <div className="pain-list">
          {ms.painPoints.map((p) => {
            const lv = LEVEL[p.level] || LEVEL.ok;
            return (
              <div key={p.id} className="pain-item">
                <span className={`anomaly-item__dot is-${p.level}`} />
                <div className="pain-item__body">
                  <div className="pain-item__title">
                    <span>{p.label}</span>
                    <Badge variant={lv.variant}>{lv.label}</Badge>
                  </div>
                  <p className="pain-item__note">{p.note}</p>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <Card title="관리 권장" subtitle="Amazon Bedrock 기반 맞춤 가이드">
        <div className="ai-guide__actions" style={{ marginTop: 0 }}>
          <div className="info-action">
            🦵 무릎에 부담이 가는 고강도 하체 운동은 피하기
          </div>
          <div className="info-action">🧊 통증 부위는 무리하지 말고 냉찜질로 완화</div>
          <div className="info-action">🪑 앉아서 하는 가벼운 스트레칭 위주로 진행</div>
        </div>
        <p className="chat__disclaimer" style={{ marginTop: 16 }}>
          통증이 지속되거나 악화되면 정형외과 진료를 권장합니다.
        </p>
      </Card>
    </div>
  );
}
