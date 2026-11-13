# WearCare Mate 프론트엔드

웨어러블 시계열 데이터를 분석하고, 생성형 AI 기반 맞춤 건강 행동 가이드를 보여주는 **웹 대시보드**입니다. 이 폴더(`frontend-b-cognito-auth`)는 Cognito 로그인 방식(B안)의 프론트엔드이며, 앱 코드는 `frontend/` 폴더에 있습니다.

- 앱 이름: `health-app` (Create React App, React 19, react-scripts 5.0.1)
- 발표 배포: https://wearcare-mate-dxqh.vercel.app/ (Vercel)

## 주요 기능

### 대시보드 (사이드바 메뉴)

| 메뉴 | 내용 |
| --- | --- |
| 대시보드 | 요약 통계, 수면 지표, 이상 탐지/AI 가이드/알림 요약 |
| 추이 분석 | 수면 · 심박 · 활동량 시계열 추이 차트 (SVG 직접 구현) |
| 이상 탐지 | 이상 패턴 항목별 상세, 심각도 기준, 탐지 방식 설명 |
| AI 가이드 | Amazon Bedrock 기반 맞춤 가이드(상세), 어제와 비교, 분석 및 가이드 다시 확인 |
| 건강 앱 연동 | 삼성 헬스 / 애플 건강 / 기타 앱 연동, 메인 앱 지정 (아래 참고) |
| 설정 | 프로필, 알림 설정, 일일 리포트 알림 |

### 로그인과 데이터 모드

`REACT_APP_API_BASE`, `REACT_APP_COGNITO_DOMAIN`, `REACT_APP_COGNITO_CLIENT_ID`가 모두 설정되면 **인증 모드(Cognito PKCE)** 로 동작합니다.

- 인증 모드: 토큰이 있어야 실제 API 데이터를 조회합니다. 토큰이 없거나 만료되면 "로그인이 필요합니다" 화면이 나타납니다. 콘텐츠 영역 우측 상단에 로그아웃 버튼이 표시됩니다.
- 인증 모드에서는 대시보드 탭에 가상 이상 시연 패널이 표시됩니다. 시연 결과를 확인한 뒤 알림 이메일 발송을 요청할 수 있습니다.
- `REACT_APP_API_BASE`만 있고 Cognito 값이 없으면 토큰 없이 API를 호출합니다(로컬 중계/비인증 조회).
- `REACT_APP_API_BASE`가 비어 있으면 목(mock) 데이터 모드로 동작합니다.

### 건강 앱 연동 (프론트 mock)

웨어러블 기기를 직접 연결하지 않고, 휴대폰의 건강 앱과 연동하는 흐름입니다. 실제 건강 데이터를 가져오지 않는 시연용 기능입니다.

**연동 가능한 앱**

- 기본 앱: 애플 건강(Apple Health), 삼성 헬스(Samsung Health)
- 기타(Other): 헬스 커넥트, 핏빗, 가민 커넥트, 미 피트니스(샤오미), 화웨이 헬스, 오우라. 앱 선택 모달에서 "기타 (Other)"를 누르면 목록이 나타나고 "뒤로"로 돌아갑니다.
- 여러 앱을 동시에 연동할 수 있고, "다른 앱 추가 연동"으로 계속 추가합니다.

**연동 흐름 (4단계, 총 약 2초)**

1. 앱 확인
2. 권한 요청
3. 데이터 불러오기
4. 완료

모달의 취소 버튼은 가운데에 있고, ESC나 배경 클릭으로도 닫을 수 있습니다(연동 중에는 닫히지 않음).

**연동 후 화면**

- 앱별 카드: 연동 시각, 마지막 동기화 시각, 상태 배지(연동됨 / 동기화 중), 메인 배지
- 다시 동기화: 약 1초 mock 로딩 뒤 마지막 동기화 시각을 갱신합니다.
- 연동 해제: 확인 창("연동을 해제할까요?")에서 해제 또는 취소를 고릅니다.
- 접이식 안내 "가져오는 데이터 · 권한 · 개인정보 안내": 걸음수, 수면, 심박, 활동 시간, 칼로리 5개 항목(예시 값 표기), 읽기 전용 권한 설명, 개인정보·데이터 이용 안내

**메인 앱과 블루투스 기기**

