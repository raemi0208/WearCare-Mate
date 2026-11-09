# AWS 연동 검증 기록과 배포 절차

## 검증 범위 (2026-10-31)

- 공개 API: https://j3cwx5vmwj.execute-api.ap-northeast-2.amazonaws.com
  - GET /health, /dashboard, /ai-guide의 외부 호출 확인. 현재 예시 데이터 모드.
  - HTTP API의 `$default` 스테이지 사용. `default` 스테이지 이름을 경로에 붙인 주소는
    기존 라우터와 맞지 않았으므로 위 기본 주소를 사용합니다.
- wearcare-mate-athena-test: 서울의 별도 함수, API Gateway/Function URL 미연결.
  - 실제 Athena 활동 데이터 조회 200.
  - 백엔드 -> AI/ML Lambda 호출과 응답 검증 200, normal.
  - 실제 GET /dashboard 및 /ai-guide 형식 이벤트를 콘솔에서 실행해 응답 변환 확인.
  - 검증 사용자 ID: 1503960366 (Fitbit 공개 데이터), 기준일: 2016-04-10.
- wearcare-mate-ml: 서울. Athena 과거 기록 조회를 통한 normal 판정 확인.
  가상 과거 기록과 감소한 걸음 수 입력으로 Bedrock 3줄 가이드 생성 및 warnings=[] 확인.
- 이상 경로 중 "가상 입력 → 실제 AI/ML Lambda → 실제 Bedrock 가이드 → 백엔드 화면용 변환"은
  아래 가상 이상 입력 검증(2026-11-02)으로 확인했습니다.
  Athena 실제 데이터에서 이상이 판정되어 가이드까지 반환되는 흐름과 공개 API 경로는 아직 검증하지 않았습니다.
- 프론트엔드: 로컬 http://localhost:3000에서 공개 예시 API 기반 대시보드·AI 가이드 표시와
  재조회 시 /ai-guide 200을 사용자가 확인했습니다(아래 CORS 참고). 실제 생성 가이드의 브라우저 표시는 미검증.

## 가상 이상 입력 검증 (2026-11-02, 사용자 콘솔 실행)

검증 범위: 가상 입력 → 실제 wearcare-mate-ml 호출 → 실제 Bedrock 가이드 생성 → 기존 백엔드 화면용 변환.
Athena 실제 데이터, 공개 API 경로, 브라우저에서 실제 생성 가이드를 표시하는 과정은 포함하지 않습니다.

- 함수: wearcare-mate-ml-virtual-check (ap-northeast-2, API Gateway 미연결)
- 핸들러: `src.ml_virtual_anomaly_check.lambda_handler`, 테스트 이벤트 `{}`, 실행 시간 약 13.8초
- 환경변수: `ML_FUNCTION_NAME=wearcare-mate-ml`, `ML_REGION=ap-northeast-2`, `ML_TIMEOUT_SECONDS=25`
- AI/ML 에 보낸 가상 입력 (AI/ML lambda_handler 형식, history_steps 가 있어 Athena 미조회):
  `{"user_id": "test-user", "date": "2026-10-30", "metrics": {"steps": 1000},
  "history_steps": [10000, 10500, 9800, 10200, 10100, 9900]}`

확인 결과 (Lambda 실행 성공과 응답 내부 판정 모두 확인):

