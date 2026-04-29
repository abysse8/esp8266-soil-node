#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <SPI.h>
#include "config.h"
#include "sensor_service.h"

static uint16_t lastRaw[SENSOR_COUNT];
static uint8_t lastMoisture[SENSOR_COUNT];

static uint16_t readMCP3008(uint8_t channel)
{
    if (channel > 7) return 0;

    digitalWrite(MCP3008_CS, LOW);

    SPI.transfer(0x01);
    uint8_t highByte = SPI.transfer((0x08 | channel) << 4);
    uint8_t lowByte = SPI.transfer(0x00);

    digitalWrite(MCP3008_CS, HIGH);

    return ((highByte & 0x03) << 8) | lowByte;
}

static uint8_t rawToMoisture(uint16_t raw)
{
    const int DRY_RAW = 850;
    const int WET_RAW = 350;

    int moisture = map(raw, DRY_RAW, WET_RAW, 0, 100);
    moisture = constrain(moisture, 0, 100);

    return (uint8_t)moisture;
}

void setupSensors()
{
    pinMode(MCP3008_CS, OUTPUT);
    digitalWrite(MCP3008_CS, HIGH);
    SPI.begin();
}

void updateReadings()
{
    for (uint8_t ch = 0; ch < SENSOR_COUNT; ch++) {
        lastRaw[ch] = readMCP3008(ch);
        lastMoisture[ch] = rawToMoisture(lastRaw[ch]);
    }
}

uint16_t getRaw(uint8_t channel)
{
    if (channel >= SENSOR_COUNT) return 0;
    return lastRaw[channel];
}

uint8_t getMoisture(uint8_t channel)
{
    if (channel >= SENSOR_COUNT) return 0;
    return lastMoisture[channel];
}

String buildReadingJson(const char* brokerName)
{
    String payload = "{";
    payload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
    payload += "\"type\":\"" + String(DEVICE_TYPE) + "\",";
    payload += "\"broker\":\"" + String(brokerName) + "\",";
    payload += "\"uptime_ms\":" + String(millis()) + ",";
    payload += "\"capabilities\":[\"sendreading\",\"heartbeat\",\"livemonitor\"],";
    payload += "\"sensors\":[";

    for (uint8_t ch = 0; ch < SENSOR_COUNT; ch++) {
        payload += "{";
        payload += "\"channel\":" + String(ch) + ",";
        payload += "\"raw\":" + String(lastRaw[ch]) + ",";
        payload += "\"moisture_pct\":" + String(lastMoisture[ch]);
        payload += "}";

        if (ch < SENSOR_COUNT - 1) {
            payload += ",";
        }
    }

    payload += "]}";
    return payload;
}

String buildHeartbeatJson(const char* brokerName)
{
    String payload = "{";
    payload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
    payload += "\"type\":\"" + String(DEVICE_TYPE) + "\",";
    payload += "\"broker\":\"" + String(brokerName) + "\",";
    payload += "\"uptime_ms\":" + String(millis()) + ",";
    payload += "\"rssi\":" + String(WiFi.RSSI());
    payload += "}";

    return payload;
}