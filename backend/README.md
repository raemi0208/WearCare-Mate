# WearCare Mate Backend

AWS Lambda와 API Gateway 기반 백엔드 서비스

## 담당 기능
- REST API 개발
- AI/ML 서비스 연동
- Amazon SNS 알림
- 오류 처리 및 AWS 인프라 관리

## 개발 상태

> ⚠️ **AWS Lambda / API Gateway 는 아직 배포하지 않았습니다.**
> ⚠️ **실제 AWS(Athena) 조회는 아직 실행·검증하지 않았습니다.**
> Athena 조회 코드는 구현되어 있지만, 가짜 Athena 클라이언트를 쓰는 로컬 단위 테스트로만 검증했습니다.
> SageMaker, Bedrock, SNS 연동 코드는 없습니다.

- [x] `GET /health` 헬스체크
- [x] `GET /users/{userId}/health-data` — MOCK (기본) / REAL(Athena, 개발·통합 테스트 전용)
- [x] `GET /users/{userId}/anomalies` — MOCK
- [x] `GET /users/{userId}/guides` — MOCK
- [x] `GET /dashboard` — 프론트엔드 API.md 스키마. MOCK (기본) / REAL(걸음 수만 Athena, 개발·통합 테스트 전용)
- [x] `GET /ai-guide` — 프론트엔드 API.md 의 aiGuide 스키마. 항상 MOCK (Bedrock 미호출)
- [x] 오류 처리: 400 / 404 / 500 / 503
- [ ] 실제 Athena 조회 검증 (AWS 환경)
- [ ] AI/ML(SageMaker·Bedrock) 연동 — 최신 `ml-interface-spec.md` 확인 후 별도 단계
- [ ] SNS 알림, `POST /users/{userId}/notifications/subscriptions` — 설계 후보
- [ ] CORS 설정 (API Gateway)
- [ ] 인증·인가
- [ ] AWS 배포

## 폴더 구조
```text
backend/
├── docs/
│   └── api-spec.md              # REST API 명세 초안
├── src/
│   ├── lambda_function.py       # Lambda 핸들러: 라우팅, 오류 처리(400/404/500/503)
│   ├── data_source.py           # DATA_SOURCE 로 health-data / dashboard 데이터 소스 선택, 공통 예외
│   ├── mock_data.py             # health-data / anomalies / guides 가상 MOCK 데이터
│   ├── dashboard_mock_data.py   # /dashboard, /ai-guide 예시 데이터 (API.md 스키마)
│   ├── mappers.py               # Fitbit 데이터 행 → API 활동 항목 변환
│   ├── health_service.py        # 사용자·날짜 필터링 및 health-data 응답 조립
│   ├── athena_repository.py     # Athena 조회 (파라미터 쿼리, 상태 확인, 페이지네이션, 타임아웃)
│   ├── real_health_data.py      # health-data REAL 빌더 (스위치·입력 검증·접근 제한·조회)
│   ├── dashboard_service.py     # 걸음 수 주간 통계 계산 (순수 함수)
│   └── dashboard_data.py        # /dashboard REAL 조립 (걸음 수만 실제 데이터)
├── tests/                       # unittest 기반 테스트 (AWS 접속 없음)
├── requirements.txt             # 외부 의존성 목록(현재 없음)
└── README.md
```

## API 엔드포인트

이벤트 기준: API Gateway HTTP API, payload format 2.0

| 메서드 | 경로 | 설명 | 현재 응답 |
| ------ | ---- | ---- | --------- |
| GET | `/health` | 헬스체크 | `{"status": "ok", "service": "WearCare Mate Backend"}` |
| GET | `/users/{userId}/health-data` | 건강 데이터 조회 | `DATA_SOURCE` 설정에 따름 |
| GET | `/users/{userId}/anomalies` | 이상탐지 결과 조회 | 항상 MOCK |
| GET | `/users/{userId}/guides` | 건강 행동 가이드 조회 | 항상 MOCK (disclaimer 포함) |
| GET | `/dashboard` | 대시보드 전체 (프론트 API.md) | `DATA_SOURCE` 설정에 따름 |
| GET | `/ai-guide` | AI 가이드 (프론트 API.md 의 aiGuide) | 항상 MOCK |

- `/users/...` MOCK 응답에는 `"mock": true` 와 `"_note"` 가 포함되며, 쿼리는 요청값을 돌려줄 뿐 필터링하지 않습니다.
- `/dashboard`, `/ai-guide` 는 프론트 API.md 에 없는 필드를 넣지 않습니다. 대신 화면에 보이는
  문자열에 예시 표시를 넣습니다. (`[예시]`, `"예시 데이터"`, `aiGuide.model = "MOCK · 실제 AI 생성 아님"`)
