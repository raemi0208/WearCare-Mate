# WearCare Mate Backend

AWS Lambda와 API Gateway 기반 백엔드 서비스

## 담당 기능
- REST API 개발
- AI/ML 서비스 연동
- Amazon SNS 알림
- 오류 처리 및 AWS 인프라 관리

## 개발 상태

> ⚠️ **AWS Lambda / API Gateway 는 아직 배포하지 않았습니다.**
> 현재 모든 기능은 로컬 단위 테스트로만 검증되었으며, AWS 서비스(Athena, Timestream,
> SageMaker, Bedrock, SNS)와의 실제 연동 코드는 없습니다.

- [x] `GET /health` 헬스체크
- [x] `GET /users/{userId}/health-data` — MOCK 응답 (데이터 소스 전환 구조 포함)
- [x] `GET /users/{userId}/anomalies` — MOCK 응답
- [x] `GET /users/{userId}/guides` — MOCK 응답
- [x] Fitbit 활동 데이터 매핑 및 health-data 응답 조립 (순수 함수, 아직 API 미연결)
- [x] 예상하지 못한 예외 → 500, 데이터 소스 사용 불가 → 503 처리
- [ ] 실제 데이터 저장소(Athena 또는 Timestream) 조회 — 저장소 미확정으로 미구현
- [ ] `POST /users/{userId}/notifications/subscriptions` (SNS) — 설계 후보
- [ ] 인증·인가
- [ ] AWS 배포

## 폴더 구조
```text
backend/
├── docs/
│   └── api-spec.md            # REST API 명세 초안
├── src/
│   ├── __init__.py
│   ├── lambda_function.py     # Lambda 핸들러: 라우팅, 오류 처리(400/404/500/503)
│   ├── data_source.py         # DATA_SOURCE 환경변수로 health-data 데이터 소스 선택
│   ├── mock_data.py           # 개발/테스트 전용 가상 MOCK 데이터
│   ├── mappers.py             # Fitbit 데이터 행 → API 활동 항목 변환
│   └── health_service.py      # 사용자·날짜 필터링 및 health-data 응답 조립
├── tests/
│   ├── __init__.py
│   ├── test_lambda.py         # 핸들러/라우팅/오류 처리 테스트
│   ├── test_data_source.py    # 데이터 소스 전환 테스트
│   ├── test_mappers.py        # Fitbit 매핑 테스트
│   └── test_health_service.py # 응답 조립 테스트
├── requirements.txt           # 외부 의존성 목록(현재 없음)
└── README.md
```

## API 엔드포인트

이벤트 기준: API Gateway HTTP API, payload format 2.0

| 메서드 | 경로 | 설명 | 현재 응답 |
| ------ | ---- | ---- | --------- |
| GET | `/health` | 헬스체크 | `{"status": "ok", "service": "WearCare Mate Backend"}` |
| GET | `/users/{userId}/health-data` | 건강 데이터 조회 | `DATA_SOURCE` 설정에 따름 (아래 참고) |
| GET | `/users/{userId}/anomalies` | 이상탐지 결과 조회 | 항상 MOCK |
| GET | `/users/{userId}/guides` | 건강 행동 가이드 조회 | 항상 MOCK (disclaimer 포함) |

- MOCK 응답에는 `"mock": true` 와 `"_note"` 가 포함되며, 모든 값은 가상 데이터입니다.
- MOCK 응답의 `from`/`to`/`severity`/`anomalyId` 쿼리는 요청값을 그대로 돌려줄 뿐
  실제 필터링은 하지 않습니다.
- 자세한 요청·응답 형식은 [`docs/api-spec.md`](docs/api-spec.md) 를 참고하세요.

### 오류 응답

모든 오류는 `{"error": "...", "message": "..."}` 형식의 JSON 입니다.

