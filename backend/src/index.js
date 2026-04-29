const http = require('http');
const express = require('express');
const cors = require('cors');
const { Server } = require('socket.io');
const mqttClient = require('./mqtt_client');

const app = express();
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: '*' } });

app.use(cors());
app.use(express.json());

app.use('/health',      require('./routes/health'));
app.use('/devices',     require('./routes/devices'));
app.use('/readings',    require('./routes/readings'));
app.use('/livemonitor', require('./routes/livemonitor'));

mqttClient.start(io);

const PORT = process.env.PORT || 3001;
server.listen(PORT, () => console.log(`Backend listening on http://localhost:${PORT}`));
