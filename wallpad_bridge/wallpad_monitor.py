import json
import os
import socket
import time
import urllib.request
from collections.abc import Sequence

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode
from wallpad_command import (
    CommandAction,
    CommandConfirmed,
    CommandFailed,
    CommandSend,
    LightCommandScheduler,
)
from wallpad_protocol import (
    LightState,
    iter_frames,
    parse_light_command_ack,
    parse_status_frame,
)


def _load_addon_options() -> dict:
    """Read Home Assistant add-on options, if running as an add-on."""
    try:
        with open("/data/options.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError, json.JSONDecodeError:
        return {}


_OPTIONS = _load_addon_options()


def _opt(key: str, env: str, default):
    """Resolve a setting from add-on options, then env var, then default."""
    value = _OPTIONS.get(key)
    if value is not None and value != "":
        return value
    return os.environ.get(env, default)


def _discover_supervisor_mqtt() -> tuple[str, int, str, str] | None:
    """Ask the Supervisor for the built-in MQTT broker credentials."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None

    try:
        request = urllib.request.Request(
            "http://supervisor/services/mqtt",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.load(response)["data"]
        return (
            data["host"],
            int(data["port"]),
            data.get("username", ""),
            data.get("password", ""),
        )
    except Exception as e:
        print("supervisor mqtt lookup failed:", e)
        return None


def _resolve_mqtt() -> tuple[str, int, str, str]:
    """Pick the MQTT broker: explicit config > built-in broker > dev default."""
    host = _OPTIONS.get("mqtt_host") or os.environ.get("MQTT_HOST")
    if host:
        port = _OPTIONS.get("mqtt_port") or os.environ.get("MQTT_PORT") or 1883
        user = _OPTIONS.get("mqtt_user") or os.environ.get("MQTT_USER", "")
        password = _OPTIONS.get("mqtt_pass") or os.environ.get("MQTT_PASS", "")
        return (str(host), int(port), str(user), str(password))

    service = _discover_supervisor_mqtt()
    if service is not None:
        return service

    # Standalone development fallback (configure via env vars; no secrets here).
    return (
        os.environ.get("MQTT_HOST", "127.0.0.1"),
        int(os.environ.get("MQTT_PORT", 1883)),
        os.environ.get("MQTT_USER", ""),
        os.environ.get("MQTT_PASS", ""),
    )


EW11_HOST = str(_opt("ew11_host", "EW11_HOST", "172.30.1.48"))
EW11_PORT = int(_opt("ew11_port", "EW11_PORT", 8899))

MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS = _resolve_mqtt()

TOPIC_PREFIX = str(_opt("topic_prefix", "TOPIC_PREFIX", "home/wallpad/light"))
AVAILABILITY_TOPIC = f"{TOPIC_PREFIX}/availability"
DISCOVERY_PREFIX = str(_opt("discovery_prefix", "DISCOVERY_PREFIX", "homeassistant"))
DEVICE_NAME = str(_opt("device_name", "DEVICE_NAME", "Wallpad"))
LIGHT_COUNT = int(_opt("light_count", "LIGHT_COUNT", 6))

COMMAND_MAX_ATTEMPTS = int(_opt("command_max_attempts", "COMMAND_MAX_ATTEMPTS", 10))
COMMAND_RETRY_STATUS_FRAMES = int(
    _opt("command_retry_status_frames", "COMMAND_RETRY_STATUS_FRAMES", 1)
)
COMMAND_CONFIRM_TIMEOUT_FRAMES = int(
    _opt("command_confirm_timeout_frames", "COMMAND_CONFIRM_TIMEOUT_FRAMES", 6)
)

last_states: list[LightState | None] = [None, None, None, None, None, None]

mqtt_client: mqtt.Client | None = None

command_scheduler = LightCommandScheduler(
    max_attempts=COMMAND_MAX_ATTEMPTS,
    status_frames_before_retry=COMMAND_RETRY_STATUS_FRAMES,
    confirm_timeout_frames=COMMAND_CONFIRM_TIMEOUT_FRAMES,
)


def publish_state(index: int, value: LightState) -> None:
    if mqtt_client is None:
        raise RuntimeError("MQTT client is not initialized")

    topic = f"{TOPIC_PREFIX}/{index + 1}/state"
    payload = value.name
    mqtt_client.publish(topic, payload, retain=True)
    print(f"publish {topic} = {payload}")


def record_state(index: int, value: LightState) -> None:
    global last_states

    if last_states[index] != value:
        last_states[index] = value
        publish_state(index, value)


def republish_state(index: int) -> None:
    value = last_states[index]
    if value is not None:
        publish_state(index, value)


def publish_discovery() -> None:
    """Announce the lights via MQTT discovery so HA creates them automatically."""
    if mqtt_client is None:
        raise RuntimeError("MQTT client is not initialized")

    device = {
        "identifiers": ["wallpad_bridge"],
        "name": DEVICE_NAME,
        "manufacturer": "Wallpad",
        "model": "EW11 RS485 Bridge",
    }

    for light_no in range(1, LIGHT_COUNT + 1):
        unique_id = f"wallpad_light_{light_no}"
        config_topic = f"{DISCOVERY_PREFIX}/light/{unique_id}/config"
        payload = {
            "name": f"Light {light_no}",
            "unique_id": unique_id,
            "command_topic": f"{TOPIC_PREFIX}/{light_no}/set",
            "state_topic": f"{TOPIC_PREFIX}/{light_no}/state",
            "payload_on": LightState.ON.name,
            "payload_off": LightState.OFF.name,
            "availability_topic": AVAILABILITY_TOPIC,
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": device,
        }
        mqtt_client.publish(config_topic, json.dumps(payload), retain=True)

    print(f"published discovery for {LIGHT_COUNT} lights")


def handle_frame(frame: bytes) -> tuple[LightState | None, ...] | None:
    states = parse_status_frame(frame)
    if states is None:
        return None

    for i, value in enumerate(states):
        if value is None:
            continue

        record_state(i, value)

    return states


def enqueue_light_command(light_no: int, state: LightState) -> None:
    command_scheduler.enqueue(light_no, state)
    print(f"queued light {light_no} {state.name}")


def handle_command_actions(
    sock: socket.socket, actions: Sequence[CommandAction]
) -> None:
    for action in actions:
        if isinstance(action, CommandSend):
            sock.sendall(action.packet)
            print(
                f"command light {action.light_no} {action.state.name} "
                f"attempt {action.attempt}: {action.packet.hex()}"
            )
            continue

        if isinstance(action, CommandConfirmed):
            print(f"confirmed light {action.light_no} {action.state.name}")
            continue

        if isinstance(action, CommandFailed):
            print(
                f"command FAILED light {action.light_no} {action.state.name} "
                f"after {COMMAND_MAX_ATTEMPTS} attempts"
            )
            # Make sure MQTT reflects the real (unchanged) state after a failure
            # so downstream consumers do not show an optimistic, wrong value.
            republish_state(action.light_no - 1)


def on_connect(
    client: mqtt.Client,
    userdata: object,
    flags: mqtt.ConnectFlags,
    reason_code: ReasonCode,
    properties: Properties | None,
) -> None:
    print("mqtt connected:", reason_code)
    client.subscribe(f"{TOPIC_PREFIX}/+/set")
    publish_discovery()
    client.publish(AVAILABILITY_TOPIC, "online", retain=True)

    # Re-publish whatever states we already know after a (re)connect.
    for i, state in enumerate(last_states):
        if state is not None:
            publish_state(i, state)


def on_message(client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
    try:
        topic = msg.topic
        payload = msg.payload.decode().strip().upper()

        if msg.retain:
            print("ignore retained command:", topic, payload)
            return

        # home/wallpad/light/1/set
        parts = topic.split("/")
        light_no = int(parts[-2])

        if payload not in LightState.__members__:
            print("unknown payload:", payload)
            return

        enqueue_light_command(light_no, LightState[payload])

    except Exception as e:
        print("command error:", e)


def create_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    # Last will: mark the bridge offline if the connection drops unexpectedly.
    client.will_set(AVAILABILITY_TOPIC, "offline", retain=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    return client


def monitor_ew11() -> None:
    while True:
        try:
            print("connecting EW11 monitor...")
            sock = socket.create_connection((EW11_HOST, EW11_PORT), timeout=10)
            # Disable Nagle so our small command frame is put on the wire
            # immediately rather than being buffered/coalesced, which would push
            # it out of the narrow post-status injection window.
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(0.2)
            print("connected")

            buffer = b""

            while True:
                try:
                    data = sock.recv(1024)
                except socket.timeout:
                    continue

                if not data:
                    raise ConnectionError("EW11 disconnected")

                frames, buffer = iter_frames(buffer + data)

                latest_states: tuple[LightState | None, ...] | None = None

                for frame in frames:
                    states = handle_frame(frame)

                    ack = parse_light_command_ack(frame)
                    if ack is not None:
                        record_state(ack.light_no - 1, ack.current_state)
                        handle_command_actions(sock, command_scheduler.on_ack(ack))

                    if states is not None:
                        latest_states = states
                        # Confirm against every status frame as soon as it lands.
                        handle_command_actions(
                            sock, command_scheduler.confirm_from_status(states)
                        )

                # Send/retry one command per read whenever a status frame was
                # seen. Retrying on every status cycle is what lets a dropped
                # command recover quickly; the scheduler stops as soon as the
                # wallpad acks, so a command that already landed is not re-sent.
                if latest_states is not None:
                    handle_command_actions(
                        sock, command_scheduler.next_action(latest_states)
                    )

        except Exception as e:
            print("monitor error:", e)
            command_scheduler.requeue_pending_after_disconnect()
            time.sleep(3)


def main() -> None:
    global mqtt_client

    print(
        f"config: ew11={EW11_HOST}:{EW11_PORT} mqtt={MQTT_HOST}:{MQTT_PORT} "
        f"topic={TOPIC_PREFIX} lights={LIGHT_COUNT} "
        f"max_attempts={COMMAND_MAX_ATTEMPTS} retry_frames={COMMAND_RETRY_STATUS_FRAMES}"
    )

    mqtt_client = create_mqtt_client()
    mqtt_client.loop_start()
    monitor_ew11()


if __name__ == "__main__":
    main()
