import unittest
from unittest.mock import patch

import wallpad_monitor


class MqttConfigTest(unittest.TestCase):
    def test_resolves_explicit_mqtt_password_option(self):
        with patch.dict(
            wallpad_monitor._OPTIONS,
            {
                "mqtt_host": "mqtt.example.local",
                "mqtt_port": 1884,
                "mqtt_user": "wallpad",
                "mqtt_password": "secret",
            },
            clear=True,
        ):
            self.assertEqual(
                wallpad_monitor._resolve_mqtt(),
                ("mqtt.example.local", 1884, "wallpad", "secret"),
            )

    def test_keeps_legacy_mqtt_pass_option_compatible(self):
        with patch.dict(
            wallpad_monitor._OPTIONS,
            {
                "mqtt_host": "mqtt.example.local",
                "mqtt_port": 1884,
                "mqtt_user": "wallpad",
                "mqtt_pass": "legacy-secret",
            },
            clear=True,
        ):
            self.assertEqual(
                wallpad_monitor._resolve_mqtt(),
                ("mqtt.example.local", 1884, "wallpad", "legacy-secret"),
            )
