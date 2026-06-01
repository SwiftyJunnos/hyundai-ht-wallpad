# Wallpad RS485 Bridge

Unofficial bridge for Korean wallpad lights (over an EW11 RS485-to-WiFi
gateway) to MQTT, with automatic Home Assistant MQTT discovery.

This project is not affiliated with, endorsed by, or sponsored by Hyundai HT.

## Install

1. Go to **Settings → Apps → Install app**, open the **⋮** menu →
   **Repositories**, and add this repository URL:
   `https://github.com/SwiftyJunnos/hyundai-ht-wallpad`
2. Refresh the app store page if needed.
3. Find **Wallpad RS485 Bridge** in the store, click **Install**, then **Start**.

The **MQTT integration** must be set up in Home Assistant (the official Mosquitto
broker app works out of the box - this app uses it automatically).

## Configuration

| Option | Default | Description |
| --- | --- | --- |
| `ew11_host` | `172.30.1.48` | IP of the EW11 gateway |
| `ew11_port` | `8899` | TCP port of the EW11 |
| `topic_prefix` | `home/wallpad/light` | Base MQTT topic for lights |
| `light_count` | `6` | Number of lights to expose |
| `device_name` | `Wallpad` | Device name shown in Home Assistant |
| `command_max_attempts` | `10` | Max send attempts before giving up |
| `command_retry_status_frames` | `1` | Status cycles to wait before retrying |
| `command_confirm_timeout_frames` | `6` | Cycles to wait after an ack for the state to reflect |
| `mqtt_host` | _(empty)_ | Override broker host (leave empty to use the built-in broker) |
| `mqtt_port` | `0` | Override broker port |
| `mqtt_user` | _(empty)_ | Override broker username |
| `mqtt_pass` | _(empty)_ | Override broker password |

Leave the `mqtt_*` options empty to auto-use the Home Assistant built-in MQTT
broker (recommended). Set them only if you run a separate broker.

## Entities

On start, the app publishes discovery configs to
`homeassistant/light/wallpad_light_<n>/config`, so each light appears as a
**light** entity automatically. State and commands use:

- State:   `home/wallpad/light/<n>/state`  (`ON` / `OFF`, retained)
- Command: `home/wallpad/light/<n>/set`    (`ON` / `OFF`)
- Availability: `home/wallpad/light/availability` (`online` / `offline`)

## Logs

The app log shows each command, its attempts, confirmations, and any
failures. If you see `command FAILED ... after N attempts`, the command was
sent repeatedly but the wallpad never acknowledged it — that points to a
bus/hardware-level issue rather than a configuration problem.
