import { useState, useEffect } from 'react';
import { X, Trash2, Copy, Plus, Eye, EyeOff, Power } from 'lucide-react';
import { getDef } from './nodeRegistry';
import api from '../../utils/api';

const Secret = ({ value, onChange }) => {
  const [show, setShow] = useState(false);
  return (
    <div className="input-row">
      <input className="input" type={show ? 'text' : 'password'} value={value || ''} onChange={(e) => onChange(e.target.value)} autoComplete="off" />
      <button type="button" className="icon-btn" onClick={() => setShow(!show)}>{show ? <EyeOff size={15} /> : <Eye size={15} />}</button>
    </div>
  );
};

/** Dropdown of the user's saved connections for one app (from awf_app_integrations). */
function IntegrationSelect({ app, value, onChange }) {
  const [list, setList] = useState(null);
  useEffect(() => {
    api.get('/integrations/options', { params: { app } })
      .then((r) => setList(r.data || []))
      .catch(() => setList([]));
  }, [app]);

  if (list && list.length === 0)
    return <p className="hint">No {app} connection yet. Add one under Settings → App integrations, then reopen this node.</p>;

  return (
    <select className="input" value={value || ''} onChange={(e) => onChange(e.target.value)}>
      <option value="">{list ? 'Select connection…' : 'Loading…'}</option>
      {(list || []).map((c) => (
        <option key={c.id} value={c.id}>
          {c.name}{c.status && c.status !== 'connected' ? ` (${c.status})` : ''}
        </option>
      ))}
    </select>
  );
}

