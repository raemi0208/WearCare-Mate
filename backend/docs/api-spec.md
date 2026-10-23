# WearCare Mate 백엔드 REST API 명세 (초안)

> 상태: **초안(Draft)** · 작성: 파트3 백엔드/인프라 담당
> 목적: 프론트엔드 · 데이터 · AI/ML 팀과 협의하기 위한 API 계약(Contract) 초안

이 문서는 아직 **확정본이 아닙니다.** 팀 협의로 바뀔 수 있으며,
각 항목에는 "확정된 사실"과 "임시 설계안(MOCK/미확정)"을 명확히 구분해 표시했습니다.

---

## 0. 읽는 방법 (초보자용 안내)

- **엔드포인트(Endpoint)**: 클라이언트가 요청을 보내는 주소(URL) + HTTP 메서드 조합입니다. 예) `GET /health`
- **경로 파라미터(Path Parameter)**: 주소 안에 들어가는 값입니다. 예) `/users/{userId}` 에서 `{userId}`.
- **쿼리 파라미터(Query Parameter)**: 주소 뒤 `?key=value` 형태로 붙는 값입니다. 예) `?from=2016-03-25`.
- **상태 코드(Status Code)**: 요청 결과를 숫자로 알려주는 값입니다. 200은 성공, 400/404는 요청 문제, 5xx는 서버 문제입니다.
- 🟢 **확정**: README/실제 데이터/구현 코드로 확인된 사실
- 🟡 **MOCK / 미확정**: 아직 합의되지 않은 임시 설계안. 실제 값/구조는 바뀔 수 있음

---

## 1. 공통 규칙 (임시 설계안 🟡)

### 1.1 Base URL
- 🟡 미확정: API Gateway 배포 후 확정됩니다. 문서에서는 상대 경로만 표기합니다.
- 이벤트 형식: 🟢 **API Gateway HTTP API, payload format 2.0** 기준 (현재 구현된 `GET /health` 와 동일).

### 1.2 공통 응답 형식
- 모든 응답 본문은 `application/json` 입니다. (🟢 `GET /health` 구현 확인)
- 성공 응답은 각 API별 본문 구조를 따릅니다.

### 1.3 공통 오류 응답 형식 (🟢 현재 코드 기준 + 🟡 확장 제안)
현재 `lambda_function.py` 는 아래 형태로 오류를 반환합니다 (🟢 확인됨).

```json
{
  "error": "not_found",
  "message": "지원하지 않는 요청입니다: GET /unknown"
}
```

🟡 제안: 디버깅과 프론트 처리를 쉽게 하기 위해 아래처럼 확장하는 것을 협의합니다.

```json
{
  "error": "not_found",
  "message": "요청한 리소스를 찾을 수 없습니다.",
  "requestId": "mock-1234-5678",
  "timestamp": "2026-10-23T00:00:00Z"
}
```

### 1.4 공통 오류 코드 표 (🟡 제안)
| 상태 코드 | error 값         | 의미                                    |
| --------- | ---------------- | --------------------------------------- |
| 400       | `bad_request`    | 요청 형식/파라미터가 잘못됨             |
| 401       | `unauthorized`   | 인증 실패 (🟡 인증 방식 미정)           |
| 403       | `forbidden`      | 접근 권한 없음 (🟡 인가 방식 미정)      |
| 404       | `not_found`      | 리소스/경로 없음                        |
| 500       | `internal_error` | 서버 내부 오류                          |
| 503       | `unavailable`    | 외부 의존 서비스(Timestream 등) 불가    |

### 1.5 인증·인가 (🟡 미정 — 매우 중요)
- 🟡 **인증/인가 방식은 아직 정해지지 않았습니다.**
- 이 문서의 `{userId}` 경로는 **"그 사용자의 데이터에 접근해도 된다"는 것을 보장하지 않습니다.**
- 즉, `userId` 만으로 실제 데이터 접근을 허용한다고 가정하면 안 됩니다. (요청자가 해당 userId 본인인지 확인하는 절차 필요)
- 실제 구현 시 `401/403` 처리와 토큰(예: Cognito/JWT) 도입 여부를 팀과 협의해야 합니다.

