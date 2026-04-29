const { Router } = require('express');
const { getReadings } = require('../db');
const router = Router();

router.get('/', (req, res) => {
  const { device_id, limit = 200 } = req.query;
  if (!device_id) return res.status(400).json({ error: 'device_id required' });
  const rows = getReadings.all(device_id, Number(limit));
  res.json(rows);
});

module.exports = router;