| 항목 | 값 |
|---|---|
| Lambda 실행 | 성공, 응답 `statusCode` 200 |
| 응답 내부 판정 | `verdict` PASS, `inputKind` virtual, `mlInvoked` true |
| 확인 항목 6개 | mlResponseValid, statusIsAnomaly, stepAnomalyDetected, guideGenerated, screenGuideGenerated, screenGuideHasActions 모두 true |
| AI/ML 판정 | status anomaly, overallSeverity high, ACTIVITY_DROP (baselineMean 10083, zScore -18.17, dropPct -90.1) |
| 가이드 | guideGenerated true, guideWarnings [], guideModelId `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| modelVersion | activity-zscore-v0.2+pop-v0.3 |
| 화면용 aiGuide | status generated, analysisStatus anomaly, referenceDate 2026-10-30, updatedAt 2026-11-02T22:49:24+09:00, actions 1개 |
| 화면용 anomalies[0] | severity danger |

생성된 가이드 본문 (Bedrock 출력, 일반 생활 습관 권고):

> 오늘 걸음 수가 1,000걸음으로 평소 10,083걸음보다 크게 적었어요.
> 오늘 하루 중 10분 정도라도 산책이나 가벼운 움직임을 의식적으로 만들어보세요.
> 이런 패턴이 계속되거나 몸이 무거운 느낌이 지속되면 전문가와 상담해보세요.

### AWS 배포본과 Git 수정본의 차이

- 위 검증에 쓴 배포 ZIP의 화면용 `anomalies[].desc`는 "기준일 걸음 수 1,000보 · 과거 기록 평균 10,083보"였습니다.
- 이후 `ai_service.py`에서 단위를 "걸음"으로 통일했습니다
  ("기준일 걸음 수 1,000걸음 · 과거 기록 평균 10,083걸음"). **이 수정은 아직 AWS에 배포하지 않았습니다.**
- 요약 카드 `summaryStats[].unit`의 "보"는 프론트엔드 API.md 예시 값이라 이번에 바꾸지 않았습니다(팀 협의 대상).

## AI/ML v0.4 반영 (백엔드 로컬 수정, 2026-11-02 · 아직 미배포)

이번 변경은 로컬 코드·테스트만 완료했습니다. AWS 배포·Lambda 호출·SNS 발송·환경변수 변경은 하지 않았습니다.
기준 명세: GitHub `origin/ai-ml` @ `1956156a`(2026-11-03)의 `docs/ml-interface-spec.md` **v0.4**
(다운로드본 `~/Downloads/ml-interface-spec.md`와 내용 동일 확인). `AI_ML/lambda_handler.py`,
`AI_ML/detector.py`도 같은 커밋 기준으로 확인했습니다. 단, 커밋된 `docs/sample_responses.json`에는
아직 `tracked_minutes`·`alert_sent`가 없어, 검증에서는 두 필드를 선택 필드로 둡니다(실제 응답은 포함).

### 1) 기록 시간 전달 (`metrics.tracked_minutes`)

- Athena 조회 컬럼에 활동 시간 네 개를 추가했습니다:
  `veryactiveminutes`, `fairlyactiveminutes`, `lightlyactiveminutes`, `sedentaryminutes`.
- `mappers`는 제공된 컬럼만 `activity`에 넣고, 네 값이 모두 유효한 정수일 때만
  `activity.trackedMinutes`(합계)를 만듭니다. 하나라도 누락·오류면 만들지 않습니다(0으로 채우지 않음).
- `ml_adapter.build_detection_request`는 기준일의 `trackedMinutes`가 있으면
  요청 `metrics.tracked_minutes`로 보내고, 없으면 생략합니다. 유효한 `0`은 그대로 보냅니다.
- **800분 미만 처리는 AI/ML 쪽 규칙이고, 범위는 "걸음 수 판정"뿐입니다.** v0.4 `detector.personal_check`는
  `tracked_minutes < 800`이면 `ACTIVITY_DROP`만 건너뛰고(해당 지표 `insufficient_data`), 수면·HRV·스트레스
  등 다른 지표는 그대로 판정합니다. 백엔드는 합계만 전달하고 `799`/`800`을 구분하지 않고 그대로 보냅니다.
  (로컬 테스트로 passthrough 확인)

### 2) v0.4 응답 처리 (`guide.lines` 보존, 최상위 `alert_sent`)

- `guide.lines` 배열을 검증·보존하고, 화면용 응답의 `aiGuide.lines`로 그대로 전달합니다.
  기존 `aiGuide.text`도 함께 유지합니다. (줄별 표시는 프론트엔드가 `lines`로 처리)
- **`alert_sent`는 ML 응답 최상위 선택 불리언**입니다(명세 7번, 핸들러 `out["alert_sent"]=send_alert(out)`).
  `guide`의 형제이며, `guide`가 `null`(이상 아님·생성 실패)이어도 `true`/`false`가 올 수 있습니다.
  `true` / `false` / **필드 없음**을 구분해 화면용 `aiGuide.alertSent`로 각각 `true` / `false` / `null`로
  전달합니다. (이전 가정이던 `guide.alert_sent` 위치에서 최상위로 수정)
- **SNS 발송은 AI/ML(`wearcare-mate-ml`, 주제 `wearcare-mate-alert`)이 담당합니다.** 백엔드는 발송 로직을
  추가하지 않았고, `alert_sent`는 표시·로그용으로만 전달합니다. 명세 9번 표에는 "백엔드가 medium 이상이면
  SNS 발송"이라는 제안 문구가 남아 있으나, 실제 팀 합의·구현(7번·11번, 핸들러)은 **AI/ML Lambda 발송**이며
  백엔드는 발송하지 않습니다(차이 기록).

### 프론트엔드가 읽을 최종 필드 경로

- 가이드 본문 줄 배열: `GET /ai-guide` 응답의 `lines` (대시보드에서는 `body.aiGuide.lines`).
  - 각 줄을 그대로 한 줄씩 표시하면 됩니다. `text`는 `\n`으로 이어 붙인 전체 문자열입니다.
  - 현 프론트엔드는 `headline`(=lines[0])과 `actions`(=lines[1:2])만 쓰고 있어, `lines` 전체
    줄 표시는 프론트엔드 소스 수정이 필요합니다(이번 백엔드 변경과 분리).
- SNS 발송 여부: `aiGuide.alertSent` (`true`/`false`/`null`).

### 3) 이상 설명 단위

- 이상 설명(`anomalies[].desc`)의 `보 → 걸음` 수정이 이번 변경에도 그대로 포함되어 있습니다
  ("기준일 걸음 수 1,000걸음 · 과거 기록 평균 10,083걸음"). 여전히 AWS에는 미배포 상태입니다.

## AI/ML v0.5 반영 (백엔드 로컬 수정, 2026-11-06 · 아직 미배포)

기준 명세: 다운로드본 `~/Downloads/ml-interface-spec.md` **v0.5**(2026-11-06). 로컬 코드·테스트만 완료했습니다.
커밋된 `sample_responses.json`에는 아직 `notify`·`alert_reason`이 없어, 검증에서는 선택 필드로 둡니다(실제 응답은 포함).

### 1) 요청 최상위 `notify` (불리언)

- `build_detection_request(..., notify=False)` 로 요청 **최상위**에 `notify`를 넣습니다. 기본값 `False`.
- `/dashboard`·`/ai-guide` 조회·재조회 경로는 SNS 발송을 하지 않으므로 항상 `notify: false`를 보냅니다.
  값은 요청에 그대로 실리므로 **같은 요청을 재시도해도 `notify: false`가 유지**됩니다.
- **SNS 발송을 허용하는 일일 평가 경로(`notify=true`)는 별도 작업으로 남깁니다.** SNS 발송 주체는
  AI/ML Lambda(`wearcare-mate-ml`, 주제 `wearcare-mate-alert`)이며 백엔드는 발송하지 않습니다.

### 2) 응답 최상위 `alert_reason` (선택 문자열)

- `alert_reason`을 응답 **최상위** 선택 필드로 검증·보존합니다(명세 7번). `guide`가 `null`이어도 보존합니다.
  v0.4 응답처럼 필드가 없는 경우(`None`)도 유효합니다.
- 값 집합(참고): `sent` / `disabled` / `notify_false` / `below_threshold` / `duplicate` / `failed`.
  집합 밖의 문자열이 와도 거절하지 않고 그대로 보존합니다(AI/ML 이 새 사유를 추가할 수 있으므로).
- 화면용 응답에 `alertReason`을 추가했습니다. 기존 `alertSent`·`lines`는 그대로 유지합니다.

### 프론트엔드 필드 계약 (v0.5 갱신)

- `aiGuide.lines`: 가이드 줄 배열(그대로 표시). `aiGuide.text`: `\n`으로 이은 전체 문자열(배열이 없을 때 대체).
- `aiGuide.alertSent`: `true` / `false` / `null`(필드 없음·가이드 없음). SNS 발송 여부.
- `aiGuide.alertReason`: 발송/미발송 사유 문자열 또는 `null`. `guide`가 없어도 보존됩니다.
- 세 필드 모두 표시·로그용이며 백엔드는 SNS 를 직접 발송하지 않습니다.

## 비공개 wearcare-mate-athena-test 실데이터 경계 검증 (2026-11-06 · 실행 완료)

실제 Athena 데이터로 날짜별 백엔드→AI/ML 경로를 검증하는 콘솔 전용 핸들러입니다. 아래 "실제 AWS
검증 결과" 항목은 발표 PC 로컬 중계 경로(`wearcare-test` 프로필)로 실제 `wearcare-mate-athena-test`
Lambda·Athena·AI/ML 을 호출해 얻은 결과입니다. 공개 API·Vercel 배포본은 변경하지 않았습니다.

- 핸들러: `src.ml_integration_check.lambda_handler` (현재 런타임 서비스 핸들러 `src.lambda_function.lambda_handler`와 별개)
- 테스트 이벤트(한 날짜씩, 각 실행 ML 1회):
  ```json
  { "target_date": "2016-04-10" }
  ```
  ```json
  { "target_date": "2016-04-12" }
  ```
- 동작:
  - 허용 날짜는 `2016-04-10`, `2016-04-12` 두 개뿐. 그 외 날짜·형식, API Gateway 이벤트는 **ML 호출 전에 거절**.
  - 사용자는 기존 테스트 사용자(`get_allowed_user_id`, 보통 `DASHBOARD_USER_ID`)만.
  - 기존 Athena 조회·매핑(`build_real_health_data`)과 변환(`collect_daily_steps`,
    `collect_daily_tracked_minutes`, `build_detection_request`)을 재사용. 활동·비활동 4개 컬럼 합계를
    `metrics.tracked_minutes`로, 요청 최상위에 `notify: false`를 넣음. **요청 값은 Athena 조회 값으로 구성**.
  - 4월 12일 제외 범위: 일반 API(`ai_service._load_result`)는 04-12 를 **기준일 선택** 단계에서만 제외한다
    (`excluded_dates=("2016-04-12",)`, `ML_TARGET_DATE=2016-04-12` 거부). 조회·과거 이력에는 적용되지 않음
    (Athena 는 날짜 필터 없이 사용자 전체 행을 읽음). 이 콘솔 핸들러는 `excluded_dates`를 비워 **04-12 도
    기준일로 조회**할 수 있게 하되, 일반 API 동작은 바꾸지 않음.
- 기대 결과(요청 값은 실제 Athena 조회 값, 아래 숫자는 비교용):

| 이벤트 | 요청 metrics | 기록 시간 기준 | ML 판정 | 근거 |
|---|---|---|---|---|
| 2016-04-10 | `{steps:10057, tracked_minutes:962}`, `notify:false` | 962 ≥ 800 | 걸음 수 판정 대상 (`normal`이어도 OK) | `trackedMinutesBelowThreshold=false` |
| 2016-04-12 | `{steps:224, tracked_minutes:41}`, `notify:false` | 41 < 800 | 걸음 수(`ACTIVITY_DROP`) **판정 제외** | `stepJudgmentSkipped=true` (ACTIVITY_DROP 없음 + 기록 시간<800) |

- 응답 확인 필드: `request.metrics.tracked_minutes`·`request.metrics.steps`(요청에 담긴 값),
  `ml.status`, `ml.stepAnomalyDetected`/`ml.anomalyTypes`, `alertSent`, `alertReason`,
  그리고 41분 케이스의 판정 제외 근거 `stepJudgmentSkipped`·`trackedMinutesBelowThreshold`.
- 두 케이스 모두 `notify: false`라 `alert_sent=false` 기대. `alert_reason`은 ML 응답 원문을 그대로 기록.
- 962분 케이스는 `normal`이어도 성공으로 봅니다(걸음 수 판정 자체는 수행됨).

### 실제 AWS 검증 결과 (2026-11-06, `wearcare-test` 프로필 · ap-northeast-2)

발표 PC 로컬 중계 서버를 통해 실제 `wearcare-mate-athena-test` Lambda(Athena + AI/ML)를 날짜별로
각 1회 호출한 결과입니다. 요청 값은 Athena 조회 값으로 구성했고, 아래 값이 기대 비교값과 일치했습니다.

| 이벤트 | 요청 metrics | 기록 시간 기준 | ML 판정 | SNS 발송 |
|---|---|---|---|---|
| 2016-04-10 | `{steps:10057, tracked_minutes:962}`, `notify:false` | 962 ≥ 800 | `normal` (걸음 수 판정 수행, 이상 없음) | `alertSent=false` (`notify:false`) |
| 2016-04-12 | `{steps:224, tracked_minutes:41}`, `notify:false` | 41 < 800 | 걸음 수(`ACTIVITY_DROP`) **판정 제외** | `alertSent=false` (`notify:false`) |

- 4월 10일: 기록 시간 962분으로 800분 기준을 넘겨 걸음 수 판정을 수행했고, 결과는 `normal`(이상 없음)입니다.
- 4월 12일: 기록 시간 41분으로 800분 미만이라 걸음 수(`ACTIVITY_DROP`) 판정에서 제외됐습니다
  (`stepJudgmentSkipped=true`, `trackedMinutesBelowThreshold=true`).
- 두 요청 모두 최상위 `notify:false`라 SNS 미발송(`alertSent=false`)을 확인했습니다. `alertReason`은 ML 응답 원문을 그대로 기록합니다.

### 검증 경로 구분 (로컬 브라우저 vs Vercel 배포)

- **로컬 브라우저 검증 (완료)**: 발표 PC에서 로컬 중계 서버(`wearcare-test` 프로필)를 통해 공개 대시보드
  프론트엔드를 실제 Athena 데이터에 연결해 확인했습니다. 주간 평균 `12,369보`, 기준주 4/10 시계열,
  `/ai-guide` 정상 판정·`alertSent=false`를 브라우저에서 확인했습니다. 발표 시연은 이 로컬 중계 경로를 사용합니다.
- **Vercel 배포 상태 (이후 인증 연결 완료 — 아래 정정 참고)**: 이 항목은 당시 기록입니다. 당시에는 발표용
  Vercel 배포본(`https://wearcare-mate-dxqh.vercel.app`)이 `REACT_APP_API_BASE` 없이 목(mock) 모드였습니다.
  > **정정(현재 확정 상태)**: 이후 **인증된 발표 API `https://tirb2qdtj8.execute-api.ap-northeast-2.amazonaws.com`가
  > 배포 완료**되었습니다. 이 API의 `GET /dashboard`·`GET /ai-guide`는 **Cognito JWT 오소라이저 + 스코프
  > `wearcare-demo/read`**로 보호되며, 연결 Lambda는 `wearcare-mate-athena-test`입니다. 발표본은 이 API로
  > Cognito 로그인 → 액세스 토큰 첨부 → 실데이터 조회를 하며, 로그인·로그아웃·재로그인과 실제 Athena 데이터
  > 표시가 이미 검증되었습니다. 기존 공개 예시 API(`j3cwx5vmwj`)는 **그대로 보존**(예시 모드)합니다.

