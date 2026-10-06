import { useEffect, useState } from 'react';
import { Plus, Pencil, Trash2, X, Package as PackageIcon, Loader2, Upload } from 'lucide-react';
import { adminAPI, errMsg } from '../../utils/api';
import { Spinner, Empty, useToast, timeAgo } from '../../components/ui';

const EXAMPLE = JSON.stringify({
  name: 'Orders DB',
  description: 'Run a SQL query through the company database API',
  color: '#0984e3',
  fields: [
    { key: 'apiKey', label: 'API key', type: 'secret' },
    { key: 'sql', label: 'SQL query', type: 'code', default: 'SELECT * FROM orders LIMIT 10' },
  ],
  request: {
    method: 'POST',
    url: 'https://db-api.example.com/query',
    headers: { Authorization: 'Bearer ${apiKey}' },
    body: { sql: '${sql}' },
  },
  output: 'db.result',
}, null, 2);

export default function AdminPackages() {
  const [rows, setRows] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(null);   // { id?, text, access, user_ids }
  const [saving, setSaving] = useState(false);
  const [toast, notify] = useToast();
  const editing = form?.id;

  const load = async () => {
    try {
      const [p, u] = await Promise.all([adminAPI.packages(), adminAPI.users()]);
      setRows(p.data || []); setUsers(u.data || []);
    } catch (e) { notify(errMsg(e, 'Failed to load packages'), 'error'); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line

  const save = async (e) => {
    e.preventDefault();
    let manifest;
    try { manifest = JSON.parse(form.text); } catch { return notify('Manifest is not valid JSON', 'error'); }
    const body = { manifest, access: form.access, user_ids: form.user_ids };
    setSaving(true);
    try {
      await (editing ? adminAPI.updatePackage(form.id, body) : adminAPI.createPackage(body));
      notify(editing ? 'Package updated' : 'Package added'); setForm(null); load();
    } catch (er) { notify(errMsg(er), 'error'); } finally { setSaving(false); }
  };
  const toggle = async (p) => {
    try { await adminAPI.updatePackage(p.id, { is_active: !p.is_active }); load(); } catch (er) { notify(errMsg(er), 'error'); }
  };
  const remove = async (p) => {
    if (!window.confirm(`Delete "${p.name}"? Workflows using it will show an "Unavailable package" node.`)) return;
    try { await adminAPI.deletePackage(p.id); notify('Package deleted'); load(); } catch (er) { notify(errMsg(er), 'error'); }
  };
  const readFile = (file) => file && file.text().then((t) => setForm((f) => ({ ...f, text: t })));
  // Logo: read the image, store it as a data URL in manifest.icon (edits the JSON in the box)
  const setLogo = (file) => {
    if (!file) return;
    if (!/^image\/(png|jpeg|webp|svg\+xml)$/.test(file.type)) return notify('Logo must be PNG, JPEG, WebP or SVG', 'error');
    if (file.size > 200 * 1024) return notify('Logo must be 200 KB or smaller', 'error');
    const rd = new FileReader();
    rd.onload = () => {
      try { const m = JSON.parse(form.text); m.icon = rd.result; setForm((f) => ({ ...f, text: JSON.stringify(m, null, 2) })); }
      catch { notify('Fix the manifest JSON first, then add the logo', 'error'); }
    };
    rd.readAsDataURL(file);
  };
  const removeLogo = () => { try { const m = JSON.parse(form.text); delete m.icon; setForm((f) => ({ ...f, text: JSON.stringify(m, null, 2) })); } catch { /* ignore */ } };
  const logo = (() => { try { return JSON.parse(form?.text || '{}').icon; } catch { return null; } })();
  const toggleUser = (id) => setForm((f) => ({ ...f, user_ids: f.user_ids.includes(id) ? f.user_ids.filter((x) => x !== id) : [...f.user_ids, id] }));
  const who = (p) => (p.access === 'all' ? 'All users' : `${p.user_ids.length} assigned user(s)`);

  return (
    <>
      <div className="row-gap"><span className="grow" />
        <button className="btn btn-primary" onClick={() => setForm({ text: EXAMPLE, access: 'all', user_ids: [] })}><Plus size={16} />Add package</button></div>
      {loading ? <Spinner /> : rows.length === 0 ? <Empty icon={PackageIcon} title="No packages yet" text="Upload a node manifest (JSON) and assign it to users." /> : (
        <div className="pkg-grid">{rows.map((p) => (
          <article key={p.id} className={`card pkg-card ${p.is_active ? '' : 'off'}`}>
            <div className="pkg-head">
              <span className="pkg-icon">{p.icon ? <img src={p.icon} alt="" /> : <PackageIcon size={22} />}</span>
              <div style={{ minWidth: 0 }}><b>{p.name}</b><div className="muted mono-sm">{who(p)} · {p.fields.length} field(s)</div></div>
              <span className="grow" /><label className="switch" title={p.is_active ? 'Enabled' : 'Disabled'}><input type="checkbox" checked={p.is_active} onChange={() => toggle(p)} /><span /></label>
            </div>
            <p className="muted clamp">{p.description || 'No description'}</p>
            <footer><span className="muted">{timeAgo(p.created_at)}</span><span className="grow" />
              <button className="icon-btn" title="Edit" onClick={() => setForm({ id: p.id, text: JSON.stringify(p.manifest, null, 2), access: p.access, user_ids: p.user_ids })}><Pencil size={15} /></button>
              <button className="icon-btn danger" title="Delete" onClick={() => remove(p)}><Trash2 size={15} /></button></footer>
          </article>))}</div>
      )}
      {form && (
        <div className="modal-bg" onClick={() => !saving && setForm(null)}>
          <form className="modal wide" onClick={(e) => e.stopPropagation()} onSubmit={save}>
            <div className="modal-head"><h3>{editing ? 'Edit package' : 'Add package'}</h3><button type="button" className="icon-btn" onClick={() => setForm(null)}><X size={16} /></button></div>
            <div className="field"><label>Logo (PNG, JPEG, WebP or SVG, up to 200 KB)</label>
              <div className="file-drop">
                <span className="pkg-icon">{logo ? <img src={logo} alt="" /> : <PackageIcon size={22} />}</span>
                <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" onChange={(e) => { setLogo(e.target.files[0]); e.target.value = ''; }} />
                {logo && <button type="button" className="btn btn-ghost" onClick={removeLogo}>Remove</button>}</div></div>
            <div className="field"><label>Node manifest (JSON) <span className="file-drop" style={{ display: 'inline-flex', marginLeft: 8 }}><Upload size={13} /><input type="file" accept=".json,application/json" onChange={(e) => readFile(e.target.files[0])} /></span></label>
              <textarea className="input mono" rows={16} spellCheck={false} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} /></div>
            <div className="field"><label>Who can use it</label>
              <select className="input" value={form.access} onChange={(e) => setForm({ ...form, access: e.target.value })}>
                <option value="all">All users</option><option value="assigned">Only selected users</option></select></div>
            {form.access === 'assigned' && (
              <div className="field" style={{ maxHeight: 160, overflow: 'auto' }}>
                {users.map((u) => (<label key={u.id} style={{ display: 'flex', gap: 8 }}>
                  <input type="checkbox" checked={form.user_ids.includes(String(u.id))} onChange={() => toggleUser(String(u.id))} />{u.username} <span className="muted">{u.email}</span></label>))}
              </div>)}
            <div className="help">
              <b>Manifest</b>: <code>fields</code> become the node's inputs (types: text, textarea, code, number, select, toggle, secret).
              <code>request</code> is the API call (or <code>operations</code> for several, shown as a dropdown; <code>auth</code> adds a connection picker); use <code>{'${fieldKey}'}</code> for field values (the URL host must be fixed).
              The response is saved as <code>{'{status, body}'}</code> at <code>output</code>. Users can also use <code>{'{{context.path}}'}</code> inside any field.
            </div>
            <div className="modal-foot"><button type="button" className="btn btn-ghost" disabled={saving} onClick={() => setForm(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={saving}>{saving && <Loader2 size={15} className="spin" />}{editing ? 'Save changes' : 'Add package'}</button></div>
          </form>
        </div>
      )}
      {toast}
    </>
  );
}