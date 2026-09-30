import { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle2, XCircle, Loader2, Trash2, Square, X, RefreshCw } from 'lucide-react';
import { StatusBadge, fmtDuration, timeAgo, pick } from '../../components/ui';

export const nodeLogInfo = (l) => ({
  nodeId: l.node_id,
  name: l.node_label || l.node_type || l.node_id,
  status: String(l.status || 'success').toLowerCase(),
  duration: l.duration_ms,
  message: l.log_message,
  branch: l.branch_taken,
  input: l.input_context,
  output: l.context_diff && Object.keys(l.context_diff).length ? l.context_diff : l.output_context,
  error: l.error_message,
});

export function NodeLogList({ logs }) {
  const [open, setOpen] = useState({});
  if (!logs?.length) return <p className="muted pad">No node logs available.</p>;
  return (
    <div className="log-list">
      {logs.map((l, i) => {
        const x = nodeLogInfo(l);
        const isOpen = open[i];
        return (
          <div key={i} className="log-item">
            <button className="log-row" onClick={() => setOpen({ ...open, [i]: !isOpen })}>
              {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              {['failed', 'error', 'cancelled'].includes(x.status) ? <XCircle size={15} className="c-err" /> : x.status === 'running' ? <Loader2 size={15} className="spin" /> : <CheckCircle2 size={15} className="c-ok" />}
              <b>{String(x.name)}</b>{x.message && <span className="muted clip">{x.message}</span>}
              <span className="grow" />
              <span className="muted">{fmtDuration(x.duration)}</span>
            </button>
            {isOpen && (
              <div className="log-detail">
                {x.error && <pre className="json err">{typeof x.error === 'string' ? x.error : JSON.stringify(x.error, null, 2)}</pre>}
                {x.input != null && <><small>Input context</small><pre className="json">{JSON.stringify(x.input, null, 2)}</pre></>}
                {x.output != null && <><small>Changes</small><pre className="json">{JSON.stringify(x.output, null, 2)}</pre></>}
                {x.input == null && x.output == null && !x.error && <pre className="json">{JSON.stringify(l, null, 2)}</pre>}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function ExecutionPanel({ tab, setTab, logs, running, history, onSelect, onRefresh, onCancel, onDelete, onClose, selectedId }) {
  return (
    <section className="exec-panel">
      <div className="exec-head">
        <div className="tabs inline">
          <button className={tab === 'run' ? 'active' : ''} onClick={() => setTab('run')}>Logs {running && <Loader2 size={12} className="spin" />}</button>
          <button className={tab === 'history' ? 'active' : ''} onClick={() => setTab('history')}>Executions</button>
        </div>
        <span className="grow" />
        {tab === 'history' && <button className="icon-btn" title="Refresh" onClick={onRefresh}><RefreshCw size={15} /></button>}
        <button className="icon-btn" onClick={onClose}><X size={16} /></button>
      </div>
      <div className="exec-body">
        {tab === 'run' && (running ? <p className="muted pad"><Loader2 size={14} className="spin" /> Running workflow…</p> : <NodeLogList logs={logs} />)}
        {tab === 'history' && (
          history.length === 0 ? <p className="muted pad">No executions yet.</p> :
          history.map((e) => (
            <div key={e.id} className={`hist-row ${selectedId === e.id ? 'active' : ''}`} onClick={() => onSelect(e)}>
              <StatusBadge status={e.status} />
              <span>{timeAgo(e.created_at)}</span>
              <span className="muted">{fmtDuration(e.duration_ms)}</span>
              <span className="grow" />
              {['running', 'pending', 'queued'].includes(String(e.status).toLowerCase()) && (
                <button className="icon-btn" title="Cancel" onClick={(ev) => { ev.stopPropagation(); onCancel(e); }}><Square size={14} /></button>
              )}
              <button className="icon-btn" title="Delete" onClick={(ev) => { ev.stopPropagation(); onDelete(e); }}><Trash2 size={14} /></button>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
