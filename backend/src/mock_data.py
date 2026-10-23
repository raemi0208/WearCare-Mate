"""WearCare Mate 백엔드 - 개발/테스트 전용 Mock 데이터 모듈.

⚠️ 주의 (중요):
    이 파일은 개발·테스트 전용입니다.
    - 실제 사용자 데이터를 조회하지 않습니다.
    - 아래 수치는 모두 "완전히 가상의 값"이며, Database 폴더의 실제 CSV
      기록을 복사한 것이 아닙니다.
    - 실제 Timestream 연동이 준비되면 이 모듈은 제거/대체되어야 하며,
      이 상태 그대로 실제 데이터 조회 기능으로 배포해서는 안 됩니다.

설계 원칙:
    - API 명세(api-spec.md)의 미확정(🟡) 항목을 임의로 확정하지 않습니다.
    - from/to 등 쿼리 값은 "그대로 돌려주기(echo)"만 하며,
      실제 날짜 필터링을 수행한 것처럼 표현하지 않습니다.
"""

# ---------------------------------------------------------------------------
# 공유 상수
# ---------------------------------------------------------------------------
# 이상탐지(anomalies)와 가이드(guides) 두 MOCK 응답이 같은 가상 anomalyId 를
# 참조하도록 한 곳에서 정의한다. 이렇게 하면 가이드의 relatedAnomalyId 가
# 항상 anomalies 의 anomalyId 중 하나와 일치하게 되어 일관성이 보장된다.
# (ID 를 바꿔도 양쪽이 자동으로 함께 바뀐다.)
MOCK_ANOMALY_IDS = ["mock-anomaly-001", "mock-anomaly-002"]

# 가이드 응답에 항상 포함할 면책 문구.
# ⚠️ 의료 진단/치료가 아니라 일반적인 생활 습관 권고임을 명시한다.
#    실제 Bedrock 연동 후에도 이 문구는 유지되어야 한다.
GUIDE_DISCLAIMER = (
    "본 안내는 일반적인 생활 습관 권고이며, 의학적 진단이나 치료를 대체하지 "
    "않습니다. 증상이 지속되면 전문가와 상담하세요."
)


def build_health_data_mock(user_id, query):
    """건강 데이터 조회(GET /users/{userId}/health-data)의 가상 응답을 만든다.

    이 함수는 외부 서비스에 연결하지 않고, 고정된 가상 값으로 응답을 구성한다.
    입력이 같으면 항상 같은 결과를 돌려주므로 테스트하기 쉽다.

    Args:
        user_id (str): 경로에서 추출한 사용자 식별자. (형식 검증은 하지 않음)
        query (dict): 쿼리 파라미터 딕셔너리. 예: {"from": "...", "to": "..."}
                      값이 없으면 None 이 아니라 빈 dict 가 들어온다고 가정한다.

    Returns:
        dict: API 응답 본문으로 쓸 파이썬 딕셔너리 (MOCK 표시 포함).
    """
    # 쿼리에서 from/to 를 그대로 꺼낸다. 없으면 None.
    # 주의: 여기서 실제 날짜 필터링은 하지 않는다. 받은 값을 그대로 보여줄 뿐이다.
    date_from = query.get("from")
    date_to = query.get("to")

    return {
        # 이 응답이 가짜 데이터임을 기계(프론트)와 사람 모두가 알 수 있게 표시
        "mock": True,
        "_note": (
            "MOCK 데이터입니다. 실제 사용자 건강 데이터가 아니며 개발/테스트 전용입니다. "
            "수치는 완전히 가상의 값이고, 날짜 필터링은 실제로 수행되지 않았습니다."
        ),
        "userId": user_id,
        # from/to 는 '요청 그대로 되돌려준 값'일 뿐, 실제 필터 결과가 아님을 이름으로 구분
        "requestedRange": {"from": date_from, "to": date_to},
        # 아래 items 는 전부 가상 값(실제 CSV 기록 복사 아님)
        "items": [
            {
                "date": "2099-01-01",
                "activity": {
                    "totalSteps": 1234,
                    "totalDistanceKm": 0.9,
                    "calories": 1000,
                    "veryActiveMinutes": 5,
                },
                "sleep": {
                    "sleepDurationHours": 7.0,
                    "sleepQualityScore": 5.0,
                    "heartRateVariability": 50.0,
                    "stressLevel": 2.0,
                },
            },
            {
                "date": "2099-01-02",
                "activity": {
                    "totalSteps": 2345,
                    "totalDistanceKm": 1.8,
                    "calories": 1100,
                    "veryActiveMinutes": 9,
                },
                "sleep": {
                    "sleepDurationHours": 6.5,
                    "sleepQualityScore": 4.0,
                    "heartRateVariability": 55.0,
                    "stressLevel": 3.0,
                },
            },
        ],
    }


