#pragma once

void setupMQTT();
void handleMQTT();
void publishReading();
void publishHeartbeat();

const char* getActiveBrokerName();