## 비공개 AWS 연동 검증 준비 (실행 전, 승인 필요)

공개 API는 예시 데이터 모드를 유지합니다. 아래는 승인 시 실행할 계획이며, 아직 실행하지 않았습니다.

- 검증 대상 함수: `wearcare-mate-ml-virtual-check`(콘솔 전용 가상 프로브). 공개 HTTP 경로 미연결.
- 배포 파일: 최상위 `src/`를 담은 ZIP (이번 로컬 수정 반영본). Python 3.13, x86_64.
- 콘솔 진입점:
  - 기존 가상 이상·가이드 점검: `src.ml_virtual_anomaly_check.lambda_handler` (기본 핸들러, 유지)
  - 기록 시간 경계 관찰: `src.ml_virtual_anomaly_check.run_tracked_minutes_boundary_check`
    (콘솔에서 직접 호출. 가이드 생성·SNS 발송을 통과 조건으로 삼지 않고 걸음 수 판정 여부만 관찰)

#### 기록 시간 경계 입력과 기대 결과 (799 / 800, v0.5)

`user_id`·`date`·`steps`·`history_steps`·`notify`는 동일하게 두고 `metrics.tracked_minutes`만 바꿉니다.
공통: `user_id="test-user"`, `date="2026-10-30"`, `steps=1000`,
`history_steps=[10000,10500,9800,10200,10100,9900]`, **`notify=false`(v0.5)**.

