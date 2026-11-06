# WearCare Mate Backend

API Gateway HTTP API(payload 2.0)와 Python 3.13 Lambda 기반 백엔드입니다.

## 현재 상태 (2026-10-31 콘솔 검증 기준)

- 공개 백엔드와 API Gateway는 서울 ap-northeast-2에 배포했습니다. 공개 /health, /dashboard, /ai-guide 호출을 확인했으며 공개 API는 예시 데이터 모드입니다.
- 별도 wearcare-mate-athena-test에서 실제 Athena 조회, AI/ML Lambda 호출 및 /dashboard, /ai-guide 응답 변환을 검증했습니다. 기준일 2016-04-10, 정상 판정입니다.
- wearcare-mate-ml에서 가상 이상 입력을 통한 실제 Bedrock 가이드 생성을 별도로 확인했습니다.
- 2026-11-02 콘솔 전용 wearcare-mate-ml-virtual-check에서 가상 이상 입력 → 실제 AI/ML 호출 → 실제 Bedrock 가이드 →
  백엔드 화면용 변환을 확인했습니다(Lambda 실행 성공, 응답 verdict PASS). 가상 입력이므로 Athena 실제 데이터는 포함하지 않습니다.
- Athena 실제 데이터에서 이상이 판정되어 가이드까지 반환되는 흐름과 공개 API 경로는 아직 AWS에서 확인하지 않았습니다.
- 화면용 이상 설명의 걸음 수 단위를 "걸음"으로 통일한 수정은 아직 AWS에 배포하지 않았습니다.
- Athena·Glue·S3는 오하이오 us-east-2, 백엔드·AI/ML Lambda와 Bedrock 호출 시작 리전은 서울입니다.
- API Gateway CORS에 로컬 개발 주소 http://localhost:3000을 등록했고, 로컬 브라우저에서 공개 예시 API 표시를 확인했습니다.
  배포 주소의 CORS, 인증·인가, 공개 API 실제 데이터 전환, 실제 생성 가이드의 브라우저 통합 검증은 미완료입니다.
- SNS, 기기 연결, 가이드 이력 저장, 프로필 서버 저장과 SageMaker 엔드포인트 호출은 구현하지 않았습니다.

GitHub push는 AWS를 변경하지 않습니다. REAL 모드의 사용자 지정과 테스트 스위치는 인증·인가가 아니므로 인증 없는 공개 API에서 활성화하지 마세요.

## API

- GET /health: 상태 확인.
- GET /dashboard: 기본 예시 데이터. REAL에서는 걸음 수를 조회하고 AI를 선택적으로 호출합니다.
- GET /ai-guide: 기본 예시 가이드. AI REAL에서는 실제 기준일 걸음 수로 AI/ML을 호출합니다.
- GET /users/{userId}/health-data: 예시 또는 Athena 데이터. REAL은 지정 사용자만 허용합니다.
- GET /users/{userId}/anomalies, /guides: 기존 예시 응답이며 AI_SOURCE와 무관합니다.
- PUT /profile은 없습니다. 현재 프론트엔드는 프로필을 브라우저에 저장합니다.

상세 계약: [api-spec.md](docs/api-spec.md). 배포와 검증: [aws-integration.md](docs/aws-integration.md).

## 환경변수

기본값은 DATA_SOURCE=mock, AI_SOURCE=mock입니다. [.env.example](.env.example)을 참고하세요.
Lambda는 .env 파일을 자동으로 읽지 않으므로 콘솔 환경변수에 설정합니다.

실제 데이터 조회에 필요한 설정:

```text
DATA_SOURCE=real
ENABLE_REAL_DATA_TESTING=true
DASHBOARD_USER_ID=<데이터셋의 실제 숫자 ID>
ATHENA_REGION=us-east-2
ATHENA_DATABASE=wearcare_mate_db
ATHENA_TABLE=fitbit_activity_table
ATHENA_WORKGROUP=primary
ATHENA_OUTPUT_LOCATION=s3://wearcare-mate-bucket-2026/athena-results/
```

실제 AI 경로는 위 설정에 더해 다음이 필요합니다.

```text
AI_SOURCE=real
ML_FUNCTION_NAME=wearcare-mate-ml
ML_REGION=ap-northeast-2
ML_TARGET_DATE=2016-04-10
```

ML_TARGET_DATE는 명시적으로 지정한 데이터 날짜입니다. 오늘 날짜로 자동 대체하지 않습니다.
기준일 누락·형식 오류, 걸음 수 누락·0·중복 충돌, 불완전한 날짜 2016-04-12는 REAL AI에서 거절합니다.
데이터셋 전체의 날짜 오류 수정·재적재 완료 여부는 데이터 담당자와 추가 확인해야 합니다.

