import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import ProtectedRoute from './components/ProtectedRoute';
import Home from './pages/Home';
import Login from './pages/auth/Login';
import Register from './pages/auth/Register';
import Dashboard from './pages/Dashboard';
import Workflows from './pages/Workflows';
import WorkflowEditor from './pages/workflow/WorkflowEditor';
import Executions from './pages/Executions';
import ExecutionDetail from './pages/ExecutionDetail';
import Scheduler from './pages/Scheduler';
import Settings from './pages/Settings';
import LLMSettings from './pages/settings/LLMSettings';
import AppIntegration from './pages/settings/AppIntegration';

/**
 * Root application component
 * Handles routing and protected routes
 */
function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(
    !!localStorage.getItem('authToken')
  );

  // Monitor auth status changes
  useEffect(() => {
    const handleAuthChange = () => {
      setIsAuthenticated(!!localStorage.getItem('authToken'));
    };

    // Same-tab login/logout — dispatched manually by setAuthToken() in api.js
    window.addEventListener('auth-change', handleAuthChange);

    // Other-tab login/logout — fired natively by the browser
    window.addEventListener('storage', handleAuthChange);

    return () => {
      window.removeEventListener('auth-change', handleAuthChange);
      window.removeEventListener('storage', handleAuthChange);
    };
  }, []);

  return (
    <Router>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Protected routes - require authentication */}
        <Route element={<ProtectedRoute isAuthenticated={isAuthenticated} />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/workflows" element={<Workflows />} />
          <Route path="/workflow/:id" element={<WorkflowEditor />} />
          <Route path="/executions" element={<Executions />} />
          <Route path="/executions/:workflowId/:id" element={<ExecutionDetail />} />
          <Route path="/scheduler" element={<Scheduler />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/settings/llm" element={<LLMSettings />} />
          <Route path="/settings/app-integration" element={<AppIntegration />} />
        </Route>

        {/* Catch-all - redirect to home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;