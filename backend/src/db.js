const Database = require('better-sqlite3');
const path = require('path');

const db = new Database(path.join(__dirname, '../data/growroom.db'));

db.exec(`
  CREATE TABLE IF NOT EXISTS devices (
    id          TEXT PRIMARY KEY,
    type        TEXT,
    capabilities TEXT,
    last_seen   TEXT,
    rssi        INTEGER,
    online      INTEGER DEFAULT 0
  );

  CREATE TABLE IF NOT EXISTS readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    channel     INTEGER NOT NULL,
    raw         INTEGER,
    moisture_pct INTEGER,
    uptime_ms   INTEGER,
    received_at TEXT NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_readings_device ON readings(device_id, received_at);
`);

const WINDOW_HOURS = 72;

const upsertDevice = db.prepare(`
  INSERT INTO devices (id, type, capabilities, last_seen, rssi, online)
  VALUES (@id, @type, @capabilities, @last_seen, @rssi, @online)
  ON CONFLICT(id) DO UPDATE SET
    type = excluded.type,
    capabilities = excluded.capabilities,
    last_seen = excluded.last_seen,
    rssi = coalesce(excluded.rssi, rssi),
    online = excluded.online
`);

const insertReading = db.prepare(`
  INSERT INTO readings (device_id, channel, raw, moisture_pct, uptime_ms, received_at)
  VALUES (@device_id, @channel, @raw, @moisture_pct, @uptime_ms, @received_at)
`);

const deleteOldReadings = db.prepare(`
  DELETE FROM readings
  WHERE received_at < datetime('now', '-${WINDOW_HOURS} hours')
`);

const getDevices = db.prepare(`SELECT * FROM devices`);

const getReadings = db.prepare(`
  SELECT * FROM readings
  WHERE device_id = ?
  ORDER BY received_at DESC
  LIMIT ?
`);

const updateDeviceStatus = db.prepare(`
  UPDATE devices SET online = @online, last_seen = @last_seen WHERE id = @id
`);

const updateDeviceHeartbeat = db.prepare(`
  UPDATE devices SET last_seen = @last_seen, rssi = @rssi WHERE id = @id
`);

function saveReading(msg) {
  const now = new Date().toISOString();
  upsertDevice.run({
    id: msg.device_id,
    type: msg.type || null,
    capabilities: JSON.stringify(msg.capabilities || []),
    last_seen: now,
    rssi: null,
    online: 1
  });
  for (const s of msg.sensors || []) {
    insertReading.run({
      device_id: msg.device_id,
      channel: s.channel,
      raw: s.raw,
      moisture_pct: s.moisture_pct,
      uptime_ms: msg.uptime_ms || null,
      received_at: now
    });
  }
  deleteOldReadings.run();
}

function saveHeartbeat(msg) {
  const now = new Date().toISOString();
  upsertDevice.run({
    id: msg.device_id,
    type: msg.type || null,
    capabilities: null,
    last_seen: now,
    rssi: msg.rssi || null,
    online: 1
  });
}

function setDeviceStatus(deviceId, online) {
  updateDeviceStatus.run({ id: deviceId, online: online ? 1 : 0, last_seen: new Date().toISOString() });
}

module.exports = { saveReading, saveHeartbeat, setDeviceStatus, getDevices, getReadings };
