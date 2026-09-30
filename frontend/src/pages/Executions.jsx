import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trash2, RefreshCw, Square, Activity } from 'lucide-react';
import { workflowAPI, executionAPI, fetchAllExecutions, errMsg } from '../utils/api';
import { PageHeader, Spinner, Empty, StatusBadge, useToast, fmtDuration, timeAgo } from '../components/ui';

export default function Executions() {
  const navigate = useNavigate();
  const [execs, setExecs] = useState([]);
  const [wfs, setWfs] = useState([]);
  const [wf, setWf] = useState('all');
  const [status, setStatus] = useState('all');
  const [loading, setLoading] = useState(true);
  const [toast, notify] = useToast();

  const load = async () => {
    setLoading(true);
    try { const list = (await workflowAPI.getAll()).data || []; setWfs(list); setExecs(await fetchAllExecutions(list, 50)); }
    catch (e) { notify(errMsg(e, 'Failed to load executions'), 'error'); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line

  const rows = useMemo(() => execs.filter((e) => (wf === 'all' || e.workflow_id === wf) && (status === 'all' || String(e.status).toLowerCase() === status)), [execs, wf, status]);

  const remove = async (e, ev) => { ev.stopPropagation(); try { await executionAPI.remove(e.workflow_id, e.id); setExecs((x) => x.filter((i) => i.id !== e.id)); } catch (er) { notify(errMsg(er), 'error'); } };
  const cancel = async (e, ev) => { ev.stopPropagation(); try { await executionAPI.cancel(e.workflow_id, e.id); notify('Cancelled'); load(); } catch (er) { notify(errMsg(er), 'error'); } };

  return (
    <div className="page">
      <PageHeader title="Executions" subtitle="History of every workflow run">
        <select className="input w-auto" value={wf} onChange={(e) => setWf(e.target.value)}><option value="all">All workflows</option>{wfs.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
        <select className="input w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>{['all', 'success', 'failed', 'partial', 'running'].map((s) => <option key={s}>{s}</option>)}</select>
        <button className="btn btn-outline" onClick={load}><RefreshCw size={15} />Refresh</button>
      </PageHeader>
      {loading ? <Spinner /> : rows.length === 0 ? <Empty icon={Activity} title="No executions" text="Runs will appear here once a workflow is executed." /> : (
        <div className="card flush">
          <table className="table"><thead><tr><th>Workflow</th><th>Status</th><th>Started</th><th>Duration</th><th /></tr></thead>
            <tbody>{rows.map((e) => (
              <tr key={e.id} onClick={() => navigate(`/executions/${e.workflow_id}/${e.id}`)}>
                <td><b>{e.workflow_name}</b><div className="muted mono-sm">{String(e.id).slice(0, 8)}</div></td>
                <td><StatusBadge status={e.status} /></td><td>{timeAgo(e.created_at)}</td><td>{fmtDuration(e.duration_ms)}</td>
                <td className="right">
                  {['running', 'pending', 'queued'].includes(String(e.status).toLowerCase()) && <button className="icon-btn" title="Cancel" onClick={(ev) => cancel(e, ev)}><Square size={14} /></button>}
                  <button className="icon-btn danger" title="Delete" onClick={(ev) => remove(e, ev)}><Trash2 size={15} /></button>
                </td>
              </tr>))}</tbody></table>
        </div>
      )}
      {toast}
    </div>
  );
}
