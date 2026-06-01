# Changelog

## 1.0.5

- Fix Python 3.12 compatibility for the Home Assistant container runtime.

## 1.0.4

- Rename the MQTT password option to `mqtt_password`.
- Use `1883` as the MQTT port default.
- Replace the EW11 host default with an example private IP.

## 1.0.3

- Make app icon and logo backgrounds transparent.
- Add unofficial project disclaimer.

## 1.0.2

- Add Home Assistant app icon and logo assets.

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