### 1.6 건강 가이드의 성격 (🟢 전제)
- 🟢 본 서비스의 가이드는 **의료 진단·치료 지시가 아니라 일반적인 생활 습관 권고**입니다.
- 모든 가이드 응답에는 면책/안내 문구(disclaimer)를 포함하도록 설계합니다 (아래 4.4 참고).

---

## 2. 참고한 실제 데이터 (🟢 확인된 사실)

데이터 파트의 Timestream 스키마는 🟡 **미확정**이지만, `Database/data/` 폴더에 실제 CSV 샘플이 있어
응답 필드 설계의 근거로 사용했습니다. (이 파일들은 수정하지 않았습니다.)

### 2.1 `FitBit data.csv` 컬럼 (🟢 실제 확인)
`Id, ActivityDate, TotalSteps, TotalDistance, TrackerDistance, LoggedActivitiesDistance, VeryActiveDistance, ModeratelyActiveDistance, LightActiveDistance, SedentaryActiveDistance, VeryActiveMinutes, FairlyActiveMinutes, LightlyActiveMinutes, SedentaryMinutes, Calories`
- 사용자 식별자 `Id` 와 날짜 `ActivityDate` 가 존재 → 활동량/칼로리 지표의 근거.

### 2.2 `wearable_tech_sleep_quality_1.csv` 컬럼 (🟢 실제 확인)
`Heart_Rate_Variability, Body_Temperature, Movement_During_Sleep, Sleep_Duration_Hours, Sleep_Quality_Score, Caffeine_Intake_mg, Stress_Level, Bedtime_Consistency, Light_Exposure_hours`
- ⚠️ 🟢 이 파일에는 **사용자 ID와 타임스탬프 컬럼이 없습니다.** → 수면 데이터를 userId/시간과 어떻게 연결할지 데이터 파트와 협의 필요.

> 아래 API 응답의 수치는 위 컬럼을 참고한 **예시(MOCK)** 입니다. 실제 필드명/단위는 Timestream 스키마 확정 후 맞춥니다.

---

## 3. API 요약 표

| # | 메서드 | 경로                                              | 목적                 | 상태            | 주요 의존 파트     |
| - | ------ | ------------------------------------------------- | -------------------- | --------------- | ------------------ |
| 1 | GET    | `/health`                                         | 서버 상태 확인       | 🟢 구현 완료     | 백엔드             |
| 2 | GET    | `/users/{userId}/health-data`                     | 건강 데이터 조회     | 🟡 초안          | 데이터(Timestream) |
| 3 | GET    | `/users/{userId}/anomalies`                       | 이상탐지 결과 조회   | 🟡 초안          | AI/ML(SageMaker)   |
| 4 | GET    | `/users/{userId}/guides`                          | 건강 행동 가이드 조회 | 🟡 초안          | AI/ML(Bedrock)     |
| 5 | POST   | `/users/{userId}/notifications/subscriptions`     | 알림 수신 등록       | 🟡 설계 후보     | 백엔드(SNS)        |

---

## 4. API 상세

### 4.1 GET /health — 서버 상태 확인 (🟢 구현 완료)

- **목적**: 서버/Lambda가 정상 동작하는지 확인하는 헬스체크. 모니터링·배포 점검용.
- **메서드/경로**: `GET /health`
- **요청 파라미터**: 없음
- **응답 예시 (200)** — 🟢 실제 구현 확인:
```json
{
  "status": "ok",
  "service": "WearCare Mate Backend"
}
```
- **상태 코드**
  | 코드 | 의미 |
  | ---- | ---- |
  | 200  | 정상 |
  | 404  | 지원하지 않는 경로/메서드 |
  | 400  | 잘못된 이벤트 형식 |
- **담당 파트 / 필요 데이터**: 백엔드 / 없음
- **합의 필요 사항**: (없음 — 이미 구현/테스트 완료)

---

### 4.2 GET /users/{userId}/health-data — 건강 데이터 조회 (🟡 초안)

