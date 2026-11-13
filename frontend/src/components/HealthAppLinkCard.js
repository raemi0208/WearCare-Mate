import React, { useEffect, useRef, useState } from "react";
import Card from "./ui/Card";
import Badge from "./ui/Badge";
import HealthLinkDetails from "./HealthLinkDetails";
import {
  HEALTH_PROVIDERS,
  MAIN_PROVIDERS,
  OTHER_PROVIDERS,
  LINK_STEPS,
  loadHealthLinks,
  addHealthLink,
  removeHealthLink,
  setMainProvider,
  touchLastSync,
} from "../services/healthLinkStorage";
import { BLUETOOTH_DEVICES, MAIN_APP_DATASETS } from "../data/healthAppMock";

// 연동 진행 단계당 시간(mock): 4단계 × 500ms = 약 2초
const STEP_MS = 500;
// 다시 동기화 로딩 시간(mock)
const SYNC_MS = 1000;

const shortName = (provider) => provider.name.split(" (")[0];
const formatTime = (iso) => new Date(iso).toLocaleString("ko-KR");

// 헬스 앱 연동 카드: 여러 앱 연동 → 메인 앱 지정 → 앱별 블루투스 기기 확인
export default function HealthAppLinkCard({ timeseries }) {
  const [state, setState] = useState(loadHealthLinks);
  const [open, setOpen] = useState(false);
  const [linkingProvider, setLinkingProvider] = useState(null);
  const [stepIndex, setStepIndex] = useState(0);
  // 앱 선택 모달에서 '기타(Other)' 목록을 보고 있는지 여부
  const [showOther, setShowOther] = useState(false);
  // 해제 확인 대상 앱 / 동기화 중인 앱 / 블루투스 기기 목록을 펼친 앱
  const [confirmProvider, setConfirmProvider] = useState(null);
  const [syncing, setSyncing] = useState({});
  const [expanded, setExpanded] = useState({});
  // 모든 타이머를 ref 에 보관해 언마운트 시 정리한다.
  const linkTimers = useRef([]);
  const syncTimers = useRef({});

  const { links, mainProvider } = state;

  const clearLinkTimers = () => {
    linkTimers.current.forEach(clearTimeout);
    linkTimers.current = [];
  };

  useEffect(
    () => () => {
      clearLinkTimers();
      Object.values(syncTimers.current).forEach(clearTimeout);
    },
    []
  );

  const openModal = () => {
    setShowOther(false);
    setOpen(true);
  };

  const closeModal = () => {
    if (linkingProvider) return; // 연동 중에는 닫지 않는다
    setOpen(false);
  };

  // ESC 로 모달/확인 창 닫기
  useEffect(() => {
    if (!open && !confirmProvider) return undefined;
    const onKey = (e) => {
      if (e.key !== "Escape") return;
      if (confirmProvider) setConfirmProvider(null);
      else if (!linkingProvider) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, confirmProvider, linkingProvider]);

  // 4단계(앱 확인 → 권한 요청 → 데이터 불러오기 → 완료) 순차 진행 후 연동 저장
  const startLink = (providerId) => {
    clearLinkTimers();
    setLinkingProvider(providerId);
    setStepIndex(0);
    for (let i = 1; i < LINK_STEPS.length; i += 1) {
      linkTimers.current.push(setTimeout(() => setStepIndex(i), STEP_MS * i));
    }
    linkTimers.current.push(
      setTimeout(() => {
        setState(addHealthLink(providerId));
        setLinkingProvider(null);
        setOpen(false);
      }, STEP_MS * LINK_STEPS.length)
    );
  };

  const handleSync = (providerId) => {
    if (syncing[providerId]) return;
    setSyncing((prev) => ({ ...prev, [providerId]: true }));
    syncTimers.current[providerId] = setTimeout(() => {
      setState(touchLastSync(providerId));
      setSyncing((prev) => ({ ...prev, [providerId]: false }));
    }, SYNC_MS);
  };

  const handleConfirmUnlink = () => {
    const target = confirmProvider;
    clearTimeout(syncTimers.current[target]);
    setSyncing((prev) => ({ ...prev, [target]: false }));
    setState(removeHealthLink(target));
    setConfirmProvider(null);
  };

  const handleSetMain = (providerId) => setState(setMainProvider(providerId));

  const toggleExpanded = (providerId) =>
    setExpanded((prev) => ({ ...prev, [providerId]: !prev[providerId] }));

  const linking = linkingProvider ? HEALTH_PROVIDERS[linkingProvider] : null;
  const confirming = confirmProvider ? HEALTH_PROVIDERS[confirmProvider] : null;
  const linkedIds = new Set(links.map((l) => l.provider));
  const mainInfo = mainProvider ? HEALTH_PROVIDERS[mainProvider] : null;
  const mainHasSample = Boolean(mainProvider && MAIN_APP_DATASETS[mainProvider]);

  return (
    <>
      <Card
        title="기기 연동 미리보기"
        subtitle="애플 건강과 삼성 헬스 연결 과정을 체험할 수 있어요. 실제 건강 데이터는 불러오지 않습니다."
        action={
          links.length > 0 ? <Badge variant="normal">{links.length}개 연동됨</Badge> : <Badge variant="ghost">미연동</Badge>
        }
      >
        {links.length > 0 ? (
          <>
            <p className="ui-note health-link-main-note">
              {mainInfo && (
                <>
                  현재 메인 앱은 <strong>{shortName(mainInfo)}</strong>입니다.{" "}
                </>
              )}
              대시보드·일일 리포트·AI 가이드의 수치는 메인 앱 기준으로 표시됩니다.
              {mainHasSample
                ? " 삼성 헬스·애플 건강은 앱마다 다른 예시 데이터를 보여 줍니다."
                : " 기타 앱이 메인이면 기존 데이터를 그대로 사용합니다."}
            </p>
            <div className="health-link-list" role="group" aria-label="연동된 건강 앱 목록">
              {links.map((link) => {
                const provider = HEALTH_PROVIDERS[link.provider];
                const isMain = link.provider === mainProvider;
                const devices = BLUETOOTH_DEVICES[link.provider] || [];
                const isOpen = Boolean(expanded[link.provider]);
                const isSyncing = Boolean(syncing[link.provider]);
                const name = shortName(provider);
                return (
                  <div key={link.provider} className={`health-link-row${isMain ? " is-main" : ""}`}>
                    <div className="health-link__status">
                      <span className="device-item__icon" aria-hidden="true">{provider.icon}</span>
                      <div className="health-link__info">
                        <div className="device-item__name">
                          {provider.name}
                          {isMain && <Badge variant="normal">메인</Badge>}
                          <Badge variant={isSyncing ? "warn" : "normal"}>{isSyncing ? "동기화 중" : "연동됨"}</Badge>
                        </div>
                        <div className="device-item__meta">연동 시각 {formatTime(link.linkedAt)}</div>
                        <div className="device-item__meta">마지막 동기화 {formatTime(link.lastSyncAt)}</div>
                      </div>
                    </div>
                    <div className="health-link-row__actions">
                      {!isMain && (
                        <button
                          type="button"
                          className="btn"
                          aria-label={`${name}을(를) 메인 앱으로 설정`}
                          onClick={() => handleSetMain(link.provider)}
                        >
                          메인으로 설정
                        </button>
                      )}
                      <button
                        type="button"
                        className="btn"
                        aria-label={`${name} 다시 동기화`}
                        disabled={isSyncing}
                        onClick={() => handleSync(link.provider)}
                      >
                        {isSyncing ? "동기화 중…" : "다시 동기화"}
                      </button>
                      <button
                        type="button"
                        className="btn"
                        aria-label={`${name} 연동 해제`}
                        onClick={() => setConfirmProvider(link.provider)}
                      >
                        연동 해제
                      </button>
                      <button
                        type="button"
                        className="btn"
                        aria-expanded={isOpen}
                        aria-controls={`bt-devices-${link.provider}`}
                        aria-label={`${name} 블루투스 기기 ${isOpen ? "접기" : "보기"}`}
                        onClick={() => toggleExpanded(link.provider)}
                      >
                        {isOpen ? "기기 접기" : "블루투스 기기"}
                      </button>
                    </div>
                    {isOpen && (
                      <div id={`bt-devices-${link.provider}`} className="bt-device-panel">
                        <h4 className="bt-device-panel__title">블루투스로 연결된 기기</h4>
                        {devices.length === 0 ? (
                          <p className="ui-note" style={{ margin: 0 }}>연결된 기기 정보가 없습니다.</p>
                        ) : (
                          <ul className="bt-device-list">
                            {devices.map((d) => (
                              <li key={d.id} className="bt-device">
                                <span className="bt-device__icon" aria-hidden="true">{d.icon}</span>
                                <span className="bt-device__info">
                                  <span className="bt-device__name">{d.name}</span>
                                  <span className="bt-device__meta">{d.type} · 데이터: {d.metrics.join(", ")}</span>
                                </span>
                                <Badge variant={d.status === "connected" ? "normal" : "ghost"}>
                                  {d.status === "connected" ? "연결됨" : "연결 끊김"}
                                </Badge>
                              </li>
                            ))}
                          </ul>
                        )}
                        <p className="ui-note" style={{ margin: "8px 0 0" }}>예시 기기 목록이며 실제 블루투스 연결 상태가 아닙니다.</p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="health-link-add">
              <button type="button" className="btn btn--primary" onClick={openModal}>
                다른 앱 추가 연동
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="ui-note">
              웨어러블을 직접 연결하지 않고, 사용 중인 휴대폰의 건강 앱과 연동해 걸음수와 수면 기록을 가져오는 방식입니다.
            </p>
            <ul className="health-link-notes">
              <li>연동하면 대시보드에서 걸음수·수면·심박 추이를 볼 수 있어요.</li>
              <li>매일 정해진 시간에 일일 리포트 알림을 받을 수 있어요.</li>
              <li>AI 건강 가이드에서 어제와 비교한 변화를 확인할 수 있어요.</li>
            </ul>
            <p className="ui-note">앱 선택 → 권한 요청 → 데이터 불러오기 → 완료 순서로 진행됩니다. 여러 앱을 연동하고 메인 앱을 고를 수 있어요.</p>
            <button type="button" className="btn btn--primary" onClick={openModal}>
              건강 앱 연동하기
            </button>
          </>
        )}
        <details className="health-link-more">
          <summary>가져오는 데이터 · 권한 · 개인정보 안내</summary>
          <HealthLinkDetails timeseries={timeseries} />
        </details>
        <p className="ui-note" style={{ marginTop: 12, marginBottom: 0 }}>
          시연용 연동이며 실제 건강 데이터를 가져오지 않습니다.
        </p>
      </Card>

      {open && (
        <div className="modal-backdrop" onClick={closeModal}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="health-link-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="health-link-title" className="modal__title">
              {linking ? `${linking.name} 연동` : showOther ? "기타 웨어러블 앱 선택" : "연동할 건강 앱 선택"}
            </h3>
            {linking ? (
              <div className="modal__loading" aria-live="polite">
                <span className="spinner" aria-hidden="true" />
                <p>
                  {shortName(linking)}과(와) 자동 연동 중…
                </p>
                <ol className="health-link-steps">
                  {LINK_STEPS.map((label, i) => (
                    <li
                      key={label}
                      className={i < stepIndex ? "is-done" : i === stepIndex ? "is-current" : ""}
                      aria-current={i === stepIndex ? "step" : undefined}
                    >
                      {i + 1}단계 · {label}
                      {i < stepIndex ? " ✓" : ""}
                    </li>
                  ))}
                </ol>
              </div>
            ) : (
              <>
                {showOther && (
                  <p className="ui-note">사용 중인 웨어러블 앱을 선택하세요.</p>
                )}
                <div className="provider-grid">
                  {Object.values(showOther ? OTHER_PROVIDERS : MAIN_PROVIDERS).map((p) => {
                    const already = linkedIds.has(p.id);
                    return (
                      <button
                        key={p.id}
                        type="button"
                        className="provider-option"
                        disabled={already}
                        onClick={() => startLink(p.id)}
                      >
                        <span className="provider-option__icon" aria-hidden="true">{p.icon}</span>
                        <span className="provider-option__name">{shortName(p)}</span>
                        <span className="provider-option__desc">{already ? "연동됨" : p.device}</span>
                      </button>
                    );
                  })}
                  {!showOther && (
                    <button
                      type="button"
                      className="provider-option provider-option--wide"
                      onClick={() => setShowOther(true)}
                    >
                      <span className="provider-option__icon" aria-hidden="true">➕</span>
                      <span className="provider-option__name">기타 (Other)</span>
                      <span className="provider-option__desc">Fitbit, Garmin, 샤오미 등 다른 웨어러블 앱</span>
                    </button>
                  )}
                </div>
                <div className="form__actions" style={{ justifyContent: "center" }}>
                  {showOther && (
                    <button type="button" className="btn" onClick={() => setShowOther(false)}>
                      뒤로
                    </button>
                  )}
                  <button type="button" className="btn" onClick={closeModal}>
                    취소
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {confirming && (
        <div className="modal-backdrop" onClick={() => setConfirmProvider(null)}>
          <div
            className="modal confirm-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            aria-describedby="confirm-desc"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="confirm-title" className="modal__title">연동을 해제할까요?</h3>
            <p id="confirm-desc" className="confirm-dialog__desc">
              {shortName(confirming)} 연동을 해제합니다.
              {confirmProvider === mainProvider && links.length > 1
                ? " 메인 앱이므로 남은 첫 번째 앱이 메인으로 바뀝니다."
                : ""}
              {confirmProvider === mainProvider && links.length <= 1
                ? " 연동된 앱이 없어 기존 데이터 표시로 돌아갑니다."
                : ""}
            </p>
            <div className="form__actions" style={{ justifyContent: "center" }}>
              <button type="button" className="btn" onClick={() => setConfirmProvider(null)}>
                취소
              </button>
              <button type="button" className="btn btn--primary" onClick={handleConfirmUnlink}>
                해제
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
