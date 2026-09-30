import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Workflow, Activity, Clock, Settings, LogOut, Zap, Bot } from 'lucide-react';
import { authAPI, setAuthToken } from '../../utils/api';

const items = [
  { to: '/dashboard', label: 'Overview', icon: LayoutDashboard },
  { to: '/workflows', label: 'Workflows', icon: Workflow },
  { to: '/executions', label: 'Executions', icon: Activity },
  { to: '/scheduler', label: 'Schedules', icon: Clock },
  { to: '/settings/llm', label: 'LLM Connections', icon: Bot },
  { to: '/settings', label: 'Settings', icon: Settings, end: true },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem('user') || 'null');
  const logout = async () => {
    try { await authAPI.logout(); } catch { /* token may already be invalid */ }
    setAuthToken(null); localStorage.removeItem('user'); navigate('/login');
  };
  return (
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Zap size={18} /></span><span className="nav-label">AWF</span></div>
      <nav>
        {items.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} title={label} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Icon size={19} /><span className="nav-label">{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-foot">
        {user?.username && <div className="user-chip nav-label">{user.username}</div>}
        <button className="nav-link" onClick={logout} title="Log out"><LogOut size={19} /><span className="nav-label">Log out</span></button>
      </div>
    </aside>
  );
}
