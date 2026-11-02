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
- 콘솔 전용 연결 프로브: src.ml_integration_check.lambda_handler
  - 고정 사용자·날짜 조회와 호출 검증을 위한 도구입니다. 공개 HTTP 경로에 연결하지 마세요.
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