- `/dashboard` 는 쿼리 파라미터를 사용하지 않습니다. `userId` 를 보내도 조회 대상이 바뀌지 않습니다.
- 자세한 요청·응답 형식은 [`docs/api-spec.md`](docs/api-spec.md) 를 참고하세요.

### 오류 응답

모든 오류는 `{"error": "...", "message": "..."}` 형식의 JSON 입니다.

| 상태 코드 | error | 발생 조건 |
| --------- | ----- | --------- |
| 400 | `bad_request` | 이벤트 형식 오류, 빈 userId, 쿼리 형식 오류, REAL 모드의 잘못된 userId·날짜·날짜 범위 |
| 404 | `not_found` | 지원하지 않는 경로·메서드, REAL 모드에서 `DASHBOARD_USER_ID` 와 다른 사용자 |
| 500 | `internal_error` | 처리되지 않은 예외, `DATA_SOURCE`/`DASHBOARD_USER_ID`/Athena 설정 오류, boto3 미설치 |
| 503 | `unavailable` | REAL 스위치 꺼짐, Athena 조회 실패·타임아웃, 대시보드 조회 결과가 최대 행 수 도달 |

- 오류 응답은 고정 문구만 사용하며, 사용자 입력값·사용자 ID·설정값·AWS 오류 원문을 포함하지 않습니다.
- 로그에는 예외 타입 이름만 기록합니다.
- REAL 모드에서 조회가 실패해도 MOCK 데이터로 대체하지 않습니다.

## `DATA_SOURCE` 와 REAL 모드

`/users/{userId}/health-data` 와 `/dashboard` 의 데이터 소스를 선택합니다.
(anomalies, guides, `/ai-guide`, `/health` 에는 영향 없음)

| 값 | 동작 |
| -- | ---- |
| 설정 안 함 (기본값) | `mock` 과 동일 |
| `mock` | 기존 MOCK 응답 (200) |
| `real` | 아래 REAL 진입 조건을 모두 갖춰야 Athena 를 조회합니다. 하나라도 없으면 503 또는 500 |
| 그 외 값, 빈 문자열 | 설정 오류(500). MOCK 으로 조용히 바꾸지 않습니다. |

### REAL 진입 조건 (개발·통합 테스트 전용)

| 환경변수 | 설명 |
| -------- | ---- |
| `DATA_SOURCE=real` | 데이터 소스 선택 |
| `ENABLE_REAL_DATA_TESTING=true` | ⚠️ 임시 개발 장치. 없으면 503. `true` 외 값은 모두 꺼짐 |
| `DASHBOARD_USER_ID` | ⚠️ 개발용 데모 조회 대상(숫자 1~20자). 없거나 형식 오류면 500 |
| `ATHENA_DATABASE`, `ATHENA_TABLE` | 필수. 소문자·숫자·밑줄 |
| `ATHENA_REGION` | 기본 `us-east-2` |
| `ATHENA_WORKGROUP` | 기본 `primary` |
| `ATHENA_OUTPUT_LOCATION` | 선택. 워크그룹에 결과 위치가 없을 때 `s3://...` |
| `ATHENA_QUERY_TIMEOUT_SECONDS` | 기본 20 |
| `ATHENA_MAX_ROWS` | 기본 1000 |

> ⚠️ `ENABLE_REAL_DATA_TESTING` 과 `DASHBOARD_USER_ID` 는 **인증·인가를 대신하지 않습니다.**
> 인증이 없는 공개 배포 환경에서는 이 조합을 설정하지 않습니다. (실제 건강 데이터 비공개 원칙)

- health-data REAL: 요청 userId 가 `DASHBOARD_USER_ID` 와 정확히 같을 때만 조회하고, 다르면 404 입니다.
  이 확인은 Athena 설정을 읽거나 클라이언트를 만들기 전에 이루어집니다.
- dashboard REAL: 요청에서 사용자를 받지 않고 `DASHBOARD_USER_ID` 사용자만 조회합니다.

## 데이터 처리 구조

```text
요청 → lambda_function (라우팅/검증)
   ├─ health-data → data_source.select_health_data_builder()
   │                   ├─ mock → mock_data.build_health_data_mock()
   │                   └─ real → real_health_data.build_real_health_data()
   │                              스위치 → 입력 검증 → 접근 대상 확인 → Athena 조회
   │                              → mappers → health_service → {userId, range, items}
   ├─ /dashboard  → data_source.select_dashboard_builder()
   │                   ├─ mock → dashboard_mock_data.build_dashboard_mock()
   │                   └─ real → dashboard_data.build_real_dashboard()
   │                              스위치 → DASHBOARD_USER_ID → Athena 조회 → mappers
   │                              → health_service(사용자 필터) → dashboard_service(주간 통계)
   └─ /ai-guide   → dashboard_mock_data.build_ai_guide_mock()
```

