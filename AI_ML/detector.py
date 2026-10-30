"""WearCare Mate 이상 탐지 (스펙 v0.3).

입력 dict + 과거 걸음 수 기록 -> 출력 dict (스펙 6, 7번).
SageMaker 노트북과 Lambda에서 같은 파일을 쓴다. 외부 의존: numpy (필수), scikit-learn (선택), boto3 (가이드 호출 시).
"""
import json
from datetime import datetime, timezone, timedelta

MODEL_VERSION = "activity-zscore-v0.2+pop-v0.3"

# ---- 집단 기준 (population_stats.json 과 동일한 값, 스펙 5번) ----
POP_STATS = {
    "heart_rate_variability": {"mean": 70.38664111641899, "std": 19.58431876382427},
    "sleep_hours": {"mean": 7.4719211733129995, "std": 1.5406987881414886},
    "stress_level": {"mean": 4.9409560684180995, "std": 2.0327084768313677},
    "movement_during_sleep": {"mean": 2.0134607082577, "std": 0.9653675462794205},
}
# (유형, 입력 지표, 나쁜 방향 부호): 부호 -1 이면 값이 낮을수록 나쁨
POP_RULES = [
    ("HRV_LOW", "heart_rate_variability", -1),
    ("SLEEP_SHORT", "sleep_hours", -1),
    ("STRESS_HIGH", "stress_level", +1),
    ("SLEEP_RESTLESS", "movement_during_sleep", +1),
]
POP_THRESHOLDS = [(3.0, "high"), (2.5, "medium"), (2.0, "low")]

# ---- 개인 기준선 (스펙 4번) ----
WINDOW, MIN_RECORDS, STD_FLOOR = 14, 5, 500.0

RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}
NAME = {v: k for k, v in RANK.items()}


def _pop_severity(z):
    for th, name in POP_THRESHOLDS:
        if z >= th:
            return name
    return "none"


def population_check(metrics):
    """집단 기준. 나쁜 방향 z만 본다. 반환: (anomalies, bad_vector)"""
    anomalies, bad_vec = [], []
    for typ, key, sign in POP_RULES:
        v = metrics.get(key)
        if v is None:
            bad_vec.append(None)
            continue
        if key == "movement_during_sleep":
            v = max(v, 0.0)  # 음수 보정
        st = POP_STATS[key]
        z_raw = (v - st["mean"]) / st["std"]
        z_bad = max(sign * z_raw, 0.0)
        bad_vec.append(z_bad)
        sev = _pop_severity(z_bad)
        if sev != "none":
            anomalies.append({
                "type": typ, "basis": "population", "metric": key,
                "value": v, "population_mean": round(st["mean"], 2),
                "z_score": round(sign * z_bad, 2) if sign < 0 else round(z_bad, 2),
                "severity": sev,
            })
    return anomalies, bad_vec


def personal_check(steps, history_steps):
    """걸음 수 개인 기준선. history_steps: 기준일 직전 기록(오래된 순 또는 무관, 마지막 최대 14개 사용).
    0걸음은 기기 미착용으로 보고 제외. 반환: (anomaly 또는 None, 'ok'|'insufficient_data')"""
    if steps is None:
        return None, "insufficient_data"
    hist = [h for h in history_steps if h and h > 0][-WINDOW:]
    if len(hist) < MIN_RECORDS:
        return None, "insufficient_data"
    n = len(hist)
    mean = sum(hist) / n
    std = (sum((h - mean) ** 2 for h in hist) / (n - 1)) ** 0.5 if n > 1 else 0.0
    std_eff = max(std, STD_FLOOR)
    z = (steps - mean) / std_eff
    drop = (steps - mean) / mean * 100.0
    sev = "none"
    if z <= -2.0 and drop <= -50:
        sev = "high"
    elif z <= -1.5 and drop <= -40:
        sev = "medium"
    elif z <= -1.0 and drop <= -40:
        sev = "low"
    if sev == "none":
        return None, "ok"
    return {
        "type": "ACTIVITY_DROP", "basis": "personal", "metric": "steps",
        "value": steps, "baseline_mean": round(mean), "baseline_std": round(std),
        "z_score": round(z, 2), "drop_pct": round(drop, 1), "severity": sev,
    }, "ok"


