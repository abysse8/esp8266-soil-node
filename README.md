# ESP8266 Soil Node

An end-to-end grow-room monitoring project with ESP8266 firmware, MQTT telemetry, a Node/Express backend, SQLite storage, JSON schemas, and a React dashboard for live readings.

## What It Does

- Reads soil/environment sensor data from an ESP8266 node.
- Publishes telemetry over MQTT.
- Validates device messages with JSON schemas.
- Stores readings in a local backend service.
- Streams live updates to a React dashboard.
- Includes additional RS485/camera experimentation under `firmware/soil_sensorCAM`.

## Architecture

```text
ESP8266 firmware -> MQTT broker -> Node backend -> SQLite/API/WebSocket -> React dashboard
```

## Repository Layout

| Path | Purpose |
| --- | --- |
| `firmware/soil_sensor/` | PlatformIO firmware for the ESP8266 soil node. |
| `firmware/soil_sensorCAM/` | Camera/RS485 protocol experiments and debugging tools. |
| `backend/` | Express service, MQTT client, routes, and database integration. |
| `frontend/` | Vite/React dashboard with charts and live monitor components. |
| `schemas/` | JSON schemas for readings, heartbeat, and command payloads. |

## Firmware Setup

```bash
cd firmware/soil_sensor
pio run
pio run -t upload
pio device monitor
```

The PlatformIO environment targets `nodemcuv2` and uses PubSubClient and ArduinoJson. OTA upload is configured for `soil-monitor.local`.

## Backend Setup

```bash
cd backend
npm install
npm run dev
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## Engineering Highlights

- Modular firmware services for MQTT, sensors, and web routes.
- Shared schemas for device/backend message contracts.
- Live dashboard built with React, Recharts, and Socket.IO.
- Backend routes for health checks, devices, readings, and live monitoring.
- Separate experimental workspace for RS485/camera capture and protocol debugging.
