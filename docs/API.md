> **현재 배포 기준 (2026-11-10)**
>
> 인증 API: `https://tirb2qdtj8.execute-api.ap-northeast-2.amazonaws.com`.
> Cognito access token을 `Authorization: Bearer ...`로 전달하며 scope는 `wearcare-demo/read`입니다.
> 아래 JSON의 수면 단계·기기·개인 심박 값은 디자인 예시이며, 현재 실제 응답을 보장하지 않습니다.
> 실제 Fitbit 기준일은 2016-04-10, 가상 시연 기준일은 2026-11-14입니다.
> 별도 데이터셋 집계는 `sleepDatasetSummary`와 `heartRateDatasetSummary`이며 개인 timeseries와 합치지 않습니다.
> 현재 탐지는 Lambda 내 기준선/집단 편차 로직입니다. SageMaker 실시간 엔드포인트를 호출하지 않습니다.

## 현재 시연·저장 요청

- 분석: `POST /demo/anomaly`, JSON `{ "scenario": "steps|sleep|restless|hrv|stress|multi" }`.
- 실제 SNS 메일: 같은 POST에 `{ "action": "send", "eventId": "분석 응답 eventId" }`.
  기존 구독자에게 저장된 가이드만 발송합니다. 주소·본문은 클라이언트에서 지정하지 않습니다.
- 알림 목록 삭제: 같은 POST에 `{ "action": "hide_notification", "eventId": "알림 id" }`.
  해당 계정 목록에서 숨길 뿐, 원본 발송 결과·중복 방지 기록·가이드를 삭제하지 않습니다.
- 저장 내역: `GET /history?cursor=...` → `guideHistory`, `notifications`, `nextCursor`, `historyStatus`.
- 분석 성공 응답에는 `scenario`, `scenarioLabel`, `aiGuide`, `anomalies`, `eventId`, `persistenceStatus`가 포함됩니다.
- 생성된 가이드·메일 요청 내역은 계정별 영구 저장입니다. 기존 미저장 기록은 소급 복원하지 않습니다.
- `accepted`는 SNS 접수 상태이며 메일 수신 확인과 구분합니다. pending/unknown은 자동 재발송하지 않습니다.
- 조회·재조회·페이지 이동·시나리오 선택만으로 메일을 보내지 않습니다.

---

# WearCare Mate · 프론트엔드 ↔ 백엔드 API 명세

백엔드 작업자를 위한 정리본입니다. 프론트엔드(React 웹 대시보드)가 **실제로 소비하는 데이터 형태**를 기준으로 작성했습니다.
아래 JSON 구조를 그대로 맞춰 주면 프론트엔드 코드 수정 없이 연동됩니다.

## 연동 방식

- 프론트는 `REACT_APP_API_BASE` 환경변수에 경로를 붙여 호출합니다. (`frontend/src/services/api.js`)
- `REACT_APP_API_BASE`가 **비어 있으면 목(mock) 데이터**로 동작하고, **값이 있으면** `fetch(\`${API_BASE}${path}\`)` → `res.json()` 결과를 그대로 화면에 바인딩합니다.
- 설정 예시 (`frontend/.env`):

  ```
  REACT_APP_API_BASE=https://your-api-gateway-url
  ```

## 엔드포인트 목록

| 메서드 | 경로 | 용도 | 대응 AWS 서비스 |
| --- | --- | --- | --- |
| `GET` | `/dashboard` | 대시보드 전체 데이터 한 번에 조회 | Athena 조회 + AI/ML Lambda 판정 + Bedrock 가이드 취합 |
| `GET` | `/ai-guide` | 실제 기록의 판정·가이드 다시 확인, 메일 미발송 | AI/ML Lambda + Bedrock |
| `POST` | `/demo/anomaly` | 가상 시나리오 분석·저장 결과 메일 발송·알림 숨김 | Lambda + Bedrock + DynamoDB + SNS |
| `GET` | `/history` | 계정별 저장 내역과 다음 페이지 조회 | DynamoDB |

> **프로필은 백엔드 API를 쓰지 않습니다.** 사용자 프로필 정보는 데이터베이스를 거치지 않고
> 브라우저 `localStorage`(키: `wearcare.profile`)에 저장됩니다. (`frontend/src/services/profileStorage.js`)
> 아래 `PUT /profile` 섹션은 추후 서버 저장이 필요해질 경우를 대비한 참고용 스펙입니다.

---

## 1. `GET /dashboard`

대시보드 화면 전체를 한 번의 요청으로 채웁니다.

### 예시 응답 스키마 (디자인 참고용, 현재 실제 데이터와 구분)

