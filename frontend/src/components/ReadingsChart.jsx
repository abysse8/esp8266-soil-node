import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const COLORS = ['#4ade80','#60a5fa','#f97316','#a78bfa','#f43f5e','#facc15','#22d3ee','#fb923c'];

export default function ReadingsChart({ readings }) {
  if (!readings.length) return <p className="no-data">No readings yet.</p>;

  // Group readings by received_at, pivot channels into columns
  const byTime = {};
  for (const r of readings) {
    const t = r.received_at;
    if (!byTime[t]) byTime[t] = { time: new Date(t).toLocaleTimeString() };
    byTime[t][`ch${r.channel}`] = r.moisture_pct;
  }
  const data = Object.values(byTime).reverse();
  const channels = [...new Set(readings.map(r => r.channel))].sort();

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <XAxis dataKey="time" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
        <YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v) => `${v}%`} />
        <Legend />
        {channels.map((ch, i) => (
          <Line
            key={ch}
            type="monotone"
            dataKey={`ch${ch}`}
            name={`Channel ${ch}`}
            stroke={COLORS[i % COLORS.length]}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
