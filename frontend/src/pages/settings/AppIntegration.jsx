import { useEffect, useState, useCallback } from 'react';
import {
  Plug, Plus, Pencil, Trash2, CheckCircle2, XCircle, Loader2, X,
  Mail, Slack, Github, FileText, Globe, Eye, EyeOff, RefreshCw,
  Send, MessageCircle, MessageSquare, Users, Sheet, Calendar, HardDrive, FileSpreadsheet, Cloud,
} from 'lucide-react';
import { PageHeader } from '../../components/ui';
import { integrationAPI, errMsg } from '../../utils/api';
import '../../styles/appintegration.css';

/* ------------------------------------------------------------------ */
/* API layer - thin wrapper over the shared axios instance             */
/* ------------------------------------------------------------------ */
// Unwrap res.data and turn axios errors into plain Errors with a readable message
const call = (promise) =>
  promise.then((r) => r.data).catch((e) => { throw new Error(errMsg(e)); });

const api = {
  list: () => call(integrationAPI.list()),
  create: (body) => call(integrationAPI.create(body)),
  update: (id, body) => call(integrationAPI.update(id, body)),
  remove: (id) => call(integrationAPI.remove(id)),
  test: (id) => call(integrationAPI.test(id)),                 // test a saved connection
  testDraft: (body) => call(integrationAPI.testDraft(body)),   // test before saving
};

/* ------------------------------------------------------------------ */
/* App catalog - add new apps here, the form is generated from fields  */
/* ------------------------------------------------------------------ */
const GROUPS = ['Email', 'Messaging', 'Google Workspace', 'Microsoft 365', 'Other'];

// Shared field sets ---------------------------------------------------
const GOOGLE_MODE = {
  key: 'authMode', label: 'Authentication method', type: 'select', default: 'service_account',
  options: [
    { value: 'service_account', label: 'Service account (JSON key)' },
    { value: 'oauth', label: 'OAuth client + refresh token' },
  ],
};
const GOOGLE_SA = [
  {
    key: 'serviceAccountJson', label: 'Service account JSON', type: 'textarea', secret: true,
    showIf: { authMode: 'service_account' }, placeholder: '{ "type": "service_account", ... }',
    hint: 'Share the file / calendar / sheet with the service account email.',
  },
];
const GOOGLE_OAUTH = [
  { key: 'clientId', label: 'OAuth client ID', showIf: { authMode: 'oauth' } },
  { key: 'clientSecret', label: 'OAuth client secret', secret: true, showIf: { authMode: 'oauth' } },
  { key: 'refreshToken', label: 'Refresh token', secret: true, showIf: { authMode: 'oauth' } },
];
const googleFields = (extra = []) => [GOOGLE_MODE, ...GOOGLE_SA, ...GOOGLE_OAUTH, ...extra];

const MS_AUTH = [
  { key: 'tenantId', label: 'Tenant (directory) ID' },
  { key: 'clientId', label: 'Application (client) ID' },
  { key: 'clientSecret', label: 'Client secret', secret: true },
];
const MS_HELP = 'Register an app in Microsoft Entra ID (Azure) and grant the Graph API permissions you need.';

