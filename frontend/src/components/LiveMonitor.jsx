import { useState } from 'react';
import axios from 'axios';
import ReadingsChart from './ReadingsChart';

const API = import.meta.env.VITE_API_URL ?? '';

export default function LiveMonitor({ deviceId, liveReadings }) {
  const [active, setActive] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [timerRef, setTimerRef] = useState(null);

  async function toggleLive() {
    if (active) {
      await axios.post(`${API}/livemonitor`, { device_id: deviceId, action: 'stop' });
      setActive(false);
      clearInterval(timerRef);
      setCountdown(0);
    } else {
      const duration = 120;
      await axios.post(`${API}/livemonitor`, {
        device_id: deviceId, action: 'start', interval_ms: 1000, duration_sec: duration
      });
      setActive(true);
      setCountdown(duration);
      const ref = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) { clearInterval(ref); setActive(false); return 0; }
          return prev - 1;
        });
      }, 1000);
      setTimerRef(ref);
    }
  }

  return (
    <div className="live-monitor">
      <div className="live-controls">
        <button className={`live-btn ${active ? 'active' : ''}`} onClick={toggleLive}>
          {active ? `Stop Live Monitor (${countdown}s)` : 'Start Live Monitor'}
        </button>
        {active && <span className="live-badge">LIVE</span>}
      </div>
      {active && liveReadings.length > 0 && (
        <div className="live-chart">
          <ReadingsChart readings={liveReadings} />
        </div>
      )}
    </div>
  );
}
