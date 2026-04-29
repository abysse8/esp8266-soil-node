#pragma once

#define DEVICE_ID "soil-monitor-01"
#define DEVICE_TYPE "soil_sensor"
#define OTA_HOSTNAME "soil-monitor"

#define MQTT_BASE_TOPIC "devices/soil-monitor-01"

#define MCP3008_CS D8
#define SENSOR_COUNT 8

#define NORMAL_READ_INTERVAL_MS 60000
#define LIVE_READ_INTERVAL_MS 1000