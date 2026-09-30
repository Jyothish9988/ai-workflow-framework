import { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Workflow, Activity, CheckCircle2, XCircle, Timer, Plus } from 'lucide-react';
import { workflowAPI, executionAPI, fetchAllExecutions, errMsg } from '../utils/api';
import { PageHeader, Spinner, StatusBadge, useToast, fmtDuration, timeAgo } from '../components/ui';

export default function Dashboard() {
  const navigate = useNavigate();
  const [wfs, setWfs] = useState([]);
  const [execs, setExecs] = useState([]);
  const [stats, setStats] = useState({ total: 0, success: 0, failed: 0, avg: null });
  const [loading, setLoading] = useState(true);
  const [toast, notify] = useToast();

  useEffect(() => {
    (async () => {
      try {
        const list = (await workflowAPI.getAll()).data || [];
        setWfs(list);
        const [all, per] = await Promise.all([
          fetchAllExecutions(list, 50),
          Promise.all(list.map((w) => executionAPI.stats(w.id).then((r) => r.data).catch(() => null))),
        ]);
        setExecs(all);
        const ok = per.filter(Boolean);
        const total = ok.reduce((a, s) => a + s.total, 0);
        const durs = ok.filter((s) => s.avg_duration_ms).map((s) => ({ v: s.avg_duration_ms, w: s.total }));
        setStats({
          total, success: ok.reduce((a, s) => a + s.success, 0), failed: ok.reduce((a, s) => a + s.failed, 0),
          avg: durs.length ? durs.reduce((a, d) => a + d.v * d.w, 0) / durs.reduce((a, d) => a + d.w, 0) : null,
        });
      } catch (e) { notify(errMsg(e, 'Failed to load dashboard'), 'error'); } finally { setLoading(false); }
    })();
  }, []); // eslint-disable-line

  // executions per day, last 14 days
  const chart = useMemo(() => {
    const days = Array.from({ length: 14 }, (_, i) => { const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - (13 - i)); return { d, ok: 0, bad: 0 }; });
    execs.forEach((e) => {
      const t = new Date(e.created_at); t.setHours(0, 0, 0, 0);
      const day = days.find((x) => x.d.getTime() === t.getTime());
      if (day) (String(e.status).toLowerCase() === 'success' ? (day.ok++) : (day.bad++));
    });
    return { days, max: Math.max(1, ...days.map((x) => x.ok + x.bad)) };
  }, [execs]);

  if (loading) return <Spinner />;
  const rate = stats.total ? Math.round((stats.success / stats.total) * 100) : 0;
  const cards = [
    { l: 'Workflows', v: wfs.length, i: Workflow, c: '#2d7ff9' },
    { l: 'Total executions', v: stats.total, i: Activity, c: '#7c5cfc' },
    { l: 'Success rate', v: `${rate}%`, i: CheckCircle2, c: '#10ac84' },
    { l: 'Failed', v: stats.failed, i: XCircle, c: '#ee5253' },
    { l: 'Avg duration', v: fmtDuration(stats.avg), i: Timer, c: '#f0932b' },
  ];

  return (
    <div className="page">
      <PageHeader title="Overview" subtitle="Monitor your automations at a glance">
        <button className="btn btn-primary" onClick={() => navigate('/workflows')}><Plus size={16} />New workflow</button>
      </PageHeader>
      <div className="stats">
        {cards.map(({ l, v, i: I, c }) => (
          <div className="card stat" key={l}><span className="stat-ico" style={{ background: `${c}18`, color: c }}><I size={20} /></span><div><small>{l}</small><b>{v}</b></div></div>
        ))}
      </div>
      <div className="grid-2">
        <section className="card">
          <h3 className="card-title">Executions — last 14 days</h3>
          <div className="bars">
            {chart.days.map((x, i) => (
              <div key={i} className="bar-col" title={`${x.d.toLocaleDateString()}: ${x.ok} ok, ${x.bad} failed`}>
                <div className="bar-stack"><div className="bar bad" style={{ height: `${(x.bad / chart.max) * 100}%` }} /><div className="bar ok" style={{ height: `${(x.ok / chart.max) * 100}%` }} /></div>
                <small>{x.d.getDate()}</small>
              </div>
            ))}
          </div>
          <div className="legend"><span className="dot ok" />Success<span className="dot bad" />Failed / other</div>
        </section>
        <section className="card">
          <h3 className="card-title">Recent workflows</h3>
          {wfs.length === 0 && <p className="muted">No workflows yet.</p>}
          {wfs.slice(0, 6).map((w) => (
            <Link key={w.id} to={`/workflow/${w.id}`} className="list-row"><Workflow size={15} /><span>{w.name}</span><span className="grow" /><small className="muted">{timeAgo(w.updated_at || w.created_at)}</small></Link>
          ))}
        </section>
      </div>
      <section className="card">
        <div className="card-title-row"><h3 className="card-title">Recent executions</h3><Link to="/executions">View all</Link></div>
        {execs.length === 0 ? <p className="muted">No executions yet. Open a workflow and press Execute.</p> : (
          <table className="table"><thead><tr><th>Workflow</th><th>Status</th><th>Started</th><th>Duration</th></tr></thead>
            <tbody>{execs.slice(0, 8).map((e) => (
              <tr key={e.id} onClick={() => navigate(`/executions/${e.workflow_id}/${e.id}`)}><td>{e.workflow_name}</td><td><StatusBadge status={e.status} /></td><td>{timeAgo(e.created_at)}</td><td>{fmtDuration(e.duration_ms)}</td></tr>
            ))}</tbody></table>
        )}
      </section>
      {toast}
    </div>
  );
}
