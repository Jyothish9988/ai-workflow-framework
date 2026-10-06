import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Activity,
  Package,
  LogOut,
  ShieldCheck,
} from 'lucide-react';
import { authAPI, setAuthToken } from '../../utils/api';

const items = [
  { to: '/admin?tab=overview', label: 'Overview', icon: LayoutDashboard },
  { to: '/admin?tab=users', label: 'Users', icon: Users },
  { to: '/admin?tab=runs', label: 'Run History', icon: Activity },
  { to: '/admin?tab=packages', label: 'Packages', icon: Package },
];

export default function AdminSidebar() {
  const navigate = useNavigate();

  const user = JSON.parse(localStorage.getItem('user') || 'null');

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch {}

    setAuthToken(null);
    localStorage.removeItem('user');
    navigate('/login');
  };

  return (
    <aside className="sidebar admin-sidebar">
      <div className="brand">
        <span className="brand-mark">
          <ShieldCheck size={18} />
        </span>
        <span className="nav-label">ADMIN</span>
      </div>

      <div className="admin-badge">
        <ShieldCheck size={14} />
        <span className="nav-label">Administrator</span>
      </div>

      <nav>
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={label}
            to={to}
            title={label}
            className="nav-link"
          >
            <Icon size={19} />
            <span className="nav-label">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-foot">
        {user?.username && (
          <div className="user-chip nav-label">
            {user.username}
          </div>
        )}

        <button
          className="nav-link"
          onClick={logout}
          title="Log out"
        >
          <LogOut size={19} />
          <span className="nav-label">Log out</span>
        </button>
      </div>
    </aside>
  );
}