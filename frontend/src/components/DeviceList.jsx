export default function DeviceList({ devices, selectedId, onSelect }) {
  if (!devices.length) {
    return <p className="no-devices">No devices seen yet.</p>;
  }
  return (
    <ul className="device-list">
      {devices.map(d => (
        <li
          key={d.id}
          className={`device-item${d.id === selectedId ? ' selected' : ''}`}
          onClick={() => onSelect(d.id)}
        >
          <span className={`dot ${d.online ? 'online' : 'offline'}`} />
          <span className="device-id">{d.id}</span>
          <span className="device-type">{d.type}</span>
          <div className="capabilities">
            {(d.capabilities || []).map(c => (
              <span key={c} className="badge">{c}</span>
            ))}
          </div>
          <span className="last-seen">{d.last_seen ? new Date(d.last_seen).toLocaleTimeString() : '—'}</span>
        </li>
      ))}
    </ul>
  );
}
