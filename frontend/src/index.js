import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';

// 로그인 가드: 로그인 플래그가 없으면 대시보드를 렌더하지 않고 로그인 페이지로 보냅니다.
// (login.html에서 로그인 버튼을 누르면 sessionStorage에 플래그를 세우고 "/"로 돌아옵니다.)
function isLoggedIn() {
  try {
    return sessionStorage.getItem('wearcare.loggedIn') === '1';
  } catch (e) {
    return false;
  }
}

if (!isLoggedIn()) {
  // PUBLIC_URL을 기준으로 로그인 페이지 경로를 구성해 어떤 호스팅 환경에서도 동작하도록 함
  const base = process.env.PUBLIC_URL || '';
  window.location.replace(`${base}/login.html`);
} else {
  const root = ReactDOM.createRoot(document.getElementById('root'));
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