```jsonc
{
  "user": {
    "name": "김웨어",
    "meta": "33세 · 일반 사용자",
    "initial": "웨"            // 아바타에 표시할 한 글자
  },

  // 상단 요약 통계 카드 (배열 순서대로 표시)
  "summaryStats": [
    {
      "id": "sleep",           // 고유 key
      "icon": "🌙",            // 이모지 (또는 프론트에서 매핑)
      "label": "평균 수면",
      "value": "6.9",          // 표시용 문자열 (포맷 포함 가능: "7,929")
      "unit": "시간",
      "delta": -4,             // 증감 % (양수=▲ 상승, 음수=▼ 하락, 0=변동없음)
      "deltaLabel": "지난주 대비"
    }
    // 권장: sleep / hr / steps / score 4개
  ],

  // 최근 7일 시계열. 각 배열은 요일 순서(월~일) 7개
  "timeseries": {
    "sleep":     [{ "label": "월", "value": 7.2 }],
    "heartRate": [{ "label": "월", "value": 62, "anomaly": false }],
    "steps":     [{ "label": "월", "value": 8200, "anomaly": false }]
  },

  // 지난밤 수면 단계. pct 합계 = 100
  "sleepStages": {
    "totalLabel": "7시간 18분",
    "segments": [
      { "id": "deep",  "label": "깊은 수면", "pct": 22, "color": "#141414" },
      { "id": "light", "label": "얕은 수면", "pct": 48, "color": "#71717a" },
      { "id": "rem",   "label": "REM",      "pct": 22, "color": "#a1a1aa" },
      { "id": "awake", "label": "깨어남",    "pct": 8,  "color": "#d6d6db" }
    ]
  },

  // AI/ML Lambda 이상 탐지 결과 목록
  "anomalies": [
    {
      "id": "a1",
      "severity": "danger",    // "danger" | "warn" | "ok"
      "title": "안정 시 심박 급등 감지",
      "time": "목요일 · 오전 3:20",
      "desc": "평소 패턴 대비 상승. 수면 중 이상 징후로 분류."
    }
  ],

  // Bedrock 생성형 AI 가이드
  "aiGuide": {
    "model": "Amazon Bedrock · Claude",  // 출처 표기용
    "updatedAt": "방금 전 생성됨",
    "headline": "한 줄 요약 문구",
    "text": "본문 설명 문단",
    "actions": ["실천 항목 1", "실천 항목 2"]   // 문자열 배열
  },

  // SNS 푸시 알림 내역
  "notifications": [
    { "id": "n1", "icon": "🔔", "title": "알림 내용", "time": "방금 전" }
  ],

  // 연결된 웨어러블 기기 (기기 연동 페이지)
  "devices": [
    {
      "id": "d1",
      "name": "Galaxy Watch 6",
      "type": "스마트워치",
      "icon": "⌚",
      "status": "connected",        // "connected" | "syncing" | "disconnected"
      "battery": 82,                 // 0~100, 없으면 null
      "lastSync": "2분 전",
      "metrics": ["심박", "수면", "활동량", "SpO2"]
    }
  ],

  // AI 가이드 생성 히스토리 (AI 가이드 페이지)
  "guideHistory": [
    {
      "id": "g1",
      "date": "오늘 · 오전 9:12",
      "headline": "가이드 한 줄 요약",
      "tag": "회복 권장"
    }
  ]
}
```

### 필드 상세

#### `user`
| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `name` | string | 사용자 이름 |
| `meta` | string | 부가 정보 (나이·구분 등 표시용) |
| `initial` | string | 아바타에 표시할 한 글자 |

#### `summaryStats[]`
| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | string | 고유 key |
| `icon` | string | 아이콘(이모지) |
| `label` | string | 통계 이름 |
| `value` | string | 표시용 값 (천단위 콤마 등 포맷 포함 가능) |
| `unit` | string | 단위 (시간, bpm, 보, /100 등) |
| `delta` | number | 증감 퍼센트. 양수=▲, 음수=▼, 0=변동없음 |
| `deltaLabel` | string | 증감 기준 설명 |

#### `timeseries.{sleep|heartRate|steps}[]`
| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `label` | string | x축 라벨 (요일) |
| `value` | number | **반드시 숫자.** 차트가 수치로 계산 |
| `anomaly` | boolean | AI/ML Lambda 이상 판정 지점 여부 (true면 빨간 점 + 점선 원 강조) |

#### `sleepStages`
| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `totalLabel` | string | 총 수면 시간 표시용 문자열 |
| `segments[].id` | string | 단계 key |
| `segments[].label` | string | 단계 이름 |
| `segments[].pct` | number | 비율(%). **합계 100** |
| `segments[].color` | string | 막대 색상(옵션). 없으면 프론트 기본색 사용 |

#### `anomalies[]`
| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | string | 고유 key |
| `severity` | string | `danger` / `warn` / `ok` **세 값만** |
| `title` | string | 이상 항목 제목 |
| `time` | string | 발생 시점 표시용 문자열 |
| `desc` | string | 상세 설명 |

#### `aiGuide`
| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `model` | string | 모델/출처 표기 |
| `updatedAt` | string | 생성 시점 표시용 문자열 |
| `headline` | string | 한 줄 요약 |
| `text` | string | 본문 설명 |
| `actions` | string[] | 실천 항목 리스트 |

