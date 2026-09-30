import { useEffect, useState } from 'react';
import { Plus, Search, Pencil, Trash2, Activity, UserX, UserCheck, X } from 'lucide-react';
import { adminAPI, errMsg } from '../../utils/api';
import { Spinner, Empty, useToast, timeAgo } from '../../components/ui';

const blank = { username: '', email: '', password: '', is_admin: false, is_active: true };

export default function AdminUsers({ onViewRuns }) {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(null);            // null | blank | existing user (edit)
  const [toast, notify] = useToast();
  const editing = form?.id;

  const load = async (search = q) => {
    try { setRows((await adminAPI.users({ search: search || undefined })).data || []); }
    catch (e) { notify(errMsg(e, 'Failed to load users'), 'error'); } finally { setLoading(false); }
  };
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [q]); // eslint-disable-line

  const save = async (e) => {
    e.preventDefault();
    try {
      if (editing) {
        const body = { username: form.username, email: form.email, is_admin: form.is_admin, is_active: form.is_active };
        if (form.password) body.password = form.password;
        await adminAPI.updateUser(form.id, body);
      } else await adminAPI.createUser({ username: form.username, email: form.email, password: form.password, is_admin: form.is_admin });
      notify(editing ? 'User updated' : 'User created'); setForm(null); load();
    } catch (er) { notify(errMsg(er), 'error'); }
  };
  const toggleActive = async (u) => {
    try { await adminAPI.updateUser(u.id, { is_active: !u.is_active }); notify(u.is_active ? 'User deactivated' : 'User activated'); load(); }
    catch (er) { notify(errMsg(er), 'error'); }
  };
  const remove = async (u) => {
    if (!window.confirm(`Delete ${u.email}? All their workflows, runs and connections are removed permanently.`)) return;
    try { await adminAPI.deleteUser(u.id); notify('User deleted'); load(); } catch (er) { notify(errMsg(er), 'error'); }
  };

  return (
    <>
      <div className="row-gap">
        <div className="search"><Search size={15} /><input placeholder="Search users…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <span className="grow" />
        <button className="btn btn-primary" onClick={() => setForm({ ...blank })}><Plus size={16} />Add user</button>
      </div>
      {loading ? <Spinner /> : rows.length === 0 ? <Empty title="No users found" /> : (
        <div className="card flush"><table className="table">
          <thead><tr><th>User</th><th>Role</th><th>Status</th><th>Workflows</th><th>Runs</th><th>Last run</th><th>Joined</th><th /></tr></thead>
          <tbody>{rows.map((u) => (
            <tr key={u.id} style={{ cursor: 'default' }}>
              <td><b>{u.username}</b><div className="muted mono-sm">{u.email}</div></td>
              <td>{u.is_admin ? <span className="badge badge-admin">admin</span> : <span className="muted">user</span>}</td>
              <td><span className={`badge ${u.is_active ? 'badge-ok' : 'badge-off'}`}>{u.is_active ? 'active' : 'disabled'}</span></td>
              <td>{u.workflows}</td><td>{u.runs}</td><td>{timeAgo(u.last_run_at)}</td><td>{timeAgo(u.created_at)}</td>
              <td className="right" style={{ whiteSpace: 'nowrap' }}>
                <button className="icon-btn" title="View runs" onClick={() => onViewRuns(u)}><Activity size={15} /></button>
                <button className="icon-btn" title="Edit" onClick={() => setForm({ ...u, password: '' })}><Pencil size={15} /></button>
                <button className="icon-btn" title={u.is_active ? 'Deactivate' : 'Activate'} onClick={() => toggleActive(u)}>{u.is_active ? <UserX size={15} /> : <UserCheck size={15} />}</button>
                <button className="icon-btn danger" title="Delete" onClick={() => remove(u)}><Trash2 size={15} /></button>
              </td>
            </tr>))}</tbody></table></div>
      )}
      {form && (
        <div className="modal-bg" onClick={() => setForm(null)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={save}>
            <div className="modal-head"><h3>{editing ? 'Edit user' : 'Add user'}</h3><button type="button" className="icon-btn" onClick={() => setForm(null)}><X size={16} /></button></div>
            <div className="field"><label>Username</label><input className="input" required minLength={3} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} autoFocus /></div>
            <div className="field"><label>Email</label><input className="input" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div className="field"><label>{editing ? 'New password (leave blank to keep)' : 'Password'}</label>
              <input className="input" type="password" minLength={6} required={!editing} autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
            <div className="field row"><label>Administrator</label><label className="switch"><input type="checkbox" checked={form.is_admin} onChange={(e) => setForm({ ...form, is_admin: e.target.checked })} /><span /></label></div>
            {editing && <div className="field row"><label>Account active</label><label className="switch"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /><span /></label></div>}
            <div className="modal-foot"><button type="button" className="btn btn-ghost" onClick={() => setForm(null)}>Cancel</button><button className="btn btn-primary">{editing ? 'Save' : 'Create user'}</button></div>
          </form>
        </div>
      )}
      {toast}
    </>
  );
}
