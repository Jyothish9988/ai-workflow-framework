import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Trash2, Square } from 'lucide-react';
import { executionAPI, workflowAPI, errMsg } from '../utils/api';
import { PageHeader, Spinner, StatusBadge, useToast, fmtDuration, pick } from '../components/ui';
import { NodeLogList } from './workflow/ExecutionPanel';

export default function ExecutionDetail() {
  const { workflowId, id } = useParams();
  const navigate = useNavigate();
  const [ex, setEx] = useState(null);
  const [logs, setLogs] = useState([]);
  const [wfName, setWfName] = useState('');
  const [loading, setLoading] = useState(true);
  const [toast, notify] = useToast();

  useEffect(() => {
    (async () => {
      try {
        const { data } = await executionAPI.get(workflowId, id);
        const e = data.data || data; setEx(e);
        const n = await executionAPI.nodes(workflowId, id).catch(() => null);
        setLogs(n?.data?.data || e.node_logs || []);
        workflowAPI.getById(workflowId).then((r) => setWfName(r.data.name)).catch(() => {});
      } catch (er) { notify(errMsg(er, 'Failed to load execution'), 'error'); } finally { setLoading(false); }
    })();
  }, [workflowId, id]); // eslint-disable-line

  const remove = async () => { if (!window.confirm('Delete this execution?')) return; try { await executionAPI.remove(workflowId, id); navigate('/executions'); } catch (e) { notify(errMsg(e), 'error'); } };
  const cancel = async () => { try { await executionAPI.cancel(workflowId, id); notify('Execution cancelled'); } catch (e) { notify(errMsg(e), 'error'); } };

  if (loading) return <Spinner />;
  if (!ex) return <div className="page"><p className="muted">Execution not found.</p>{toast}</div>;
  const running = ['running', 'pending', 'queued'].includes(String(ex.status).toLowerCase());
  const err = pick(ex, ['error_message', 'error']);

  return (
    <div className="page">
      <Link to="/executions" className="back"><ArrowLeft size={15} />Executions</Link>
      <PageHeader title={wfName || 'Execution'} subtitle={<span className="mono-sm">{id}</span>}>
        {running && <button className="btn btn-outline" onClick={cancel}><Square size={14} />Cancel</button>}
        <Link to={`/workflow/${workflowId}`} className="btn btn-outline">Open workflow</Link>
        <button className="btn btn-danger" onClick={remove}><Trash2 size={15} />Delete</button>
      </PageHeader>
      <div className="stats">
        <div className="card stat"><div><small>Status</small><StatusBadge status={ex.status} /></div></div>
        <div className="card stat"><div><small>Started</small><b className="sm">{ex.created_at ? new Date(ex.created_at).toLocaleString() : '—'}</b></div></div>
        <div className="card stat"><div><small>Duration</small><b className="sm">{fmtDuration(ex.duration_ms)}</b></div></div>
        <div className="card stat"><div><small>Nodes run</small><b className="sm">{logs.length}</b></div></div>
      </div>
      {err && <div className="alert alert-err">{typeof err === 'string' ? err : JSON.stringify(err)}</div>}
      <section className="card flush"><h3 className="card-title pad">Node execution</h3><NodeLogList logs={logs} /></section>
      {toast}
    </div>
  );
}