def build_anomalies_mock(user_id, query):
    """이상탐지 결과 조회(GET /users/{userId}/anomalies)의 가상 응답을 만든다.

    ⚠️ 개발/테스트 전용. 실제 AI/ML(SageMaker) 결과가 아니라 고정된 가상 값이다.
    api-spec.md 4.3절의 임시 필드(anomalyId, detectedAt, metric, severity,
    score, description)를 따른다.

    설계 원칙:
        - AI/ML 파트의 실제 출력 스키마(특히 severity 값 집합, score 범위)는
          아직 확정되지 않았다. 따라서 이 함수는 값을 검증/확정하지 않고
          고정 가상값만 넣는다.
        - from/to/severity 쿼리는 requestedRange/requestedFilters 로
          "그대로 되돌려주기(echo)"만 하며, 실제 필터링은 수행하지 않는다.

    Args:
        user_id (str): 경로에서 추출한 사용자 식별자. (형식 검증은 하지 않음)
        query (dict): 쿼리 파라미터 딕셔너리. 예: {"from": ..., "to": ..., "severity": ...}
                      값이 없으면 None 이 아니라 빈 dict 가 들어온다고 가정한다.

    Returns:
        dict: API 응답 본문으로 쓸 파이썬 딕셔너리 (MOCK 표시 포함).
    """
    # 쿼리 값을 그대로 꺼낸다(없으면 None). 실제 필터링은 하지 않는다.
    date_from = query.get("from")
    date_to = query.get("to")
    severity_filter = query.get("severity")

    return {
        # 이 응답이 가짜 데이터임을 기계(프론트)와 사람 모두가 알 수 있게 표시
        "mock": True,
        "_note": (
            "MOCK 데이터입니다. 실제 AI/ML(SageMaker) 이상탐지 결과가 아니며 "
            "개발/테스트 전용입니다. 모든 값은 완전히 가상이고, "
            "from/to/severity 는 요청값을 그대로 되돌려줄 뿐 실제 필터링은 "
            "수행되지 않았습니다. 이상탐지 결과 스키마는 아직 미확정입니다."
        ),
        "userId": user_id,
        # 요청값 echo (실제 필터 결과가 아님을 이름으로 구분)
        "requestedRange": {"from": date_from, "to": date_to},
        "requestedFilters": {"severity": severity_filter},
        # 아래 items 는 전부 가상 값(실제 데이터/개인정보 아님)
        # anomalyId 는 공유 상수를 참조한다(값 자체는 기존과 동일 → 응답 불변).
        "items": [
            {
                "anomalyId": MOCK_ANOMALY_IDS[0],
                "detectedAt": "2099-01-01T23:10:00Z",
                "metric": "sleep_quality",
                "severity": "medium",
                "score": 0.82,
                "description": "평소 대비 수면의 질이 낮아진 가상 패턴입니다.",
            },
            {
                "anomalyId": MOCK_ANOMALY_IDS[1],
                "detectedAt": "2099-01-02T07:05:00Z",
                "metric": "heart_rate_variability",
                "severity": "low",
                "score": 0.41,
                "description": "평소 대비 심박 변이가 소폭 변화한 가상 패턴입니다.",
            },
        ],
    }


