"""Console-only integration probe; do not attach this handler to API Gateway."""

from datetime import date

from src.ml_adapter import build_detection_request
from src.ml_client import MLClient, MLConfig, create_lambda_client
from src.real_health_data import build_real_health_data


def lambda_handler(event, context):
    user_id = "1503960366"
    target_date = "2016-04-10"
    health = build_real_health_data(user_id, {})
    daily_steps = {
        date.fromisoformat(item["date"]): item["activity"]["totalSteps"]
        for item in health["items"]
        if item.get("activity", {}).get("totalSteps") is not None
    }
    request = build_detection_request(user_id, target_date, daily_steps)
    config = MLConfig.from_env()
    result = MLClient(create_lambda_client(config), config).invoke_detection(request)
    return {
        "statusCode": 200,
        "integration": "backend-athena-ml",
        "status": result["status"],
        "overall_severity": result["overall_severity"],
        "anomaly_count": len(result["anomalies"]),
        "guide_generated": result["guide"] is not None,
    }