- **목적**: 특정 사용자의 수면·심박·활동량 등 웨어러블 시계열 데이터를 기간별로 조회.
- **메서드/경로**: `GET /users/{userId}/health-data`
- **요청 파라미터**
  | 위치   | 이름     | 필수 | 예시         | 설명                                   |
  | ------ | -------- | ---- | ------------ | -------------------------------------- |
  | path   | userId   | ✅   | `u-1001`     | 사용자 식별자 (🟡 형식 미정)           |
  | query  | from     | ⬜   | `2016-03-25` | 조회 시작일 (🟡 기본값/형식 미정)      |
  | query  | to       | ⬜   | `2016-03-31` | 조회 종료일                            |
  | query  | metric   | ⬜   | `sleep`      | `sleep` / `activity` / `heart` 등 (🟡) |
  | query  | interval | ⬜   | `day`        | 집계 단위 (🟡 Timestream 설계 의존)    |

- **응답 예시 (200)** — 🟡 MOCK (필드는 2장의 실제 CSV 컬럼 참고):
```json
{
  "userId": "u-1001",
  "range": { "from": "2016-03-25", "to": "2016-03-26" },
  "_note": "MOCK 데이터입니다. 실제 필드/단위는 Timestream 스키마 확정 후 변경됩니다.",
  "items": [
    {
      "date": "2016-03-25",
      "activity": {
        "totalSteps": 11004,
        "totalDistanceKm": 7.11,
        "calories": 1819,
        "veryActiveMinutes": 33
      },
      "sleep": {
        "sleepDurationHours": 6.2,
        "sleepQualityScore": 7.6,
        "heartRateVariability": 67.2,
        "stressLevel": 3.7
      }
    }
  ]
}
```

- **상태 코드**
  | 코드 | 의미 |
  | ---- | ---- |
  | 200  | 조회 성공 |
  | 400  | 날짜 형식 오류 등 잘못된 파라미터 |
  | 401/403 | 🟡 인증/인가 실패 (방식 미정) |
  | 404  | 사용자 없음 또는 데이터 없음 |
  | 503  | 🟡 Timestream 등 데이터 소스 접근 불가 |

- **담당 파트 / 필요 데이터**: 데이터 파트(Timestream) / 사용자별·시간별 측정값, 표준 단위
- **합의 필요 사항**
  - 🟡 Timestream의 measure/dimension 구조 (예: dimension=`userId`, measure=`steps`·`sleep_quality` …)
  - 🟡 수면 CSV에 userId/타임스탬프가 없음 → 어떻게 사용자·시간과 매핑하는가
  - 🟡 날짜 형식(로컬 vs UTC, ISO 8601 여부), 기본 조회 기간, 페이지네이션 방식

---

### 4.3 GET /users/{userId}/anomalies — 이상탐지 결과 조회 (🟡 초안)

- **목적**: AI/ML(SageMaker) 모델이 탐지한 사용자별 이상 패턴(Anomaly) 목록 조회.
- **메서드/경로**: `GET /users/{userId}/anomalies`
- **요청 파라미터**
  | 위치   | 이름     | 필수 | 예시         | 설명                                   |
  | ------ | -------- | ---- | ------------ | -------------------------------------- |
  | path   | userId   | ✅   | `u-1001`     | 사용자 식별자                          |
  | query  | from     | ⬜   | `2016-03-25` | 조회 시작일                            |
  | query  | to       | ⬜   | `2016-03-31` | 조회 종료일                            |
  | query  | severity | ⬜   | `high`       | 심각도 필터 (🟡 값 체계 미정)          |

- **응답 예시 (200)** — 🟡 MOCK (AI/ML 결과 JSON 미확정):
```json
{
  "userId": "u-1001",
  "_note": "MOCK 데이터입니다. 이상탐지 결과 JSON 구조는 AI/ML 파트와 미확정 상태입니다.",
  "items": [
    {
      "anomalyId": "mock-anomaly-001",
      "detectedAt": "2016-03-25T23:10:00Z",
      "metric": "sleep_quality",
      "severity": "medium",
      "score": 0.82,
      "description": "평소 대비 수면 질 점수가 크게 낮아졌습니다."
    }
  ]
}
```

