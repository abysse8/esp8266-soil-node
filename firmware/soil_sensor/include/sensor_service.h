#pragma once
#include <Arduino.h>

void setupSensors();
void updateReadings();

uint16_t getRaw(uint8_t channel);
uint8_t getMoisture(uint8_t channel);

String buildReadingJson(const char* brokerName);
String buildHeartbeatJson(const char* brokerName);