def build_guides_mock(user_id, query):
    """건강 행동 가이드 조회(GET /users/{userId}/guides)의 가상 응답을 만든다.

    ⚠️ 개발/테스트 전용. 실제 생성형 AI(Bedrock)가 만든 가이드가 아니라
    고정된 가상 문구이다. api-spec.md 4.4절의 필드를 따른다.

    설계 원칙:
        - 가이드는 '일반적인 생활 습관 권고'만 담는다.
          의료 진단/치료/약물 지시는 포함하지 않는다.
        - relatedAnomalyId 는 공유 상수 MOCK_ANOMALY_IDS 를 참조하므로
          anomalies MOCK 의 anomalyId 와 항상 일치한다.
        - anomalyId 쿼리는 requestedFilters 로 그대로 되돌려줄(echo) 뿐,
          실제 필터링은 수행하지 않는다.
        - disclaimer 로 의료 행위가 아님을 항상 고지한다.

    Args:
        user_id (str): 경로에서 추출한 사용자 식별자. (형식 검증은 하지 않음)
        query (dict): 쿼리 파라미터 딕셔너리. 예: {"anomalyId": "..."}
                      값이 없으면 None 이 아니라 빈 dict 가 들어온다고 가정한다.

    Returns:
        dict: API 응답 본문으로 쓸 파이썬 딕셔너리 (MOCK 표시 포함).
    """
    # 쿼리의 anomalyId 를 그대로 꺼낸다(없으면 None). 실제 필터링은 하지 않는다.
    anomaly_id_filter = query.get("anomalyId")

    return {
        # 이 응답이 가짜 데이터임을 기계(프론트)와 사람 모두가 알 수 있게 표시
        "mock": True,
        "_note": (
            "MOCK 데이터입니다. 실제 생성형 AI(Bedrock)가 만든 가이드가 아니며 "
            "개발/테스트 전용입니다. 모든 문구는 완전히 가상이고, "
            "anomalyId 는 요청값을 그대로 되돌려줄 뿐 실제 필터링은 수행되지 "
            "않았습니다. 가이드 출력 형식은 아직 미확정입니다."
        ),
        "userId": user_id,
        # 의료 행위가 아님을 항상 고지(공유 상수 사용)
        "disclaimer": GUIDE_DISCLAIMER,
        # 요청값 echo (실제 필터 결과가 아님을 이름으로 구분)
        "requestedFilters": {"anomalyId": anomaly_id_filter},
        # 아래 items 는 전부 가상 값. message 는 일반 생활 습관 권고만 담는다.
        # relatedAnomalyId 는 anomalies MOCK 의 anomalyId 와 일치(공유 상수 참조).
        "items": [
            {
                "guideId": "mock-guide-001",
                "relatedAnomalyId": MOCK_ANOMALY_IDS[0],
                "title": "규칙적인 취침 시간 유지하기",
                "message": (
                    "최근 수면의 질이 낮아진 가상 상황입니다. 매일 비슷한 시간에 "
                    "잠자리에 들면 수면 리듬을 안정시키는 데 도움이 됩니다."
                ),
                "category": "sleep",
                "createdAt": "2099-01-03T08:00:00Z",
            },
            {
                "guideId": "mock-guide-002",
                "relatedAnomalyId": MOCK_ANOMALY_IDS[1],
                "title": "가벼운 신체 활동 늘리기",
                "message": (
                    "활동량이 평소보다 적은 가상 상황입니다. 하루 중 짧게라도 "
                    "걷기나 스트레칭을 더하면 컨디션 관리에 도움이 됩니다."
                ),
                "category": "activity",
                "createdAt": "2099-01-03T08:05:00Z",
            },
        ],
    }
