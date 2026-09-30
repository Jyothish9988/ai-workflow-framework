import { useEffect, useState } from 'react';
import { LayoutDashboard, Users, Activity, Package, Workflow, PlayCircle, AlertTriangle, ShieldCheck } from 'lucide-react';
import { adminAPI, errMsg } from '../../utils/api';
import { PageHeader, Spinner, useToast } from '../../components/ui';
import AdminUsers from './AdminUsers';
import AdminRuns from './AdminRuns';
import AdminPackages from './AdminPackages';
import '../../styles/admin.css';

const TABS = [['overview', 'Overview', LayoutDashboard], ['users', 'Users', Users], ['runs', 'Run history', Activity], ['packages', 'Packages', Package]];

function Overview() {
  const [s, setS] = useState(null);
  const [toast, notify] = useToast();
  useEffect(() => { adminAPI.stats().then((r) => setS(r.data)).catch((e) => notify(errMsg(e), 'error')); }, []); // eslint-disable-line
  if (!s) return <Spinner />;
  const cards = [
    ['Users', s.users, Users, '#2d7ff9'], ['Active users', s.active_users, Users, '#10ac84'], ['Admins', s.admins, ShieldCheck, '#7c5cfc'],
    ['Workflows', s.workflows, Workflow, '#f0932b'], ['Running now', s.running_now, PlayCircle, '#2d7ff9'],
    ['Runs (24h)', s.runs_24h, Activity, '#7c5cfc'], ['Failed (24h)', s.failed_24h, AlertTriangle, '#ee5253'], ['Packages', s.packages, Package, '#64748b'],
  ];
  return (
    <div className="stat-grid-4">
      {cards.map(([label, value, I, c]) => (
        <div className="card stat" key={label}><span className="stat-ico" style={{ background: `${c}18`, color: c }}><I size={20} /></span><div><small>{label}</small><b>{value}</b></div></div>
      ))}
      {toast}
    </div>
  );
}

export default function AdminPage() {
  const [tab, setTab] = useState('overview');
  const [runUser, setRunUser] = useState(null);      // "View runs" on a user jumps to the run history filtered by that user
  return (
    <div className="page">
      <PageHeader title="Administration" subtitle="Manage users, monitor runs and publish node packages" />
      <div className="tabs page-tabs">
        {TABS.map(([id, label, I]) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => { setTab(id); if (id !== 'runs') setRunUser(null); }}><I size={15} />{label}</button>)}
      </div>
      {tab === 'overview' && <Overview />}
      {tab === 'users' && <AdminUsers onViewRuns={(u) => { setRunUser(u.id); setTab('runs'); }} />}
      {tab === 'runs' && <AdminRuns initialUser={runUser} />}
      {tab === 'packages' && <AdminPackages />}
    </div>
  );
}
