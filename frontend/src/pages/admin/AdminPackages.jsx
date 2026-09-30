import { useEffect, useState } from 'react';
import { Plus, Pencil, Trash2, X, Package as PackageIcon, AlertTriangle, Loader2 } from 'lucide-react';
import { adminAPI, errMsg } from '../../utils/api';
import { Spinner, Empty, useToast, timeAgo } from '../../components/ui';

const blank = { name: '', description: '', file: null, icon: null };
const fmtSize = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

export default function AdminPackages() {
  const [rows, setRows] = useState([]);
  const [rt, setRt] = useState(null);                 // server platform / limits
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(null);             // null | blank | existing package (edit)
  const [saving, setSaving] = useState(false);
  const [toast, notify] = useToast();
  const editing = form?.id;

  const load = async () => {
    try { const [p, r] = await Promise.all([adminAPI.packages(), adminAPI.packageRuntime()]); setRows(p.data || []); setRt(r.data); }
    catch (e) { notify(errMsg(e, 'Failed to load packages'), 'error'); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line

  const save = async (e) => {
    e.preventDefault();
    if (!editing && !form.file) return notify('Choose the file to upload', 'error');
    const fd = new FormData();
    fd.append('name', form.name); fd.append('description', form.description || '');
    if (form.file) fd.append('file', form.file);
    if (form.icon) fd.append('icon', form.icon);
    setSaving(true);
    try { await (editing ? adminAPI.updatePackage(form.id, fd) : adminAPI.createPackage(fd)); notify(editing ? 'Package updated' : 'Package added — it is now a node in every user\'s editor'); setForm(null); load(); }
    catch (er) { notify(errMsg(er), 'error'); } finally { setSaving(false); }
  };
  const toggle = async (p) => {
    const fd = new FormData(); fd.append('is_active', String(!p.is_active));
    try { await adminAPI.updatePackage(p.id, fd); load(); } catch (er) { notify(errMsg(er), 'error'); }
  };
  const remove = async (p) => {
    if (!window.confirm(`Delete "${p.name}"? Workflows that use it will show a "missing package" node.`)) return;
    try { await adminAPI.deletePackage(p.id); notify('Package deleted'); load(); } catch (er) { notify(errMsg(er), 'error'); }
  };

  return (
    <>
      {rt && (
        <div className="banner"><AlertTriangle size={18} style={{ flexShrink: 0 }} />
          <div>The server runs <b>{rt.platform}</b>, so packages must be {rt.platform === 'linux' ? 'Linux executables (ELF) or .so libraries' : 'Windows .exe / .dll files'} (max {rt.max_mb} MB).
            {rt.platform === 'linux' && ' Windows .exe / .dll files cannot run inside the Linux Docker container.'} Packages run as separate processes, but they are not fully sandboxed — only upload files you trust.</div></div>
      )}
      <div className="row-gap"><span className="grow" /><button className="btn btn-primary" onClick={() => setForm({ ...blank })}><Plus size={16} />Add package</button></div>
      {loading ? <Spinner /> : rows.length === 0 ? <Empty icon={PackageIcon} title="No packages yet" text="Upload an executable or library and it becomes a node for every user." /> : (
        <div className="pkg-grid">{rows.map((p) => (
          <article key={p.id} className={`card pkg-card ${p.is_active ? '' : 'off'}`}>
            <div className="pkg-head">
              <span className="pkg-icon">{p.icon ? <img src={p.icon} alt="" /> : <PackageIcon size={22} />}</span>
              <div style={{ minWidth: 0 }}><b>{p.name}</b><div className="muted mono-sm">{p.kind.toUpperCase()} · {p.platform} · {fmtSize(p.size)}</div></div>
              <span className="grow" /><label className="switch" title={p.is_active ? 'Enabled' : 'Disabled'}><input type="checkbox" checked={p.is_active} onChange={() => toggle(p)} /><span /></label>
            </div>
            <p className="muted clamp">{p.description || 'No description'}</p>
            <footer><span className="muted mono-sm" title={p.sha256}>{p.original_name} · {p.sha256.slice(0, 10)}…</span><span className="grow" />
              <span className="muted">{timeAgo(p.created_at)}</span>
              <button className="icon-btn" title="Edit" onClick={() => setForm({ ...p, file: null, icon: null, icon_url: p.icon })}><Pencil size={15} /></button>
              <button className="icon-btn danger" title="Delete" onClick={() => remove(p)}><Trash2 size={15} /></button></footer>
          </article>))}</div>
      )}
      {form && (
        <div className="modal-bg" onClick={() => !saving && setForm(null)}>
          <form className="modal wide" onClick={(e) => e.stopPropagation()} onSubmit={save}>
            <div className="modal-head"><h3>{editing ? 'Edit package' : 'Add package'}</h3><button type="button" className="icon-btn" onClick={() => setForm(null)}><X size={16} /></button></div>
            <div className="field"><label>Package name (shown as the node name)</label><input className="input" required minLength={2} maxLength={60} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus /></div>
            <div className="field"><label>Description</label><textarea className="input" rows="3" maxLength={1000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
            <div className="field"><label>{editing ? 'Replace file (optional)' : 'File'} — {rt ? rt.extensions.join(' ') : '.exe .dll .so'}</label>
              <div className="file-drop"><input type="file" accept={(rt?.extensions || []).join(',')} onChange={(e) => setForm({ ...form, file: e.target.files[0] || null })} /></div></div>
            <div className="field"><label>Icon (PNG, JPEG or WebP, up to 200 KB)</label>
              <div className="file-drop">
                <span className="pkg-icon">{form.icon ? <img src={URL.createObjectURL(form.icon)} alt="" /> : form.icon_url ? <img src={form.icon_url} alt="" /> : <PackageIcon size={22} />}</span>
                <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setForm({ ...form, icon: e.target.files[0] || null })} /></div></div>
            <div className="help">
              <b>How your package is called</b><br />
              Executable: receives <code>{'{"input": …}'}</code> as JSON on <code>stdin</code>, prints the result (JSON or text) to <code>stdout</code>, exits with code 0.<br />
              Library (.dll / .so): export <code>const char* awf_run(const char* json_input)</code> returning the result as text.<br />
              Users set the input in the node (variables like <code>{'{{http.body.id}}'}</code> work) and the result is saved to <code>package.output</code>.
            </div>
            <div className="modal-foot"><button type="button" className="btn btn-ghost" disabled={saving} onClick={() => setForm(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={saving}>{saving && <Loader2 size={15} className="spin" />}{editing ? 'Save changes' : 'Upload package'}</button></div>
          </form>
        </div>
      )}
      {toast}
    </>
  );
}