선택 설정:
- ATHENA_QUERY_TIMEOUT_SECONDS: 기본 20초.
- ATHENA_MAX_ROWS: 기본 1000. 대시보드에서 상한에 도달하면 잘린 결과로 통계를 만들지 않고 503.
- ML_TIMEOUT_SECONDS: 기본 15초, 최대 29초. Lambda와 API Gateway의 전체 응답 시간 안에서 설정해야 합니다.

백엔드 변수명 ATHENA_DATABASE/ATHENA_OUTPUT_LOCATION과 AI/ML 함수의 ATHENA_DB/ATHENA_OUTPUT은 다릅니다.
Bedrock 모델과 AI/ML 환경변수는 AI/ML 담당자가 관리합니다.

## REAL AI 응답 규칙

- 요청: {user_id, date, metrics: {steps}}. history_steps는 보내지 않고 AI/ML이 Athena에서 조회합니다.
- 실제 기준일 걸음 수를 사용합니다. Athena id는 bigint이므로 SQL 파라미터도 숫자로 전달합니다.
- 수면·심박 데이터는 빈 배열, 수면 단계는 데이터 없음으로 반환합니다.
- 대시보드는 기준일 이하 기록의 기준 주를 사용합니다. 지난주 비교 불가 시 delta=null입니다.
- low/medium은 화면 warn, high는 danger로 변환합니다.
- analysis.evaluatedDates의 날짜만 판정했습니다. 다른 날짜의 anomaly=false는 정상 판정의 증거가 아닙니다.
- aiGuide는 model, updatedAt, headline, text, actions와 status, analysisStatus, referenceDate, warnings를 반환합니다.
- 정상·데이터 부족은 status=not_applicable이며 analysisStatus로 구분합니다. 이상인데 생성 실패 시 missing, 생성 성공 시 generated입니다.
- REAL AI 대시보드의 devices, guideHistory, notifications는 빈 배열입니다.
- 조회·호출·응답 검증 실패는 예시 데이터로 대체하지 않습니다(503 또는 설정 오류 500).
- 현재 AI/ML은 과거 조회 실패를 insufficient_data로 처리할 수도 있어 200만으로 모든 하위 호출 성공을 단정하지 마세요.

## 코드 구조

- src/lambda_function.py: HTTP 라우팅과 고정 오류 응답. 서비스 핸들러는 src.lambda_function.lambda_handler.
- src/athena_repository.py, real_health_data.py: 조회·대상 확인·매핑.
  (활동 시간 네 컬럼 very/fairly/lightly/sedentary 를 함께 조회 — AI/ML v0.4 tracked_minutes 근거값)
- src/dashboard_service.py, dashboard_data.py: 주간 통계와 실제 대시보드.
- src/ml_adapter.py, ml_client.py: 요청 생성, Lambda 호출, 응답 검증.
  (v0.4: 요청 metrics.tracked_minutes 선택 전달, 응답 guide.lines 보존·응답 최상위 alert_sent 선택 처리)
  (v0.5: 요청 최상위 notify 전달(조회·재조회 경로는 False), 응답 최상위 alert_reason 선택 처리)
- src/ai_service.py: REAL API 조립과 화면용 변환.
- src/ml_integration_check.py: 고정 공개 데이터 ID/날짜의 콘솔 전용 검증 핸들러. API Gateway나 Function URL에 연결하지 마세요.
- src/ml_virtual_anomaly_check.py: 고정 가상 입력의 콘솔 전용 이상 경로 검증 핸들러(Athena 미사용, Bedrock 비용 발생 가능).
  API Gateway 이벤트는 거절하고, `{}` 이벤트는 가상 이상·가이드 점검을 실행합니다. API Gateway나 Function URL에 연결하지 마세요.
  v0.5 경계 테스트: lambda_handler 에 `{"check":"tracked_minutes_boundary","tracked_minutes":799|800}` 이벤트를 주면
  해당 케이스만 ML 을 1회 호출합니다(최상위 notify=false, 799→ACTIVITY_DROP 없음·800→ACTIVITY_DROP 감지,
  둘 다 alert_sent=false, alert_reason 원문 기록, 지원 외 값은 호출 전 거절).

## 로컬 검증

backend 폴더에서 Python 3.13으로 실행합니다.

```text
python -m unittest discover -s tests
```

428개 테스트가 가짜 AWS 클라이언트/패치된 연결로 실행됩니다(2026-11-06 로컬 실행 기준). 실제 AWS에는 접속하지 않습니다.
MOCK 경로와 테스트는 표준 라이브러리로 실행하며 실제 AWS 경로는 boto3/botocore가 필요합니다.
현재 Lambda 런타임 포함 SDK를 사용한 배포를 검증했습니다. SDK 버전 고정은 별도 작업입니다.