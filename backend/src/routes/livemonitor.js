const { Router } = require('express');
const { publishCommand } = require('../mqtt_client');
const router = Router();

router.post('/', (req, res) => {
  const { device_id, action, interval_ms = 1000, duration_sec = 120 } = req.body;
  if (!device_id || !action) return res.status(400).json({ error: 'device_id and action required' });
  if (action !== 'start' && action !== 'stop') return res.status(400).json({ error: 'action must be start or stop' });

  const command = action === 'start'
    ? { command: 'start_livemonitor', interval_ms, duration_sec }
    : { command: 'stop_livemonitor' };

  try {
    publishCommand(device_id, command);
    res.json({ ok: true, command });
  } catch (err) {
    res.status(503).json({ error: err.message });
  }
});

module.exports = router;
