import React, { useState } from "react";
import Card from "../components/ui/Card";
import { updateProfile } from "../services/api";

export default function SettingsPage({ user, onProfileSaved }) {
  const [form, setForm] = useState({
    name: user?.name || "",
    age: user?.age || "",
    gender: user?.gender || "",
    height: user?.height || "",
    weight: user?.weight || "",
    goal: user?.goal || "balanced",
    notifyAnomaly: user?.notifyAnomaly ?? true,
    notifyGuide: user?.notifyGuide ?? true,
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const update = (field) => (e) => {
    const value =
      e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((prev) => ({ ...prev, [field]: value }));
    setSaved(false);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setSaving(true);
    // name에서 이니셜 재계산, meta 문구 갱신
    const meta = [form.age && `${form.age}세`, form.gender]
      .filter(Boolean)
      .join(" · ");
    const payload = {
      ...user,
      ...form,
      meta: meta || user?.meta,
      initial: form.name ? form.name.charAt(0) : user?.initial,
    };
    updateProfile(payload)
      .then((updated) => {
        onProfileSaved?.(updated);
        setSaved(true);
      })
      .finally(() => setSaving(false));
  };

  return (
    <div className="grid">
      <Card icon="👤" title="프로필 정보" subtitle="이 브라우저에 저장되는 표시용 프로필입니다">
        <p className="ui-note">이 정보는 현재 AI 분석에 사용되지 않으며, 다른 브라우저나 기기와 공유되지 않습니다.</p>
        <form className="form" onSubmit={handleSubmit}>
          <div className="form__row">
            <label className="form__field">
              <span className="form__label">이름</span>
              <input
                className="form__input"
                type="text"
                value={form.name}
                onChange={update("name")}
                placeholder="이름"
              />
            </label>
            <label className="form__field">
              <span className="form__label">나이</span>
              <input
                className="form__input"
                type="number"
                min="0"
                value={form.age}
                onChange={update("age")}
                placeholder="예: 33"
              />
            </label>
          </div>

          <div className="form__row">
            <label className="form__field">
              <span className="form__label">성별</span>
              <select
                className="form__input"
                value={form.gender}
                onChange={update("gender")}
              >
                <option value="">선택 안 함</option>
                <option value="남성">남성</option>
                <option value="여성">여성</option>
                <option value="기타">기타</option>
              </select>
            </label>
            <label className="form__field">
              <span className="form__label">건강 목표</span>
              <select
                className="form__input"
                value={form.goal}
                onChange={update("goal")}
              >
                <option value="balanced">균형 잡힌 관리</option>
                <option value="sleep">수면 개선</option>
                <option value="activity">활동량 증가</option>
                <option value="recovery">회복/휴식</option>
              </select>
            </label>
          </div>

          <div className="form__row">
            <label className="form__field">
              <span className="form__label">키 (cm)</span>
              <input
                className="form__input"
                type="number"
                min="0"
                value={form.height}
                onChange={update("height")}
                placeholder="예: 172"
              />
            </label>
            <label className="form__field">
              <span className="form__label">몸무게 (kg)</span>
              <input
                className="form__input"
                type="number"
                min="0"
                value={form.weight}
                onChange={update("weight")}
                placeholder="예: 68"
              />
            </label>
          </div>

          <div className="form__actions">
            <button type="submit" className="btn btn--primary" disabled={saving}>
              {saving ? "저장 중…" : "변경 사항 저장"}
            </button>
            {saved && <span className="form__saved">✓ 저장되었습니다</span>}
          </div>
        </form>
      </Card>

      <Card icon="🔔" title="알림 설정" subtitle="시연용 알림 선호 설정">
        <p className="ui-note">변경 사항 저장을 누르면 이 브라우저에만 저장됩니다. 실제 SNS 이메일 수신 설정에는 반영되지 않습니다. 분석만으로는 메일을 보내지 않으며, 대시보드의 SNS 메일 발송 버튼을 누르면 기존 구독 주소로 실제 이메일을 보냅니다.</p>
        <div className="toggle-list">
          <label className="toggle-item">
            <span>
              <span className="toggle-item__title">이상 패턴 알림</span>
              <span className="toggle-item__desc">
                심박·수면·활동량 이상 감지 시 알림
              </span>
            </span>
            <input
              type="checkbox"
              checked={form.notifyAnomaly}
              onChange={update("notifyAnomaly")}
            />
          </label>
          <label className="toggle-item">
            <span>
              <span className="toggle-item__title">AI 가이드 알림</span>
              <span className="toggle-item__desc">
                새 맞춤 건강 가이드 생성 시 알림
              </span>
            </span>
            <input
              type="checkbox"
              checked={form.notifyGuide}
              onChange={update("notifyGuide")}
            />
          </label>
        </div>
      </Card>
    </div>
  );
}
