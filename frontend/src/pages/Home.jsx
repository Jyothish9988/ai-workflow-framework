import { Navigate } from 'react-router-dom';
export default function Home() {
  return <Navigate to={localStorage.getItem('authToken') ? '/dashboard' : '/login'} replace />;
}
