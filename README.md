> **현재 HTTPS 발표 구현 (2026-11-10)**
>
> [Vercel 발표 사이트](https://wearcare-mate-dxqh.vercel.app/) · 배포 브랜치 `frontend-b-cognito-auth`.
> Cognito 로그인 → API Gateway/Lambda → S3/Glue/Athena 실제 데이터 조회,
> AI/ML Lambda 판정 + Bedrock 가이드 생성, Vercel 웹 배포를 사용합니다.
> 알림·가이드 이력은 계정별 DynamoDB 보관이며, SNS 메일 발송 버튼은 기존 구독자에게 실제 이메일을 보냅니다.
> 알림 삭제는 목록 숨김이며 발송 기록·중복 방지·가이드는 유지합니다.
> 프로필과 알림 선호 설정은 표시용 브라우저 저장이며 실제 SNS 구독 설정을 바꾸지 않습니다.
> Fitbit 개인 기록·별도 수면/심박 집계·가상 시나리오 입력을 구분합니다.
> 수면 단계 정보와 실제 기기 연결은 제공하지 않습니다. [현재 API 명세](docs/API.md)를 참고하세요.

# WearCare Mate · 웨어러블 기반 AI 건강 주치의

웨어러블 시계열 데이터를 분석하고, 생성형 AI 기반 개인 맞춤형 건강 행동 가이드를 제공하는 서비스입니다.
이 저장소는 그중 **웹 대시보드 프론트엔드**를 담당합니다.

## 소개

현대인의 웨어러블 기기는 수면·심박·활동량 등 방대한 건강 데이터를 수집하지만, 대부분의 서비스는 단순 수치 나열에 그칩니다. WearCare Mate는 개인의 평소 생활 패턴을 학습해 미세한 이상 징후를 탐지하고, 생성형 AI로 사용자 눈높이에 맞는 건강 행동 가이드를 제공해 주도적인 건강 관리를 돕습니다.

프론트엔드는 분석 결과를 한눈에 보여주는 웹 대시보드 UI를 구현합니다.

- 웨어러블 시계열 데이터 시각화 (수면·심박·활동량)
- AI 이상 패턴(Anomaly) 탐지 결과 표시
- 생성형 AI 맞춤형 건강 행동 가이드 표시
- 실시간 알림 내역

## 기술 스택

- **React 19** (Create React App 기반)
- 외부 차트 라이브러리 없이 **SVG로 직접 구현한 라인 차트**
- 흑백 모노톤 디자인 (CSS 변수 기반 디자인 토큰)
- 백엔드 연동 대비 **API 서비스 레이어** 분리

## 시작하기

사전 요구사항: Node.js 18 이상

```bash
cd frontend
npm install
npm start
```

개발 서버가 실행되면 브라우저에서 [http://localhost:3000](http://localhost:3000) 으로 접속합니다.

## 사용 가능한 스크립트

`frontend` 디렉터리에서 실행합니다.

### `npm start`

개발 모드로 앱을 실행합니다. 코드를 수정하면 자동으로 새로고침됩니다.

### `npm test`

테스트 러너를 watch 모드로 실행합니다. 1회만 실행하려면 `CI=true npm test`를 사용합니다.

### `npm run build`

`build` 폴더에 프로덕션 빌드를 생성합니다. 번들이 최소화되고 파일명에 해시가 포함됩니다.

## 프로젝트 구조

```
frontend/
  public/
    index.html           페이지 메타 정보
  src/
    data/
      mockData.js         목(mock) 데이터 (수면/심박/활동량, 이상탐지, AI가이드, 알림)
    services/
      api.js              API 서비스 레이어 (fetchDashboard, fetchAiGuide)
    components/
      ui/
        Card.js           재사용 카드 컨테이너
        Badge.js          상태 배지
        StatCard.js       요약 통계 카드
        LineChart.js      SVG 라인 차트 (이상치 강조)
      Sidebar.js          좌측 내비게이션
      Topbar.js           상단바 (사용자/동기화 상태)
      TrendChart.js       시계열 추이 차트 (수면/심박/활동량 탭)
      SleepStages.js      수면 단계 분석
      AnomalyPanel.js     이상 패턴 탐지 패널
      AiGuide.js          AI 맞춤 건강 가이드
      Notifications.js    알림 목록
    App.js                전체 레이아웃 조립 및 데이터 로딩
    App.css               대시보드 레이아웃/컴포넌트 스타일
    index.css             전역 스타일 및 디자인 토큰
```

## 백엔드 연동

현재는 `src/data/mockData.js`의 목 데이터로 동작합니다. 실제 백엔드가 준비되면 환경변수만 설정하면 됩니다.

`frontend/.env` 파일을 만들고 다음을 추가합니다.

```
REACT_APP_API_BASE=https://your-api-gateway-url
```

`src/services/api.js`는 `REACT_APP_API_BASE`가 설정되면 해당 엔드포인트로 `fetch`를 수행하고, 없으면 목 데이터를 반환합니다. 각 함수가 Promise를 반환하므로 호출부 컴포넌트 코드는 수정할 필요가 없습니다.

| 함수 | 설명 | 예상 엔드포인트 |
| --- | --- | --- |
| `fetchDashboard()` | 대시보드 전체 데이터 조회 | `GET /dashboard` |
| `fetchAiGuide()` | AI 건강 가이드 재생성 | `GET /ai-guide` |

## 시스템 아키텍처 (전체 서비스 기준)

이 프론트엔드가 연동되는 전체 데이터 파이프라인은 다음과 같습니다.

1. **데이터 수집 및 저장** — 웨어러블 데이터셋 Amazon S3 적재, AWS Lambda 전처리
2. **시계열 저장 및 이상 탐지** — Amazon Timestream 저장, Amazon SageMaker 평소 패턴 학습/이상 탐지
3. **AI 가이드 생성** — Amazon Bedrock이 맞춤형 행동 가이드 생성
4. **알림 및 웹 서빙** — Amazon SNS 푸시 알림, Vercel에 배포된 웹 대시보드(본 저장소)를 통한 결과 확인

## 문서

- [API 명세 (백엔드 연동용)](docs/API.md)
- [변경 이력](docs/CHANGELOG.md)

## 담당

헬스케어 3조 — 백엔드 & 프론트엔드 파트 (웹 대시보드 UI)

## 수정사항

```
frontend/
  public/
    login.html           더미 로그인 페이지
```