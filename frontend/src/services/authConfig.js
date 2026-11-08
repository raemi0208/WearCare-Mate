// WearCare Mate - 인증 설정 (B안: Cognito + PKCE)
//
// 모든 값은 빌드 타임 환경변수(REACT_APP_*)에서 읽습니다. 공개 가능한 값만 사용합니다.
// (Cognito 도메인, 공개 앱 클라이언트 ID, 리전, 스코프 등은 공개되어도 안전합니다.)
// 클라이언트 시크릿/비밀번호/AWS 자격 증명은 절대 넣지 않습니다. (PKCE 공개 클라이언트)
//
// 인증 활성 조건: Cognito 도메인 + 클라이언트 ID + API_BASE 가 모두 있을 때.
// 하나라도 비어 있으면 인증 비활성(A안 로컬/목 모드)으로 동작합니다.

function clean(value) {
  return (value || "").trim();
}

function stripTrailingSlash(value) {
  return clean(value).replace(/\/+$/, "");
}

// 콜백/로그아웃 URL 은 Cognito 에 등록한 값과 "정확히 일치"해야 한다.
// 01 스크립트가 trailing slash 를 붙여 등록(.../)하므로 여기서도 slash 를 보존한다.
// stripTrailingSlash 를 쓰면 slash 가 사라져 Cognito 가 redirect_uri 불일치로 거부한다.
function defaultOriginWithSlash() {
  return typeof window !== "undefined" ? window.location.origin + "/" : "";
}

export const authConfig = {
  // 예: https://wearcare-mate-demo.auth.ap-northeast-2.amazoncognito.com
  domain: stripTrailingSlash(process.env.REACT_APP_COGNITO_DOMAIN),
  // 공개 SPA 앱 클라이언트 ID (시크릿 없음)
  clientId: clean(process.env.REACT_APP_COGNITO_CLIENT_ID),
  // 콜백/로그아웃 리다이렉트. 환경변수가 있으면 slash 를 보존한 채 그대로, 없으면 현재 origin + "/".
  redirectUri:
    clean(process.env.REACT_APP_COGNITO_REDIRECT_URI) || defaultOriginWithSlash(),
  logoutUri:
    clean(process.env.REACT_APP_COGNITO_LOGOUT_URI) || defaultOriginWithSlash(),
  // 데모 조회용 커스텀 스코프 + openid (id 토큰 확보). 공백 구분.
  scope:
    clean(process.env.REACT_APP_COGNITO_SCOPE) ||
    "openid wearcare-demo/read",
};

// API 기본 주소 (새 인증 API). 비어 있으면 목 모드.
export const apiBase = stripTrailingSlash(process.env.REACT_APP_API_BASE);

// 인증을 사용할지 여부. Cognito 설정과 API_BASE 가 모두 있어야 활성.
export function isAuthEnabled() {
  return Boolean(authConfig.domain && authConfig.clientId && apiBase);
}

// 로그인 진단 모드. 명시적으로 REACT_APP_AUTH_DIAG=1 일 때만 켜진다.
// 켜지면 로그인 준비와 이동을 분리해, "Cognito 로그인 계속" 버튼을 눌러야 이동한다.
// (민감정보 없는 origin/저장 성공 여부만 화면에 표시하기 위한 모드)
export function isAuthDiagEnabled() {
  return clean(process.env.REACT_APP_AUTH_DIAG) === "1";
}
