import React, { useEffect, useState } from "react";
import Card from "./ui/Card";
import { isAuthEnabled } from "../services/authConfig";
import { getDailyReport, saveDailyReport } from "../services/api";
import "./TodayStepsCard.css";

const number = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 });
const fields = [
  { key: "steps", label: "오늘 걸음 수", min: 0, step: 1 },
  { key: "goal", label: "목표 걸음 수", min: 1, step: 1 },
  { key: "sleep", label: "수면 시간 (시간)", min: 0, max: 24, step: "any" },
];

export default function TodayStepsCard({ onPersonalTrends }) {
  const [draft, setDraft] = useState({ steps: "", goal: "10000", sleep: "" });
  const [history, setHistory] = useState([]);
  const [reportDate, setReportDate] = useState("");
  const [record, setRecord] = useState(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [time, setTime] = useState("21:00");
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const authenticated = isAuthEnabled();
  useEffect(() => {
    if (!authenticated) return undefined;
    let active = true;
    getDailyReport().then((report) => {
      if (!active) return;
      setConnected(true);
      setEnabled(report.enabled);
      setTime(report.time);
      setRecord(report.record);
      setHistory(report.records || []);
      setReportDate(report.date || "");
      if (report.record) {
        const { steps, goal, sleep } = report.record;
        setDraft({ steps: String(steps), goal: String(goal), sleep: sleep == null ? "" : String(sleep) });
      }
    }).catch(() => {
      if (active) setNotice("예약 설정을 불러오지 못했습니다. 새로고침 후 다시 시도해 주세요.");
    });
    return () => { active = false; };
  }, [authenticated]);

  async function saveSchedule(event) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    try {
      await saveDailyReport({ enabled, time });
      setNotice(enabled ? "일일 이메일 리포트 예약을 저장했습니다." : "일일 이메일 리포트를 껐습니다.");
    } catch {
      setNotice("설정을 저장하지 못했습니다. 계정 이메일 인증 상태를 확인해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  const percentage = record ? record.steps / record.goal * 100 : 0;
  const remaining = record ? Math.max(0, record.goal - record.steps) : 0;
  const sleep = record?.sleep == null ? "미입력" : number.format(record.sleep) + "시간";

  const start = Date.parse(reportDate) - 7 * 86400000;
  const recent = history.filter((entry) => entry.date < reportDate &&
    Date.parse(entry.date) >= start && Number.isFinite(entry.sleep));
  const average = recent.length >= 3
    ? recent.reduce((sum, entry) => sum + entry.sleep, 0) / recent.length : null;
  const difference = average === null || record?.sleep == null
    ? null : Math.round((record.sleep - average) * 10) / 10;

  async function showReport(event) {
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
    const next = { steps, goal, sleep: sleepHours };
    if (authenticated) {
      setBusy(true);
      try {
        const saved = await saveDailyReport({ record: next });
        setRecord(saved.record);
        setHistory(saved.records || []);
        setReportDate(saved.date || "");
      } catch {
        setError("오늘 기록을 저장하지 못했습니다. 다시 시도해 주세요.");
        return;
      } finally {
        setBusy(false);
      }
    } else {
      setRecord(next);
    }
    setError("");
    setEditing(false);
  }

  return (
    <Card icon="📋" title="오늘의 건강 리포트" subtitle="Apple 건강에서 확인 · 직접 입력">
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
        {authenticated && record?.sleep != null && (
          <p className="ui-note">{difference === null
            ? "수면 기록이 더 쌓이면 평소와 비교할 수 있어요."
            : `최근 7일 평균 ${number.format(average)}시간 (${recent.length}일 기록) · ${difference === 0
                ? "오늘 수면은 최근 평균과 같아요."
                : `오늘은 ${number.format(Math.abs(difference))}시간 ${difference < 0 ? "적어요." : "많아요."}`}`}</p>
        )}
        {!record && !editing && <p className="ui-note">오늘 기록을 입력해 주세요.</p>}
        <div className="today-report__actions">
          <button type="button" className="btn btn--primary" aria-expanded={editing}
            onClick={() => { setEditing(!editing); setError(""); }}>
            {editing ? "입력 닫기" : record ? "오늘 기록 수정" : "오늘 기록 입력"}
          </button>
          {authenticated && onPersonalTrends && (
            <button type="button" className="btn" onClick={onPersonalTrends}>내 기록 추이 보기</button>
          )}
          <button type="button" className="btn" aria-expanded={preview} onClick={() => setPreview(!preview)}>
            {preview ? "이메일 설정 닫기" : "이메일 리포트 설정"}
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
            <button type="submit" className="btn btn--primary" disabled={busy}>리포트 보기</button>
          </form>
        )}
        {preview && (
          <form className="today-report__section" aria-label="이메일 리포트 설정" onSubmit={saveSchedule}>
            <div className="today-report__schedule">
              <label className="today-report__toggle">
                <input type="checkbox" role="switch" checked={enabled} disabled={!connected || busy}
                  onChange={(event) => setEnabled(event.target.checked)} />
                <span>매일 이메일로 받기</span>
              </label>
              <label className="today-report__time">
                <span>발송 시간 <small>한국 시간</small></span>
                <input className="form__input" type="time" value={time} required
                  disabled={!connected || !enabled || busy} onChange={(event) => setTime(event.target.value)} />
              </label>
              <button type="submit" className="btn btn--primary" disabled={!connected || busy}>
                {busy ? "저장 중…" : "저장"}
              </button>
            </div>
            <p className="ui-note">{connected
              ? "예약 시각에 오늘 기록이 있으면 계정의 인증된 이메일로 발송합니다."
              : "이메일 예약은 인증된 발표 환경에서 사용할 수 있습니다."}</p>
            {notice && <p className="ui-note" role="status">{notice}</p>}
            <p className="today-report__preview ui-note">{record
              ? number.format(record.steps) + "걸음 · 목표 " + number.format(percentage) + "% · 수면 " + sleep
              : "오늘 기록을 입력하면 이메일 내용을 미리 볼 수 있습니다."}</p>
          </form>
        )}
      </div>
    </Card>
  );
}
