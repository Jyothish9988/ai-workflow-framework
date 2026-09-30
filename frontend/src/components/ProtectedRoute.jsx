import { Navigate, Outlet, useLocation } from 'react-router-dom';
import Sidebar from './layout/Sidebar';

export default function ProtectedRoute({ isAuthenticated }) {
  const { pathname } = useLocation();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  const full = pathname.startsWith('/workflow/'); // editor is full-bleed
  return (
    <div className="shell">
      <Sidebar />
      <main className={full ? 'main main-full' : 'main'}><Outlet /></main>
    </div>
  );
}
