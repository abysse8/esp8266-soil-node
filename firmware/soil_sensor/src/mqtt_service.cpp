#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

#include "secrets.h"
#include "config.h"
#include "sensor_service.h"
#include "mqtt_service.h"
#include "web_routes.h"

static WiFiClient wifiClient;
static PubSubClient mqttClient(wifiClient);

static const char* activeHost = MQTT_MAC_HOST;
static const char* activeBrokerName = "mac";

static void onMqttMessage(char* topic, byte* payload, unsigned int length)
{
    JsonDocument doc;
    if (deserializeJson(doc, payload, length)) return;

    const char* command = doc["command"];
    if (!command) return;

    if (strcmp(command, "start_livemonitor") == 0) {
        unsigned long durationSec = doc["duration_sec"] | 120;
        setLiveMonitor(true, durationSec * 1000UL);
        Serial.printf("Live monitor on: %lus\n", durationSec);
    } else if (strcmp(command, "stop_livemonitor") == 0) {
        setLiveMonitor(false);
        Serial.println("Live monitor off");
    }
}

static void setBroker(const char* host, const char* name)
{
    activeHost = host;
    activeBrokerName = name;
    mqttClient.setServer(activeHost, MQTT_PORT);
}

static bool tryConnect(const char* host, const char* name)
{
    setBroker(host, name);

    String clientId = String(DEVICE_ID) + "-" + String(ESP.getChipId(), HEX);

    Serial.print("Trying MQTT broker ");
    Serial.println(host);

    if (mqttClient.connect(clientId.c_str())) {
        Serial.print("MQTT connected to ");
        Serial.println(name);

        String statusTopic = String(MQTT_BASE_TOPIC) + "/status";
        mqttClient.publish(statusTopic.c_str(), "online", true);

        String cmdTopic = String(MQTT_BASE_TOPIC) + "/commands";
        mqttClient.subscribe(cmdTopic.c_str());

        return true;
    }

    Serial.print("MQTT failed rc=");
    Serial.println(mqttClient.state());

    return false;
}

static bool connectMQTT()
{
    if (tryConnect(MQTT_MAC_HOST, "mac")) {
        return true;
    }

    if (tryConnect(MQTT_PI_HOST, "raspberry_pi")) {
        return true;
    }

    Serial.println("No MQTT broker available.");
    return false;
}

void setupMQTT()
{
    mqttClient.setCallback(onMqttMessage);
    connectMQTT();
}

void handleMQTT()
{
    if (!mqttClient.connected()) {
        connectMQTT();
    }

    mqttClient.loop();
}

void publishReading()
{
    if (!mqttClient.connected()) {
        connectMQTT();
    }

    if (!mqttClient.connected()) {
        Serial.println("Cannot publish reading. No MQTT broker.");
        return;
    }

    String topic = String(MQTT_BASE_TOPIC) + "/readings";
    String payload = buildReadingJson(activeBrokerName);

    mqttClient.publish(topic.c_str(), payload.c_str());

    Serial.println(payload);
}

void publishHeartbeat()
{
    if (!mqttClient.connected()) {
        return;
    }

    String topic = String(MQTT_BASE_TOPIC) + "/heartbeat";
    String payload = buildHeartbeatJson(activeBrokerName);

    mqttClient.publish(topic.c_str(), payload.c_str());
}

const char* getActiveBrokerName()
{
    return activeBrokerName;
}