def _overall(anomalies):
    if not anomalies:
        return "none"
    top = max(RANK[a["severity"]] for a in anomalies)
    if len({a["metric"] for a in anomalies}) >= 2:  # 서로 다른 지표 2개 이상이면 한 단계 올림 (high 유지)
        top = min(top + 1, 3)
    return NAME[top]


def detect(inp, history_steps=None, iforest=None):
    """inp: 스펙 6번 입력 dict. history_steps: 직전 걸음 수 리스트. iforest: 학습된 IsolationForest (선택)."""
    m = inp.get("metrics", {}) or {}
    anomalies, checked = [], 0

    pers, pstat = personal_check(m.get("steps"), history_steps or [])
    if pstat == "ok":
        checked += 1
    if pers:
        anomalies.append(pers)

    pop, bad_vec = population_check(m)
    checked += sum(v is not None for v in bad_vec)
    anomalies.extend(pop)

    out = {"user_id": inp.get("user_id"), "date": inp.get("date"),
           "anomalies": [], "anomaly_score": None, "guide": None, "model_version": MODEL_VERSION}
    if checked == 0:
        out.update(status="insufficient_data", overall_severity="none")
        return out

    anomalies.sort(key=lambda a: RANK[a["severity"]], reverse=True)  # 심각도 높은 순 (프롬프트 순서 규칙)
    out["anomalies"] = anomalies
    out["overall_severity"] = _overall(anomalies)
    out["status"] = "anomaly" if anomalies else "normal"

    if iforest is not None and all(v is not None for v in bad_vec):
        out["anomaly_score"] = round(float(-iforest.score_samples([bad_vec])[0]), 2)  # 참고값, 심각도에는 미반영
    return out


def fit_iforest(rows):
    """rows: [{'heart_rate_variability':..,'sleep_hours':..,'stress_level':..,'movement_during_sleep':..}, ...]"""
    from sklearn.ensemble import IsolationForest
    X = []
    for r in rows:
        _, vec = population_check(r)
        if all(v is not None for v in vec):
            X.append(vec)
    return IsolationForest(n_estimators=200, contamination=0.05, random_state=42).fit(X)


# ---- Bedrock 가이드 (프롬프트 v6: v5 + 시점/직접 계산 금지, 행동 수치 포함 - 검증 중) ----
SYSTEM_PROMPT = """너는 웨어러블 데이터를 바탕으로 건강 습관을 안내하는 도우미야.

규칙:
- 의학적 진단, 병명 언급, 약 처방은 하지 않는다.
- 입력된 수치의 원인이나 지표 간 연관을 추측하지 않는다. 수치만 서술한다.
- 퍼센트나 배수를 새로 계산하지 말고, 입력의 수치를 그대로 인용한다. "절반", "두 배", "○% 감소"처럼 직접 계산한 표현은 쓰지 않는다.
- 입력의 "평소"는 본인의 평소 기록, "평균"은 전체 사용자 평균이다. 입력에 쓰인 표현을 그대로 쓰고 "평소 평균"처럼 섞어 쓰지 않는다.
- 입력된 이상 징후를 빠짐없이 반영하고, 입력에 나열된 순서대로 다룬다 (앞쪽일수록 더 심각하다).
- 입력에 없는 사실(시점, 원인, 생활 습관)을 추측하지 않는다. 시점은 입력에 있는 "오늘"만 쓰고 "어제", "어젯밤", "지난주" 같은 표현은 쓰지 않는다.
- 이모지는 쓰지 않는다.
- 말투는 친근한 해요체(~해요, ~보세요)로 쓴다. "~습니다"체는 쓰지 않는다.
- 정확히 3줄로 쓰고, 한 줄은 한 문장이다. 문장이 끝나면 반드시 줄을 바꾼다. 한 문단으로 이어 쓰지 않는다.
  - 1줄: 입력된 이상 징후를 입력 순서대로 모두 요약한다.
  - 2줄: 일상에서 할 수 있는 구체적인 행동을 한 문장으로 제안한다. 시간, 횟수, 시각 중 하나의 수치를 포함한다 (예: 취침 시각 30분 앞당기기, 10분 걷기).
  - 3줄: 증상이 지속되거나 불편하면 전문가와 상담하라는 문장으로 한다."""

