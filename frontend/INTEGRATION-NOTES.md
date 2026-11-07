# 프론트엔드 ↔ 백엔드 API 연동 메모

PR #8 (`frontend-api-integration` → `frontend`)의 변경 범위와 연동 시 주의 사항을 정리합니다.
이 문서는 로컬 검증 결과를 기록한 것이며, **공개 API와 프론트엔드의 실제 통합 검증 완료를 뜻하지 않습니다.**

## 변경 사항 (PR #8)

- 웹 업로드로 `frontend/` 바로 아래에 잘못 들어간 중복 소스 28개를 제거하고,
  수정본을 `frontend/src/`의 원래 하위 경로(`components/`, `components/ui/`, `pages/`, `data/`, `services/`)에 반영.
- `env.example` → `.env.example` 이름 수정.
- 실제 백엔드 응답 대응
  - 정상 판정, 데이터 부족, 가이드 생성 실패, 실제 생성, 예시 가이드의 배지 구분
  - 가이드 기준일 및 출력 규칙 검사 경고 표시
  - 빈 수면/심박 배열에서 Infinity/-Infinity 또는 0으로 잘못 표시하지 않음
  - `delta=null`이면 "비교 데이터 없음"으로 표시
  - 기기, 알림, 가이드 이력이 비어 있으면 안내 문구 표시
  - 연결되지 않은 실시간 동기화·SageMaker 표시를 기록 조회/활동량 기준선으로 정정
  - 대시보드에 분석 기준일과 날짜별 판정 범위 표시
  - 가이드 재조회 실패 시 기존 대시보드를 유지하고 오류와 재시도 버튼 표시
  - API 기본 주소 끝의 슬래시 제거

## API 연결 설정

- 주소는 `src/services/api.js`가 `REACT_APP_API_BASE`에서 읽습니다.
  - 비어 있으면 API를 호출하지 않고 `src/data/mockData.js`의 예시 데이터로 동작합니다.
  - 값이 있으면 `GET {REACT_APP_API_BASE}/dashboard`, `GET {REACT_APP_API_BASE}/ai-guide`를 호출합니다.
- 사용 방법: `.env.example`을 **`frontend/.env.local`**로 복사한 뒤 `npm start`를 다시 시작하거나 다시 빌드합니다.
  (CRA는 빌드 시점에 값을 넣으므로 실행 중에 바꿔도 반영되지 않습니다.)
- ⚠️ 이 브랜치의 루트 `.gitignore`는 CRA 기본값이라 **`.env`는 Git에서 제외되지 않습니다.**
  제외되는 것은 `.env.local`, `.env.development.local`, `.env.test.local`, `.env.production.local`입니다.
  그래서 로컬 설정은 `.env.local`에 둡니다. (`git check-ignore -v frontend/.env.local`로 확인 가능)
  자격 증명은 어떤 파일에도 넣지 않습니다.
- (정정) 이전 버전의 이 문서와 `.env.example`은 "`.env`가 루트 `.gitignore`로 제외된다"고 안내했지만
  사실이 아니었습니다. 백엔드 브랜치의 `.gitignore`를 잘못 참고한 내용입니다.
- 기존 공개 API(`https://j3cwx5vmwj.execute-api.ap-northeast-2.amazonaws.com`)는 여전히 **예시 데이터 모드**이며 그대로 유지됩니다.
- **(업데이트) HTTPS 인증 시연용 실데이터 API 가 별도로 배포 완료**되었습니다.
  - 인증 API: `https://tirb2qdtj8.execute-api.ap-northeast-2.amazonaws.com` (JWT 오소라이저 + 스코프 `wearcare-demo/read`)
  - 연결 Lambda `wearcare-mate-athena-test` 에 최신 집계 ZIP·권한·환경변수 반영 완료.
  - 콘솔 `/dashboard` 응답 200, 걸음 수 12,369, 데이터셋 요약 3개 모두 `status=ok` 확인.
  - 이 API 는 Cognito 로그인으로 얻은 액세스 토큰이 있어야 200 을 반환합니다(토큰 없음 401 / 스코프 없음 403).
  - 상세 배포 구성·환경변수는 `WearCare-Mate-artifacts/b-cognito-deploy/README.md` 참고.

## 로그인 화면 (frontend 브랜치 `b14feb9`, PR #8 범위 밖)

`frontend` 브랜치에 추가된 `public/login.html`을 읽고 확인한 내용입니다.

- **시연용 화면이며 인증 기능이 아닙니다.** 아이디·비밀번호를 확인하지 않고, 로그인 버튼은
  `window.location.href = "/"`로 React 대시보드 루트로 이동만 합니다. 대시보드는 로그인 없이도 열립니다.
- 스타일은 `App.css`/`index.css`를 불러오지 않고 파일 안 `<style>`에 디자인 값을 복사해 둡니다.
  그래서 `App.css` 변경이 로그인 화면에 반영되지 않습니다. 디자인 값을 바꿀 때 두 곳을 함께 맞춰야 합니다.
- 브라우저 저장소에 **아무것도 저장하지 않습니다.** 비밀번호도 저장하지 않습니다.
  대시보드가 쓰는 localStorage 키는 설정 화면의 프로필 `wearcare.profile` 하나이며, 로그인 화면과 충돌하지 않습니다.
  프로필 이름은 API 응답의 `user`보다 우선 표시됩니다 (`src/services/api.js`).
