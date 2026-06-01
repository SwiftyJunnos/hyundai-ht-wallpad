import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
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


class FakeMqttClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, retain=False):
        self.published.append((topic, payload, retain))


class MqttDiscoveryTest(unittest.TestCase):
    def test_publishes_switch_discovery_with_hyundai_ht_device(self):
        client = FakeMqttClient()

        with (
            patch.object(wallpad_monitor, "mqtt_client", client),
            patch.object(wallpad_monitor, "LIGHT_COUNT", 1),
            patch.object(wallpad_monitor, "TOPIC_PREFIX", "home/wallpad/switch"),
            patch.object(wallpad_monitor, "AVAILABILITY_TOPIC", "home/wallpad/switch/availability"),
            patch.object(wallpad_monitor, "DEVICE_NAME", "Hyundai HT Wallpad"),
            redirect_stdout(StringIO()),
        ):
            wallpad_monitor.publish_discovery()

        self.assertEqual(client.published[0], ("homeassistant/light/wallpad_light_1/config", "", True))
        config_topic, payload, retain = client.published[1]
        self.assertEqual(config_topic, "homeassistant/switch/wallpad_switch_1/config")
        self.assertTrue(retain)
        config = json.loads(payload)
        self.assertEqual(config["name"], "Switch 1")
        self.assertEqual(config["device"]["name"], "Hyundai HT Wallpad")
        self.assertEqual(config["device"]["manufacturer"], "Hyundai HT")