| 입력 | 요청 | 기대 결과 |
|---|---|---|
| 799분 | `metrics={"steps":1000,"tracked_minutes":799}`, `notify=false` | 기록 시간 기준 미달(<800) → **걸음 수(ACTIVITY_DROP) 판정 제외**. `notify=false`라 `alert_sent=false` 기대 |
| 800분 | `metrics={"steps":1000,"tracked_minutes":800}`, `notify=false` | 기준 통과(=800) → **현재 가상 입력(급감)으로 `ACTIVITY_DROP` 이상 감지** 기대. `notify=false`라 `alert_sent=false` 기대(가이드 생성은 필수 아님) |

- 800분 미만 제외는 **AI/ML 쪽 규칙**입니다. 백엔드는 `799`/`800`을 구분하지 않고 그대로 전달만 하며,
  `notify=false`도 두 요청에 그대로 싣습니다. (로컬 테스트로 두 값·notify 전달 확인)
- `alert_reason`은 실제 값을 기록합니다. **799분에서 `below_threshold`와 `notify_false` 중 어느 사유가
  우선되는지는 배포 구현이나 실제 응답으로 확인합니다**(추측하지 않음).
- 실제 데이터 정상 경로는 `2016-04-10`으로 별도 확인(기존에 검증한 기준일).

#### 콘솔 실행 방법 (핸들러·테스트 이벤트)

핸들러: `src.ml_virtual_anomaly_check.lambda_handler`. 환경변수 `ML_FUNCTION_NAME=wearcare-mate-ml`,
`ML_REGION=ap-northeast-2` 필요. 한 번 실행에 ML 을 **정확히 한 번** 호출합니다.

Lambda 콘솔 테스트 이벤트로 아래 둘 중 하나를 넣어 경계 케이스 **하나씩** 실행합니다(각 실행 ML 1회):

```json
{ "check": "tracked_minutes_boundary", "tracked_minutes": 799 }
```
```json
{ "check": "tracked_minutes_boundary", "tracked_minutes": 800 }
```

- 이때 AI/ML 로 전송되는 실제 요청 JSON(핸들러가 내부에서 생성, 최상위 `notify: false`):
  ```json
  { "user_id": "test-user", "date": "2026-10-30",
    "metrics": { "steps": 1000, "tracked_minutes": 799 },
    "history_steps": [10000, 10500, 9800, 10200, 10100, 9900], "notify": false }
  ```
  ```json
  { "user_id": "test-user", "date": "2026-10-30",
    "metrics": { "steps": 1000, "tracked_minutes": 800 },
    "history_steps": [10000, 10500, 9800, 10200, 10100, 9900], "notify": false }
  ```
- 지원하지 않는 `tracked_minutes`(799/800 외, 또는 정수가 아닌 값)는 **ML 호출 전에** `verdict=REJECTED`,
  `statusCode=400` 으로 거절합니다.
- 성공 조건(verdict PASS): 799 → `ACTIVITY_DROP` 없음, 800 → `ACTIVITY_DROP` 감지, **두 경우 모두
  `alert_sent=false`**(notify=false). `alert_sent=true`(발송됨)면 FAIL. **`sent` 는 성공 조건이 아닙니다.**
  `alert_reason` 은 ML 응답 원문을 그대로 기록하며 성공 판정에 쓰지 않습니다.