// App catalog ---------------------------------------------------------
const APPS = {
  /* ---------------- Email ---------------- */
  smtp: {
    group: 'Email', label: 'Email (SMTP / IMAP)', icon: Mail,
    help: 'Works with any provider: Zoho, Yahoo, your own mail server, etc.',
    fields: [
      { key: 'host', label: 'SMTP host', placeholder: 'smtp.example.com' },
      { key: 'port', label: 'SMTP port', placeholder: '587' },
      {
        key: 'secure', label: 'Security', type: 'select', default: 'starttls',
        options: [
          { value: 'starttls', label: 'STARTTLS (usually 587)' },
          { value: 'ssl', label: 'SSL/TLS (usually 465)' },
          { value: 'none', label: 'None' },
        ],
      },
      { key: 'username', label: 'Username', placeholder: 'you@example.com' },
      { key: 'password', label: 'Password', secret: true },
      { key: 'from', label: 'From address', placeholder: 'you@example.com' },
      { key: 'imapHost', label: 'IMAP host (for reading mail)', optional: true, placeholder: 'imap.example.com' },
      { key: 'imapPort', label: 'IMAP port', optional: true, placeholder: '993' },
    ],
  },
  gmail: {
    group: 'Email', label: 'Gmail', icon: Mail,
    help: 'App passwords need 2-Step Verification: Google Account → Security → App passwords.',
    fields: [
      {
        key: 'authMode', label: 'Authentication method', type: 'select', default: 'app_password',
        options: [
          { value: 'app_password', label: 'App password (SMTP/IMAP)' },
          { value: 'oauth', label: 'OAuth client + refresh token' },
        ],
      },
      { key: 'email', label: 'Gmail address', placeholder: 'you@gmail.com' },
      { key: 'appPassword', label: 'App password', secret: true, showIf: { authMode: 'app_password' } },
      ...GOOGLE_OAUTH,
    ],
  },
  outlook: {
    group: 'Email', label: 'Outlook / Microsoft mail', icon: Mail, help: MS_HELP,
    fields: [...MS_AUTH, { key: 'mailbox', label: 'Mailbox (user email)', placeholder: 'you@company.com' }],
  },

  /* ---------------- Messaging ---------------- */
  telegram: {
    group: 'Messaging', label: 'Telegram', icon: Send,
    help: 'Create a bot with @BotFather to get the token. Send the bot a message, then use its chat ID.',
    fields: [
      { key: 'botToken', label: 'Bot token', secret: true, placeholder: '123456:ABC-DEF...' },
      { key: 'chatId', label: 'Default chat ID', optional: true, placeholder: '-1001234567890' },
    ],
  },
  whatsapp: {
    group: 'Messaging', label: 'WhatsApp (Cloud API)', icon: MessageCircle,
    help: 'Uses the Meta WhatsApp Business Cloud API. Find these values in Meta for Developers → WhatsApp → API Setup.',
    fields: [
      { key: 'accessToken', label: 'Permanent access token', secret: true },
      { key: 'phoneNumberId', label: 'Phone number ID' },
      { key: 'businessAccountId', label: 'Business account ID', optional: true },
      { key: 'verifyToken', label: 'Webhook verify token', secret: true, optional: true },
      { key: 'apiVersion', label: 'API version', optional: true, placeholder: 'v20.0' },
    ],
  },
  slack: {
    group: 'Messaging', label: 'Slack', icon: Slack,
    fields: [
      { key: 'token', label: 'Bot token', placeholder: 'xoxb-...', secret: true },
      { key: 'channel', label: 'Default channel', optional: true, placeholder: '#general' },
    ],
  },
  teams: {
    group: 'Messaging', label: 'Microsoft Teams', icon: Users,
    help: 'Webhook is the quickest way to post to a channel. Use the Graph app for reading/creating chats and meetings.',
    fields: [
      {
        key: 'authMode', label: 'Connection type', type: 'select', default: 'webhook',
        options: [
          { value: 'webhook', label: 'Incoming webhook / Workflows URL' },
          { value: 'graph', label: 'Microsoft Graph app registration' },
        ],
      },
      { key: 'webhookUrl', label: 'Webhook URL', secret: true, showIf: { authMode: 'webhook' } },
      ...MS_AUTH.map((f) => ({ ...f, showIf: { authMode: 'graph' } })),
    ],
  },
  discord: {
    group: 'Messaging', label: 'Discord', icon: MessageSquare,
    fields: [{ key: 'webhookUrl', label: 'Webhook URL', secret: true }],
  },

  /* ---------------- Google Workspace ---------------- */
  gsheets: {
    group: 'Google Workspace', label: 'Google Sheets', icon: Sheet,
    help: 'Enable the Google Sheets API in Google Cloud Console first.',
    fields: googleFields([{ key: 'spreadsheetId', label: 'Default spreadsheet ID', optional: true }]),
  },
  gcalendar: {
    group: 'Google Workspace', label: 'Google Calendar', icon: Calendar,
    help: 'Enable the Google Calendar API in Google Cloud Console first.',
    fields: googleFields([{ key: 'calendarId', label: 'Default calendar ID', optional: true, placeholder: 'primary' }]),
  },
  gdrive: {
    group: 'Google Workspace', label: 'Google Drive', icon: HardDrive,
    help: 'Enable the Google Drive API in Google Cloud Console first.',
    fields: googleFields([{ key: 'folderId', label: 'Default folder ID', optional: true }]),
  },
  gdocs: {
    group: 'Google Workspace', label: 'Google Docs', icon: FileText,
    help: 'Enable the Google Docs API in Google Cloud Console first.',
    fields: googleFields(),
  },
  google_other: {
    group: 'Google Workspace', label: 'Other Google API', icon: Cloud,
    help: 'For Forms, Tasks, Contacts, YouTube, Meet, Admin SDK, etc. List the OAuth scopes you need.',
    fields: googleFields([
      { key: 'scopes', label: 'Scopes (one per line)', type: 'textarea', placeholder: 'https://www.googleapis.com/auth/tasks' },
    ]),
  },

  /* ---------------- Microsoft 365 ---------------- */
  outlook_calendar: {
    group: 'Microsoft 365', label: 'Outlook Calendar', icon: Calendar, help: MS_HELP,
    fields: [...MS_AUTH, { key: 'mailbox', label: 'Calendar owner (user email)', placeholder: 'you@company.com' }],
  },
  excel: {
    group: 'Microsoft 365', label: 'Excel (Microsoft 365)', icon: FileSpreadsheet, help: MS_HELP,
    fields: [...MS_AUTH, { key: 'driveUser', label: 'OneDrive owner (user email)', placeholder: 'you@company.com' }],
  },
  onedrive: {
    group: 'Microsoft 365', label: 'OneDrive / SharePoint / Word', icon: Cloud, help: MS_HELP,
    fields: [...MS_AUTH, { key: 'siteId', label: 'SharePoint site ID', optional: true }, { key: 'driveUser', label: 'OneDrive owner (user email)', optional: true }],
  },

  /* ---------------- Other ---------------- */
  github: {
    group: 'Other', label: 'GitHub', icon: Github,
    fields: [
      { key: 'token', label: 'Personal access token', secret: true },
      { key: 'owner', label: 'Owner / organisation', optional: true, placeholder: 'my-org' },
    ],
  },
  notion: {
    group: 'Other', label: 'Notion', icon: FileText,
    fields: [{ key: 'apiKey', label: 'Integration secret', secret: true }],
  },
  custom: {
    group: 'Other', label: 'Custom API', icon: Globe,
    fields: [
      { key: 'baseUrl', label: 'Base URL', placeholder: 'https://api.example.com' },
      { key: 'headerName', label: 'Auth header name', placeholder: 'Authorization' },
      { key: 'apiKey', label: 'API key / token', secret: true },
    ],
  },
};

