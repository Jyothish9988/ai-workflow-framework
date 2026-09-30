import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Zap, AlertCircle, Loader2 } from 'lucide-react';
import { authAPI, errMsg } from '../../utils/api';

export default function Register() {
  const navigate = useNavigate();
  const [f, setF] = useState({ username: '', email: '', password: '', confirm: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (f.username.trim().length < 3) return setError('Username must be at least 3 characters');
    if (!f.email.trim()) return setError('Email is required');
    if (f.password.length < 6) return setError('Password must be at least 6 characters');
    if (f.password !== f.confirm) return setError('Passwords do not match');
    setLoading(true); setError('');
    try { await authAPI.register(f.username.trim(), f.email.trim(), f.password); navigate('/login'); }
    catch (err) { setError(errMsg(err, 'Registration failed')); } finally { setLoading(false); }
  };

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <span className="brand-mark lg"><Zap size={24} /></span>
        <h1>Create your account</h1><p className="muted">Start automating in minutes</p>
        {error && <div className="alert alert-err"><AlertCircle size={15} />{error}</div>}
        <div className="field"><label>Username</label><input className="input" value={f.username} onChange={set('username')} autoFocus /></div>
        <div className="field"><label>Email</label><input className="input" type="email" value={f.email} onChange={set('email')} /></div>
        <div className="field"><label>Password</label><input className="input" type="password" value={f.password} onChange={set('password')} /></div>
        <div className="field"><label>Confirm password</label><input className="input" type="password" value={f.confirm} onChange={set('confirm')} /></div>
        <button className="btn btn-primary btn-block" disabled={loading}>{loading && <Loader2 size={15} className="spin" />}Create account</button>
        <p className="muted center">Already registered? <Link to="/login">Sign in</Link></p>
      </form>
    </div>
  );
}
