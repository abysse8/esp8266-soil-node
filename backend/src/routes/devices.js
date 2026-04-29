const { Router } = require('express');
const { getDevices } = require('../db');
const router = Router();

router.get('/', (req, res) => {
  const rows = getDevices.all();
  const devices = rows.map(d => ({
    ...d,
    capabilities: d.capabilities ? JSON.parse(d.capabilities) : [],
    online: Boolean(d.online)
  }));
  res.json(devices);
});

module.exports = router;