const defaultsFor = (app) =>
  Object.fromEntries((APPS[app]?.fields || []).filter((f) => f.default !== undefined).map((f) => [f.key, f.default]));

const isVisible = (f, values) =>
  !f.showIf || Object.entries(f.showIf).every(([k, v]) => values[k] === v);

/* ------------------------------------------------------------------ */
/* Small helpers                                                       */
/* ------------------------------------------------------------------ */
function StatusBadge({ status, testing }) {
  if (testing) return <span className="badge badge-run"><Loader2 size={13} className="spin" /> Testing…</span>;
  if (status === 'connected') return <span className="badge badge-ok"><CheckCircle2 size={13} /> Connected</span>;
  if (status === 'failed') return <span className="badge badge-err"><XCircle size={13} /> Failed</span>;
  return <span className="badge ai-idle">Untested</span>;
}

function SecretInput({ value, onChange, placeholder }) {
  const [show, setShow] = useState(false);
  return (
    <div className="ai-secret">
      <input
        className="input"
        type={show ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete="new-password"
      />
      <button type="button" className="icon-btn ai-eye" onClick={() => setShow((x) => !x)} aria-label="Toggle visibility">
        {show ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Add / Edit modal                                                    */
/* ------------------------------------------------------------------ */
function SecretTextarea({ value, onChange, placeholder }) {
  const [show, setShow] = useState(false);
  return (
    <div className="ai-secret is-multiline">
      <textarea
        className="input mono"
        rows={5}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{ WebkitTextSecurity: show ? 'none' : 'disc' }}
        spellCheck={false}
      />
      <button type="button" className="icon-btn ai-eye" onClick={() => setShow((x) => !x)} aria-label="Toggle visibility">
        {show ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}

function IntegrationModal({ initial, onClose, onSaved }) {
  const editing = !!initial;
  const startApp = initial?.app || 'smtp';
  const [app, setApp] = useState(startApp);
  const [name, setName] = useState(initial?.name || '');
  const [values, setValues] = useState({ ...defaultsFor(startApp), ...(initial?.config || {}) });
  const [busy, setBusy] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState('');

  const def = APPS[app];
  const visible = def.fields.filter((f) => isVisible(f, values));

  const changeApp = (a) => { setApp(a); setValues(defaultsFor(a)); setTestResult(null); setError(''); };
  const setField = (k, v) => setValues((p) => ({ ...p, [k]: v }));

  // On edit, blank secret fields are omitted so the server keeps the stored value
  const buildPayload = () => {
    const config = {};
    let keptSecrets = false;
    visible.forEach((f) => {
      const v = values[f.key];
      if (f.secret && editing && !v) { keptSecrets = true; return; }
      config[f.key] = v ?? '';
    });
    return { payload: { app, name: name.trim() || def.label, config }, keptSecrets };
  };

  const validate = () => {
    if (!name.trim()) return 'Please give this connection a name.';
    for (const f of visible) {
      if (f.optional || f.type === 'select') continue;
      if (f.secret && editing) continue;
      if (!String(values[f.key] ?? '').trim()) return `${f.label} is required.`;
    }
    return '';
  };

  const handleTest = async () => {
    const msg = validate();
    if (msg) return setError(msg);
    setError(''); setBusy(true); setTestResult(null);
    try {
      const { payload } = buildPayload();
      // include id when editing so the server can merge stored secrets
      const r = await api.testDraft(editing ? { ...payload, id: initial.id } : payload);
      setTestResult({ ok: r.ok !== false, message: r.message || 'Connection successful' });
    } catch (e) {
      setTestResult({ ok: false, message: e.message });
    } finally { setBusy(false); }
  };

  const handleSave = async () => {
    const msg = validate();
    if (msg) return setError(msg);
    setError(''); setBusy(true);
    try {
      const { payload } = buildPayload();
      const saved = editing ? await api.update(initial.id, payload) : await api.create(payload);
      onSaved(saved);
    } catch (e) {
      setError(e.message);
    } finally { setBusy(false); }
  };

  const renderField = (f) => {
    const val = values[f.key] ?? '';
    const ph = editing && f.secret ? 'Leave blank to keep current' : f.placeholder;
    if (f.type === 'select')
      return (
        <select className="input" value={val} onChange={(e) => setField(f.key, e.target.value)}>
          {f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      );
    if (f.type === 'textarea' && f.secret) return <SecretTextarea value={val} onChange={(v) => setField(f.key, v)} placeholder={ph} />;
    if (f.type === 'textarea') return <textarea className="input mono" rows={4} value={val} onChange={(e) => setField(f.key, e.target.value)} placeholder={ph} />;
    if (f.secret) return <SecretInput value={val} onChange={(v) => setField(f.key, v)} placeholder={ph} />;
    return <input className="input" value={val} onChange={(e) => setField(f.key, e.target.value)} placeholder={ph} />;
  };

  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal ai-modal" role="dialog" aria-modal="true">
        <div className="modal-head">
          <h3>{editing ? 'Edit connection' : 'Add connection'}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>

        <div className="field">
          <label>App</label>
          <select className="input" value={app} disabled={editing} onChange={(e) => changeApp(e.target.value)}>
            {GROUPS.map((g) => (
              <optgroup key={g} label={g}>
                {Object.entries(APPS).filter(([, v]) => v.group === g).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </optgroup>
            ))}
          </select>
          {def.help && <span className="hint">{def.help}</span>}
        </div>

        <div className="field">
          <label>Connection name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder={`e.g. Work ${def.label}`} />
        </div>

        {visible.map((f) => (
          <div className="field" key={f.key}>
            <label>{f.label}{f.optional && <span className="muted"> (optional)</span>}</label>
            {renderField(f)}
            {f.hint && <span className="hint">{f.hint}</span>}
          </div>
        ))}

        {error && <div className="alert alert-err">{error}</div>}
        {testResult && (
          <div className={`alert ${testResult.ok ? 'alert-ok' : 'alert-err'}`}>
            {testResult.ok ? <CheckCircle2 size={15} /> : <XCircle size={15} />} {testResult.message}
          </div>
        )}

        <div className="modal-foot">
          <button className="btn btn-outline" onClick={handleTest} disabled={busy}>
            {busy ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />} Test connection
          </button>
          <span className="grow" />
          <button className="btn btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={busy}>
            {editing ? 'Save changes' : 'Add connection'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */
export default function AppIntegration() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState(null);      // null | { initial? }
  const [testing, setTesting] = useState({});    // id -> bool
  const [notes, setNotes] = useState({});        // id -> last test message

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const data = await api.list();
      setItems(Array.isArray(data) ? data : data.items || []);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const patch = (id, changes) => setItems((prev) => prev.map((i) => (i.id === id ? { ...i, ...changes } : i)));

  const runTest = async (item) => {
    setTesting((t) => ({ ...t, [item.id]: true }));
    try {
      const r = await api.test(item.id);
      const ok = r.ok !== false;
      patch(item.id, { status: ok ? 'connected' : 'failed', lastChecked: new Date().toISOString() });
      setNotes((n) => ({ ...n, [item.id]: r.message || (ok ? 'Connection successful' : 'Connection failed') }));
    } catch (e) {
      patch(item.id, { status: 'failed', lastChecked: new Date().toISOString() });
      setNotes((n) => ({ ...n, [item.id]: e.message }));
    } finally { setTesting((t) => ({ ...t, [item.id]: false })); }
  };

  const remove = async (item) => {
    if (!window.confirm(`Delete "${item.name}"? Workflows using it will stop working.`)) return;
    try { await api.remove(item.id); setItems((p) => p.filter((i) => i.id !== item.id)); }
    catch (e) { setError(e.message); }
  };

  const handleSaved = (saved) => {
    setModal(null);
    load(); // simplest way to stay in sync with the server
    if (saved?.id) runTest(saved);
  };

  return (
    <div className="page narrow">
      <PageHeader title="App integrations" subtitle="Manage credentials for your connected apps" />

      <div className="ai-toolbar">
        <button className="btn btn-primary" onClick={() => setModal({})}><Plus size={16} /> Add connection</button>
        <button className="btn btn-outline" onClick={load} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>

      {error && <div className="alert alert-err">{error}</div>}

      {loading && !items.length ? (
        <div className="center-msg"><Loader2 size={18} className="spin" /> Loading…</div>
      ) : !items.length ? (
        <div className="empty">
          <Plug size={28} />
          <h3>No connections yet</h3>
          <p>Add your first app to use it inside workflows.</p>
        </div>
      ) : (
        <div className="card flush">
          {items.map((item) => {
            const Icon = APPS[item.app]?.icon || Plug;
            const note = notes[item.id] || (item.status === 'failed' ? item.lastError : '');
            return (
              <div key={item.id} className="list-row big ai-row">
                <span className="ai-app-ico"><Icon size={18} /></span>
                <div className="ai-info">
                  <b>{item.name}</b>
                  <span className="muted ai-meta">
                    {APPS[item.app]?.label || item.app}
                    {item.lastChecked && ` · checked ${new Date(item.lastChecked).toLocaleString()}`}
                  </span>
                  {note && <span className={`ai-note ${item.status === 'failed' ? 'bad' : ''}`}>{note}</span>}
                </div>
                <span className="grow" />
                <StatusBadge status={item.status} testing={testing[item.id]} />
                <div className="ai-actions">
                  <button className="icon-btn" title="Test connection" onClick={() => runTest(item)} disabled={testing[item.id]}><RefreshCw size={16} /></button>
                  <button className="icon-btn" title="Edit" onClick={() => setModal({ initial: item })}><Pencil size={16} /></button>
                  <button className="icon-btn danger" title="Delete" onClick={() => remove(item)}><Trash2 size={16} /></button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {modal && <IntegrationModal initial={modal.initial} onClose={() => setModal(null)} onSaved={handleSaved} />}
    </div>
  );
}