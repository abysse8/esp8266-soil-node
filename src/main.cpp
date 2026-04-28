#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>
#include <ArduinoOTA.h>
#include <SPI.h>
#define MCP3008_CS D2

const char* WIFI_SSID = "4G-WIFI-9353";
const char* WIFI_PASS = "1234567890";

const char* OTA_HOSTNAME = "soil-monitor";

ESP8266WebServer server(80);

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

const char* MQTT_HOST = "192.168.0.199";
const uint16_t MQTT_PORT = 1883;
const char* MQTT_CLIENT_ID = "soil-monitor-esp8266";
const char* MQTT_READING_TOPIC = "growroom/soil/bed1/reading";
const char* MQTT_HEARTBEAT_TOPIC = "growroom/device/soil-monitor-esp8266/heartbeat";

const int SENSOR_COUNT = 3;

// Calibration values.

// Raw value goes down when soil gets wetter.

const int DRY[SENSOR_COUNT] = {794, 789, 816};

const int WET[SENSOR_COUNT] = {184, 305, 262};

int lastRaw[SENSOR_COUNT] = {0, 0, 0};

int lastMoisture[SENSOR_COUNT] = {0, 0, 0};

// One reading per minute.

const unsigned long READ_INTERVAL_MS = 60000;

unsigned long lastReadMs = 0;

// 24 hours * 60 minutes = 1440 samples.

const int HISTORY_SIZE = 1440;

uint32_t historyMinute[HISTORY_SIZE];

uint16_t historyRaw[SENSOR_COUNT][HISTORY_SIZE];

uint8_t historyMoisture[SENSOR_COUNT][HISTORY_SIZE];

int historyIndex = 0;

int historyCount = 0;

int readMCP3008(uint8_t channel)

{

    if (channel > 7) {

        return -1;

    }

    digitalWrite(MCP3008_CS, LOW);

    SPI.transfer(0x01);

    uint8_t highByte = SPI.transfer(0x80 | (channel << 4));

    uint8_t lowByte = SPI.transfer(0x00);

    digitalWrite(MCP3008_CS, HIGH);

    int value = ((highByte & 0x03) << 8) | lowByte;

    return value;

}

int readMCP3008Average(uint8_t channel)

{

    long sum = 0;

    for (int i = 0; i < 20; i++) {

        sum += readMCP3008(channel);

        delay(2);

        ArduinoOTA.handle();

        server.handleClient();

    }

    return sum / 20;

}

int moisturePercent(int raw, uint8_t channel)

{

    if (channel >= SENSOR_COUNT) {

        return 0;

    }

    int dry = DRY[channel];

    int wet = WET[channel];

    if (dry == wet) {

        return 0;

    }

    int percent = (dry - raw) * 100 / (dry - wet);

    return constrain(percent, 0, 100);

}

void updateReadings()

{

    for (uint8_t ch = 0; ch < SENSOR_COUNT; ch++) {

        lastRaw[ch] = readMCP3008Average(ch);

        lastMoisture[ch] = moisturePercent(lastRaw[ch], ch);

    }

}

void logHistory()

{

    uint32_t minuteNow = millis() / 60000UL;

    historyMinute[historyIndex] = minuteNow;

    for (int ch = 0; ch < SENSOR_COUNT; ch++) {

        historyRaw[ch][historyIndex] = lastRaw[ch];

        historyMoisture[ch][historyIndex] = lastMoisture[ch];

    }

    historyIndex = (historyIndex + 1) % HISTORY_SIZE;

    if (historyCount < HISTORY_SIZE) {

        historyCount++;

    }

}

void connectMQTT()
{
    if (mqttClient.connected()) {
        return;
    }

    Serial.print("Connecting to MQTT at ");
    Serial.print(MQTT_HOST);
    Serial.print(":");
    Serial.println(MQTT_PORT);

    if (mqttClient.connect(MQTT_CLIENT_ID)) {
        Serial.println("MQTT connected");
    } else {
        Serial.print("MQTT failed, rc=");
        Serial.println(mqttClient.state());
    }
}

void publishReadingsMQTT()
{
    if (!mqttClient.connected()) {
        connectMQTT();
    }

    if (!mqttClient.connected()) {
        return;
    }

    String json = "{";
    json += "\"device_id\":\"soil-monitor-esp8266\",";
    json += "\"ip\":\"";
    json += WiFi.localIP().toString();
    json += "\",";
    json += "\"uptime_s\":";
    json += String(millis() / 1000UL);
    json += ",";
    json += "\"sensors\":[";

    for (int ch = 0; ch < SENSOR_COUNT; ch++) {
        json += "{";
        json += "\"channel\":";
        json += String(ch);
        json += ",";
        json += "\"raw\":";
        json += String(lastRaw[ch]);
        json += ",";
        json += "\"moisture\":";
        json += String(lastMoisture[ch]);
        json += "}";

        if (ch < SENSOR_COUNT - 1) {
            json += ",";
        }
    }

    json += "]}";

    mqttClient.publish(MQTT_READING_TOPIC, json.c_str(), true);
    Serial.print("Published MQTT reading: ");
    Serial.println(json);
}