- **상태 코드**: 200 / 400 / 401·403(🟡) / 404 / 503(🟡 모델 결과 저장소 접근 불가)
- **담당 파트 / 필요 데이터**: AI/ML 파트(SageMaker) / 이상탐지 결과 저장 위치·스키마
- **합의 필요 사항**
  - 🟡 이상탐지 결과 JSON 필드 (score 범위, severity 값 집합, metric 명칭)
  - 🟡 결과 저장 방식 (Timestream / S3 / DB 중 어디에서 백엔드가 읽는가)
  - 🟡 실시간 탐지인지, 배치 결과 조회인지

---

### 4.4 GET /users/{userId}/guides — 건강 행동 가이드 조회 (🟡 초안)

- **목적**: 이상 패턴을 바탕으로 생성형 AI(Bedrock)가 만든 **일반적인 생활 습관 권고** 조회.
- **메서드/경로**: `GET /users/{userId}/guides`
- **⚠️ 전제 (🟢)**: 의료 진단/치료 지시가 아님. 응답에 면책 문구를 반드시 포함.
- **요청 파라미터**
  | 위치   | 이름      | 필수 | 예시                | 설명                          |
  | ------ | --------- | ---- | ------------------- | ----------------------------- |
  | path   | userId    | ✅   | `u-1001`            | 사용자 식별자                 |
  | query  | anomalyId | ⬜   | `mock-anomaly-001`  | 특정 이상 패턴에 대한 가이드 (🟡) |

- **응답 예시 (200)** — 🟡 MOCK:
```json
{
  "userId": "u-1001",
  "_note": "MOCK 데이터입니다. Bedrock 프롬프트/출력 형식은 AI/ML 파트와 미확정 상태입니다.",
  "disclaimer": "본 안내는 일반적인 생활 습관 권고이며, 의학적 진단이나 치료를 대체하지 않습니다. 증상이 지속되면 전문가와 상담하세요.",
  "items": [
    {
      "guideId": "mock-guide-001",
      "relatedAnomalyId": "mock-anomaly-001",
      "title": "규칙적인 취침 시간 유지하기",
      "message": "최근 수면의 질이 낮아졌어요. 매일 비슷한 시간에 잠자리에 들면 수면 리듬을 안정시키는 데 도움이 됩니다.",
      "category": "sleep",
      "createdAt": "2016-03-26T08:00:00Z"
    }
  ]
}
```

- **상태 코드**: 200 / 400 / 401·403(🟡) / 404 / 503(🟡 Bedrock/저장소 접근 불가)
- **담당 파트 / 필요 데이터**: AI/ML 파트(Bedrock) / 가이드 텍스트, 이상탐지 결과 연계
- **합의 필요 사항**
  - 🟡 가이드 생성 시점 (조회 시 실시간 생성 vs 사전 생성 후 저장)
  - 🟡 가이드 출력 형식(카테고리 집합, 길이 제한, 다국어 여부)
  - 🟢 면책 문구 문안 확정 (법무/기획 검토 권장)

---

### 4.5 POST /users/{userId}/notifications/subscriptions — 알림 수신 등록 (🟡 설계 후보)

- **목적**: 사용자가 이상 패턴/가이드 알림을 받도록 구독을 등록. (Amazon SNS 연동 예정)
- **메서드/경로**: `POST /users/{userId}/notifications/subscriptions`
- **요청 파라미터**
  | 위치 | 이름    | 필수 | 예시       | 설명                                 |
  | ---- | ------- | ---- | ---------- | ------------------------------------ |
  | path | userId  | ✅   | `u-1001`   | 사용자 식별자                        |
  | body | channel | ✅   | `email`    | 🟡 알림 채널 (email/sms/web-push 미정) |
  | body | target  | ✅   | `a@b.com`  | 🟡 수신 대상(이메일/엔드포인트 등)   |

- **요청 본문 예시** — 🟡 MOCK:
```json
{
  "channel": "email",
  "target": "user@example.com"
}
```

- **응답 예시 (201)** — 🟡 MOCK:
```json
{
  "userId": "u-1001",
  "_note": "MOCK 응답입니다. SNS 연동 전까지 실제 구독은 생성되지 않습니다.",
  "subscriptionId": "mock-sub-001",
  "status": "pending_confirmation",
  "channel": "email"
}
```