기존 이벤트 동작은 그대로입니다:
- `{}` (빈 이벤트): 가상 이상·가이드 점검(`run_check`). 내부에서 아래 요청을 전송:
  ```json
  { "user_id": "test-user", "date": "2026-10-30", "metrics": { "steps": 1000 },
    "history_steps": [10000, 10500, 9800, 10200, 10100, 9900], "notify": false }
  ```
- API Gateway 형식 이벤트(`requestContext`/`routeKey`/`rawPath`/`httpMethod` 포함)는 AI/ML 을 호출하지 않고
  `REFUSED`를 돌려줍니다(경계 필드가 있어도 거절이 우선). 콘솔 전용 도구이며 공개 HTTP 경로에 연결하지 마세요.

두 경계를 한 번에 관찰만 하려면(ML 2회 호출) 함수 `run_tracked_minutes_boundary_check` 를 직접 호출할 수도
있습니다. 단, 콘솔 테스트 이벤트로는 위 단일 케이스 방식을 씁니다.

#### v0.5 명세로 확정된 항목

- **`notify` 위치·기본값**: 요청 **최상위**, 불리언. 조회·재조회 경로는 `false`로 고정(SNS 미발송). 구현 완료.
- **`alert_reason` 위치**: 응답 **최상위** 선택 문자열. `ml_adapter`가 최상위에서 읽어 `alertReason`으로 전달. 구현 완료.
- **799(<800) 판정 제외 범위**: `ACTIVITY_DROP`(걸음 수)만 건너뜀. 다른 지표(수면·HRV·스트레스)는 그대로 판정.
  (명세 11번: "ACTIVITY_DROP만 insufficient_data, 다른 지표는 그대로")

#### 여전히 실제 응답으로 확인할 항목

- 서울의 비공개 테스트 Lambda `wearcare-mate-ml-virtual-check`에서 가상 입력으로 두 케이스 모두 `statusCode=200`, `verdict=PASS`를 확인했습니다.
- 799분은 걸음 수 판정을 건너뛰었으며 `insufficient_data`, 심각도 `none`, 가이드 `not_applicable`이 반환됐습니다.
- 800분은 걸음 수 급감이 감지됐으며 `anomaly`, 심각도 `high`, 가이드 `generated`가 반환됐습니다.
- 두 요청 모두 최상위 `notify=false`를 전달했고, `alertSent=false`, `alertReason=notify_false`가 반환됐습니다. 800분에서는 가이드 생성과 SNS 발송 억제가 함께 확인됐습니다.
- 이번 v0.5 경계 검증의 범위는 가상 입력과 비공개 Lambda 호출입니다. Athena 실제 데이터 경계 검증과 공개 API·브라우저 통합 검증은 남아 있습니다.

## 프론트엔드 응답 예시 (로컬 예시 — 실제 v0.5 AWS 응답 아님)

아래는 현재 백엔드 변환 함수(`ai_service.guide_for_frontend`)가 만드는 결과입니다(v0.5, alertReason 포함).
실제 v0.5 AWS 응답으로 확인하기 전까지는 **로컬 예시**입니다. `/dashboard`에서는 `body.aiGuide`,
`/ai-guide`에서는 응답 본문이 곧 이 객체입니다(동일 스키마). 예시의 alertSent/alertReason 값은 설명용입니다.

### 이상 + 가이드 생성 (배열 있음, notify=false → alert_sent=false 예시)

```json
{
  "status": "generated",
  "analysisStatus": "anomaly",
  "referenceDate": "2026-10-30",
  "updatedAt": "2026-10-30T14:40:09+09:00",
  "warnings": [],
  "alertSent": false,
  "alertReason": "notify_false",
  "model": "Amazon Bedrock · global.anthropic.claude-haiku-4-5-20251001-v1:0",
  "headline": "오늘 걸음 수가 1,000걸음으로 평소 10,083걸음보다 크게 적었어요.",
  "text": "오늘 걸음 수가 1,000걸음으로 평소 10,083걸음보다 크게 적었어요.\n오늘 하루 중 10분 정도라도 산책이나 가벼운 움직임을 의식적으로 만들어보세요.\n이런 패턴이 계속되거나 몸이 무거운 느낌이 지속되면 전문가와 상담해보세요.",
  "actions": ["오늘 하루 중 10분 정도라도 산책이나 가벼운 움직임을 의식적으로 만들어보세요."],
  "lines": [
    "오늘 걸음 수가 1,000걸음으로 평소 10,083걸음보다 크게 적었어요.",
    "오늘 하루 중 10분 정도라도 산책이나 가벼운 움직임을 의식적으로 만들어보세요.",
    "이런 패턴이 계속되거나 몸이 무거운 느낌이 지속되면 전문가와 상담해보세요."
  ]
}
```

### 가이드 없음 (배열 없음 — 정상/데이터 부족/799 판정 제외 등)

```json
{
  "status": "not_applicable",
  "analysisStatus": "insufficient_data",
  "referenceDate": "2026-10-30",
  "updatedAt": "생성된 가이드 없음",
  "warnings": [],
  "alertSent": false,
  "alertReason": "below_threshold",
  "model": "활동량 분석 · 생성형 가이드 없음",
  "headline": "활동량을 판정할 과거 기록이 부족해요.",
  "text": "데이터 부족 상태이며 정상 판정이나 AI 가이드 생성 결과가 아니에요.",
  "actions": []
}
```

### 프론트엔드 표시 방법

- **줄별 표시**: `lines` 배열이 있으면 각 줄을 한 줄씩 표시합니다. (가이드 생성 시에만 존재)
- **배열이 없는 기존 응답**: `lines`가 없거나(`status != "generated"`) 빈 경우 `text`를 그대로 씁니다.
  `text`는 생성 시 `\n`으로 이어 붙인 전체 문자열이고, 가이드가 없을 때는 안내 문구 한 덩어리입니다.
  줄바꿈을 유지해 표시하면 됩니다. 즉 **`lines`가 있으면 줄별로, 없으면 `text`(줄바꿈 유지)로** 표시하면
  두 경우를 모두 처리할 수 있습니다.
