import pandas as pd
from detector import detect, fit_iforest

df = pd.read_csv("wearable_tech_sleep_quality_fixed.csv")
rows = [{"heart_rate_variability": r.Heart_Rate_Variability,
         "sleep_hours": r.Sleep_Duration_Hours,
         "stress_level": r.Stress_Level,
         "movement_during_sleep": r.Movement_During_Sleep} for r in df.itertuples()]

model = fit_iforest(rows)
outs = [detect({"user_id": "t", "date": "x", "metrics": m}, iforest=model) for m in rows]

print("전체 심각도 분포 (개별 최대 + 서로 다른 지표 2개 이상이면 한 단계 올림):")
print(pd.Series([o["overall_severity"] for o in outs]).value_counts()
      .reindex(["none", "low", "medium", "high"]).fillna(0).astype(int).to_string())
print("\n유형별 건수:")
print(pd.Series([a["type"] for o in outs for a in o["anomalies"]]).value_counts().to_string())
print("\n한 행에 이상 2개 이상:", sum(len(o["anomalies"]) >= 2 for o in outs), "건")
