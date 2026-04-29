#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266mDNS.h>
#include <ArduinoOTA.h>

#include "secrets.h"
#include "config.h"
#include "sensor_service.h"
#include "mqtt_service.h"
#include "web_routes.h"

static unsigned long lastReadMs = 0;
static unsigned long lastHeartbeatMs = 0;

static void setupWiFiAndOTA()
{
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    Serial.print("Connecting to WiFi");

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    Serial.println();
    Serial.print("Connected. IP address: ");
    Serial.println(WiFi.localIP());

    if (MDNS.begin(OTA_HOSTNAME)) {
        Serial.println("mDNS started");
    } else {
        Serial.println("mDNS failed");
    }

    ArduinoOTA.setHostname(OTA_HOSTNAME);
    ArduinoOTA.begin();

    Serial.println("OTA ready.");
}

void setup()
{
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("ESP8266 distributed soil sensor");

    setupSensors();
    setupWiFiAndOTA();
    setupMQTT();
    setupWebRoutes();

    updateReadings();
    publishReading();
    publishHeartbeat();

    lastReadMs = millis();
    lastHeartbeatMs = millis();
}

void loop()
{
    ArduinoOTA.handle();
    MDNS.update();
    handleWebServer();
    handleMQTT();

    unsigned long now = millis();

    unsigned long readInterval = liveMonitorEnabled()
        ? LIVE_READ_INTERVAL_MS
        : NORMAL_READ_INTERVAL_MS;

    if (now - lastReadMs >= readInterval) {
        lastReadMs = now;

        updateReadings();
        publishReading();
    }

    if (now - lastHeartbeatMs >= 60000) {
        lastHeartbeatMs = now;

        publishHeartbeat();
    }
}