- `headline`(=lines[0])과 `actions`(=lines[1:2])는 기존 화면이 쓰던 필드로 그대로 유지됩니다.
  현 프론트엔드는 이 둘만 쓰고 있어, `lines` 전체 줄 표시는 프론트엔드 소스 수정이 필요합니다(이번 백엔드 변경과 분리).
- `alertSent`는 `true`/`false`/`null`(필드 없음·가이드 없음)로 구분됩니다. 표시 여부는 프론트엔드 결정입니다.
- `alertReason`(v0.5)은 발송/미발송 사유 문자열 또는 `null`입니다. `guide`가 없어도 보존됩니다.

## API Gateway CORS (사용자 콘솔 설정, 2026-11-02)

- 허용 Origin: `http://localhost:3000` (로컬 개발 주소. 배포 주소는 아직 미확정)
- `$default` 스테이지 자동 배포: Enabled
- 공개 API는 여전히 예시 데이터 모드입니다. 배포 주소가 정해지면 그 Origin을 추가합니다. `*`는 쓰지 않습니다.

이 기록은 콘솔 테스트 결과이며 자동 모니터링한 현재 상태를 의미하지 않습니다.

## 리소스 및 권한

- 백엔드/AI Lambda: ap-northeast-2. Athena/Glue/S3: us-east-2.
- 워크그룹 primary, DB wearcare_mate_db, 테이블 fitbit_activity_table.
- 원본: s3://wearcare-mate-bucket-2026/raw-data/fitbit/
- 결과: s3://wearcare-mate-bucket-2026/athena-results/
- 백엔드 역할: 로그 기록, primary의 Athena 실행/상태/결과/중단,
  해당 Glue 테이블·DB·카탈로그 읽기, 원본 S3 읽기, 결과 폴더 읽기·쓰기,
  wearcare-mate-ml에 한정한 lambda:InvokeFunction.
- AI/ML 역할의 Bedrock·Athena 권한과 모델 설정은 AI/ML 담당자가 관리합니다.

AWS 키는 코드나 .env.example에 넣지 않으며 실행 역할을 사용합니다.

## 패키징과 진입점

배포 ZIP의 최상위에 src/가 있어야 합니다. backend/ 폴더나 Windows .venv를 통째로 압축하지 마세요.
배포 ZIP과 캐시 파일은 Git에 올리지 않습니다.

- 일반 서비스: src.lambda_function.lambda_handler
- 콘솔 전용 Athena 실데이터 경계 프로브: src.ml_integration_check.lambda_handler
  - 이벤트 `{"target_date":"2016-04-10"}` 또는 `{"target_date":"2016-04-12"}`로 한 날짜만 조회·검증합니다.
  - 허용 날짜 2개와 기존 테스트 사용자만 씁니다. 지원 외 날짜·API Gateway 이벤트는 ML 호출 전에 거절합니다.
  - 기존 Athena 조회·요청 변환을 재사용해 활동·비활동 4개 컬럼 합계를 metrics.tracked_minutes 로 보내고,
    요청 최상위에 notify=false 를 넣습니다. ML 을 정확히 한 번 호출합니다.
  - 아래 "비공개 wearcare-mate-athena-test 실데이터 경계 검증" 참고. 공개 HTTP 경로에 연결하지 마세요.
- 콘솔 전용 가상 이상 프로브: src.ml_virtual_anomaly_check.lambda_handler
  - 고정 가상 입력으로 AI/ML·Bedrock 호출과 화면용 변환을 확인합니다. Athena를 쓰지 않습니다.
  - API Gateway 형식 이벤트가 들어오면 AI/ML을 호출하지 않고 REFUSED를 돌려줍니다.
  - 호출할 때마다 Bedrock 비용이 들 수 있습니다. 공개 HTTP 경로에 연결하지 마세요.

Python 3.13, x86_64에서 검증했습니다. 백엔드·테스트 함수 timeout은 30초,
AI/ML은 1분으로 설정했습니다. 전체 동기 API의 응답 시간은 별도 제약이므로
Lambda timeout만 늘려 해결된다고 간주하지 마세요.

## 재검증 순서

1. API Gateway가 없는 테스트 함수에만 새 코드를 업로드하고 일반 서비스 핸들러 설정.
2. README의 REAL 설정을 적용하고 ML_TARGET_DATE=2016-04-10 지정.
3. HTTP API payload 2.0 이벤트로 GET /dashboard와 GET /ai-guide 실행.
4. statusCode=200, analysisStatus/status, referenceDate, 가이드 유무를 함께 확인.
5. 이상 경로는 가상 이상 프로브로 실제 가이드 생성과 화면 변환을 확인했다(위 기록).
   Athena 실제 데이터에서의 이상 판정과 공개 API 경로는 별도로 확인.
6. 인증·인가, 데이터 날짜 품질, CORS origin, 프론트엔드 계약 및 지연/실패 처리를 확인한 뒤
   공개 API의 REAL 전환 여부를 결정. 기존 공개 mock 설정은 이 Git 변경만으로 바뀌지 않음.

GET 재조회도 Athena와 Bedrock 비용이 발생할 수 있으며 생성 캐시/요청 제한은 아직 없습니다.
정상 결과는 Bedrock을 호출하지 않고 not_applicable을 반환합니다. insufficient_data는
과거 기록 자체가 부족하거나 AI/ML 내부 조회가 실패한 경우일 수 있어 필요 시 조회 로그를 확인합니다.
다른 날짜의 차트 anomaly=false를 정상 판정으로 해석하지 마세요.

## AI/ML 담당자 공유 사항

- 커밋 4732493c677c9cd7e329b00c55f5f21b0ecfcb15.
- detector.py의 걸음 수 단위를 보 -> 걸음으로 바꾸어 wearcare-mate-ml에 직접 배포했다고 공유받았습니다.
- 입출력 형식과 환경변수 변경 없음, timeout 1분 유지라는 공유 기준이며 이 백엔드 작업에서
  해당 배포를 다시 수행하지 않았습니다. AI/ML 원본은 별도 브랜치에서 관리합니다.