- 연동한 앱 중 하나를 **메인 앱**으로 지정합니다. 첫 번째로 연동한 앱이 자동으로 메인이 되고, "메인으로 설정"으로 바꿀 수 있습니다. 메인 앱을 해제하면 남은 첫 번째 앱이 메인을 이어받습니다.
- "블루투스 기기" 버튼으로 앱별로 블루투스 연결된 기기 목록(이름, 종류, 가져오는 데이터, 연결됨/연결 끊김)을 볼 수 있습니다. 예시 목록이며 실제 블루투스 상태가 아닙니다.
- **삼성 헬스와 애플 건강**은 서로 다른 예시 측정 데이터셋을 가집니다. 메인 앱에 따라 대시보드, 추이 분석, 설정의 일일 리포트, AI 가이드 "어제와 비교" 수치가 달라지고 "메인 앱 예시 데이터" 배지가 표시됩니다. 애플 건강은 어제보다 모두 좋아진 예시, 삼성 헬스는 모두 나빠진 예시입니다.
- 기타 앱이 메인이거나 연동한 앱이 없으면 기존 데이터를 그대로 사용합니다. 가상 이상 시연 중에는 시연 값(AI 가이드, 이상 탐지)이 우선합니다.
- 백엔드 응답은 바꾸지 않고, 화면에 쓰는 데이터만 프론트에서 덮어씁니다(원본 보존).

저장: 브라우저 localStorage `wearcare.healthLink` = `{ links: [{ provider, linkedAt, lastSyncAt }], mainProvider }`. 예전 단일 저장 형식은 읽을 때 자동 변환합니다.

### 일일 리포트 알림 (프론트 mock)

"설정" 메뉴의 "일일 리포트 알림" 카드에서 관리합니다.

**설정 항목**

- 알림 ON/OFF
- 수신 시간 (기본 21:00)
- 수신 요일: 월~일 토글 버튼(기본 매일, 마지막 하나는 해제할 수 없음)
- 목표 걸음수 (기본 10,000걸음)
- 리포트에 포함할 항목: 걸음수, 수면, 안정 시 심박(기본은 걸음수·수면, 최소 1개 유지)
- 수신 시간 요약 문구: 예) "매일 오후 9:00에 받아요", "평일 오전 8:00에 받아요", "월·수·금 …", 꺼져 있으면 "리포트 알림이 꺼져 있어요"

**리포트 내용**

- 걸음수와 목표 달성률(진행 막대), 남은 걸음
- 수면시간과 수면 평가(6시간 미만 부족 / 6~8시간 적정 / 8시간 초과 충분)
- 어제 대비 걸음·수면 변화
- 안정 시 심박(포함 시)
- 달성률과 수면 상태를 조합한 한 줄 코멘트
- 메인 앱이 있으면 "기준 앱"을 함께 표시, 값이 없어 목 데이터로 대체하면 "예시 데이터" 표시

**시스템 알림 권한**

- 권한 상태 배지(허용됨 / 차단됨 / 아직 묻지 않음 / 미지원)를 보여 주고, 차단된 경우 주소창 자물쇠에서 알림을 허용하도록 안내합니다.
- 권한과 관계없이 앱 안 토스트는 항상 표시됩니다.

**동작 방식**

- `App.js`가 30초마다 현재 시각, 요일, 설정을 비교합니다. 어느 페이지에 있어도 동작합니다.
- 설정 시각 5분 이내에만 표시하므로, 한참 지난 뒤 앱을 열어도 뒤늦게 표시하지 않습니다.
- 같은 날 한 번 표시했으면 다시 표시하지 않습니다.
- "지금 리포트 보기"는 미리보기이며 하루 1회 표시 기록에 영향을 주지 않습니다.
- 설정은 localStorage `wearcare.dailyReport`에 저장됩니다. 요일(`days`)과 포함 항목(`include`)은 기존 저장값과 병합되어 호환됩니다.

### AI 가이드: 대시보드(간단) vs 카테고리(상세)

- 대시보드의 AI 가이드는 요약만 간단히 보여 줍니다.
- "AI 가이드" 카테고리는 같은 가이드를 더 자세히 보여 주고, **어제와 비교** 섹션이 추가됩니다.

**어제와 비교 계산 방식**

- 생성형 AI 문장이 아니라, 시계열 데이터의 마지막 두 값(오늘, 어제)을 프론트에서 단순 비교한 결과입니다.
- 걸음수·수면시간은 늘수록, 안정 시 심박은 낮을수록 "좋아졌어요"입니다. 반대는 "나빠졌어요"입니다.
- 변화가 작으면(걸음 ±1%, 수면 ±0.1시간, 심박 ±1bpm 이내) "비슷해요"로 분류합니다.
- 색에만 의존하지 않도록 기호와 텍스트 라벨을 함께 씁니다.

