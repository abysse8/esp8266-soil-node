import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { io } from 'socket.io-client';
import DeviceList from './components/DeviceList';
import ReadingsChart from './components/ReadingsChart';
import LiveMonitor from './components/LiveMonitor';
import './App.css';

const API = import.meta.env.VITE_API_URL ?? '';
const LIVE_BUFFER = 120;

export default function App() {
  const [devices, setDevices] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [readings, setReadings] = useState([]);
  const [liveReadings, setLiveReadings] = useState([]);
  const socketRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/devices`).then(r => {
      setDevices(r.data);
      if (r.data.length > 0) selectDevice(r.data[0].id);
    });

    const socket = io(API || window.location.origin);
    socketRef.current = socket;

    socket.on('reading', msg => {
      setDevices(prev =>
        prev.map(d => d.id === msg.device_id ? { ...d, online: true, last_seen: new Date().toISOString() } : d)
      );
      setReadings(prev => [msg, ...prev].slice(0, 500));
      setLiveReadings(prev => {
        const flat = (msg.sensors || []).map(s => ({
          ...s, received_at: new Date().toISOString(), device_id: msg.device_id
        }));
        return [...prev, ...flat].slice(-LIVE_BUFFER * 8);
      });
    });

    socket.on('device_update', msg => {
      setDevices(prev => prev.map(d => d.id === msg.device_id ? { ...d, ...msg } : d));
    });

    return () => socket.disconnect();
  }, []);

  async function selectDevice(id) {
    setSelectedId(id);
    setLiveReadings([]);
    const r = await axios.get(`${API}/readings`, { params: { device_id: id, limit: 200 } });
    setReadings(r.data);
  }

  const deviceReadings = readings
    .filter(r => r.device_id === selectedId && Array.isArray(r.sensors))
    .flatMap(r => r.sensors.map(s => ({ ...s, received_at: r.received_at || new Date().toISOString() })));

  const deviceLiveReadings = liveReadings.filter(r => r.device_id === selectedId);

  return (
    <div className="app">
      <header className="app-header">
        <h1>Growroom Monitor</h1>
      </header>
      <main className="app-main">
        <aside className="sidebar">
          <h2>Devices</h2>
          <DeviceList devices={devices} selectedId={selectedId} onSelect={selectDevice} />
        </aside>
        <section className="content">
          {selectedId ? (
            <>
              <h2>{selectedId}</h2>
              <h3>Moisture History</h3>
              <ReadingsChart readings={deviceReadings} />
              <LiveMonitor deviceId={selectedId} liveReadings={deviceLiveReadings} />
            </>
          ) : (
            <p className="no-selection">Select a device to view data.</p>
          )}
        </section>
      </main>
    </div>
  );
}
