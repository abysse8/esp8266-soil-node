#include <Arduino.h>
#include <ESP8266WebServer.h>

#include "sensor_service.h"
#include "mqtt_service.h"
#include "web_routes.h"

ESP8266WebServer server(80);

static bool liveMode = false;
static unsigned long liveUntilMs = 0;

void setLiveMonitor(bool enabled, unsigned long durationMs)
{
    liveMode = enabled;
    liveUntilMs = enabled && durationMs > 0 ? millis() + durationMs : 0;
}

bool liveMonitorEnabled()
{
    if (liveMode && liveUntilMs > 0 && millis() >= liveUntilMs) {
        liveMode = false;
        liveUntilMs = 0;
    }
    return liveMode;
}

void setupWebRoutes()
{
    server.on("/", []() {
        server.send(200, "text/plain", "soil-monitor online");
    });

    server.on("/capabilities", []() {
        String payload = "{";
        payload += "\"device\":\"soil-monitor-01\",";
        payload += "\"capabilities\":[";
        payload += "\"/sendreading\",";
        payload += "\"/heartbeat\",";
        payload += "\"/livemonitor/start\",";
        payload += "\"/livemonitor/stop\",";
        payload += "\"/json\"";
        payload += "]}";

        server.send(200, "application/json", payload);
    });

    server.on("/json", []() {
        updateReadings();
        String payload = buildReadingJson(getActiveBrokerName());
        server.send(200, "application/json", payload);
    });

    server.on("/livemonitor/start", []() {
        setLiveMonitor(true, 120000);
        server.send(200, "application/json", "{\"live\":true}");
    });

    server.on("/livemonitor/stop", []() {
        setLiveMonitor(false);
        server.send(200, "application/json", "{\"live\":false}");
    });

    server.begin();
}

void handleWebServer()
{
    server.handleClient();
}