"""WearCare Mate 백엔드 - /dashboard, /ai-guide 개발/테스트 전용 MOCK 데이터.

프론트엔드 API.md 의 JSON 스키마(필드 이름·타입)를 그대로 따릅니다.

⚠️ 주의 (중요):
    - 모든 값은 화면 확인용 "예시 데이터"입니다. 실제 사용자, 실제 측정값,
      실제 AI(SageMaker/Bedrock) 분석 결과가 아닙니다.
    - 실제 결과로 오인되지 않도록, 화면에 그대로 보이는 문자열에 예시 표시를 넣었습니다.
        · user.name / user.meta        → "예시 사용자", "예시 데이터 · 실제 사용자 아님"
        · summaryStats[].deltaLabel    → "예시 데이터"
        · anomalies / notifications    → title 앞 "[예시]", desc 끝 안내 문구
        · aiGuide.model / updatedAt    → "MOCK · 실제 AI 생성 아님", "예시 데이터"
        · aiGuide.headline / text      → "[예시]" 표시와 의료 면책 문구
    - 프론트 API.md 에 없는 필드(mock, _note, meta 등)는 넣지 않습니다.
      (meta.dataSources 확장 필드는 프론트엔드 호환 확인 후 추가 예정)
    - 날짜·시간은 실제 시점처럼 보이지 않도록 요일/상대시간 대신 "예시" 표기를 씁니다.
    - 가이드는 일반적인 생활 습관 권고만 담으며, 의료 진단·치료 지시가 아닙니다.

매 호출마다 새 dict 를 만들어 돌려주므로, 호출한 쪽에서 값을 바꿔도 다음 응답에 영향이 없습니다.
"""

EXAMPLE_LABEL = "예시 데이터"
EXAMPLE_PREFIX = "[예시] "
EXAMPLE_DESC_SUFFIX = " (AI 분석 결과가 아닌 예시 데이터입니다.)"

MOCK_GUIDE_MODEL = "MOCK · 실제 AI 생성 아님"
MOCK_GUIDE_DISCLAIMER = (
    "이 안내는 화면 확인용 예시이며, 일반적인 생활 습관 권고입니다. "
    "의학적 진단이나 치료를 대체하지 않습니다. 증상이 지속되면 전문가와 상담하세요."
)

# 요일 라벨 (월~일)
WEEKDAY_LABELS = ("월", "화", "수", "목", "금", "토", "일")


def build_ai_guide_mock():
    """aiGuide 객체(= GET /ai-guide 응답)의 MOCK 을 만든다. Bedrock 을 호출하지 않는다."""
    return {
        "model": MOCK_GUIDE_MODEL,
        "updatedAt": EXAMPLE_LABEL,
        "headline": EXAMPLE_PREFIX + "수면 리듬을 일정하게 유지해 보세요",
        "text": (
            "예시 화면에서 수면 시간이 줄어든 상황을 가정한 문구입니다. "
            "취침과 기상 시간을 비슷하게 맞추면 생활 리듬을 안정시키는 데 도움이 됩니다. "
            + MOCK_GUIDE_DISCLAIMER
        ),
        "actions": [
            "매일 비슷한 시간에 잠자리에 들기",
            "잠들기 1시간 전에는 화면 밝기 줄이기",
            "낮 시간에 가벼운 걷기 더하기",
        ],
    }


def _series(values, anomaly_index=None):
    """요일 순서(월~일) 7개 시계열을 만든다. value 는 숫자, anomaly 는 bool."""
    return [
        {"label": label, "value": value, "anomaly": index == anomaly_index}
        for index, (label, value) in enumerate(zip(WEEKDAY_LABELS, values))
    ]


