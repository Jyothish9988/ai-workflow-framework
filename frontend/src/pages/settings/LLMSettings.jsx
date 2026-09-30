import { useState, useEffect, useRef } from 'react';
import { Plus, Trash2, Zap, X, Loader2, Download, CheckCircle2, Star, Bot } from 'lucide-react';
import { llmAPI, errMsg } from '../../utils/api';
import { PageHeader, Spinner, Empty, useToast, timeAgo } from '../../components/ui';

const PROVIDERS = { openai: { model: 'gpt-4o-mini', url: '' }, anthropic: { model: 'claude-sonnet-4-5', url: '' }, groq: { model: 'llama-3.3-70b-versatile', url: '' }, ollama: { model: 'llama3.2', url: 'http://host.docker.internal:11434' } };
const blank = { name: '', provider: 'openai', api_key: '', base_url: '', model: PROVIDERS.openai.model, is_default: false };

export default function LLMSettings() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  const [testing, setTesting] = useState(false);
  const [testRes, setTestRes] = useState(null);
  const [pull, setPull] = useState(null); // { model, pct, status }
  const es = useRef(null);
  const [toast, notify] = useToast();

  const load = async () => { try { setRows((await llmAPI.list()).data || []); } catch (e) { notify(errMsg(e, 'Failed to load connections'), 'error'); } finally { setLoading(false); } };
  useEffect(() => { load(); return () => es.current?.close(); }, []); // eslint-disable-line

  const setProvider = (p) => setForm({ ...form, provider: p, model: PROVIDERS[p].model, base_url: PROVIDERS[p].url });
  const body = () => ({ ...form, api_key: form.api_key || '', base_url: form.base_url || null });

  const test = async () => {
    setTesting(true); setTestRes(null);
    try { setTestRes((await llmAPI.test(body())).data); } catch (e) { setTestRes({ success: false, message: errMsg(e) }); } finally { setTesting(false); }
  };
  const create = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return notify('Give the connection a name', 'error');
    try { await llmAPI.create(body()); notify('Connection saved'); setOpen(false); setForm(blank); setTestRes(null); load(); }
    catch (er) { notify(errMsg(er, 'Failed to save'), 'error'); }
  };
  const remove = async (c) => { if (!window.confirm(`Delete "${c.name}"?`)) return; try { await llmAPI.remove(c.id); setRows((r) => r.filter((x) => x.id !== c.id)); } catch (e) { notify(errMsg(e), 'error'); } };

  const pullModel = (model) => {
    if (!model) return;
    es.current?.close();
    setPull({ model, pct: 0, status: 'starting' });
    const src = new EventSource(llmAPI.pullUrl(model)); es.current = src;
    src.onmessage = (m) => {
      try {
        const d = JSON.parse(m.data);
        setPull({ model, status: d.status, pct: d.total ? Math.round((d.completed / d.total) * 100) : 0 });
        if (d.status === 'success') { src.close(); notify(`${model} is ready`); }
      } catch { /* ignore partial line */ }
    };
    src.onerror = () => { src.close(); setPull((p) => p && (p.status === 'success' ? p : { ...p, status: 'stream closed' })); };
  };

  return (
    <div className="page">
      <PageHeader title="LLM connections" subtitle="Credentials used by AI nodes in your workflows">
        <button className="btn btn-primary" onClick={() => { setForm(blank); setTestRes(null); setOpen(true); }}><Plus size={16} />Add connection</button>
      </PageHeader>
      {loading ? <Spinner /> : rows.length === 0 ? <Empty icon={Bot} title="No connections" text="Add a provider to use LLM nodes." /> : (
        <div className="cards">{rows.map((c) => (
          <article key={c.id} className="card">
            <div className="card-title-row"><h3>{c.name}</h3>{c.is_default && <span className="badge badge-ok"><Star size={11} />default</span>}</div>
            <p className="muted"><b>{c.provider}</b> · {c.model}</p>
            {c.base_url && <p className="muted mono-sm">{c.base_url}</p>}
            <footer><span className="muted">{c.has_key ? 'API key stored' : 'No key'} · {timeAgo(c.created_at)}</span><span className="grow" />
              {c.provider === 'ollama' && <button className="icon-btn" title="Pull model" onClick={() => pullModel(c.model)}><Download size={15} /></button>}
              <button className="icon-btn danger" onClick={() => remove(c)}><Trash2 size={15} /></button></footer>
          </article>))}</div>
      )}
      {pull && (
        <div className="card pull"><div className="card-title-row"><b>Pulling {pull.model}</b><button className="icon-btn" onClick={() => { es.current?.close(); setPull(null); }}><X size={14} /></button></div>
          <div className="progress"><div style={{ width: `${pull.pct}%` }} /></div><small className="muted">{pull.status} {pull.pct ? `· ${pull.pct}%` : ''}</small></div>
      )}
      {open && (
        <div className="modal-bg" onClick={() => setOpen(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={create}>
            <div className="modal-head"><h3>Add LLM connection</h3><button type="button" className="icon-btn" onClick={() => setOpen(false)}><X size={16} /></button></div>
            <div className="field"><label>Name</label><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="My OpenAI" autoFocus /></div>
            <div className="field"><label>Provider</label><select className="input" value={form.provider} onChange={(e) => setProvider(e.target.value)}>{Object.keys(PROVIDERS).map((p) => <option key={p}>{p}</option>)}</select></div>
            <div className="field"><label>Model</label><input className="input" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} /></div>
            {form.provider !== 'ollama' && <div className="field"><label>API key</label><input className="input" type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} autoComplete="off" /></div>}
            <div className="field"><label>Base URL <span className="muted">(optional)</span></label><input className="input" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} /></div>
            <div className="field row"><label>Use as default</label><label className="switch"><input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} /><span /></label></div>
            {testRes && <div className={`alert ${testRes.success ? 'alert-ok' : 'alert-err'}`}>{testRes.success && <CheckCircle2 size={15} />}{testRes.message}</div>}
            <div className="modal-foot">
              <button type="button" className="btn btn-outline" onClick={test} disabled={testing}>{testing ? <Loader2 size={15} className="spin" /> : <Zap size={15} />}Test</button>
              <span className="grow" /><button className="btn btn-primary">Save</button>
            </div>
          </form>
        </div>
      )}
      {toast}
    </div>
  );
}