**한계**

- 실제 API 응답은 수면·심박 시계열이 비어 있을 수 있어, 비교 가능한 지표만 표시됩니다. 하나도 없으면 "비교할 어제 데이터가 없습니다"를 보여 줍니다.
- 가상 시연 중에는 기준일이 어긋나 오해를 줄 수 있어 비교를 숨기고 안내 문구만 표시합니다.

### 이상 탐지 상세

"이상 탐지" 메뉴에서 항목별 상세를 확인합니다(대시보드의 이상 탐지 패널은 간단한 목록 그대로입니다).

**항목별 상세 필드**

- 지표 이름, 측정값, 평소값, 차이(%)
- 심각도 배지(위험 / 주의 / 정상)와 의미
- 비교 기준(내 평소 기록 / 전체 사용자 평균)
- 탐지 시각
- 가능한 원인(참고용 문구, 단정하지 않음)과 권장 행동

**심각도 기준**

- 주의: 평소와 차이가 있어 지켜볼 단계(분석 결과 낮음·중간)
- 위험: 평소와 크게 달라 먼저 확인해 볼 단계(분석 결과 높음)
- 정상: 이상이 감지되지 않은 상태

**탐지 방식**

- 개인 기준선: 내 과거 기록 평균과 비교
- 집단 평균: 전체 사용자 평균이나 권장 기준과 비교

**필드 누락 시 처리**

- 백엔드가 주는 이상 항목은 `id, severity, title, time, desc`뿐이라, 측정값·평소값은 `desc` 문장에서 읽어 옵니다. 읽을 수 없는 칸은 값을 추정하지 않고 "정보 없음"으로 표시합니다.
- `undefined`, `NaN`, `Infinity`가 화면에 나오지 않도록 처리합니다.
- 이상 없음, 데이터 부족, 빈 목록은 각각 별도 안내문을 보여 줍니다.
- 결과는 참고용이며 의학적 진단이 아니라는 면책 문구를 함께 표시합니다.
## 기술 스택

- React 19, Create React App (react-scripts 5.0.1)
- 외부 차트 라이브러리 없이 SVG로 직접 구현한 라인 차트
- CSS 변수 기반 디자인 토큰 (`public/theme.css`)
- Amazon Cognito (Hosted UI + PKCE) 로그인
- 테스트: Jest + React Testing Library
- 배포: Vercel

## 폴더 구조

```
frontend-b-cognito-auth/
  docs/
    API.md                    API 명세
    CHANGELOG.md              변경 이력
  vercel.json                 Vercel 빌드/라우팅 설정
  frontend/                   ← 앱 코드 (npm 명령은 여기서 실행)
    .env.example              환경변수 예시
    INTEGRATION-NOTES.md      연동 메모
    package.json
    public/                   index.html, login.html, theme.css 등 정적 파일
    src/
      index.js                진입점
      App.js                  전체 레이아웃, 페이지 전환, 데이터 로딩, 일일 리포트 스케줄러
      App.css, index.css      스타일
      pages/                  DashboardPage, TrendsPage, AnomalyPage, GuidePage, DevicesPage, SettingsPage
      components/
        Sidebar.js, Topbar.js 내비게이션, 상단바
        TrendChart.js         시계열 추이 차트
        SleepMetrics.js, SleepStages.js, DatasetSummaryCards.js, DatasetTrends.js
        AnomalyPanel.js, DemoAnomalyPanel.js, DemoBanner.js
        AnomalyDetailItem.js  이상 탐지 항목별 상세
        AiGuide.js, Notifications.js
        YesterdayCompare.js   AI 가이드 '어제와 비교' 섹션
        HealthAppLinkCard.js  건강 앱 연동 카드, 앱 선택 모달, 메인 앱, 블루투스 기기
        HealthLinkDetails.js  가져오는 데이터, 권한, 개인정보 안내
        DailyReportSettings.js 일일 리포트 설정 카드
        ReportToast.js        리포트 토스트
        ui/                   Card, Badge, StatCard, LineChart
      services/
        api.js                API 호출 (대시보드, AI 가이드, 이력, 시연 등)
        authConfig.js         환경변수 기반 인증 설정
        cognitoAuth.js        Cognito 로그인/로그아웃 (PKCE)
        healthLinkStorage.js  건강 앱 연동(다중)·메인 앱 상태 저장
        reportSettingsStorage.js 일일 리포트 설정 저장
        dailyReport.js        리포트 계산, 메시지 생성, 표시 시점 판단
        profileStorage.js     프로필 저장
      utils/
        compareYesterday.js   오늘·어제 비교 계산
        anomalyDetail.js      이상 탐지 항목 상세 정리(desc 파싱)
      data/
        mockData.js           목 데이터
        healthAppMock.js      앱별 블루투스 기기, 삼성/애플 예시 데이터셋
```

