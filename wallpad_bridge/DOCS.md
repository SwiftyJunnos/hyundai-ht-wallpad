# Wallpad RS485 Bridge

Unofficial bridge for Korean wallpad switches (over an EW11 RS485-to-WiFi
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
| `ew11_host` | `192.168.1.100` | IP of the EW11 gateway |
| `ew11_port` | `8899` | TCP port of the EW11 |
| `topic_prefix` | `home/wallpad/switch` | Base MQTT topic for switches |
| `light_count` | `6` | Number of switches to expose |
| `device_name` | `Hyundai HT Wallpad` | Device name shown in Home Assistant |
| `command_max_attempts` | `10` | Max send attempts before giving up |
| `command_retry_status_frames` | `1` | Status cycles to wait before retrying |
| `command_confirm_timeout_frames` | `6` | Cycles to wait after an ack for the state to reflect |
| `mqtt_host` | _(empty)_ | Override broker host (leave empty to use the built-in broker) |
| `mqtt_port` | `1883` | Override broker port |
| `mqtt_user` | _(empty)_ | Override broker username |
| `mqtt_password` | _(empty)_ | Override broker password |

Leave `mqtt_host`, `mqtt_user`, and `mqtt_password` empty to auto-use the Home
Assistant built-in MQTT broker (recommended). Set them only if you run a
separate broker.

## Entities

On start, the app publishes discovery configs to
`homeassistant/switch/wallpad_switch_<n>/config`, so each wallpad channel appears
as a **switch** entity automatically. State and commands use:

- State:   `home/wallpad/switch/<n>/state`  (`ON` / `OFF`, retained)
- Command: `home/wallpad/switch/<n>/set`    (`ON` / `OFF`)
- Availability: `home/wallpad/switch/availability` (`online` / `offline`)

## Logs

The app log shows each command, its attempts, confirmations, and any
failures. If you see `command FAILED ... after N attempts`, the command was
sent repeatedly but the wallpad never acknowledged it — that points to a
bus/hardware-level issue rather than a configuration problem.
