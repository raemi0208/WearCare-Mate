import unittest
from unittest.mock import patch

from src import ml_integration_check as probe


class IntegrationProbeTest(unittest.TestCase):
    def test_reads_target_steps_and_invokes_existing_client(self):
        health = {"items": [{"date": "2016-04-10", "activity": {"totalSteps": 10057}}]}
        result = {"status": "normal", "overall_severity": "none", "anomalies": [], "guide": None}
        with patch.object(probe, "build_real_health_data", return_value=health), \
             patch.object(probe.MLConfig, "from_env"), \
             patch.object(probe, "create_lambda_client"), \
             patch.object(probe, "MLClient") as client:
            client.return_value.invoke_detection.return_value = result
            response = probe.lambda_handler({}, None)
            client.return_value.invoke_detection.assert_called_once_with({
                "user_id": "1503960366", "date": "2016-04-10", "metrics": {"steps": 10057},
                "notify": False,
            })
            self.assertEqual(response["statusCode"], 200)
            self.assertFalse(response["guide_generated"])
            self.assertNotIn("items", response)
