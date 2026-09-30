import { useEffect, useState, useCallback } from 'react';
import { RefreshCw, Square, Eye, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { adminAPI, errMsg } from '../../utils/api';
import { Spinner, Empty, StatusBadge, useToast, fmtDuration, timeAgo } from '../../components/ui';
import { NodeLogList } from '../workflow/ExecutionPanel';

const PAGE = 25;

export default function AdminRuns({ initialUser }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [users, setUsers] = useState([]);
  const [userId, setUserId] = useState(initialUser || '');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);        // { run, logs, withData }
  const [toast, notify] = useToast();

  const load = useCallback(async (quiet) => {
    try {
      const r = await adminAPI.runs({ user_id: userId || undefined, status: status || undefined, limit: PAGE, offset });
      setRows(r.data.data || []); setTotal(r.data.total || 0);
    } catch (e) { if (!quiet) notify(errMsg(e, 'Failed to load runs'), 'error'); } finally { setLoading(false); }
  }, [userId, status, offset]); // eslint-disable-line

  useEffect(() => { adminAPI.users().then((r) => setUsers(r.data || [])).catch(() => {}); }, []);
  useEffect(() => { setLoading(true); load(); }, [load]);
  useEffect(() => {                                   // live refresh while something is running
    if (!rows.some((r) => r.status === 'running')) return undefined;
    const t = setInterval(() => load(true), 4000); return () => clearInterval(t);
  }, [rows, load]);

  const terminate = async (run) => {
    if (!window.confirm(`Terminate this run of "${run.workflow_name}" for ${run.email}?`)) return;
    try { await adminAPI.terminateRun(run.id); notify('Stop signal sent'); setTimeout(() => load(true), 800); }
    catch (e) { notify(errMsg(e, 'Could not terminate'), 'error'); }
  };
  const open = async (run, withData = false) => {
    try { const r = await adminAPI.runNodes(run.id, withData); setDetail({ run, logs: r.data.data || [], withData }); }
    catch (e) { notify(errMsg(e), 'error'); }
  };

  return (
    <>
      <div className="row-gap">
        <select className="input w-auto" value={userId} onChange={(e) => { setOffset(0); setUserId(e.target.value); }}>
          <option value="">All users</option>{users.map((u) => <option key={u.id} value={u.id}>{u.username} ({u.email})</option>)}
        </select>
        <select className="input w-auto" value={status} onChange={(e) => { setOffset(0); setStatus(e.target.value); }}>
          <option value="">Any status</option>{['running', 'success', 'failed', 'partial', 'cancelled'].map((s) => <option key={s}>{s}</option>)}
        </select>
        <span className="grow" />
        <button className="btn btn-outline" onClick={() => load()}><RefreshCw size={15} />Refresh</button>
      </div>
      {loading ? <Spinner /> : rows.length === 0 ? <Empty title="No runs" text="Runs from all users appear here." /> : (
        <div className="card flush">
          <table className="table">
            <thead><tr><th>User</th><th>Workflow</th><th>Status</th><th>Started</th><th>Duration</th><th>Nodes</th><th /></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.id} onClick={() => open(r)}>
                <td><b>{r.username}</b><div className="muted mono-sm">{r.email}</div></td>
                <td>{r.workflow_name}</td><td><StatusBadge status={r.status} /></td>
                <td>{timeAgo(r.created_at)}</td><td>{fmtDuration(r.duration_ms)}</td>
                <td>{r.nodes_success ?? 0}/{r.nodes_total ?? 0}{r.nodes_failed ? <span className="c-err"> · {r.nodes_failed} failed</span> : null}</td>
                <td className="right" style={{ whiteSpace: 'nowrap' }} onClick={(e) => e.stopPropagation()}>
                  <button className="icon-btn" title="Details" onClick={() => open(r)}><Eye size={15} /></button>
                  {r.status === 'running' && <button className="icon-btn danger" title="Terminate" onClick={() => terminate(r)}><Square size={15} /></button>}
                </td>
              </tr>))}</tbody>
          </table>
          <div className="pager">
            <span>{offset + 1}–{Math.min(offset + PAGE, total)} of {total}</span>
            <button className="icon-btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}><ChevronLeft size={16} /></button>
            <button className="icon-btn" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}><ChevronRight size={16} /></button>
          </div>
        </div>
      )}
      {detail && (
        <div className="modal-bg" onClick={() => setDetail(null)}>
          <div className="modal wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head"><h3>{detail.run.workflow_name} <span className="muted" style={{ fontWeight: 400 }}>· {detail.run.email}</span></h3><button className="icon-btn" onClick={() => setDetail(null)}><X size={16} /></button></div>
            <div className="row-gap" style={{ marginBottom: 10 }}>
              <StatusBadge status={detail.run.status} /><span className="muted">{fmtDuration(detail.run.duration_ms)}</span><span className="grow" />
              <label className="row-gap muted" style={{ fontSize: 13 }}>Show users' data
                <span className="switch"><input type="checkbox" checked={detail.withData} onChange={(e) => open(detail.run, e.target.checked)} /><span /></span></label>
            </div>
            {detail.run.error_message && <div className="alert alert-err">{detail.run.error_message}</div>}
            <div style={{ border: '1px solid var(--line)', borderRadius: 10, maxHeight: '55vh', overflow: 'auto' }}><NodeLogList logs={detail.logs} /></div>
            <p className="hint" style={{ marginTop: 8 }}>Workflow data (emails, API responses…) stays hidden unless you switch it on.</p>
          </div>
        </div>
      )}
      {toast}
    </>
  );
}
