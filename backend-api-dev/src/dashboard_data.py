"""WearCare Mate 백엔드 - /dashboard 데이터 조립 (MOCK / REAL).

데이터 소스 선택은 기존 health-data 와 같은 방식으로 data_source.select_dashboard_builder() 가 한다.
    - DATA_SOURCE=mock(기본값): dashboard_mock_data.build_dashboard_mock() (기존 MOCK 그대로)
    - DATA_SOURCE=real        : 이 모듈의 build_real_dashboard()

REAL 대시보드 (개발·통합 테스트 전용):
    - 진입 조건: DATA_SOURCE=real + ENABLE_REAL_DATA_TESTING=true + DASHBOARD_USER_ID
      (health-data REAL 과 같은 조건. 하나라도 없으면 503 또는 500)
    - 조회 대상: DASHBOARD_USER_ID 사용자 1명. 요청에서 사용자 ID 를 받지 않는다.
      ⚠️ 개발용 데모 대상 지정일 뿐 인증·인가를 대신하지 않는다. 공개 배포 환경에서 켜지 않는다.
    - 실제 데이터로 채우는 항목: summaryStats 의 steps 카드, timeseries.steps (Athena 걸음 수)
    - 데이터가 없어 비우는 항목 (임의 수치 생성 금지):
        summaryStats 의 sleep/hr/score 카드 → 넣지 않음
        timeseries.sleep / heartRate → []
        sleepStages → {"totalLabel": "데이터 없음", "segments": []}
    - MOCK 유지 항목 (AI/ML·SNS 연동 전, "[예시]" 표시 유지): anomalies, aiGuide, notifications
    - user: 실제 이름·나이 데이터가 없으므로 개발용 데모 표시 문구를 쓴다. 사용자 ID 는 넣지 않는다.
    - 조회 실패 시 MOCK 으로 대체하지 않는다. (503)

⚠️ 실제 AWS 조회 검증 여부:
    로컬 단위 테스트(가짜 Athena 클라이언트)로만 검증했다. 실제 Athena 조회는 아직 실행하지 않았다.
"""

from src.dashboard_mock_data import build_dashboard_mock
from src.dashboard_service import (
    build_steps_summary_card,
    build_steps_timeseries,
    compute_weekly_steps,
)
from src.data_source import DataSourceUnavailableError
from src.health_service import build_activity_items
from src.real_health_data import (
    fetch_mapped_activity_rows,
    get_allowed_user_id,
    is_real_data_testing_enabled,
)

REAL_DEMO_USER = {
    "name": "데모 사용자",
    "meta": "개발용 데모 · 인증 미적용 · Fitbit 공개 데이터",
    "initial": "데",
}

NO_SLEEP_STAGES = {"totalLabel": "데이터 없음", "segments": []}


def fetch_dashboard_activity_items(client_factory=None, environ=None):
    """REAL 대시보드용 활동 데이터를 조회한다. (DASHBOARD_USER_ID 사용자만)

    처리 순서:
        1) 실제 데이터 테스트 스위치 확인 → 꺼져 있으면 503
        2) DASHBOARD_USER_ID 확인 → 없거나 형식 오류면 500
        3) Athena 조회 (날짜 조건 없이, 최대 행 수까지) → 매핑
        4) 결과가 최대 행 수에 도달하면 503
           (조회는 오래된 날짜부터 정렬되므로, 잘린 경우 "가장 최근 주"를 보장할 수 없다.
            잘못된 통계를 보여주지 않기 위해 오류로 처리한다.)
        5) health_service.build_activity_items 로 사용자 필터링(방어) + {date, activity} 변환

    Returns:
        list[dict]: [{"date": "YYYY-MM-DD", "activity": {...}}, ...]
    """
    if not is_real_data_testing_enabled(environ):
        raise DataSourceUnavailableError("실제 데이터 조회가 활성화되어 있지 않습니다.")

    user_id = get_allowed_user_id(environ)
    mapped_rows, config = fetch_mapped_activity_rows(
        user_id, client_factory=client_factory, environ=environ
    )
    if len(mapped_rows) >= config.max_rows:
        raise DataSourceUnavailableError("조회 결과가 최대 행 수에 도달해 최근 데이터를 보장할 수 없습니다.")

    return build_activity_items(mapped_rows, user_id)


def build_real_dashboard(client_factory=None, environ=None):
    """REAL 대시보드 응답 본문을 만든다. (API.md 스키마, 걸음 수만 실제 데이터)

    Args:
        client_factory (callable | None): region 을 받아 Athena 클라이언트를 돌려주는 함수.
            None 이면 athena_repository.create_athena_client. 테스트에서는 가짜를 넣는다.
        environ (Mapping | None): 읽을 환경변수. None 이면 os.environ.

    Raises:
        DataSourceUnavailableError: 스위치 꺼짐, AWS 조회 실패, 최대 행 수 도달 (503)
        DataSourceConfigError: DASHBOARD_USER_ID/Athena 설정 오류, boto3 미설치 (500)
    """
    items = fetch_dashboard_activity_items(client_factory=client_factory, environ=environ)
    stats = compute_weekly_steps(items)
    steps_card = build_steps_summary_card(stats)

    # MOCK 을 바탕으로 하되, 실제 데이터가 없는 항목은 비우고 걸음 수만 실제 값으로 바꾼다.
    # anomalies / aiGuide / notifications 는 "[예시]" 표시가 있는 MOCK 그대로 둔다.
    body = build_dashboard_mock()
    body["user"] = dict(REAL_DEMO_USER)
    body["summaryStats"] = [steps_card] if steps_card is not None else []
    body["timeseries"] = {
        "sleep": [],
        "heartRate": [],
        "steps": build_steps_timeseries(stats),
    }
    body["sleepStages"] = {"totalLabel": NO_SLEEP_STAGES["totalLabel"], "segments": []}
    return body
