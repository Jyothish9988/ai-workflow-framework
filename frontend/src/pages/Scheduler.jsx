import { useState, useEffect } from 'react';
import { Plus, Trash2, Clock, X } from 'lucide-react';
import { schedulerAPI, workflowAPI, errMsg } from '../utils/api';
import { PageHeader, Spinner, Empty, useToast, timeAgo, pick } from '../components/ui';

// ── Repeat options shown in the dropdown ─────────────────────────────────────
const MODES = [
  ['once', 'Once (pick date & time)'],
  ['minutes', 'Every N minutes'],
  ['hourly', 'Every hour'],
  ['daily', 'Every day'],
  ['weekly', 'Every week'],
  ['monthly', 'Every month'],
];

const WEEKDAYS = [['1', 'Mon'], ['2', 'Tue'], ['3', 'Wed'], ['4', 'Thu'], ['5', 'Fri'], ['6', 'Sat'], ['0', 'Sun']];

// ── Helpers ──────────────────────────────────────────────────────────────────
const pad = (n) => String(n).padStart(2, '0');
const todayStr = () => {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};
const browserTz = () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

const newForm = () => ({
  workflow: '',
  mode: 'daily',
  date: todayStr(),     // yyyy-mm-dd
  time: '09:00',        // HH:mm (24h)
  everyN: 15,           // used by "Every N minutes"
  weekdays: ['1'],      // used by "Every week" (0 = Sunday)
  timezone: browserTz(),
  enabled: true,
});

// Accept either a bare array or an object wrapping the array under a known key
const asList = (d, ...keys) => {
  if (Array.isArray(d)) return d;
  for (const k of keys) if (Array.isArray(d?.[k])) return d[k];
  return [];
};

// Workflows may expose their display name under different fields
const wfLabel = (w) => w.name || w.title || w.workflow_name || String(w.id);

// ── Picker values -> cron  (minute hour day-of-month month day-of-week) ─────
const toCron = (f) => {
  const [hh, mm] = (f.time || '09:00').split(':').map(Number);
  const [, mo, d] = (f.date || '').split('-').map(Number);
  const days = [...f.weekdays].sort((a, b) => a - b).join(',');
  switch (f.mode) {
    case 'minutes': return `*/${Math.min(59, Math.max(1, Number(f.everyN) || 1))} * * * *`;
    case 'hourly':  return `${mm} * * * *`;
    case 'daily':   return `${mm} ${hh} * * *`;
    case 'weekly':  return `${mm} ${hh} * * ${days}`;
    case 'monthly': return `${mm} ${hh} ${d} * *`;
    case 'once':    return `${mm} ${hh} ${d} ${mo} *`;
    default:        return '';
  }
};

// Human-readable summary shown under the picker
const describe = (f) => {
  const t = f.time;
  switch (f.mode) {
    case 'minutes': return `Runs every ${Number(f.everyN) || 1} minute(s)`;
    case 'hourly':  return `Runs every hour at minute :${(t || '00:00').split(':')[1]}`;
    case 'daily':   return `Runs every day at ${t}`;
    case 'weekly': {
      const names = WEEKDAYS.filter(([v]) => f.weekdays.includes(v)).map(([, n]) => n).join(', ');
      return `Runs every ${names || '—'} at ${t}`;
    }
    case 'monthly': return `Runs on day ${Number((f.date || '').split('-')[2])} of every month at ${t}`;
    case 'once':    return `Runs on ${f.date} at ${t}`;
    default:        return '';
  }
};

