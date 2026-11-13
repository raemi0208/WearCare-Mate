import React, { useMemo, useState } from "react";
import Card from "./ui/Card";
import Badge from "./ui/Badge";
import {
  buildDailyReport,
  formatSleep,
  formatScheduleSummary,
  todayString,
  DAY_LABELS,
} from "../services/dailyReport";

// 요일 버튼 표시 순서(월~일)
const DAY_ORDER = [1, 2, 3, 4, 5, 6, 0];

// 포함 항목 체크박스 정의
const INCLUDE_ITEMS = [
  { id: "steps", label: "걸음수" },
  { id: "sleep", label: "수면" },
  { id: "heartRate", label: "안정 시 심박" },
];

// 시스템 알림 권한 상태 → 배지 문구/색
function permissionInfo(permission) {
  switch (permission) {
    case "granted":
      return { label: "알림 허용됨", variant: "normal" };
    case "denied":
      return { label: "알림 차단됨", variant: "danger" };
    case "default":
      return { label: "아직 묻지 않음", variant: "ghost" };
    default:
      return { label: "알림 미지원", variant: "ghost" };
  }
}

const readPermission = () => (typeof Notification === "undefined" ? "unsupported" : Notification.permission);

// 일일 리포트 알림 설정 카드: ON/OFF, 수신 시간·요일, 포함 항목, 목표 걸음수, 상세 미리보기
export default function DailyReportSettings({ settings, onChange, timeseries, onPreview, sourceLabel }) {
  const [saved, setSaved] = useState(false);
  const [notifyNote, setNotifyNote] = useState("");
  const [permission, setPermission] = useState(readPermission);
  const days = Array.isArray(settings.days) ? settings.days : [0, 1, 2, 3, 4, 5, 6];
  const include = settings.include || { steps: true, sleep: true, heartRate: false };
  const report = useMemo(
    () => buildDailyReport(timeseries, settings.stepGoal, { sourceLabel }),
    [timeseries, settings.stepGoal, sourceLabel]
  );

  const apply = (patch) => {
    onChange({ ...settings, ...patch });
    setSaved(true);
  };

  const handleToggle = (e) => {
    const enabled = e.target.checked;
    apply({ enabled });
    if (!enabled) {
      setNotifyNote("");
      return;
    }
    if (typeof Notification === "undefined") {
      setNotifyNote("이 브라우저는 시스템 알림을 지원하지 않아 앱 안 알림으로만 표시됩니다.");
    } else if (Notification.permission === "default") {
      Notification.requestPermission().then((perm) => {
        setPermission(perm);
        if (perm !== "granted") setNotifyNote("시스템 알림이 허용되지 않아 앱 안 알림으로만 표시됩니다.");
      });
    } else if (Notification.permission === "denied") {
      setNotifyNote("시스템 알림이 차단되어 있어 앱 안 알림으로만 표시됩니다.");
    }
  };

  const handleGoal = (e) => {
    const n = Number(e.target.value);
    if (n > 0) apply({ stepGoal: n });
  };

  // 요일 선택: 마지막 하나는 해제할 수 없다
  const toggleDay = (day) => {
    const next = days.includes(day) ? days.filter((d) => d !== day) : [...days, day];
    if (next.length === 0) return;
    apply({ days: next.sort((a, b) => a - b) });
  };

  // 포함 항목: 마지막 하나는 해제할 수 없다(빈 리포트 방지)
  const toggleInclude = (id) => {
    const next = { ...include, [id]: !include[id] };
    if (!next.steps && !next.sleep && !next.heartRate) return;
    apply({ include: next });
  };

  const percentBar = Math.min(Math.max(report.percent, 0), 100);
  const perm = permissionInfo(permission);
  const today = new Date();
  const todayLabel = `${todayString(today)} (${DAY_LABELS[today.getDay()]})`;

  return (
    <Card title="일일 리포트 알림" subtitle="매일 정해진 시간에 걸음수와 수면 리포트를 받습니다">
      <p className="ui-note">앱이 열려 있을 때 알림이 표시됩니다. 서버 푸시는 사용하지 않습니다.</p>
      <div className="toggle-list">
        <label className="toggle-item">
          <span>
            <span className="toggle-item__title">리포트 알림</span>
            <span className="toggle-item__desc">설정한 시간에 오늘의 걸음수·수면 리포트 표시</span>
          </span>
          <input
            type="checkbox"
            role="switch"
            checked={settings.enabled}
            onChange={handleToggle}
          />
        </label>
      </div>
      <div className="form">
        <div className="form__row">
          <label className="form__field">
            <span className="form__label">수신 시간</span>
            <input
              className="form__input"
              type="time"
              value={settings.time}
              disabled={!settings.enabled}
              onChange={(e) => e.target.value && apply({ time: e.target.value })}
            />
          </label>
          <label className="form__field">
            <span className="form__label">목표 걸음수</span>
            <input
              className="form__input"
              type="number"
              min="1000"
              step="500"
              defaultValue={settings.stepGoal}
              onChange={handleGoal}
            />
          </label>
        </div>

        <div className="form__field">
          <span className="form__label" id="report-days-label">수신 요일</span>
          <div className="report-days" role="group" aria-labelledby="report-days-label">
            {DAY_ORDER.map((d) => (
              <button
                key={d}
                type="button"
                className={`report-day${days.includes(d) ? " is-on" : ""}`}
                aria-pressed={days.includes(d)}
                aria-label={`${DAY_LABELS[d]}요일`}
                disabled={!settings.enabled}
                onClick={() => toggleDay(d)}
              >
                {DAY_LABELS[d]}
              </button>
            ))}
          </div>
        </div>

        <fieldset className="report-include">
          <legend className="form__label">리포트에 포함할 항목</legend>
          {INCLUDE_ITEMS.map((item) => (
            <label key={item.id} className="report-include__item">
              <input
                type="checkbox"
                checked={Boolean(include[item.id])}
                onChange={() => toggleInclude(item.id)}
              />
              <span>{item.label}</span>
            </label>
          ))}
          <p className="ui-note" style={{ margin: 0 }}>항목은 최소 1개 선택되어 있어야 해요.</p>
        </fieldset>

        <p className="report-schedule" role="status">{formatScheduleSummary(settings)}</p>

        <div className="report-permission">
          <span>시스템 알림 권한</span>
          <Badge variant={perm.variant}>{perm.label}</Badge>
        </div>
        {permission === "denied" && (
          <p className="ui-note" role="status">
            브라우저에서 알림이 차단되어 있어요. 주소창 왼쪽 자물쇠 → 알림 허용으로 바꾼 뒤 새로고침하면 시스템 알림도 받을 수 있어요. 앱 안 알림은 권한과 관계없이 표시됩니다.
          </p>
        )}
        {notifyNote && <p className="ui-note" role="status">{notifyNote}</p>}

        <div className="report-preview" aria-label="리포트 미리보기">
          <div className="report-preview__head">
            <strong>오늘의 건강 리포트</strong>
            <span className="report-preview__date">{todayLabel}</span>
          </div>
          {report.sourceLabel && <div className="report-preview__line">기준 앱: {report.sourceLabel}</div>}
          {include.steps && (
            <>
              <div className="report-preview__line">
                걸음수 {report.steps.toLocaleString("ko-KR")} / {report.goal.toLocaleString("ko-KR")}걸음 (달성률 {report.percent}%)
              </div>
              <div
                className="report-progress"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={percentBar}
                aria-label="목표 걸음수 달성률"
              >
                <div className="report-progress__bar" style={{ width: `${percentBar}%` }} />
              </div>
              <div className="report-preview__line">
                {report.remaining > 0
                  ? `남은 걸음 ${report.remaining.toLocaleString("ko-KR")}걸음`
                  : "목표 걸음을 달성했어요"}
                {report.stepsDelta && ` · 어제 대비 ${report.stepsDelta.text}`}
              </div>
            </>
          )}
          {include.sleep && (
            <div className="report-preview__line">
              수면시간 {formatSleep(report.sleepHours)} · 수면 평가 {report.sleepVerdict}
              {report.sleepDelta && ` · 어제 대비 ${report.sleepDelta.text}`}
            </div>
          )}
          {include.heartRate && (
            <div className="report-preview__line">
              안정 시 심박 {report.heartRate != null ? `${report.heartRate}bpm` : "기록 없음"}
            </div>
          )}
          <div className="report-preview__comment">{report.comment}</div>
          {report.isSample && <p className="ui-note" style={{ margin: 0 }}>예시 데이터입니다.</p>}
        </div>

        <div className="form__actions">
          <button type="button" className="btn" onClick={onPreview}>
            지금 리포트 보기
          </button>
          {saved && <span className="form__saved">✓ 저장되었습니다</span>}
        </div>
      </div>
    </Card>
  );
}