## 웹 가상 이상 시연 (POST /demo/anomaly, 백엔드 로컬 구현 · 아직 미배포)

발표 화면에서 "가상 이상 입력 → 실제 AI/ML → 화면 변환"을 버튼 한 번으로 보여 주기 위한 공개 라우트입니다.
콘솔 전용 도구(`src.ml_virtual_anomaly_check`)는 API Gateway 이벤트를 `REFUSED`로 거절하므로 그대로 두고,
웹 경로용으로 `src/demo_anomaly.py`를 새로 만들어 `src.lambda_function` 라우터에 연결했습니다.
이번 변경은 로컬 코드·테스트만 완료했고 AWS·Vercel·실제 ML 호출은 하지 않았습니다.

### 동작 요약

- **라우트**: `POST /demo/anomaly` (`src.lambda_function._route_request` 2-3 분기).
- **기능 스위치(기본 비활성)**: `ENABLE_DEMO_ANOMALY=true` 일 때만 동작합니다. 꺼져 있으면 라우트 매칭에서
  빠져 그 외 경로와 같이 **404**(존재를 드러내지 않음). `GET /demo/anomaly`는 스위치와 무관하게 404입니다.
- **서버 고정 입력(클라이언트가 못 바꿈)**: 요청 본문을 읽지 않습니다. `src.demo_anomaly.DEMO_REQUEST` 고정.
  ```json
  { "user_id": "test-user", "date": "2026-10-30",
    "metrics": { "steps": 1000, "tracked_minutes": 800 },
    "history_steps": [10000, 10500, 9800, 10200, 10100, 9900], "notify": false }
  ```
  `history_steps`가 있어 AI/ML Lambda는 Athena를 조회하지 않고 그 값을 기준선으로 씁니다.
  `notify: false`를 요청 최상위에 고정해 SNS 발송을 막습니다(발표 중 알림 금지).
- **재사용**: 기존 `MLClient.invoke_detection`(unwrap + `validate_detection_result`)와
  `ai_service.guide_for_frontend` / `anomalies_for_frontend`를 그대로 씁니다(변환 로직 복제 없음).
- **성공 응답(200)**: `inputKind: "virtual"`, `referenceDate`, `analysisStatus`, `overallSeverity`,
  `aiGuide`(= `guide_for_frontend`), `anomalies`(= `anomalies_for_frontend`), 서버가 보낸 `request`.
- **실패 시 예시 대체 없음**: 설정·boto3 오류는 503(stage=config), 호출·응답 검증 실패는 502
  (stage=invoke_or_validate). 예외 원문 메시지는 응답에 넣지 않고 타입 이름만 담습니다.

### 테스트 (실제 AWS 미접속, 가짜 Lambda 주입)

- `tests/test_demo_anomaly.py`: 스위치 기본 비활성, 고정 입력·`notify=false` 전달, 성공 응답의
  aiGuide/anomalies/inputKind, 설정·호출·응답 실패 처리(예시 대체 없음)를 검증합니다.
- `tests/test_lambda_demo_anomaly.py`: 라우팅 레벨에서 비활성 404(ML 미호출), 활성 시 상태 코드·본문 변환,
  기존 GET 경로(/health·/dashboard·/ai-guide·/users/...) 보존을 검증합니다.
- 전체 스위트(`py -m unittest discover -s tests`) 473건 통과. 기존 테스트 변경 없음.

### 배포 절차 (승인 후 실행 — 인증된 발표 API `tirb2qdtj8`에만 추가)

**어느 API에 추가하는가 (정정)**: `POST /demo/anomaly`는 **인증된 발표 API
`https://tirb2qdtj8.execute-api.ap-northeast-2.amazonaws.com`에만** 추가합니다. 이 API는 이미 Cognito JWT
오소라이저 + 스코프 `wearcare-demo/read`로 보호되고, 연결 Lambda는 `wearcare-mate-athena-test`입니다.
**기존 공개 예시 API `j3cwx5vmwj`에는 추가하지 않습니다**(예시 모드 그대로 보존). 즉 JWT 보호를 새로
"세우는" 것이 아니라, **이미 보호된 API에 보호된 라우트 하나를 추가**하는 작업입니다.

> ⚠️ 연결 Lambda 구분: 발표 API는 `wearcare-mate-athena-test`에 연결되어 있습니다. 이 데모 라우트의 진입점은
> `src.lambda_function.lambda_handler`입니다. `wearcare-mate-athena-test`가 이 핸들러로 라우팅되는지 먼저
> 확인하세요. 아니라면 해당 Lambda의 배포 ZIP·핸들러에 이번 변경(`src/demo_anomaly.py` + 라우터 분기)이
> 포함되도록 반영해야 합니다.

1. **패키징**: 최상위에 `src/`가 들어가도록 ZIP(이번 수정본 포함). `backend/`나 `.venv`를 통째로 넣지 않습니다.
   진입점은 `src.lambda_function.lambda_handler` 그대로입니다. 발표 API 연결 Lambda(`wearcare-mate-athena-test`)에 배포합니다.
2. **새 POST 라우트에 JWT·scope 적용**: `POST /demo/anomaly` 라우트를 추가하고, 기존 `GET /dashboard`·
   `GET /ai-guide`와 **동일한 JWT 오소라이저**를 지정합니다.
   - issuer/audience는 기존 두 GET 라우트와 같은 값(이미 운영 중인 Cognito User Pool·앱 클라이언트)을 씁니다.
   - 스코프: 기존 `wearcare-demo/read`를 그대로 쓸지 검토합니다. 아래 "스코프 검토" 참고.
   - 토큰 없는 호출은 401, 스코프 부족은 403이어야 합니다(기존 GET과 동일 동작).
