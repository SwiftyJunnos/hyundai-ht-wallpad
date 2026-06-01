# Changelog

## 1.0.1

- Apply formatter cleanup.

## 1.0.0

- Initial Home Assistant add-on release.
- Bridges EW11 RS485 wallpad lights to MQTT.
- MQTT auto-discovery: lights appear in Home Assistant automatically.
- Uses the built-in MQTT broker by default (no credentials needed); optional
  external broker override.
- Ack-aware fast retry: a dropped command is retried every status cycle and
  stops as soon as the wallpad acknowledges it.
- Availability (online/offline) via MQTT last-will.