#### `notifications[]`
| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | string | 고유 key |
| `icon` | string | 아이콘(이모지) |
| `title` | string | 알림 내용 |
| `time` | string | 수신 시점 표시용 문자열 |

#### `devices[]`
| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | string | 고유 key |
| `name` | string | 기기 이름 |
| `type` | string | 기기 종류 (스마트워치 등) |
| `icon` | string | 아이콘(이모지) |
| `status` | string | `connected` / `syncing` / `disconnected` |
| `battery` | number\|null | 배터리 잔량(0~100). 없으면 `null` |
| `lastSync` | string | 마지막 동기화 시점 표시용 문자열 |
| `metrics` | string[] | 해당 기기가 수집하는 지표 목록 |

#### `guideHistory[]`
| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | string | 고유 key |
| `date` | string | 가이드 생성 시점 표시용 문자열 |
| `headline` | string | 가이드 한 줄 요약 |
| `tag` | string | 분류 태그 (회복 권장, 유지 등) |

---

## 2. `GET /ai-guide`

AI 건강 가이드만 다시 생성합니다. (대시보드의 "가이드 다시 생성" 버튼)

### 응답 스키마

`/dashboard` 응답의 `aiGuide` 객체와 **동일한 형태를 단독 반환**합니다.

```jsonc
{
  "model": "Amazon Bedrock · Claude",
  "updatedAt": "방금 전 생성됨",
  "headline": "한 줄 요약 문구",
  "text": "본문 설명 문단",
  "actions": ["실천 항목 1", "실천 항목 2"]
}
```

---

## 3. `PUT /profile` (현재 미사용 · 참고용)

설정 페이지에서 수정한 사용자 프로필을 저장합니다.

> **현재 프론트는 이 API를 호출하지 않고 브라우저 `localStorage`에 저장합니다.**
> 나중에 여러 기기 간 동기화나 서버 보관이 필요해지면, 아래 스펙으로 서버 저장을
> 추가하고 `updateProfile()`에서 이 엔드포인트를 호출하도록 전환하면 됩니다.

### 요청 본문

```jsonc
{
  "name": "김웨어",
  "age": "33",                 // 문자열 또는 숫자
  "gender": "남성",            // "남성" | "여성" | "기타" | ""
  "height": "172",             // cm
  "weight": "68",              // kg
  "goal": "balanced",          // "balanced" | "sleep" | "activity" | "recovery"
  "notifyAnomaly": true,       // 이상 패턴 알림 수신 여부
  "notifyGuide": true,         // AI 가이드 알림 수신 여부
  "meta": "33세 · 남성",        // 표시용 메타 문구 (프론트에서 재생성해 전송)
  "initial": "김"              // 아바타 글자 (프론트에서 이름 첫 글자로 전송)
}
```

### 응답

저장된 사용자 객체를 반환합니다. 프론트는 이 응답으로 상단 프로필 표시를 즉시 갱신합니다.
(목 모드에서는 요청 본문을 그대로 반환합니다.)

---

## 백엔드 체크리스트

- [ ] `timeseries`의 `value`는 **숫자**로 반환 (문자열 X). 요약 카드 `summaryStats.value`만 표시용 문자열.
- [ ] AI/ML Lambda 이상 판정 지점은 `timeseries[].anomaly = true`로 플래그.
- [ ] `severity`는 `danger` / `warn` / `ok` 세 값만 사용.
- [ ] `sleepStages.segments[].pct` 합계 = 100.
- [ ] `time`, `updatedAt`, `meta` 등 표시용 문자열은 포맷(요일/상대시간)까지 서버에서 생성 권장.
- [ ] API Gateway에서 **CORS 허용** (Vercel 배포 도메인 기준).
- [ ] 응답 실패(HTTP 4xx/5xx) 시 프론트는 에러 화면을 표시 → 적절한 상태코드 반환.

## 전체 데이터 흐름 (참고)

1. **데이터 수집·저장** — 웨어러블 데이터셋 S3 적재, Lambda 전처리
2. **시계열 저장·이상 탐지** — Athena 저장, AI/ML Lambda 평소 패턴 학습/이상 탐지 → `anomalies`, `timeseries[].anomaly`
3. **AI 가이드 생성** — Bedrock → `aiGuide`
4. **알림·웹 서빙** — SNS 푸시(`notifications`), Vercel 웹 대시보드가 `GET /dashboard`로 취합 조회

## 수면 관련 지표 확장

수면 단계 대신 `sleepDatasetSummary`의 평균 수면 시간과 수면 중 움직임을 표시합니다.
추가 필드: `averageMovement`(수치 또는 null), `movementRecordCount`(건수 또는 null),
`movementStatus`(ok/empty/unavailable/error), `movementUnit`(현재 null).
움직임 값은 유효 수면 시간 기록 중 0 이상인 값만 집계하며, 횟수·수면 단계 비율로 해석하지 않습니다.
가상 시연 `restless`는 고정 입력 movement_during_sleep=6.0으로 실제 AI/ML의 SLEEP_RESTLESS 판정을 확인합니다.