3. **CORS에 POST 허용**: 발표 API의 CORS에 `POST` 메서드와 `Authorization` 헤더를 허용 목록에 추가합니다.
   허용 Origin은 발표 도메인 `https://wearcare-mate-dxqh.vercel.app`(끝 슬래시 없음). `*`는 쓰지 않습니다.
   (기존 GET만 허용돼 있으면 프리플라이트 OPTIONS에서 POST가 막힐 수 있으니 반드시 확인)
4. **Lambda 호출 권한**: `wearcare-mate-athena-test`의 실행 역할에 `wearcare-mate-ml`(AI/ML Lambda)에 한정한
   `lambda:InvokeFunction`이 있어야 합니다. 기존 `/ai-guide` 경로가 이미 AI/ML을 호출하므로 대개 충족돼 있지만,
   발표 API 연결 Lambda 기준으로 재확인합니다.
5. **기능 스위치 + ML 환경변수**: Lambda 환경변수 `ENABLE_DEMO_ANOMALY=true`와 `ML_FUNCTION_NAME=wearcare-mate-ml`,
   `ML_REGION=ap-northeast-2`를 설정합니다. 스위치는 발표 때만 켜고 끝나면 제거해 라우트를 404로 되돌립니다.
6. **전체 응답 시간 확인**: 데모 호출은 실제 AI/ML(Bedrock 가이드 생성 포함)을 동기로 기다립니다. 가상 이상 입력
   콘솔 검증에서 약 13.8초가 걸린 적이 있으므로, API Gateway 통합 타임아웃(HTTP API 최대 30초)과
   `ML_TIMEOUT_SECONDS`(기본 15, 최대 29) 안에 들어오는지 확인합니다. 필요 시 `ML_TIMEOUT_SECONDS`를
   29 이하에서 조정합니다. 프론트엔드는 자동 재시도를 하지 않으므로, 타임아웃 시 사용자에게 오류만 표시됩니다.
7. **프론트엔드 연결**: 로그인으로 받은 Cognito 액세스 토큰을 `Authorization: Bearer <token>`로 실어
   `POST {API_BASE}/demo/anomaly`를 호출합니다(본문 불필요 — 서버가 입력 고정). 응답의 `aiGuide`·`anomalies`를
   기존 대시보드 화면 컴포넌트에 그대로 전달합니다(스키마가 `/ai-guide`와 동일). 구현 완료(아래 프론트엔드 섹션).
8. **검증**: 토큰 없이 401, 스코프 부족 403, 유효 토큰으로 200과 `inputKind: "virtual"`·anomaly 가이드를 확인합니다.

#### 기존 `wearcare-demo/read` 스코프를 데모 POST에도 쓸지 검토

- **그대로 쓰는 쪽 근거**: 발표용 단일 데모 계정만 쓰고, 새 스코프·앱 클라이언트·동의 화면을 늘리지 않아 발표
  준비가 단순합니다. 데모 입력은 서버가 고정하고 실제 사용자 데이터를 쓰지 않으므로, 읽기 권한과 위험 수준이
  비슷합니다(가상 이상 1건 조회·표시).
- **분리하는 쪽 근거(`wearcare-demo/demo` 등 별도 스코프)**: 이 라우트는 GET 조회와 달리 **실제 AI/ML Lambda를
  호출(비용·지연 발생)**하고 **쓰기 성격의 작업**에 가깝습니다. 스코프를 분리하면 "읽기만 허용된 토큰"으로는
  ML 호출을 못 하게 최소 권한을 지킬 수 있고, 발표 후 데모만 선택적으로 막기도 쉽습니다.
- **판단**: 발표 범위가 좁고(가상 입력·단일 계정·기능 스위치로 상시 차단 가능) 실사용자 데이터를 쓰지 않으므로,
  1차로는 **기존 `wearcare-demo/read` 재사용**이 합리적입니다. 다만 기능 스위치(`ENABLE_DEMO_ANOMALY`)로 상시
  비활성을 유지하는 것을 전제로 하며, 데모가 상시 노출로 바뀌면 그때 별도 스코프로 분리할 것을 권장합니다.

> 주의: 이 작업에서는 커밋·push·AWS·Vercel 변경과 실제 ML 호출을 하지 않았습니다. 위 절차는 승인 후 실행 계획입니다.
> 백엔드 로컬 테스트 473건 통과는 **로컬 검증 결과일 뿐 AWS 배포 완료가 아닙니다.**

### 2026-11-09 최종 상태 (위 구현 당시 기록의 후속 정정)

- 사용자가 `wearcare-mate-athena-test`에 최신 ZIP을 업로드하고, Lambda `/dashboard` 200 응답 및 HTTPS 화면을 확인했습니다. 가상 이상 시연과 실제 데이터 복귀도 사용자 브라우저에서 확인했습니다.
- 수면은 지정된 fixed CSV의 0~24시간 기록만 집계합니다. 실제 Athena 결과는 1,000건, 평균 7.47시간, 최솟값 3.11시간, 최댓값 12.36시간입니다. 분포는 [0,4), [4,6), [6,8), [8,10), [10,24] 순서로 9/165/455/319/52건입니다. 날짜 의미가 미확인이라 일별 수면 추이는 만들지 않습니다.
- 심박은 전체 30,000행 중 양수 29,794행, 0값 206행입니다. 양수 평균은 79.9이며, 날짜별 양수 평균은 2025-10-15~2025-11-20의 37개 날짜를 반환합니다. 단위는 확정하지 않아 `unit=null`, `unitBasis=unconfirmed`로 반환합니다. Fitbit 사용자의 안정 시 심박으로 해석하지 않습니다.
- 심리상담은 파일별 통합 1,328행·검증 175행만 반환합니다. 원문·개인 점수는 조회하지 않습니다. 세 요약은 별도 데이터셋이며 개별 실패를 격리합니다.
- 웹 시연은 `notify=false` 고정으로 SNS 메일을 발송하지 않습니다. 기존 공개 예시 API는 유지합니다.
- 현재 소스로 백엔드 전체 테스트 486개 통과를 재확인했습니다. 테스트 목 값과 위 실제 Athena 검증값은 구분합니다. 이 저장 작업에서 AWS 설정을 변경하거나 재배포하지 않았습니다.