void publishHeartbeatMQTT()
{
    if (!mqttClient.connected()) {
        connectMQTT();
    }

    if (!mqttClient.connected()) {
        return;
    }

    String json = "{";
    json += "\"device_id\":\"soil-monitor-esp8266\",";
    json += "\"status\":\"online\",";
    json += "\"ip\":\"";
    json += WiFi.localIP().toString();
    json += "\",";
    json += "\"wifi_rssi\":";
    json += String(WiFi.RSSI());
    json += ",";
    json += "\"uptime_s\":";
    json += String(millis() / 1000UL);
    json += "}";

    mqttClient.publish(MQTT_HEARTBEAT_TOPIC, json.c_str(), true);
}

String jsonCurrent()

{

    String json = "{";

    json += "\"ip\":\"";

    json += WiFi.localIP().toString();

    json += "\",";

    json += "\"uptime_min\":";

    json += String(millis() / 60000UL);

    json += ",";

    json += "\"history_count\":";

    json += String(historyCount);

    json += ",";

    json += "\"sensors\":[";

    for (int ch = 0; ch < SENSOR_COUNT; ch++) {

        json += "{";

        json += "\"channel\":";

        json += String(ch);

        json += ",";

        json += "\"raw\":";

        json += String(lastRaw[ch]);

        json += ",";

        json += "\"moisture\":";

        json += String(lastMoisture[ch]);

        json += "}";

        if (ch < SENSOR_COUNT - 1) {

            json += ",";

        }

    }

    json += "]}";

    return json;

}

String jsonHistory()

{

    String json = "{";

    json += "\"history_count\":";

    json += String(historyCount);

    json += ",";

    json += "\"interval_seconds\":60,";

    json += "\"samples\":[";

    for (int i = 0; i < historyCount; i++) {

        int idx = (historyIndex - historyCount + i + HISTORY_SIZE) % HISTORY_SIZE;

        json += "{";

        json += "\"age_min\":";

        json += String((millis() / 60000UL) - historyMinute[idx]);

        json += ",";

        json += "\"minute\":";

        json += String(historyMinute[idx]);

        for (int ch = 0; ch < SENSOR_COUNT; ch++) {

            json += ",\"m";

            json += String(ch);

            json += "\":";

            json += String(historyMoisture[ch][idx]);

            json += ",\"r";

            json += String(ch);

            json += "\":";

            json += String(historyRaw[ch][idx]);

        }

        json += "}";

        if (i < historyCount - 1) {

            json += ",";

        }

    }

    json += "]}";

    return json;

}

String htmlPage()