def build_dashboard_mock():
    """GET /dashboard 응답 전체의 MOCK 을 만든다. (API.md 스키마)"""
    return {
        "user": {
            "name": "예시 사용자",
            "meta": "예시 데이터 · 실제 사용자 아님",
            "initial": "예",
        },
        # 권장 4개: sleep / hr / steps / score
        "summaryStats": [
            {"id": "sleep", "icon": "🌙", "label": "평균 수면", "value": "6.9",
             "unit": "시간", "delta": -4, "deltaLabel": EXAMPLE_LABEL},
            {"id": "hr", "icon": "❤️", "label": "안정 시 심박", "value": "64",
             "unit": "bpm", "delta": 2, "deltaLabel": EXAMPLE_LABEL},
            {"id": "steps", "icon": "👟", "label": "평균 걸음 수", "value": "7,929",
             "unit": "보", "delta": 5, "deltaLabel": EXAMPLE_LABEL},
            {"id": "score", "icon": "⭐", "label": "컨디션 점수", "value": "78",
             "unit": "/100", "delta": 0, "deltaLabel": EXAMPLE_LABEL},
        ],
        # 최근 7일(월~일). value 는 반드시 숫자.
        # anomaly=true 는 화면 강조 확인용 예시이며 실제 이상 판정이 아니다.
        "timeseries": {
            "sleep": _series([7.2, 6.8, 7.0, 5.9, 6.5, 7.8, 7.4]),
            "heartRate": _series([62, 63, 61, 74, 64, 62, 63], anomaly_index=3),
            "steps": _series([8200, 7600, 9100, 6200, 7400, 10300, 6700]),
        },
        # pct 합계 = 100
        "sleepStages": {
            "totalLabel": "7시간 18분 (예시)",
            "segments": [
                {"id": "deep", "label": "깊은 수면", "pct": 22, "color": "#141414"},
                {"id": "light", "label": "얕은 수면", "pct": 48, "color": "#71717a"},
                {"id": "rem", "label": "REM", "pct": 22, "color": "#a1a1aa"},
                {"id": "awake", "label": "깨어남", "pct": 8, "color": "#d6d6db"},
            ],
        },
        # severity 는 danger / warn / ok 세 값만 사용
        "anomalies": [
            {"id": "mock-a1", "severity": "warn",
             "title": EXAMPLE_PREFIX + "안정 시 심박 상승 패턴",
             "time": EXAMPLE_LABEL,
             "desc": "평소 대비 심박이 높게 나타난 가상의 상황입니다." + EXAMPLE_DESC_SUFFIX},
            {"id": "mock-a2", "severity": "ok",
             "title": EXAMPLE_PREFIX + "활동량 정상 범위",
             "time": EXAMPLE_LABEL,
             "desc": "걸음 수가 평소 범위 안에 있는 가상의 상황입니다." + EXAMPLE_DESC_SUFFIX},
        ],
        "aiGuide": build_ai_guide_mock(),
        "notifications": [
            {"id": "mock-n1", "icon": "🔔",
             "title": EXAMPLE_PREFIX + "새 건강 가이드가 준비되었습니다", "time": EXAMPLE_LABEL},
            {"id": "mock-n2", "icon": "🔔",
             "title": EXAMPLE_PREFIX + "주간 활동 요약을 확인해 보세요", "time": EXAMPLE_LABEL},
        ],
        # 발표용 "별도 데이터셋" 요약 (MOCK). REAL 에서는 실제 Athena 집계로 덮어쓴다.
        # 스키마 일관성을 위해 MOCK 에도 같은 키를 둔다. 값은 예시임을 status/라벨로 구분.
        "sleepDatasetSummary": {
            "status": "ok", "sourceLabel": "별도 데이터셋",
            "averageHours": 7.47, "recordCount": 1000,
        },
        "heartRateDatasetSummary": {
            "status": "ok", "sourceLabel": "별도 데이터셋",
            "totalRows": 30000, "numericRows": 30000, "zeroRows": 206, "positiveRows": 29794,
            "averageValue": 79.9, "averageBasis": "positive", "unit": "bpm",
        },
        "psychologyDatasetSummary": {
            "status": "ok", "sourceLabel": "별도 데이터셋", "unit": "데이터 행 수",
            "files": [
                {"id": "integrated", "label": "통합 데이터셋", "rowCount": 1328},
                {"id": "validation", "label": "검증 데이터셋", "rowCount": 175},
            ],
        },
    }
