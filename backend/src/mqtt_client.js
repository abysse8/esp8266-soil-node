const mqtt = require('mqtt');
const { saveReading, saveHeartbeat, setDeviceStatus } = require('./db');

const BROKER_URL = process.env.MQTT_BROKER || 'mqtt://localhost';

let client;
let ioRef;

function start(io) {
  ioRef = io;
  client = mqtt.connect(BROKER_URL);

  client.on('connect', () => {
    console.log(`MQTT connected to ${BROKER_URL}`);
    client.subscribe('devices/+/readings');
    client.subscribe('devices/+/heartbeat');
    client.subscribe('devices/+/status');
  });

  client.on('message', (topic, payload) => {
    const parts = topic.split('/');
    const deviceId = parts[1];
    const kind = parts[2];

    let msg;
    try {
      msg = JSON.parse(payload.toString());
    } catch {
      return;
    }

    if (kind === 'readings') {
      saveReading(msg);
      ioRef.emit('reading', { device_id: deviceId, ...msg });
    } else if (kind === 'heartbeat') {
      saveHeartbeat(msg);
      ioRef.emit('device_update', { device_id: deviceId, event: 'heartbeat', ...msg });
    } else if (kind === 'status') {
      const online = payload.toString() === 'online';
      setDeviceStatus(deviceId, online);
      ioRef.emit('device_update', { device_id: deviceId, event: 'status', online });
    }
  });

  client.on('error', (err) => console.error('MQTT error:', err.message));
}

function publishCommand(deviceId, payload) {
  if (!client || !client.connected) throw new Error('MQTT not connected');
  client.publish(`devices/${deviceId}/commands`, JSON.stringify(payload));
}

module.exports = { start, publishCommand };
