# Hyundai HT Wallpad — Unofficial Home Assistant app repository

An unofficial Home Assistant app repository that bridges Korean (Hyundai HT)
wallpad lights to MQTT over an EW11 RS485-to-WiFi gateway, with automatic
Home Assistant MQTT discovery.

This project is not affiliated with, endorsed by, or sponsored by Hyundai HT.

## Install

In Home Assistant: **Settings → Apps → Install app → ⋮ → Repositories**, add:

```
https://github.com/SwiftyJunnos/hyundai-ht-wallpad
```

Then install **Wallpad RS485 Bridge**. See
[`wallpad_bridge/DOCS.md`](wallpad_bridge/DOCS.md) for configuration and the
install notes.

## Repository layout

```
.
├── repository.yaml          # app repository metadata
└── wallpad_bridge/          # the app
    ├── config.yaml / Dockerfile
    ├── wallpad_protocol.py   # frame build/parse (length-aware, checksum-validated)
    ├── wallpad_command.py    # ack-aware retry scheduler
    ├── wallpad_monitor.py    # EW11 ↔ MQTT bridge, discovery, entrypoint
    └── tests/                # unit tests
```

## Development (standalone)

```bash
uv run wallpad_bridge/wallpad_monitor.py
```

Configuration comes from app options (`/data/options.json`) when run as a
Home Assistant app, otherwise from environment variables (`EW11_HOST`, `MQTT_HOST`,
`MQTT_USER`, `MQTT_PASS`, `TOPIC_PREFIX`, `LIGHT_COUNT`, `COMMAND_MAX_ATTEMPTS`,
...). No secrets are baked into the source.

## Tests

```bash
PYTHONPATH=wallpad_bridge:wallpad_bridge/tests \
  python -m unittest test_wallpad_command test_wallpad_protocol
```