export default function Scheduler() {
  const [rows, setRows] = useState([]);
  const [wfs, setWfs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(newForm());
  const [toast, notify] = useToast();

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const usesDate = form.mode === 'once' || form.mode === 'monthly';
  const usesTime = form.mode !== 'minutes';
  const cron = toCron(form);

  // Load schedules and workflows independently so one failure doesn't blank the other
  const load = async () => {
    const [s, w] = await Promise.allSettled([schedulerAPI.getAll(), workflowAPI.getAll()]);

    if (w.status === 'fulfilled') setWfs(asList(w.value.data, 'workflows', 'items', 'results', 'data'));
    else notify(errMsg(w.reason, 'Failed to load workflows'), 'error');

    if (s.status === 'fulfilled') setRows(asList(s.value.data, 'schedules', 'items', 'results'));
    else notify(errMsg(s.reason, 'Failed to load schedules'), 'error');

    setLoading(false);
  };
  useEffect(() => { load(); }, []); // eslint-disable-line

  const wfName = (id) => {
    const w = wfs.find((x) => String(x.id) === String(id));
    return w ? wfLabel(w) : id;
  };

  const openModal = () => { setForm(newForm()); setOpen(true); };

  const toggleDay = (v) =>
    set({ weekdays: form.weekdays.includes(v) ? form.weekdays.filter((x) => x !== v) : [...form.weekdays, v] });

  const save = async (e) => {
    e.preventDefault();
    if (!form.workflow) return notify('Select a workflow', 'error');
    if (usesDate && !form.date) return notify('Pick a date', 'error');
    if (usesTime && !form.time) return notify('Pick a time', 'error');
    if (form.mode === 'weekly' && form.weekdays.length === 0) return notify('Pick at least one weekday', 'error');
    if (form.mode === 'once' && new Date(`${form.date}T${form.time}`) <= new Date())
      return notify('Pick a date and time in the future', 'error');

    try {
      await schedulerAPI.upsert(form.workflow, { cron, timezone: form.timezone, enabled: form.enabled });
      notify('Schedule saved');
      setOpen(false);
      load();
    } catch (er) {
      notify(errMsg(er, 'Failed to save schedule'), 'error');
    }
  };

  const toggle = async (s) => {
    const cur = pick(s, ['enabled', 'is_active']) !== false;
    try {
      await schedulerAPI.patch(s.id, { enabled: !cur });
      setRows((r) => r.map((x) => (x.id === s.id ? { ...x, enabled: !cur } : x)));
    } catch (er) {
      notify(errMsg(er), 'error');
    }
  };

  const remove = async (s) => {
    if (!window.confirm('Delete this schedule?')) return;
    try {
      await schedulerAPI.delete(s.id);
      setRows((r) => r.filter((x) => x.id !== s.id));
      notify('Schedule deleted');
    } catch (er) {
      notify(errMsg(er), 'error');
    }
  };

  return (
    <div className="page">
      <PageHeader title="Schedules" subtitle="Run workflows automatically on a schedule">
        <button className="btn btn-primary" onClick={openModal}>
          <Plus size={16} />New schedule
        </button>
      </PageHeader>

      {loading ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <Empty icon={Clock} title="No schedules" text="Create a schedule, or add a Schedule Trigger node in the editor." />
      ) : (
        <div className="card flush">
          <table className="table">
            <thead>
              <tr><th>Workflow</th><th>Cron</th><th>Last run</th><th>Next run</th><th>Active</th><th /></tr>
            </thead>
            <tbody>
              {rows.map((s) => {
                const next = pick(s, ['next_run_at', 'next_run']);
                return (
                  <tr key={s.id}>
                    <td><b>{wfName(s.workflow_id)}</b></td>
                    <td><code className="code-chip">{pick(s, ['cron_expression', 'cron']) || '—'}</code></td>
                    <td>{timeAgo(pick(s, ['last_run_at', 'last_run']))}</td>
                    <td>{next ? new Date(next).toLocaleString() : '—'}</td>
                    <td>
                      <label className="switch">
                        <input
                          type="checkbox"
                          checked={pick(s, ['enabled', 'is_active']) !== false}
                          onChange={() => toggle(s)}
                        />
                        <span />
                      </label>
                    </td>
                    <td className="right">
                      <button className="icon-btn danger" onClick={() => remove(s)}>
                        <Trash2 size={15} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {open && (
        <div className="modal-bg" onClick={() => setOpen(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={save}>
            <div className="modal-head">
              <h3>New schedule</h3>
              <button type="button" className="icon-btn" onClick={() => setOpen(false)}>
                <X size={16} />
              </button>
            </div>

            {/* Workflow */}
            <div className="field">
              <label>Workflow</label>
              <select className="input" value={form.workflow} onChange={(e) => set({ workflow: e.target.value })}>
                <option value="">{wfs.length ? 'Select…' : 'No workflows found'}</option>
                {wfs.map((w) => (
                  <option key={w.id} value={w.id}>{wfLabel(w)}</option>
                ))}
              </select>
            </div>

            {/* Repeat (controlled, so the selection stays visible) */}
            <div className="field">
              <label>Repeat</label>
              <select className="input" value={form.mode} onChange={(e) => set({ mode: e.target.value })}>
                {MODES.map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </div>

            {/* Every N minutes */}
            {form.mode === 'minutes' && (
              <div className="field">
                <label>Every (minutes)</label>
                <input
                  type="number"
                  min="1"
                  max="59"
                  className="input"
                  value={form.everyN}
                  onChange={(e) => set({ everyN: e.target.value })}
                />
              </div>
            )}

            {/* Weekday chips */}
            {form.mode === 'weekly' && (
              <div className="field">
                <label>Days</label>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {WEEKDAYS.map(([v, n]) => (
                    <button
                      key={v}
                      type="button"
                      className={`btn ${form.weekdays.includes(v) ? 'btn-primary' : 'btn-ghost'}`}
                      style={{ padding: '4px 10px' }}
                      onClick={() => toggleDay(v)}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Date picker (Once / Monthly) */}
            {usesDate && (
              <div className="field">
                <label>{form.mode === 'monthly' ? 'Day of month (from date)' : 'Date'}</label>
                <input
                  type="date"
                  className="input"
                  min={form.mode === 'once' ? todayStr() : undefined}
                  value={form.date}
                  onChange={(e) => set({ date: e.target.value })}
                />
                {form.mode === 'monthly' && Number((form.date || '').split('-')[2]) > 28 && (
                  <small style={{ opacity: 0.7 }}>Months without this day will be skipped.</small>
                )}
              </div>
            )}

            {/* Clock picker */}
            {usesTime && (
              <div className="field">
                <label>{form.mode === 'hourly' ? 'At minute (uses the minutes of this time)' : 'Time'}</label>
                <input type="time" className="input" value={form.time} onChange={(e) => set({ time: e.target.value })} />
              </div>
            )}

            <div className="field">
              <label>Timezone</label>
              <input className="input" value={form.timezone} onChange={(e) => set({ timezone: e.target.value })} />
            </div>

            {/* Preview of what will be saved */}
            <div className="field">
              <label>Summary</label>
              <div>{describe(form)}</div>
              <code className="code-chip">{cron}</code>
            </div>

            <div className="field row">
              <label>Active</label>
              <label className="switch">
                <input type="checkbox" checked={form.enabled} onChange={(e) => set({ enabled: e.target.checked })} />
                <span />
              </label>
            </div>

            <div className="modal-foot">
              <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
              <button className="btn btn-primary">Save schedule</button>
            </div>
          </form>
        </div>
      )}
      {toast}
    </div>
  );
}