테스트 파일(`*.test.js`)은 각 소스 옆과 `src/` 아래에 있습니다.

## 환경변수 설정

`frontend/.env.example`을 `frontend/.env.local`로 복사한 뒤 값을 확인하세요. CRA는 **빌드 시점**에 값을 넣으므로 수정 후에는 `npm start`를 다시 시작해야 합니다. 클라이언트 시크릿이나 AWS 자격 증명은 넣지 않습니다.

| 변수 | 설명 |
| --- | --- |
| `REACT_APP_API_BASE` | API Gateway 주소. 비우면 목 데이터 모드 |
| `REACT_APP_COGNITO_DOMAIN` | Cognito 도메인 |
| `REACT_APP_COGNITO_CLIENT_ID` | 공개 SPA 앱 클라이언트 ID |
| `REACT_APP_COGNITO_SCOPE` | 스코프 (기본값 `openid wearcare-demo/read`) |
| `REACT_APP_COGNITO_REDIRECT_URI` | 선택. 비우면 현재 origin + `/` |
| `REACT_APP_COGNITO_LOGOUT_URI` | 선택. 비우면 현재 origin + `/` |
| `REACT_APP_AUTH_DIAG` | 선택. `1`이면 로그인 진단 모드 |

명시한 리다이렉트 주소는 Cognito 앱 클라이언트에 등록한 값과 끝의 `/`까지 정확히 같아야 합니다.

## 설치 및 실행

반드시 `frontend` 폴더로 이동한 뒤 명령을 실행하세요. 상위 폴더에서 실행하면 `react-scripts`를 찾지 못합니다. Node.js 18 이상을 권장합니다.

```bash
cd frontend-b-cognito-auth/frontend
npm install
npm start
```

브라우저에서 http://localhost:3000 으로 접속합니다.

| 명령 | 설명 |
| --- | --- |
| `npm start` | 개발 서버 실행 |
| `npm run build` | `build/` 폴더에 프로덕션 빌드 생성 |
| `npm test` | 테스트 실행 (watch 모드). 1회 실행은 `npm test -- --watchAll=false` |

### 문제 해결

- `'react-scripts' is not recognized` 오류는 `npm install`을 하지 않았거나 `frontend` 폴더가 아닌 곳에서 실행했을 때 발생합니다. `frontend` 폴더에서 `npm install`을 먼저 실행하세요.
- OneDrive 동기화 폴더에서는 파일 잠금으로 `npm install`이 `EPERM` 등으로 실패할 수 있습니다. 그럴 때는 OneDrive 밖의 폴더로 복사해 설치하세요.

## 참고사항

- 건강 앱 연동과 일일 리포트 알림은 **프론트엔드 mock 시뮬레이션**입니다. 실제 Apple HealthKit, Samsung Health SDK 연동이나 푸시 서버는 없으며, 실제 건강 데이터를 가져오지 않습니다.
- 4단계 진행 후 약 2초 만에 연동 완료로 처리하는 것은 화면 흐름을 보여주기 위한 시연입니다. 블루투스 기기 목록과 삼성/애플 데이터셋도 예시 값입니다.
- 어제와 비교, 이상 탐지 상세의 수치는 프론트에서 계산하거나 응답 문장에서 읽은 값이며 백엔드 응답 형식은 바꾸지 않았습니다.
- 일일 리포트는 앱(브라우저 탭)이 열려 있을 때만 표시됩니다. 탭을 닫으면 알림이 오지 않습니다.
- 브라우저 Notification은 사용자가 권한을 허용한 경우에만 표시됩니다. 거부하거나 지원하지 않아도 앱 내 토스트는 동작합니다.
- 목표 걸음수는 서버 데이터에 없으므로 사용자가 설정한 값(기본 10,000)을 사용합니다.
- 연동 상태(메인 앱 포함)와 리포트 설정은 브라우저 localStorage에만 저장되어 기기 간에 공유되지 않습니다.
- 프로필과 알림 선호 설정은 표시용 브라우저 저장이며 실제 SNS 구독 설정을 바꾸지 않습니다.
- 자세한 API 내용은 [docs/API.md](docs/API.md), 변경 이력은 [docs/CHANGELOG.md](docs/CHANGELOG.md)를 참고하세요.
