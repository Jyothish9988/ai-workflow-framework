import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Zap, AlertCircle, Loader2 } from 'lucide-react';
import { authAPI, setAuthToken, errMsg } from '../../utils/api';

export default function Login() {
  const navigate = useNavigate();
  const [f, setF] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!f.email || !f.password) return setError('Please fill in all fields');
    setLoading(true); setError('');
    /*
    try {
      const { data } = await authAPI.login(f.email.trim(), f.password);
      if (!data.access_token) throw new Error('No access token returned');
      localStorage.setItem('user', JSON.stringify(data.user || { email: f.email.trim(), username: f.email.split('@')[0] }));
      setAuthToken(data.access_token);
      navigate('/dashboard');
    } catch (err) { setError(errMsg(err, 'Login failed')); } finally { setLoading(false); }
    */
    try {
    const { data } = await authAPI.login(f.email.trim(), f.password);

    if (!data.access_token) {
      throw new Error('No access token returned');
    }

    setAuthToken(data.access_token);

    localStorage.setItem(
      'user',
      JSON.stringify(data.user)
    );

    if (data.user?.role === 'admin') {
      navigate('/admin');
    } else {
      navigate('/dashboard');
    }
  } catch (err) {
    setError(errMsg(err, 'Login failed'));
  } finally {
    setLoading(false);
  }

  };

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <span className="brand-mark lg"><Zap size={24} /></span>
        <h1>Welcome back</h1><p className="muted">Sign in to AI Workflow Framework</p>
        {error && <div className="alert alert-err"><AlertCircle size={15} />{error}</div>}
        <div className="field"><label>Email</label><input className="input" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} autoFocus /></div>
        <div className="field"><label>Password</label><input className="input" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></div>
        <button className="btn btn-primary btn-block" disabled={loading}>{loading && <Loader2 size={15} className="spin" />}Sign in</button>
        <p className="muted center">No account? <Link to="/register">Create one</Link></p>
      </form>
    </div>
  );
}
