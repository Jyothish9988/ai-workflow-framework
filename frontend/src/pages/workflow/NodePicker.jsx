import { useState, useMemo } from 'react';
import { Search, X } from 'lucide-react';
import { NODES, CATEGORIES } from './nodeRegistry';

export default function NodePicker({ onPick, onClose }) {
  const [q, setQ] = useState('');
  const groups = useMemo(() => {
    const s = q.trim().toLowerCase();
    return CATEGORIES.map((c) => ({
      ...c,
      items: Object.entries(NODES).filter(([, d]) => d.cat === c.id && (!s || `${d.label} ${d.desc}`.toLowerCase().includes(s))),
    })).filter((g) => g.items.length);
  }, [q]);

  return (
    <aside className="picker">
      <div className="picker-head">
        <h3>Add a node</h3>
        <button className="icon-btn" onClick={onClose}><X size={16} /></button>
      </div>
      <div className="search"><Search size={15} /><input autoFocus placeholder="Search nodes…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      <div className="picker-list">
        {groups.length === 0 && <p className="muted pad">No nodes match "{q}"</p>}
        {groups.map((g) => (
          <section key={g.id}>
            <h4>{g.label}</h4>
            {g.items.map(([type, d]) => {
              const Icon = d.icon;
              return (
                <button key={type} className="picker-item" draggable onClick={() => onPick(type)}
                  onDragStart={(e) => { e.dataTransfer.setData('application/wf-node', type); e.dataTransfer.effectAllowed = 'move'; }}>
                  <span className="picker-ico" style={{ background: d.color }}><Icon size={17} /></span>
                  <span><b>{d.label}</b><small>{d.desc}</small></span>
                </button>
              );
            })}
          </section>
        ))}
      </div>
    </aside>
  );
}
