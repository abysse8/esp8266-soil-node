#pragma once
#include <ESP8266WebServer.h>

extern ESP8266WebServer server;

void setupWebRoutes();
bool liveMonitorEnabled();
void setLiveMonitor(bool enabled, unsigned long durationMs = 0);
void handleWebServer();