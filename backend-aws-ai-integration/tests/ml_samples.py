"""AI/ML v0.3 샘플 요청·응답 (테스트 픽스처).

출처: origin/ai-ml @ 3dc9a94 의 docs/sample_responses.json (AI/ML 파트 작성).
원본 파일은 수정하지 않았으며, 값과 필드를 그대로 옮겼다.
가이드 문장은 원본 샘플의 내용이며, 의료 진단이 아닌 일반 생활 습관 권고이다.

이 모듈은 test_ 로 시작하지 않으므로 unittest 가 테스트로 수집하지 않는다.
테스트에서 값을 바꿔도 다른 테스트에 영향이 없도록 sample() 은 깊은 복사본을 돌려준다.
"""

import copy

_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
_MODEL_VERSION = "activity-zscore-v0.2+pop-v0.3"
_HISTORY = [12000, 11500, 13000, 12400, 12800, 11900, 12300]

_SAMPLES = {
    "activity_drop_high": {
        "request": {
            "user_id": "demo-user-1",
            "date": "2026-10-30",
            "metrics": {"steps": 2100},
            "history_steps": list(_HISTORY),
        },
        "response": {
            "user_id": "demo-user-1",
            "date": "2026-10-30",
            "anomalies": [
                {
                    "type": "ACTIVITY_DROP", "basis": "personal", "metric": "steps",
                    "value": 2100, "baseline_mean": 12271, "baseline_std": 522,
                    "z_score": -19.49, "drop_pct": -82.9, "severity": "high",
                }
            ],
            "anomaly_score": None,
            "guide": {
                "text": (
                    "오늘 걸음 수가 평소 12,271보보다 2,100보로 크게 줄었네요.\n"
                    "오늘부터 매일 10분씩 산책하는 시간을 만들어보세요.\n"
                    "증상이 지속되거나 불편하면 전문가와 상담해보세요."
                ),
                "lines": [
                    "오늘 걸음 수가 평소 12,271보보다 2,100보로 크게 줄었네요.",
                    "오늘부터 매일 10분씩 산책하는 시간을 만들어보세요.",
                    "증상이 지속되거나 불편하면 전문가와 상담해보세요.",
                ],
                "model_id": _MODEL_ID,
                "warnings": [],
                "generated_at": "2026-10-30T14:40:09+09:00",
            },
            "model_version": _MODEL_VERSION,
            "overall_severity": "high",
            "status": "anomaly",
        },
    },
    "sleep_stress_hrv_high": {
        "request": {
            "user_id": "demo-user-2",
            "date": "2026-10-30",
            "metrics": {"sleep_hours": 3.6, "heart_rate_variability": 28.0, "stress_level": 9.4},
        },
        "response": {
            "user_id": "demo-user-2",
            "date": "2026-10-30",
            "anomalies": [
                {"type": "SLEEP_SHORT", "basis": "population", "metric": "sleep_hours",
                 "value": 3.6, "population_mean": 7.47, "z_score": -2.51, "severity": "medium"},
                {"type": "HRV_LOW", "basis": "population", "metric": "heart_rate_variability",
                 "value": 28.0, "population_mean": 70.39, "z_score": -2.16, "severity": "low"},
                {"type": "STRESS_HIGH", "basis": "population", "metric": "stress_level",
                 "value": 9.4, "population_mean": 4.94, "z_score": 2.19, "severity": "low"},
            ],
            "anomaly_score": None,
            "guide": {
                "text": (
                    "오늘 수면 시간이 3.6시간으로 평균 7.5시간보다 크게 부족했고, 심박 변이도는 28.0으로 "
                    "평균 70.4에 미치지 못했으며, 스트레스 점수는 9.4로 평균 4.9보다 매우 높아요.\n"
                    "오늘부터 취침 시각을 지금보다 2시간 앞당기고, 자기 전에 5분간 깊게 숨 쉬는 시간을 "
                    "가져보세요.\n"
                    "증상이 지속되거나 불편하면 전문가와 상담해보세요."
                ),
                "lines": [
                    "오늘 수면 시간이 3.6시간으로 평균 7.5시간보다 크게 부족했고, 심박 변이도는 28.0으로 "
                    "평균 70.4에 미치지 못했으며, 스트레스 점수는 9.4로 평균 4.9보다 매우 높아요.",
                    "오늘부터 취침 시각을 지금보다 2시간 앞당기고, 자기 전에 5분간 깊게 숨 쉬는 시간을 "
                    "가져보세요.",
                    "증상이 지속되거나 불편하면 전문가와 상담해보세요.",
                ],
                "model_id": _MODEL_ID,
                "warnings": [],
                "generated_at": "2026-10-30T14:40:09+09:00",
            },
            "model_version": _MODEL_VERSION,
            "overall_severity": "high",
            "status": "anomaly",
        },
    },
    "normal": {
        "request": {
            "user_id": "demo-user-3",
            "date": "2026-10-30",
            "metrics": {"steps": 11800, "sleep_hours": 7.2, "stress_level": 4.5},
            "history_steps": list(_HISTORY),
        },
        "response": {
            "user_id": "demo-user-3",
            "date": "2026-10-30",
            "anomalies": [],
            "anomaly_score": None,
            "guide": None,
            "model_version": _MODEL_VERSION,
            "overall_severity": "none",
            "status": "normal",
        },
    },
    "insufficient_data": {
        "request": {
            "user_id": "demo-user-4",
            "date": "2026-10-30",
            "metrics": {"steps": 2000},
            "history_steps": [8000, 7500, 8200],
        },
        "response": {
            "user_id": "demo-user-4",
            "date": "2026-10-30",
            "anomalies": [],
            "anomaly_score": None,
            "guide": None,
            "model_version": _MODEL_VERSION,
            "status": "insufficient_data",
            "overall_severity": "none",
        },
    },
}

SAMPLE_NAMES = tuple(_SAMPLES)


def sample(name):
    """샘플 {request, response} 의 깊은 복사본."""
    return copy.deepcopy(_SAMPLES[name])