_LABEL = {
    "steps": ("걸음 수", "보", 0), "sleep_hours": ("수면 시간", "시간", 1),
    "heart_rate_variability": ("심박 변이도(HRV)", "", 1), "stress_level": ("스트레스 점수(10점 만점)", "", 1),
    "movement_during_sleep": ("수면 중 움직임", "", 1),
}


def _fmt(v, nd):
    return f"{v:,.0f}" if nd == 0 else f"{v:.{nd}f}"


def build_prompt(anomalies):
    """anomalies(심각도순) -> 프롬프트 v4 의 '[오늘의 이상 징후]' 블록. personal='평소', population='평균'."""
    lines = ["[오늘의 이상 징후]"]
    for a in anomalies:
        name, unit, nd = _LABEL[a["metric"]]
        if a["basis"] == "personal":
            ref = f"평소 {_fmt(a['baseline_mean'], nd)}{unit}"
        else:
            ref = f"평균 {_fmt(a['population_mean'], nd)}{unit}"
        lines.append(f"- {name}: {_fmt(a['value'], nd)}{unit} ({ref})")
    return "\n".join(lines)


BANNED = ["어제", "어젯밤", "지난주", "지난밤", "절반", "두 배", "두배", "%", "퍼센트", "습니다", "합니다",
          "영향을 미", "영향을 줄", "질환", "질병", "우울증", "불면증", "당뇨", "고혈압"]  # 앞쪽: 시점/계산/격식체, 뒤쪽: 결과 예측과 병명


def validate_guide(lines, anomalies=None):
    """가이드 규칙 위반을 찾는다. anomalies를 주면 오늘 수치가 답변에 있는지도 본다. 반환: 문제 문자열 리스트 (비어 있으면 통과)."""
    import re
    issues = []
    if len(lines) != 3:
        issues.append(f"줄 수 {len(lines)}")
    for i, l in enumerate(lines, 1):
        if len(re.findall(r"[.!?](?:\s|$)", l)) > 1:
            issues.append(f"{i}줄에 문장 2개 이상")
        for w in BANNED:
            if w in l:
                issues.append(f"{i}줄 금지 표현 '{w}'")
        if re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", l):
            issues.append(f"{i}줄 이모지")
    if lines and "상담" not in lines[-1]:
        issues.append("마지막 줄 상담 권유 없음")
    if anomalies:
        body = " ".join(lines)
        for a in anomalies:
            _, unit, nd = _LABEL[a["metric"]]
            v = _fmt(a["value"], nd)
            if v not in body and v.replace(",", "") not in body:
                issues.append(f"오늘 수치 누락 {a['metric']}={v}")
    return issues


def generate_guide(anomalies, model_id, region, context=None, max_tries=2):
    """Bedrock converse 호출. [미검증] 노트북/Lambda 권한 해결 후 테스트 필요. 실패 시 None (탐지 결과는 그대로 반환)."""
    try:
        import boto3
        text = build_prompt(anomalies)
        if context:
            text += "\n\n[참고 정보(원인으로 단정하지 말 것)]\n" + json.dumps(context, ensure_ascii=False)
        client = boto3.client("bedrock-runtime", region_name=region)
        guide = None
        for _ in range(max_tries):  # 규칙 위반이면 한 번 더 시도, 끝까지 위반이면 마지막 결과에 warnings를 달아 반환
            r = client.converse(
                modelId=model_id,
                system=[{"text": SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": [{"text": text}]}],
                inferenceConfig={"maxTokens": 400, "temperature": 0.3},
            )
            lines = split_lines(r["output"]["message"]["content"][0]["text"])
            issues = validate_guide(lines, anomalies)
            guide = {"text": "\n".join(lines), "lines": lines, "model_id": model_id, "warnings": issues,
                     "generated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")}
            if not issues:
                break
        return guide
    except Exception as e:  # GUIDE_FAILED
        print("GUIDE_FAILED:", repr(e))
        return None


def split_lines(raw):
    """빈 줄 제거, 줄바꿈이 없으면 문장 단위로 분리 (스펙 8번)."""
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    if len(lines) <= 1:
        import re
        lines = [s.strip() for s in re.split(r"(?<=[.!?요다])\s+(?=[가-힣A-Z0-9])", raw.strip()) if s.strip()]
    return lines[:3] if len(lines) > 3 else lines
