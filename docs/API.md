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
| `GET` | `/dashboard` | 대시보드 전체 데이터 한 번에 조회 | Timestream 조회 + SageMaker 결과 + Bedrock 가이드 취합 |
| `GET` | `/ai-guide` | AI 건강 가이드만 재생성 | Bedrock 재호출 |

---

## 1. `GET /dashboard`

대시보드 화면 전체를 한 번의 요청으로 채웁니다.

### 응답 스키마

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

  // SageMaker 이상 탐지 결과 목록
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
| `anomaly` | boolean | SageMaker 이상 판정 지점 여부 (true면 빨간 점 + 점선 원 강조) |

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

## 백엔드 체크리스트

- [ ] `timeseries`의 `value`는 **숫자**로 반환 (문자열 X). 요약 카드 `summaryStats.value`만 표시용 문자열.
- [ ] SageMaker 이상 판정 지점은 `timeseries[].anomaly = true`로 플래그.
- [ ] `severity`는 `danger` / `warn` / `ok` 세 값만 사용.
- [ ] `sleepStages.segments[].pct` 합계 = 100.
- [ ] `time`, `updatedAt`, `meta` 등 표시용 문자열은 포맷(요일/상대시간)까지 서버에서 생성 권장.
- [ ] API Gateway에서 **CORS 허용** (Amplify 배포 도메인 기준).
- [ ] 응답 실패(HTTP 4xx/5xx) 시 프론트는 에러 화면을 표시 → 적절한 상태코드 반환.

## 전체 데이터 흐름 (참고)

1. **데이터 수집·저장** — 웨어러블 데이터셋 S3 적재, Lambda 전처리
2. **시계열 저장·이상 탐지** — Timestream 저장, SageMaker 평소 패턴 학습/이상 탐지 → `anomalies`, `timeseries[].anomaly`
3. **AI 가이드 생성** — Bedrock → `aiGuide`
4. **알림·웹 서빙** — SNS 푸시(`notifications`), Amplify 웹 대시보드가 `GET /dashboard`로 취합 조회
