# 변경 이력 (Frontend)

WearCare Mate 웹 대시보드 프론트엔드 작업 내역 정리본입니다.

---

## 3차 작업 · 프로필 저장을 localStorage로 전환

### 요약
- 사용자 프로필을 **데이터베이스/백엔드 API 없이 브라우저 `localStorage`에 저장**하도록 변경했습니다.
- 같은 브라우저에서 새로고침·재방문해도 수정한 프로필이 유지됩니다.

### 구현
- `src/services/profileStorage.js` 신규 — `loadProfile` / `saveProfile` / `clearProfile` (저장 키: `wearcare.profile`).
- `src/services/api.js`
  - `updateProfile()` — 이제 `saveProfile()`로 localStorage에 저장 (백엔드 호출 제거).
  - `fetchDashboard()` — 로드 시 저장된 프로필을 목/서버 user에 병합(`resolveUser`)해 반영.
- 쿠키 대신 localStorage 사용: 프로필은 서버로 전송할 필요가 없고(쿠키는 매 요청에 자동 첨부), 용량·JSON 저장 면에서 유리.

### 문서
- `docs/API.md` — `PUT /profile`을 "현재 미사용(참고용)"으로 표기. 프로필은 localStorage 저장임을 명시.

### 검증
- `npm run build` → **Compiled successfully**

---

## 2차 작업 · 사이드바 페이지 전체 구현 + 프로필 설정

### 요약
- 사이드바 6개 카테고리를 **모두 실제 페이지로 구현**하고, `App.js`를 페이지 전환(라우팅 유사) 구조로 리팩터링했습니다.
- 상단 **사용자 프로필(김웨어) 칩을 클릭하면 설정(프로필 변경) 페이지로 이동**합니다.
- 설정 페이지에서 프로필을 저장하면 상단 프로필 표시가 즉시 갱신됩니다.

### 페이지 전환 구조
- `App.js`가 `activeNav` 상태에 따라 콘텐츠 영역만 교체합니다. 사이드바/상단바는 공통 레이아웃으로 유지됩니다.
- `PAGE_META` 객체로 페이지별 상단 제목/부제목을 매핑합니다.

### 추가한 페이지 (`src/pages/`)
| 파일 | 카테고리 | 내용 |
| --- | --- | --- |
| `DashboardPage.js` | 대시보드 | 기존 대시보드(요약 통계·차트·이상탐지·AI가이드·알림) |
| `TrendsPage.js` | 추이 분석 | 수면·심박·활동량 개별 차트 + 평균/최고/최저 통계 |
| `AnomalyPage.js` | 이상 탐지 | 위험/주의/정상 건수 요약 + SageMaker 이상 내역 상세 |
| `GuidePage.js` | AI 가이드 | Bedrock 가이드 + 과거 생성 히스토리 |
| `DevicesPage.js` | 기기 연동 | 연결된 웨어러블 기기 목록(상태·배터리·수집 지표) |
| `SettingsPage.js` | 설정 | 프로필 정보 수정 폼 + 알림 설정 토글 |

### 프로필 변경 흐름
1. 상단 프로필 칩(`Topbar`)을 버튼으로 변경 → 클릭 시 `settings` 페이지로 이동.
2. `SettingsPage`에서 이름·나이·성별·키·몸무게·건강 목표 수정.
3. 저장 시 `updateProfile()` API 호출 → `onProfileSaved`로 `data.user` 갱신.
4. 이름 첫 글자로 아바타, 나이·성별로 메타 문구를 재생성해 상단에 즉시 반영.

### 수정/추가된 파일
**신규**
- `src/pages/DashboardPage.js`
- `src/pages/TrendsPage.js`
- `src/pages/AnomalyPage.js`
- `src/pages/GuidePage.js`
- `src/pages/DevicesPage.js`
- `src/pages/SettingsPage.js`

**수정**
- `src/App.js` — 페이지 전환 구조로 리팩터링, 프로필 저장 핸들러 추가
- `src/components/Topbar.js` — 프로필 칩 버튼화(클릭 이동), 페이지별 제목 props
- `src/components/AnomalyPanel.js` — `embedded` prop 추가(다른 Card 안에 삽입 시 헤더 중복 방지)
- `src/data/mockData.js` — `devices`, `guideHistory` 목 데이터 추가
- `src/services/api.js` — `updateProfile()` 추가, `/dashboard` 응답에 `devices`·`guideHistory` 포함
- `src/App.css` — 추이/히스토리/기기/폼/토글/버튼/프로필 버튼 스타일 추가

### API 영향 (백엔드 참고)
- `GET /dashboard` 응답에 `devices`, `guideHistory` 필드 추가
- `PUT /profile` 엔드포인트 추가 (프로필 저장). 목 모드에서는 입력값을 그대로 반환.
- 상세 스키마는 `docs/API.md` 참고.

### 검증
- `npm run build` → **Compiled successfully** (ESLint 경고 없음)

---

## 1차 작업 · 대시보드 초기 구축

### 요약
- Create React App 기본 템플릿을 걷어내고 WearCare Mate 건강 대시보드를 구축했습니다.
- 기획서의 흑백 모노톤 디자인을 CSS 변수(디자인 토큰)로 구현했습니다.
- 외부 차트 라이브러리 없이 SVG로 라인 차트를 직접 구현했습니다.

### 추가한 기능
- **요약 통계 카드 4종** — 평균 수면 / 안정 시 심박 / 평균 걸음 수 / 건강 점수 (지난주 대비 증감 표시)
- **시계열 추이 차트** — 수면·심박·활동량 탭 전환, SageMaker 이상치(Anomaly) 지점 강조
- **수면 단계 분석** — 깊은 수면/얕은 수면/REM/깨어남 비율 막대
- **이상 패턴 탐지 패널** — SageMaker 결과를 위험/주의/정상 등급으로 목록화
- **AI 맞춤 건강 가이드** — Bedrock 결과 + 실천 액션 + 재생성 버튼
- **알림 목록** — SNS 푸시 내역
- **사이드바 / 상단바** — 브랜딩, 네비게이션, 사용자 정보, 동기화 상태

### 구조
- `data/mockData.js` — 목 데이터
- `services/api.js` — API 서비스 레이어 (`REACT_APP_API_BASE` 설정 시 실제 API로 전환)
- `components/ui/` — Card, Badge, StatCard, LineChart (재사용 컴포넌트)
- `index.css` — 디자인 토큰, `App.css` — 대시보드 스타일 전면 교체

### 정리/수정
- `App.js` 대시보드로 교체, `App.test.js` 테스트 갱신
- `public/index.html` 제목/언어(ko)/설명 갱신
- 미사용 `logo.svg` 삭제
- `package.json` ESLint 설정 충돌(`jest/globals`) 해결
- `README.md` 한글 프로젝트 문서로 재작성
