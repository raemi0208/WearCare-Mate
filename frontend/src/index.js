import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import { isAuthEnabled } from './services/authConfig';
import {
  handleRedirectCallback,
  isAuthenticated,
  login,
  getLastAuthDiagnostics,
} from './services/cognitoAuth';

// 앱을 실제로 렌더링
function renderApp() {
  const root = ReactDOM.createRoot(document.getElementById('root'));
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

// 로그인 진단 요약을 사람이 읽을 수 있는 한 줄로 변환한다.
// 민감정보(state/verifier/code/token)는 포함하지 않고 존재 여부·일치 여부·origin·횟수만 표시.
function formatDiagnostics(d) {
  if (!d) return '';
  const yn = (v) => (v ? 'Y' : 'N');
  // originMatch 는 3상태: true / false / null(시작 주소 확인 불가)
  const originMatchLabel =
    d.originMatches === null ? '시작 주소 확인 불가' : yn(d.originMatches);
  const lines = [
    `savedState=${yn(d.savedStatePresent)}`,
    `returnedState=${yn(d.returnedStatePresent)}`,
    `stateMatch=${yn(d.stateMatches)}`,
    `verifier=${yn(d.verifierPresent)}`,
    `originMatch=${originMatchLabel}`,
    `login=${d.loginCount}`,
    `callback=${d.callbackCount}`,
  ];
  // origin 은 쿼리/경로 없이 origin 만.
  // 시작/콜백이 "다를 때"(false)만 두 origin 을 함께 노출. unknown(null)이면 콜백 origin 만 표시.
  let originLine = '';
  if (d.originMatches === false) {
    originLine = `start=${d.startOrigin || '(none)'} / callback=${d.callbackOrigin}`;
  } else if (d.originMatches === null) {
    originLine = `callback=${d.callbackOrigin}`;
  }
  return [lines.join(' · '), originLine].filter(Boolean).join('\n');
}

// 간단한 전체 화면 메시지 (인증 처리 중/실패 시)
function renderMessage(title, detail, diagnostics) {
  const el = document.getElementById('root');
  if (!el) return;
  el.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.style.cssText =
    'min-height:100vh;display:flex;align-items:center;justify-content:center;' +
    'font-family:sans-serif;color:#111;text-align:center;padding:24px;';
  const inner = document.createElement('div');
  const h = document.createElement('p');
  h.textContent = title;
  h.style.cssText = 'font-size:16px;font-weight:700;margin:0 0 8px;';
  const p = document.createElement('p');
  p.textContent = detail || '';
  p.style.cssText = 'font-size:13px;color:#666;margin:0;';
  inner.appendChild(h);
  if (detail) inner.appendChild(p);
  const diagText = formatDiagnostics(diagnostics);
  if (diagText) {
    const pre = document.createElement('pre');
    pre.textContent = diagText;
    pre.style.cssText =
      'font-size:12px;color:#888;margin:16px auto 0;max-width:520px;' +
      'white-space:pre-wrap;word-break:break-word;text-align:left;' +
      'background:#f5f5f5;border:1px solid #e0e0e0;border-radius:6px;padding:10px 12px;';
    inner.appendChild(pre);
  }
  wrap.appendChild(inner);
  el.appendChild(wrap);
}

// ---------- 목/로컬 모드 (A안): 기존 sessionStorage 로그인 가드 ----------
function mockLoginGuard() {
  let loggedIn = false;
  try {
    loggedIn = sessionStorage.getItem('wearcare.loggedIn') === '1';
  } catch (e) {
    loggedIn = false;
  }
  if (!loggedIn) {
    const base = process.env.PUBLIC_URL || '';
    window.location.replace(`${base}/login.html`);
    return;
  }
  renderApp();
}

// ---------- 인증 모드 (B안): Cognito Authorization Code + PKCE ----------
async function cognitoGuard() {
  try {
    // 콜백(redirect_uri?code=...)이면 토큰으로 교환
    const handled = await handleRedirectCallback();
    if (handled || isAuthenticated()) {
      renderApp();
      return;
    }
    // 인증되지 않았으면 Cognito 관리형 로그인으로 보낸다
    renderMessage('로그인 페이지로 이동 중…', '잠시만 기다려 주세요.');
    await login();
  } catch (err) {
    const diagnostics = (err && err.diagnostics) || getLastAuthDiagnostics();
    renderMessage(
      '로그인이 필요합니다.',
      (err && err.message) || '로그인에 실패했습니다. 다시 시도해 주세요.',
      diagnostics
    );
  }
}

if (isAuthEnabled()) {
  cognitoGuard();
} else {
  mockLoginGuard();
}

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
