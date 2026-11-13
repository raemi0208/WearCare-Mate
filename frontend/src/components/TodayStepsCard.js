import React, { useState } from "react";
import Card from "./ui/Card";

const formatter = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 });

export default function TodayStepsCard() {
  const [steps, setSteps] = useState("");
  const [goal, setGoal] = useState("10000");
  const [sleep, setSleep] = useState("");
  const [reportTime, setReportTime] = useState("21:00");
  const [reportEnabled, setReportEnabled] = useState(false);
  const [preview, setPreview] = useState(false);
  const validSleep = sleep !== "" && Number(sleep) >= 0 && Number(sleep) <= 24;
  const validSteps = /^\d+$/.test(steps) && Number.isSafeInteger(Number(steps));
  const validGoal = /^\d+$/.test(goal) && Number.isSafeInteger(Number(goal)) && Number(goal) > 0;
  const percentage = validSteps && validGoal ? (Number(steps) / Number(goal)) * 100 : null;

  return (
    <Card title="오늘의 건강 리포트" subtitle="Apple 건강에서 확인한 값 · 수동 입력">
      <div className="form__row">
        <label className="form__field">
          <span className="form__label">오늘 걸음 수</span>
          <input className="form__input" type="number" inputMode="numeric" min="0" step="1"
            value={steps} onChange={(event) => setSteps(event.target.value)}
            placeholder="건강 앱에서 확인한 걸음 수" />
        </label>
        <label className="form__field">
          <span className="form__label">목표 걸음 수</span>
          <input className="form__input" type="number" inputMode="numeric" min="1" step="1"
            value={goal} onChange={(event) => setGoal(event.target.value)} />
        </label>
      </div>
      <div className="form__row">
        <label className="form__field">
          <span className="form__label">수면 시간 (시간)</span>
          <input className="form__input" type="number" min="0" max="24" step="any"
            value={sleep} onChange={(event) => setSleep(event.target.value)} />
        </label>
      </div>
      <p role="status">
        {percentage !== null
          ? <>목표 달성률 <strong>{formatter.format(percentage)}%</strong></>
          : "오늘 걸음 수는 0 이상의 정수, 목표는 1 이상의 정수로 입력해 주세요."}
      </p>
      <fieldset>
        <legend>일일 이메일 리포트 설정</legend>
        <label>
          <input type="checkbox" checked={reportEnabled}
            onChange={(event) => setReportEnabled(event.target.checked)} />
          {" "}매일 리포트 받기
        </label>
        <label className="form__field">
          <span className="form__label">받을 시간 (한국 시간)</span>
          <input className="form__input" type="time" value={reportTime}
            disabled={!reportEnabled} onChange={(event) => setReportTime(event.target.value)} />
        </label>
        <p className="ui-note">미리보기용 설정입니다. 예약 발송은 아직 연결되지 않았습니다.</p>
        <button className="btn" type="button" aria-expanded={preview}
          onClick={() => setPreview(!preview)}>
          {preview ? "미리보기 닫기" : "일일 리포트 미리보기"}
        </button>
        {preview && (
          <div>
            <p>{reportEnabled && reportTime ? `매일 ${reportTime} (한국 시간)` : "수신 시간 미설정"}</p>
            <p>오늘 걸음 수 {validSteps ? formatter.format(Number(steps)) + "걸음" : "미입력"}</p>
            <p>목표 {validGoal ? formatter.format(Number(goal)) + "걸음" : "미입력"}</p>
            <p>목표 달성률 {percentage === null ? "미계산" : formatter.format(percentage) + "%"}</p>
            <p>수면 시간 {validSleep ? formatter.format(Number(sleep)) + "시간" : "미입력"}</p>
          </div>
        )}
      </fieldset>
    </Card>
  );
}