- **상태 코드**
  | 코드 | 의미 |
  | ---- | ---- |
  | 201  | 구독 등록(또는 요청) 성공 |
  | 400  | 채널/대상 형식 오류 |
  | 401/403 | 🟡 인증/인가 실패 |
  | 409  | 🟡 이미 등록된 구독 (중복 처리 정책 미정) |
  | 503  | 🟡 SNS 접근 불가 |

- **담당 파트 / 필요 데이터**: 백엔드(SNS) / 구독 정보 저장 위치
- **합의 필요 사항 (SNS 전달 방식은 확정하지 않음 🟡)**
  - 🟡 **웹 푸시 전달 방식 미확정** — SNS로 웹 푸시가 바로 가능한지, 아니면 이메일/SMS + 별도 푸시 서비스(FCM 등) 조합인지 추가 협의
  - 🟡 이메일/SMS 구독의 확인(confirmation) 플로우 처리
  - 🟡 구독 정보 저장소(DB/파일/DynamoDB 등) 선정
  - 🟡 구독 해제(DELETE) 엔드포인트 필요 여부

---

## 5. 확정된 사실 vs 미확정 요약

### 🟢 확정된 사실
- `GET /health` 는 구현·테스트 완료 (200/404/400 동작, unittest 6개 통과).
- 이벤트 형식은 API Gateway HTTP API payload 2.0.
- 응답은 JSON, 오류는 `{error, message}` 형태.
- 실제 샘플 데이터 컬럼(FitBit/수면 CSV)과 README의 아키텍처·파트 분배.
- 가이드는 의료 행위가 아닌 생활 습관 권고 (면책 문구 포함 원칙).

### 🟡 미확정 (팀 협의 필요)
- Timestream 스키마(measure/dimension), 날짜·단위 표준, 페이지네이션.
- 수면 CSV의 userId/타임스탬프 부재 → 사용자·시간 매핑 방법.
- 이상탐지 결과 JSON 구조 및 저장 위치.
- 가이드 생성/저장 방식 및 출력 형식.
- 인증·인가 방식(401/403, 토큰 도입 여부).
- SNS 알림 채널 및 웹 푸시 전달 방식.
- Base URL / 배포 환경.

---

## 6. 팀별 확인 질문 (협의용 체크리스트)

### 데이터 파트에게
1. Timestream의 dimension/measure 구조를 어떻게 정의하나요? (`userId`가 dimension인가요?)
2. 수면 데이터(`wearable_tech_sleep_quality_1.csv`)에는 userId·타임스탬프가 없는데, 어떻게 사용자/시간과 연결하나요?
3. 날짜/시간은 UTC로 저장하나요, 로컬 시간인가요? 표준 단위(걸음·거리·시간)는 무엇인가요?
4. 백엔드가 데이터를 읽는 인터페이스는 Timestream 직접 쿼리인가요, 중간 API인가요?

### AI/ML 파트에게
5. 이상탐지 결과 JSON의 필드와 값 체계(score 범위, severity 집합)는 어떻게 되나요?
6. 이상탐지 결과는 어디에 저장되며 백엔드가 어떻게 읽나요? (실시간 vs 배치)
7. 가이드는 조회 시 실시간 생성인가요, 미리 생성 후 저장인가요? 출력 형식/카테고리는?

### 프론트엔드 파트에게
8. 조회 API의 기본 기간·페이지네이션·필터는 어떤 UX를 전제로 하나요?
9. 오류 응답에 `requestId`/`timestamp` 확장이 필요한가요?

### 팀 공통 (백엔드 주도)
10. 인증·인가 방식(예: Cognito/JWT)을 도입하나요? `userId` 접근 통제는 어떻게 하나요?
11. SNS 알림 채널(email/sms/web-push)과 **웹 푸시 전달 방식**을 어떻게 가져가나요?
12. 구독 정보 저장소와 구독 해제 기능이 필요한가요?

---

> 이 문서는 초안이며, 위 체크리스트가 합의되는 대로 🟡 항목을 🟢(확정)으로 갱신합니다.
