import React, { useState } from "react";
import Card from "./ui/Card";
import "./TodayStepsCard.css";

const number = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 });
const fields = [
  { key: "steps", label: "오늘 걸음 수", min: 0, step: 1 },
  { key: "goal", label: "목표 걸음 수", min: 1, step: 1 },
  { key: "sleep", label: "수면 시간 (시간)", min: 0, max: 24, step: "any" },
];

export default function TodayStepsCard() {
  const [draft, setDraft] = useState({ steps: "", goal: "10000", sleep: "" });
  const [record, setRecord] = useState(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [time, setTime] = useState("21:00");
  const percentage = record ? record.steps / record.goal * 100 : 0;
  const remaining = record ? Math.max(0, record.goal - record.steps) : 0;
  const sleep = record?.sleep == null ? "미입력" : number.format(record.sleep) + "시간";

  function showReport(event) {
    event.preventDefault();
    const steps = Number(draft.steps);
    const goal = Number(draft.goal);
    const sleepHours = draft.sleep === "" ? null : Number(draft.sleep);
    if (draft.steps === "" || !Number.isSafeInteger(steps) || steps < 0 ||
        !Number.isSafeInteger(goal) || goal < 1) {
      setError("걸음 수는 0 이상, 목표는 1 이상의 정수로 입력해 주세요.");
      return;
    }
    if (sleepHours !== null && !(sleepHours >= 0 && sleepHours <= 24)) {
      setError("수면 시간은 0~24시간 사이로 입력해 주세요.");
      return;
    }
    setRecord({ steps, goal, sleep: sleepHours });
    setError("");
    setEditing(false);
  }

  return (
    <Card title="오늘의 건강 리포트" subtitle="Apple 건강에서 확인 · 직접 입력">
      <div className="today-report">
        <dl className="today-report__row" aria-live="polite">
          <div>
            <dt>오늘 걸음 수</dt>
            <dd>{record ? number.format(record.steps) + "걸음" : "—"}</dd>
            {record && <p className="ui-note">목표 {number.format(record.goal)}걸음</p>}
          </div>
          <div>
            <dt>목표 달성률</dt>
            <dd>{record ? number.format(percentage) + "%" : "—"}</dd>
            {record && (
              <>
                <progress aria-label="걸음 목표 진행률" value={Math.min(percentage, 100)} max="100" />
                <p className="ui-note">{remaining ? "목표까지 " + number.format(remaining) + "걸음" : "목표 달성"}</p>
              </>
            )}
          </div>
          <div><dt>수면 시간</dt><dd>{record ? sleep : "—"}</dd></div>
        </dl>
        {!record && !editing && <p className="ui-note">오늘 기록을 입력해 주세요.</p>}
        <div className="today-report__actions">
          <button type="button" className="btn btn--primary" aria-expanded={editing}
            onClick={() => { setEditing(!editing); setError(""); }}>
            {editing ? "입력 닫기" : record ? "오늘 기록 수정" : "오늘 기록 입력"}
          </button>
          <button type="button" className="btn" aria-expanded={preview} onClick={() => setPreview(!preview)}>
            {preview ? "이메일 미리보기 닫기" : "이메일 리포트 미리보기"}
          </button>
        </div>
        {editing && (
          <form className="today-report__section" onSubmit={showReport} noValidate>
            <div className="today-report__row">
              {fields.map(({ key, label, ...limits }) => (
                <label className="form__field" key={key}>
                  <span className="form__label">{label}</span>
                  <input className="form__input" type="number" {...limits} value={draft[key]}
                    onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} />
                </label>
              ))}
            </div>
            {error && <p className="ui-note" role="alert">{error}</p>}
            <button type="submit" className="btn btn--primary">리포트 보기</button>
          </form>
        )}
        {preview && (
          <section className="today-report__section" aria-label="이메일 리포트 미리보기">
            <div className="today-report__actions">
              <label><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> 매일 받기</label>
              <label>받을 시간 (한국 시간) <input className="form__input" type="time" value={time}
                disabled={!enabled} onChange={(event) => setTime(event.target.value)} /></label>
            </div>
            <p className="ui-note">미리보기용 설정입니다. 예약 발송은 아직 연결되지 않았습니다.</p>
            <p>{record
              ? number.format(record.steps) + "걸음 · 목표 " + number.format(percentage) + "% · 수면 " + sleep
              : "오늘 기록을 입력하면 이메일 내용을 미리 볼 수 있습니다."}</p>
          </section>
        )}
      </div>
    </Card>
  );
}
