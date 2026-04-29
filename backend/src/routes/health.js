const { Router } = require('express');
const router = Router();

const startedAt = Date.now();

router.get('/', (req, res) => {
  res.json({ status: 'ok', uptime_ms: Date.now() - startedAt });
});

module.exports = router;