function Field({ fl, data, set, connections }) {
  const v = data[fl.key] ?? fl.default;
  switch (fl.type) {
    case 'textarea':
    case 'code':
      return <textarea className={`input ${fl.type === 'code' ? 'mono' : ''}`} rows={fl.rows || 4} value={v || ''} placeholder={fl.placeholder} onChange={(e) => set(fl.key, e.target.value)} spellCheck={false} />;
    case 'number':
      return <input className="input" type="number" step={fl.step || 1} value={v ?? ''} onChange={(e) => set(fl.key, e.target.value === '' ? '' : Number(e.target.value))} />;
    case 'select':
      return (
        <select className="input" value={v ?? ''} onChange={(e) => { set(fl.key, e.target.value); if (fl.sync && e.target.value) set(fl.sync, e.target.value); }}>
          {fl.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      );
    case 'toggle':
      return <label className="switch"><input type="checkbox" checked={!!v} onChange={(e) => set(fl.key, e.target.checked)} /><span /></label>;
    case 'secret':
      return <Secret value={v} onChange={(x) => set(fl.key, x)} />;
    case 'integration':
      return <IntegrationSelect app={fl.app} value={v} onChange={(x) => set(fl.key, x)} />;
    case 'llm':
      return (
        <select className="input" value={v || ''} onChange={(e) => set(fl.key, e.target.value)}>
          <option value="">Default connection</option>
          {connections.map((c) => <option key={c.id} value={c.id}>{c.name} — {c.provider}/{c.model}</option>)}
        </select>
      );
    case 'list': {
      const list = Array.isArray(v) ? v : [];
      return (
        <div className="stack-sm">
          {list.map((item, i) => (
            <div className="input-row" key={i}>
              <input className="input" value={item} onChange={(e) => set(fl.key, list.map((x, j) => (j === i ? e.target.value : x)))} />
              <button className="icon-btn" onClick={() => set(fl.key, list.filter((_, j) => j !== i))}><X size={15} /></button>
            </div>
          ))}
          <button className="btn btn-ghost btn-sm" onClick={() => set(fl.key, [...list, ''])}><Plus size={14} />{fl.add || 'Add'}</button>
        </div>
      );
    }
    case 'kv': {
      const list = Array.isArray(v) ? v : [];
      const upd = (i, k, val) => set(fl.key, list.map((x, j) => (j === i ? { ...x, [k]: val } : x)));
      return (
        <div className="stack-sm">
          {list.map((item, i) => (
            <div className="input-row" key={i}>
              <input className="input" placeholder={fl.keyLabel || 'name'} value={item.key || ''} onChange={(e) => upd(i, 'key', e.target.value)} />
              <input className="input" placeholder={fl.valueLabel || 'value'} value={item.value || ''} onChange={(e) => upd(i, 'value', e.target.value)} />
              <button className="icon-btn" onClick={() => set(fl.key, list.filter((_, j) => j !== i))}><X size={15} /></button>
            </div>
          ))}
          <button className="btn btn-ghost btn-sm" onClick={() => set(fl.key, [...list, { key: '', value: '' }])}><Plus size={14} />{fl.add || 'Add'}</button>
        </div>
      );
    }
    default:
      return <input className="input" value={v || ''} placeholder={fl.placeholder} onChange={(e) => set(fl.key, e.target.value)} />;
  }
}

export default function Inspector({ node, connections, output, onChange, onDelete, onDuplicate, onClose }) {
  const [tab, setTab] = useState('params');
  const def = getDef(node.type);
  const Icon = def.icon;
  const data = node.data || {};
  const set = (k, v) => onChange(node.id, k, v);

  return (
    <aside className="inspector">
      <div className="insp-head">
        <span className="insp-icon" style={{ background: def.color }}><Icon size={18} /></span>
        <input className="insp-title" value={data.label ?? def.label} onChange={(e) => set('label', e.target.value)} />
        <button className="icon-btn" onClick={onClose}><X size={16} /></button>
      </div>
      <div className="tabs">
        {[['params', 'Parameters'], ['settings', 'Settings'], ['output', 'Output']].map(([id, l]) => (
          <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>{l}</button>
        ))}
      </div>
      <div className="insp-body">
        {tab === 'params' && (
          <>
            <p className="muted">{def.desc}</p>
            {def.fields.length === 0 && <p className="muted">This node has no parameters.</p>}
            {def.fields.filter((fl) => !fl.show || fl.show(data)).map((fl) => (
              <div className="field" key={fl.key}>
                <label>{fl.label}</label>
                <Field fl={fl} data={data} set={set} connections={connections} />
              </div>
            ))}
            <p className="hint">Use <code>{'{{http.body.field}}'}</code> to use values from the workflow context.</p>
          </>
        )}
        {tab === 'settings' && (
          <>
            <div className="field row"><label><Power size={14} /> Disable node</label><label className="switch"><input type="checkbox" checked={!!data.disabled} onChange={(e) => set('disabled', e.target.checked)} /><span /></label></div>
            <div className="field row"><label>Continue on fail</label><label className="switch"><input type="checkbox" checked={!!data.continueOnFail} onChange={(e) => set('continueOnFail', e.target.checked)} /><span /></label></div>
            <div className="field row"><label>Retry on fail</label><label className="switch"><input type="checkbox" checked={!!data.retryOnFail} onChange={(e) => set('retryOnFail', e.target.checked)} /><span /></label></div>
            {data.retryOnFail && <div className="field"><label>Max retries</label><input className="input" type="number" min="1" max="10" value={data.maxRetries ?? 3} onChange={(e) => set('maxRetries', Number(e.target.value))} /></div>}
            <div className="field"><label>Notes</label><textarea className="input" rows="4" value={data.notes || ''} onChange={(e) => set('notes', e.target.value)} placeholder="Describe what this node does" /></div>
            <div className="field"><label>Node ID</label><code className="code-chip">{node.id}</code></div>
          </>
        )}
        {tab === 'output' && (
          output ? <pre className="json">{JSON.stringify(output, null, 2)}</pre> : <p className="muted">No output yet. Execute the workflow to see this node's result.</p>
        )}
      </div>
      <div className="insp-foot">
        <button className="btn btn-ghost btn-sm" onClick={() => onDuplicate(node.id)}><Copy size={14} />Duplicate</button>
        <button className="btn btn-danger btn-sm" onClick={() => onDelete(node.id)}><Trash2 size={14} />Delete</button>
      </div>
    </aside>
  );
}