import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, Trash2, Copy, Play, Workflow as WfIcon } from 'lucide-react';
import { workflowAPI, executionAPI, errMsg } from '../utils/api';
import { PageHeader, Spinner, Empty, useToast, timeAgo } from '../components/ui';
import { getDef } from './workflow/nodeRegistry';

export default function Workflows() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [toast, notify] = useToast();

  const load = async () => {
    try { setItems((await workflowAPI.getAll()).data || []); }
    catch (e) { notify(errMsg(e, 'Failed to load workflows'), 'error'); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line

  const create = async () => {
    try { const { data } = await workflowAPI.create({ name: 'My workflow', description: '' }); navigate(`/workflow/${data.id}`); }
    catch (e) { notify(errMsg(e, 'Failed to create workflow'), 'error'); }
  };
  const remove = async (w) => {
    if (!window.confirm(`Delete "${w.name}"?`)) return;
    try { await workflowAPI.delete(w.id); setItems((x) => x.filter((i) => i.id !== w.id)); notify('Workflow deleted'); }
    catch (e) { notify(errMsg(e), 'error'); }
  };
  const duplicate = async (w) => {
    try {
      const { data } = await workflowAPI.create({ name: `${w.name} (copy)`, description: w.description || '' });
      const j = w.workflow_json || {};
      if (j.nodes?.length) await workflowAPI.save(data.id, j.nodes, j.edges || []);
      notify('Workflow duplicated'); load();
    } catch (e) { notify(errMsg(e), 'error'); }
  };
  const run = async (w) => {
    try { await executionAPI.execute(w.id); notify(`"${w.name}" executed`); } catch (e) { notify(errMsg(e, 'Execution failed'), 'error'); }
  };

  const list = useMemo(() => items.filter((w) => `${w.name} ${w.description || ''}`.toLowerCase().includes(q.toLowerCase())), [items, q]);

  return (
    <div className="page">
      <PageHeader title="Workflows" subtitle={`${items.length} workflow${items.length === 1 ? '' : 's'}`}>
        <div className="search"><Search size={15} /><input placeholder="Search workflows…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <button className="btn btn-primary" onClick={create}><Plus size={16} />Create workflow</button>
      </PageHeader>
      {loading ? <Spinner /> : list.length === 0 ? (
        <Empty icon={WfIcon} title={q ? 'No workflows match' : 'No workflows yet'} text="Create your first workflow to start automating." action={!q && <button className="btn btn-primary" onClick={create}><Plus size={16} />Create workflow</button>} />
      ) : (
        <div className="cards">
          {list.map((w) => {
            const nodes = w.workflow_json?.nodes || [];
            return (
              <article key={w.id} className="card wf-card" onClick={() => navigate(`/workflow/${w.id}`)}>
                <h3>{w.name}</h3>
                <p className="muted clamp">{w.description || 'No description'}</p>
                <div className="chips">
                  {nodes.slice(0, 6).map((n) => { const d = getDef(n.type); const I = d.icon; return <span key={n.id} className="chip-ico" style={{ background: d.color }} title={d.label}><I size={13} /></span>; })}
                  {nodes.length > 6 && <span className="muted">+{nodes.length - 6}</span>}
                  {!nodes.length && <span className="muted">Empty canvas</span>}
                </div>
                <footer onClick={(e) => e.stopPropagation()}>
                  <span className="muted">Updated {timeAgo(w.updated_at || w.created_at)}</span>
                  <span className="grow" />
                  <button className="icon-btn" title="Execute" onClick={() => run(w)}><Play size={15} /></button>
                  <button className="icon-btn" title="Duplicate" onClick={() => duplicate(w)}><Copy size={15} /></button>
                  <button className="icon-btn danger" title="Delete" onClick={() => remove(w)}><Trash2 size={15} /></button>
                </footer>
              </article>
            );
          })}
        </div>
      )}
      {toast}
    </div>
  );
}