- PR #8 브랜치에는 이 파일이 없지만, `frontend`와 PR #8은 서로 다른 파일만 바꾸므로 충돌 없이 합쳐집니다
  (`git merge-tree`로 확인).
- 권장 후속 작업 (프론트엔드 담당): 안내 문구 "계정 정보를 입력해 대시보드에 접속하세요"를
  "시연용 화면입니다. 실제 인증은 아직 구현되지 않았습니다." 같은 문구로 바꾸기.

## 실행 모드 구분 (중요)

이 프론트는 환경변수 조합으로 세 가지 모드로 동작합니다 (`src/services/authConfig.js`, `src/services/api.js` 기준).

| 모드 | 조건 | 동작 |
|---|---|---|
| 목(mock) | `REACT_APP_API_BASE` 비어 있음 | API 호출 없이 `src/data/mockData.js` 예시 데이터 표시 |
| 로컬 중계(비인증) | `API_BASE` 만 있고 Cognito 값 없음 | 토큰 없이 `GET {API_BASE}/dashboard`·`/ai-guide` 호출 |
| HTTPS 인증(B안) | `API_BASE` + `COGNITO_DOMAIN` + `COGNITO_CLIENT_ID` 모두 있음 | Cognito PKCE 로그인 → 액세스 토큰 첨부 → 실데이터 조회 |

- `isAuthEnabled()` 는 위 세 값이 모두 있을 때만 true. 인증 모드에서 토큰을 못 얻으면 실제 요청을 막고 로그인 안내(AuthGate)로 전환합니다.
- **인증 설정이 비어 있다고 해서 무조건 목 데이터는 아닙니다.** `API_BASE` 만 있으면 토큰 없이 실 API 를 호출하는 로컬 중계 모드입니다.

## 실행 주소

- 로컬 목/중계: `http://localhost:3000/login.html` (로그인 화면), `http://localhost:3000/` (대시보드).
  프론트엔드 담당자가 공유한 로컬 개발 서버 주소입니다.
- HTTPS 인증 시연: `https://wearcare-mate-dxqh.vercel.app` (Cognito 로그인 → 실데이터).
- 배포 주소(Vercel): `https://wearcare-mate-dxqh.vercel.app`.
  - 인증 API(`tirb2qdtj8`) CORS Origin 은 `https://wearcare-mate-dxqh.vercel.app` (**끝 슬래시 없음**). 전체 허용(`*`)은 쓰지 않습니다.
  - Cognito callback/logout URL 은 `https://wearcare-mate-dxqh.vercel.app/` (**끝 슬래시 있음**). CORS Origin 과 슬래시가 다르므로 혼동 주의.
  - 기존 공개 API(`j3cwx5vmwj`)의 CORS 에는 로컬 `http://localhost:3000` 만 등록되어 있으며, 이 값은 로컬 중계 확인용으로 유지됩니다.

## 검증

- `5665f860` 기준: 사용자 터미널에서 Jest 테스트 8개 통과, 프로덕션 빌드 성공을 확인했습니다.
  테스트 범위: 6개 메뉴 전환, 실제 응답의 빈 배열, nullable delta, 가이드 상태와 경고,
  재조회 실패 후 복구.
- `d0f582d1` 기준: Jest 테스트 8개 통과, 프로덕션 빌드 성공(저장소 밖 임시 폴더로 출력).

### 로컬 브라우저 연결 확인 (2026-11-02, 사용자 확인)

- 실행 주소: `http://localhost:3000` (로컬 개발 서버. 배포 주소 아님)
- `frontend/.env.local`에 `REACT_APP_API_BASE`를 공개 API 기본 주소로 설정 (커밋하지 않음)
- API Gateway CORS에 `http://localhost:3000` 등록, `$default` 스테이지 자동 배포 Enabled
- 공개 예시 API 기반 대시보드 표시 성공
- AI 가이드 예시 화면 표시 성공
- 가이드 재조회 시 브라우저 Network에서 `/ai-guide` 요청 200 확인

이 확인은 **공개 API의 예시 데이터(mock) 응답**을 화면에 연결한 것입니다.
실제 Athena 데이터나 실제 생성 가이드를 브라우저에 표시한 검증이 아닙니다.

### 하지 않은 것

- 로그인 화면 → 대시보드 이동 확인 (이 브랜치에는 `login.html`이 없음)
- 공개 API를 통한 실제 데이터·AI 통합 확인
- 실제 생성 가이드(Bedrock)의 브라우저 표시 확인
- 배포 주소에서의 CORS·화면 확인, 시각 검수

## 팀에서 확인할 사항

1. 프론트엔드 배포 주소를 받아 백엔드 API Gateway CORS에 추가 등록 (현재는 `http://localhost:3000`만 등록).
2. 실제 데이터 공개 전 백엔드 인증·인가와 데이터 접근 범위 확정. (로그인 화면은 인증을 대신하지 않음)
3. 새 응답의 `analysis`, 가이드 `status`/`warnings`, `delta=null`을 최종 API 명세에 반영.
4. 그래프의 `anomaly: false`는 그날이 정상이라는 뜻이 아님. `analysis.evaluatedDates`에 있는 날짜만 판정됨.
5. 프로필은 브라우저에만 저장. 기기 연결, SNS 알림, 가이드 이력 저장은 아직 실제 연동이 아님.
6. 가이드 재조회는 정상일에 생성을 강제하지 않음. 생성을 요청하게 바꿀 때는 비용과 지연을 따로 검증.
