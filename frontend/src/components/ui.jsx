import { useState, useCallback, useRef } from 'react';
import { Loader2, CheckCircle2, XCircle, AlertCircle, Inbox } from 'lucide-react';

export const pick = (o, keys) => { for (const k of keys) if (o?.[k] !== undefined && o?.[k] !== null) return o[k]; return undefined; };

export const fmtDuration = (ms) => {
  if (ms === undefined || ms === null || ms === '') return '—';
  ms = Number(ms);
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
};

export const timeAgo = (d) => {
  if (!d) return '—';
  const s = Math.floor((Date.now() - new Date(d).getTime()) / 1000);
  if (s < 0 || Number.isNaN(s)) return new Date(d).toLocaleString();
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 604800) return `${Math.floor(s / 86400)}d ago`;
  return new Date(d).toLocaleDateString();
};

export const StatusBadge = ({ status }) => {
  const s = String(status || 'unknown').toLowerCase();
  const kind = ['success', 'completed'].includes(s) ? 'ok' : ['failed', 'error', 'cancelled'].includes(s) ? 'err' : ['running', 'pending', 'queued'].includes(s) ? 'run' : 'warn';
  const Icon = kind === 'ok' ? CheckCircle2 : kind === 'err' ? XCircle : kind === 'run' ? Loader2 : AlertCircle;
  return <span className={`badge badge-${kind}`}><Icon size={12} className={kind === 'run' ? 'spin' : ''} />{s}</span>;
};

export const Spinner = ({ label = 'Loading…' }) => (
  <div className="center-msg"><Loader2 className="spin" size={22} /><span>{label}</span></div>
);

export const Empty = ({ icon: Icon = Inbox, title, text, action }) => (
  <div className="empty"><Icon size={34} strokeWidth={1.5} /><h3>{title}</h3>{text && <p>{text}</p>}{action}</div>
);

export const PageHeader = ({ title, subtitle, children }) => (
  <header className="page-head"><div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div><div className="page-actions">{children}</div></header>
);

/** tiny toast hook: const [toast, notify] = useToast(); render {toast} */
export const useToast = () => {
  const [t, setT] = useState(null);
  const timer = useRef();
  const notify = useCallback((msg, type = 'success') => {
    setT({ msg, type }); clearTimeout(timer.current); timer.current = setTimeout(() => setT(null), 3500);
  }, []);
  const node = t && <div className={`toast toast-${t.type}`}>{t.type === 'error' ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}{t.msg}</div>;
  return [node, notify];
};
