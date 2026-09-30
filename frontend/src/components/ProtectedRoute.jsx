import { Navigate, Outlet, useLocation } from 'react-router-dom';
import Sidebar from './layout/Sidebar';
import AdminSidebar from './layout/AdminSidebar';

export default function ProtectedRoute({ isAuthenticated }) {
  const { pathname } = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const user = JSON.parse(
    localStorage.getItem('user') || 'null'
  );

  const isAdmin = user?.role === 'admin';
  const full = pathname.startsWith('/workflow/');

  return (
    <div className="shell">
      {isAdmin ? <AdminSidebar /> : <Sidebar />}

      <main className={full ? 'main main-full' : 'main'}>
        <Outlet />
      </main>
    </div>
  );
}