{

    String html = R"rawliteral(

<!DOCTYPE html>

<html>

<head>

<meta charset="utf-8">

<meta name="viewport" content="width=device-width, initial-scale=1">

<title>Soil Monitor</title>

<style>

body {

    font-family: Arial, sans-serif;

    margin: 18px;

    background: #111;

    color: #eee;

}

.card {

    background: #222;

    padding: 14px;

    margin: 12px 0;

    border-radius: 12px;

}

.value {

    font-size: 30px;

    font-weight: bold;

}

.raw {

    color: #aaa;

    font-size: 14px;

}

canvas {

    width: 100%;

    height: 280px;

    background: #181818;

    border-radius: 12px;

}

button {

    padding: 10px 14px;

    border-radius: 8px;

    border: 0;

    margin-right: 8px;

}

</style>

</head>

<body>

<h1>Soil Monitor</h1>

<div class="card">

    <p>Updates once per minute. Memory keeps last 24 hours unless the ESP reboots.</p>

    <p id="status">Loading...</p>

    <button onclick="loadData()">Refresh now</button>

</div>

<div class="card">

    <h2>Current</h2>

    <div id="current"></div>

</div>

<div class="card">

    <h2>Last 24 hours</h2>

    <canvas id="chart" width="900" height="320"></canvas>

    <p class="raw">Y axis is moisture percent. X axis is time, oldest left, newest right.</p>

</div>

<script>

async function loadData() {

    const currentRes = await fetch('/json');

    const current = await currentRes.json();

    const historyRes = await fetch('/history');

    const history = await historyRes.json();

    document.getElementById('status').innerText =

        'IP: ' + current.ip +

        ' | uptime: ' + current.uptime_min + ' min' +

        ' | samples: ' + current.history_count;

    let html = '';

    current.sensors.forEach((s, i) => {

        html += '<div class="card">';

        html += '<h3>Pot ' + (i + 1) + '</h3>';

        html += '<div class="value">' + s.moisture + '%</div>';

        html += '<p class="raw">Raw ADC: ' + s.raw + '</p>';

        html += '</div>';

    });

    document.getElementById('current').innerHTML = html;

    drawChart(history.samples);

}

function drawChart(samples) {

    const canvas = document.getElementById('chart');

    const ctx = canvas.getContext('2d');

    const w = canvas.width;

    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    ctx.strokeStyle = '#555';

    ctx.lineWidth = 1;

    ctx.beginPath();

    for (let p = 0; p <= 100; p += 25) {

        const y = h - (p / 100) * h;

        ctx.moveTo(0, y);

        ctx.lineTo(w, y);

    }

    ctx.stroke();

    ctx.fillStyle = '#aaa';

    ctx.font = '14px Arial';

    ctx.fillText('100%', 6, 16);

    ctx.fillText('75%', 6, h * 0.25);

    ctx.fillText('50%', 6, h * 0.50);

    ctx.fillText('25%', 6, h * 0.75);

    ctx.fillText('0%', 6, h - 8);

    if (!samples || samples.length < 2) {

        ctx.fillStyle = '#eee';

        ctx.fillText('Not enough data yet. Wait a few minutes.', 40, h / 2);

        return;

    }

    const series = [

        { key: 'm0', color: '#4caf50' },

        { key: 'm1', color: '#2196f3' },

        { key: 'm2', color: '#ff9800' }

    ];

    series.forEach((s) => {

        ctx.strokeStyle = s.color;

        ctx.lineWidth = 2;

        ctx.beginPath();

        samples.forEach((sample, i) => {

            const x = (i / (samples.length - 1)) * w;

            const y = h - (sample[s.key] / 100) * h;

            if (i === 0) {

                ctx.moveTo(x, y);

            } else {

                ctx.lineTo(x, y);

            }

        });

        ctx.stroke();

    });

    ctx.fillStyle = '#4caf50';

    ctx.fillText('Pot 1', w - 170, 20);

    ctx.fillStyle = '#2196f3';

    ctx.fillText('Pot 2', w - 110, 20);

    ctx.fillStyle = '#ff9800';

    ctx.fillText('Pot 3', w - 50, 20);

}

loadData();

setInterval(loadData, 60000);

</script>

</body>

</html>

)rawliteral";

    return html;

}

void setupWebServer()

{

    server.on("/", []() {

        server.send(200, "text/html", htmlPage());

    });

    server.on("/json", []() {

        server.send(200, "application/json", jsonCurrent());

    });

    server.on("/history", []() {

        server.send(200, "application/json", jsonHistory());

    });

    server.on("/health", []() {

        server.send(200, "text/plain", "OK");

    });

    server.begin();

    Serial.println("Web server started");

}

void setupWiFiAndOTA()

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

    Serial.print("OTA ready. Hostname: ");

    Serial.println(OTA_HOSTNAME);

}

void setup()

{

    Serial.begin(115200);

    delay(1000);

    pinMode(MCP3008_CS, OUTPUT);

    digitalWrite(MCP3008_CS, HIGH);

    SPI.begin();

    Serial.println();

    Serial.println("ESP8266 + MCP3008 soil monitor with 24h graph");

    setupWiFiAndOTA();

    mqttClient.setServer(MQTT_HOST, MQTT_PORT);

    setupWebServer();

    updateReadings();

    logHistory();

    publishReadingsMQTT();

    publishHeartbeatMQTT();

    lastReadMs = millis();

}

void loop()

{

    ArduinoOTA.handle();

    server.handleClient();

    MDNS.update();

    if (WiFi.status() == WL_CONNECTED) {
        if (!mqttClient.connected()) {
            connectMQTT();
        }
        mqttClient.loop();
    }

    unsigned long now = millis();

    if (now - lastReadMs >= READ_INTERVAL_MS) {

        lastReadMs = now;

        updateReadings();

        logHistory();

        publishReadingsMQTT();

        publishHeartbeatMQTT();

        Serial.print("Logged sample ");

        Serial.print(historyCount);

        Serial.print("/");

        Serial.print(HISTORY_SIZE);

        Serial.print(" | ");

        for (uint8_t ch = 0; ch < SENSOR_COUNT; ch++) {

            Serial.print("CH");

            Serial.print(ch);

            Serial.print(" raw=");

            Serial.print(lastRaw[ch]);

            Serial.print(" moisture=");

            Serial.print(lastMoisture[ch]);

            Serial.print("%");

            if (ch < SENSOR_COUNT - 1) {

                Serial.print(" | ");

            }

        }

        Serial.println();

    }

}
