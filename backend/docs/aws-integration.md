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
- 새 백엔드 API 조립 경로에서 이상·생성 가이드가 반환되는 전체 AWS 흐름은 아직 별도 검증 필요.
- 프론트엔드 수정 PR #8은 별도 작업이며 실제 브라우저 통합은 미완료.

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

Python 3.13, x86_64에서 검증했습니다. 백엔드·테스트 함수 timeout은 30초,
AI/ML은 1분으로 설정했습니다. 전체 동기 API의 응답 시간은 별도 제약이므로
Lambda timeout만 늘려 해결된다고 간주하지 마세요.

## 재검증 순서

1. API Gateway가 없는 테스트 함수에만 새 코드를 업로드하고 일반 서비스 핸들러 설정.
2. README의 REAL 설정을 적용하고 ML_TARGET_DATE=2016-04-10 지정.
3. HTTP API payload 2.0 이벤트로 GET /dashboard와 GET /ai-guide 실행.
4. statusCode=200, analysisStatus/status, referenceDate, 가이드 유무를 함께 확인.
5. 이상 경로는 담당자와 검증 입력을 확정해 실제 가이드 생성까지 별도로 확인.
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