### `/dashboard` REAL 모드의 항목별 데이터 출처

| 항목 | REAL 모드 내용 |
| ---- | -------------- |
| `summaryStats` | **steps 카드 1개만 실제 데이터.** 수면·심박·점수 카드는 넣지 않음 |
| `timeseries.steps` | **실제 데이터** (기준 주 중 데이터가 있는 날만) |
| `timeseries.sleep`, `heartRate` | `[]` — 데이터 없음. 임의 수치를 만들지 않음 |
| `sleepStages` | `{"totalLabel": "데이터 없음", "segments": []}` |
| `user` | 개발용 데모 표시 문구. 사용자 ID 는 넣지 않음 |
| `anomalies`, `aiGuide`, `notifications` | `[예시]` 표시가 있는 MOCK (AI/ML·SNS 연동 전) |

### 걸음 수 주간 통계 규칙 (임시 처리 방식, 프론트 협의 필요)

- 기준 주: 데이터 중 걸음 수가 있는 **가장 최근 날짜**가 속한 주(월~일). 실제 Fitbit 데이터가 2016년이라
  오늘 날짜를 기준으로 하지 않습니다. `deltaLabel` 에 기준 주 기간을 표시합니다.
- 하루 평균: 기준 주에서 걸음 수가 있는 날만 평균. **데이터가 없는 날을 0걸음으로 보지 않습니다.**
  (기록된 0걸음은 포함)
- 지난주 대비: `(이번 주 평균 - 지난주 평균) / 지난주 평균 × 100`, 정수 반올림(0.5 는 0에서 먼 쪽).
  **지난주 데이터가 없거나 지난주 평균이 0이면 `delta` 를 `null` 로 둡니다.** (0% 로 표시하지 않음)
  ⚠️ API.md 의 `delta` 타입(number)과 다르므로 프론트 확인 필요.
- 시계열: 데이터가 없는 요일은 넣지 않으므로 7개보다 적을 수 있습니다. `anomaly` 는 항상 `false`.
- 걸음 수로 쓸 수 없는 값(None, 음수 등)과 같은 날짜의 서로 다른 값은 제외합니다.
- 조회 결과가 `ATHENA_MAX_ROWS` 에 도달하면 최근 주를 보장할 수 없으므로 503 입니다.

## 로컬 테스트 실행 방법

아래 명령은 모두 `backend/` 폴더에서 실행합니다.

### 1) 가상환경 활성화 (Windows / cmd)
```bat
.venv\Scripts\activate
```

### 2) 단위 테스트 실행
```bat
python -m unittest discover -s tests -v
```

가상환경을 활성화하지 않고 바로 실행하려면(권장, 경로 문제 예방):
```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

- 외부 패키지가 필요 없으므로 `pip install` 없이 바로 실행됩니다. (boto3 미설치 환경에서도 실행)
- **AWS 에 접속하지 않습니다.** Athena 는 가짜 클라이언트를 사용하고, 실수로 실제 클라이언트를
  만들려 하면 테스트가 실패하도록 차단합니다. 테스트 데이터는 모두 가상 값입니다.
- 반드시 `backend/` 폴더에서 실행해야 `tests` 패키지를 찾을 수 있습니다.
- 테스트는 개발 PC 의 `DATA_SOURCE`, `ENABLE_REAL_DATA_TESTING`, `DASHBOARD_USER_ID`, `ATHENA_*`
  설정과 관계없이 같은 결과를 냅니다. (테스트마다 환경변수를 격리)

### 3) 테스트 현황 (Python 3.13 기준, 총 272개 통과)

| 파일 | 테스트 수 |
| ---- | --------- |
| `tests/test_lambda.py` | 45 |
| `tests/test_mappers.py` | 30 |
| `tests/test_health_service.py` | 28 |
| `tests/test_data_source.py` | 20 |
| `tests/test_athena_repository.py` | 44 |
| `tests/test_real_data_source.py` | 36 |
| `tests/test_dashboard.py` | 24 |
| `tests/test_dashboard_service.py` | 26 |
| `tests/test_dashboard_real.py` | 19 |
| **합계** | **272** |

### (참고) 특정 테스트 파일만 실행
```bat
python -m unittest tests.test_lambda -v
```