| 상태 코드 | error | 발생 조건 |
| --------- | ----- | --------- |
| 400 | `bad_request` | 이벤트 형식 오류, 빈 userId, 쿼리 파라미터 형식 오류 |
| 404 | `not_found` | 지원하지 않는 경로 또는 메서드 |
| 500 | `internal_error` | 처리되지 않은 예외, `DATA_SOURCE` 설정 오류 |
| 503 | `unavailable` | 데이터 소스 사용 불가 (현재는 `DATA_SOURCE=real`) |

- 500/503 응답은 고정 문구만 사용하며, 예외 메시지·스택 트레이스·사용자 ID 를 포함하지 않습니다.
- 로그에는 예외 타입 이름만 기록합니다.
- 인증·인가는 아직 구현되지 않았습니다. userId 만으로 데이터 접근이 허용된 것이 아닙니다.

## 데이터 처리 구조

```text
요청 → lambda_function (라우팅/검증)
          └─ health-data → data_source.select_health_data_builder()
                              ├─ mock → mock_data.build_health_data_mock()  ← 현재 사용
                              └─ real → 미구현 (503)

[준비 완료, API 미연결]
원본 행(CSV/조회 결과) → mappers.map_fitbit_activity_rows()
                       → health_service.build_health_data_response()
```

- `mappers.py`: `Id`→`userId`(문자열), `ActivityDate`→`date`(ISO), `TotalSteps`, `Calories`,
  `VeryActiveMinutes`(값이 있을 때만) 를 매핑합니다. CSV 형식(`TotalSteps`)과
  소문자 형식(`totalsteps`) 컬럼명을 모두 지원합니다.
  `TotalDistance` 는 단위 미확정으로 매핑하지 않고, 수면 데이터는 제외합니다.
- `health_service.py`: 요청 사용자 ID 와 일치하는 행만 남기고, 유효한 ISO 날짜의
  `from`/`to` 로 필터링합니다. 날짜가 없거나 잘못된 행은 제외합니다.
  응답은 `{userId, range, items}` 형식입니다.

## `DATA_SOURCE` 환경변수

health-data API 의 데이터 소스를 선택합니다. (anomalies, guides, /health 에는 영향 없음)

| 값 | 동작 |
| -- | ---- |
| 설정 안 함 (기본값) | `mock` 과 동일 |
| `mock` | 기존 MOCK 응답 (200) |
| `real` | ⚠️ **실제 AWS 조회는 아직 구현되지 않았습니다.** MOCK 으로 대체하지 않고 503 을 반환합니다. |
| 그 외 값, 빈 문자열 | 설정 오류로 처리해 500 을 반환합니다. MOCK 으로 조용히 바꾸지 않습니다. 로그에 `DataSourceConfigError` 가 남습니다. |

- 값의 앞뒤 공백과 대소문자는 무시합니다. (예: ` MOCK ` → `mock`)
- 환경변수는 요청마다 읽습니다.

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

- 외부 패키지가 필요 없으므로 `pip install` 없이 바로 실행됩니다.
- AWS 에 접속하지 않으며, 테스트 데이터는 모두 가상 값입니다.
- 반드시 `backend/` 폴더에서 실행해야 `tests` 패키지를 찾을 수 있습니다.
- 테스트는 개발 PC 의 `DATA_SOURCE` 설정과 관계없이 같은 결과를 냅니다.
  (`test_lambda.py` 는 `DATA_SOURCE=mock` 으로, `test_data_source.py` 는 테스트마다
  환경변수를 격리해 실행합니다.)

### 3) 테스트 현황 (Python 3.13 기준, 총 123개 통과)

| 파일 | 테스트 수 |
| ---- | --------- |
| `tests/test_lambda.py` | 45 |
| `tests/test_mappers.py` | 30 |
| `tests/test_health_service.py` | 28 |
| `tests/test_data_source.py` | 20 |
| **합계** | **123** |

### (참고) 특정 테스트 파일만 실행
```bat
python -m unittest tests.test_lambda -v
```
