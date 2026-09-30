import { Link } from 'react-router-dom';
import { Bot, Clock, User, Plug, ChevronRight } from 'lucide-react';
import { PageHeader } from '../components/ui';

export default function Settings() {
  const user = JSON.parse(localStorage.getItem('user') || 'null');
  const items = [
    { to: '/settings/llm', icon: Bot, t: 'LLM connections', d: 'OpenAI, Anthropic, Groq and local Ollama models' },
    { to: '/scheduler', icon: Clock, t: 'Schedules', d: 'Manage cron triggers for your workflows' },
    { to: '/settings/app-integration', icon: Plug, t: 'App integrations', d: 'Add, edit and test credentials for your connected apps' },
  ];
  return (
    <div className="page narrow">
      <PageHeader title="Settings" subtitle="Configure your workspace" />
      <div className="card"><div className="list-row static"><User size={18} /><div><b>{user?.username || 'Account'}</b><div className="muted">{user?.email || 'Signed in'}</div></div></div></div>
      <div className="card flush">
        {items.map(({ to, icon: I, t, d }) => (
          <Link key={to} to={to} className="list-row big"><I size={20} /><div><b>{t}</b><div className="muted">{d}</div></div><span className="grow" /><ChevronRight size={16} /></Link>
        ))}
      </div>
    </div>
  );
}