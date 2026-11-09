# 가상 이상 시연과 영구 보관

- 기준일: 2026-11-14. 실제 Fitbit 기록의 2016-04-10 기준일은 바꾸지 않습니다.
- POST /demo/anomaly: `{ "scenario": "steps|sleep|hrv|stress|multi" }`.
- steps: 걸음 수 1,000, 기록 시간 800분. 나머지 시나리오의 걸음 수는 정상 기준 10,000.
- sleep: 수면 3시간, hrv: HRV 15, stress: 스트레스 10. multi는 세 지표 동시 입력.
- 값은 서버에서 고정합니다. 실제 데이터셋이나 개인 진단 결과가 아닙니다. 분석 호출은 항상 notify=false입니다.

## 이메일 시연

분석 후 반환된 eventId로 `{ "action": "send", "eventId": "..." }`를 같은 POST 경로에 보냅니다.
저장된 가이드만 기존 SNS 주제로 발송합니다. 수신 주소·본문·SNS ARN은 브라우저에서 받지 않습니다.
DynamoDB 조건부 갱신으로 발송을 먼저 예약하고 SNS를 호출합니다. 같은 eventId는 한 번만 발송을 시도합니다.
SNS SDK 자동 재시도는 끕니다. 타임아웃·중단 시 pending/unknown 상태를 유지하며 자동 재발송하지 않습니다.
accepted는 SNS가 발송 요청을 접수했다는 뜻이며 이메일 수신함 도착을 보장하는 상태가 아닙니다.

## 영구 보관

HISTORY_TABLE=wearcare-mate-demo-history, Seoul, on-demand. pk는 검증된 Cognito sub의 해시,
sk는 시간 순서가 포함된 이벤트 ID입니다. TTL 없음, 삭제 보호 사용.
가상 시연의 생성 가이드, 실제 기록에서 생성된 가이드, 이메일 발송 요청 내역을 계정별로 저장합니다.
이전 배포에서 보관하지 않았던 가이드·메일 내역은 소급 복원하지 않습니다.
GET /dashboard가 첫 25개 이벤트의 내역을 함께 반환합니다. GET /history?cursor=... 로 다음 페이지를 조회합니다.
JWT authorizer sxfyqg 및 wearcare-demo/read scope는 기존 경로와 동일합니다.
로그아웃·재로그인 후에도 보관됩니다. 결과 저장 실패 시 발송 버튼을 활성화하지 않습니다.

DEMO_SNS_TOPIC_ARN=arn:aws:sns:ap-northeast-2:709569057941:wearcare-mate-alert.
실행 역할은 해당 테이블 GetItem/PutItem/UpdateItem/Query 및 해당 SNS 주제 Publish만 추가합니다.
기존 조회·재확인·페이지 이동·새로고침은 이메일을 발송하지 않습니다.

## 알림 목록 정리

POST /demo/anomaly에 `{ "action": "hide_notification", "eventId": "..." }`를 보내면
로그인 계정의 해당 알림만 목록에서 숨깁니다. notificationHidden 속성만 갱신하며,
가이드·원본 발송 결과·중복 발송 방지 기록은 유지합니다. 이메일을 회수하거나 재발송을 허용하지 않습니다.
실제 메일 발송 버튼 표시는 `SNS 메일 발송`입니다. 분석·조회는 발송하지 않고 버튼에서만 기존 구독자에게 발송합니다.
