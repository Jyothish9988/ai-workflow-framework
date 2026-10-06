import { useState, useEffect } from 'react';
import {
  Plus,
  Trash2,
  Clock,
  X,
  Pencil,
  Play,
} from 'lucide-react';

import {
  schedulerAPI,
  workflowAPI,
  errMsg,
} from '../utils/api';

import {
  PageHeader,
  Spinner,
  Empty,
  useToast,
  timeAgo,
  pick,
} from '../components/ui';


// ─────────────────────────────────────────────────────────────────────────────
// Repeat options
// ─────────────────────────────────────────────────────────────────────────────

const MODES = [
  ['once', 'Once (pick date & time)'],
  ['minutes', 'Every N minutes'],
  ['hourly', 'Every hour'],
  ['daily', 'Every day'],
  ['weekly', 'Every week'],
  ['monthly', 'Every month'],
];

const WEEKDAYS = [
  ['1', 'Mon'],
  ['2', 'Tue'],
  ['3', 'Wed'],
  ['4', 'Thu'],
  ['5', 'Fri'],
  ['6', 'Sat'],
  ['0', 'Sun'],
];


// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

const pad = (n) => String(n).padStart(2, '0');

const todayStr = () => {
  const d = new Date();

  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

const browserTz = () =>
  Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';


// ─────────────────────────────────────────────────────────────────────────────
// Timezone list (IANA names), grouped by region, with the current UTC offset
// ─────────────────────────────────────────────────────────────────────────────

const FALLBACK_TIMEZONES = [
  'Asia/Kolkata', 'Asia/Dubai', 'Asia/Singapore', 'Asia/Tokyo',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin',
  'America/New_York', 'America/Chicago', 'America/Denver',
  'America/Los_Angeles', 'Australia/Sydney',
];

const tzOffsetLabel = (tz) => {
  try {
    const part = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      timeZoneName: 'shortOffset',
    })
      .formatToParts(new Date())
      .find((p) => p.type === 'timeZoneName');

    return part ? part.value.replace('GMT', 'UTC') : 'UTC';
  } catch {
    return '';
  }
};

const TIMEZONE_GROUPS = (() => {
  let names;

  try {
    names = Intl.supportedValuesOf('timeZone');
  } catch {
    names = FALLBACK_TIMEZONES;
  }

  const groups = {};

  names.forEach((tz) => {
    const region = tz.includes('/') ? tz.split('/')[0] : 'Other';

    (groups[region] = groups[region] || []).push({
      value: tz,
      label: `(${tzOffsetLabel(tz)}) ${tz.replace(/_/g, ' ')}`,
    });
  });

  return Object.keys(groups)
    .sort()
    .map((region) => [region, groups[region]]);
})();

const hasTimezone = (tz) =>
  tz === 'UTC' ||
  TIMEZONE_GROUPS.some(([, list]) =>
    list.some((o) => o.value === tz)
  );


// ─────────────────────────────────────────────────────────────────────────────
// New form
// ─────────────────────────────────────────────────────────────────────────────

const newForm = () => ({
  workflow: '',
  mode: 'daily',
  date: todayStr(),
  time: '09:00',
  everyN: 15,
  weekdays: ['1'],
  timezone: browserTz(),
  enabled: true,
});


// ─────────────────────────────────────────────────────────────────────────────
// Response helpers
// ─────────────────────────────────────────────────────────────────────────────

const asList = (d, ...keys) => {
  if (Array.isArray(d)) return d;

  for (const k of keys) {
    if (Array.isArray(d?.[k])) {
      return d[k];
    }
  }

  return [];
};


const wfLabel = (w) =>
  w.name ||
  w.title ||
  w.workflow_name ||
  String(w.id);


// ─────────────────────────────────────────────────────────────────────────────
// Cron generation
// minute hour day-of-month month day-of-week
// ─────────────────────────────────────────────────────────────────────────────

const toCron = (f) => {
  const [hh, mm] = (f.time || '09:00')
    .split(':')
    .map(Number);

  const [, mo, d] = (f.date || '')
    .split('-')
    .map(Number);

  const days = [...(f.weekdays || [])]
    .sort((a, b) => Number(a) - Number(b))
    .join(',');

  switch (f.mode) {
    case 'minutes':
      return `*/${Math.min(
        59,
        Math.max(1, Number(f.everyN) || 1)
      )} * * * *`;

    case 'hourly':
      return `${mm} * * * *`;

    case 'daily':
      return `${mm} ${hh} * * *`;

    case 'weekly':
      return `${mm} ${hh} * * ${days}`;

    case 'monthly':
      return `${mm} ${hh} ${d} * *`;

    case 'once':
      return `${mm} ${hh} ${d} ${mo} *`;

    default:
      return '';
  }
};


// ─────────────────────────────────────────────────────────────────────────────
// Human readable description
// ─────────────────────────────────────────────────────────────────────────────

const describe = (f) => {
  const t = f.time;

  switch (f.mode) {
    case 'minutes':
      return `Runs every ${Number(f.everyN) || 1} minute(s)`;

    case 'hourly':
      return `Runs every hour at minute :${(t || '00:00').split(':')[1]}`;

    case 'daily':
      return `Runs every day at ${t}`;

    case 'weekly': {
      const names = WEEKDAYS
        .filter(([v]) => (f.weekdays || []).includes(v))
        .map(([, n]) => n)
        .join(', ');

      return `Runs every ${names || '—'} at ${t}`;
    }

    case 'monthly':
      return `Runs on day ${
        Number((f.date || '').split('-')[2]) || 1
      } of every month at ${t}`;

    case 'once':
      return `Runs on ${f.date} at ${t}`;

    default:
      return '';
  }
};


// ─────────────────────────────────────────────────────────────────────────────
// Parse existing cron into form values
// ─────────────────────────────────────────────────────────────────────────────

const cronToForm = (schedule) => {
  const cron =
    pick(schedule, ['cron_expression', 'cron']) || '';

  const result = {
    workflow: String(schedule.workflow_id || ''),
    mode: 'daily',
    date: todayStr(),
    time: '09:00',
    everyN: 15,
    weekdays: ['1'],
    timezone: schedule.timezone || browserTz(),
    enabled:
      pick(schedule, ['enabled', 'is_active']) !== false,
  };

  const parts = cron.trim().split(/\s+/);

  if (parts.length !== 5) {
    return result;
  }

  const [minute, hour, day, month, weekday] = parts;

  // Every N minutes
  if (
    minute.startsWith('*/') &&
    hour === '*' &&
    day === '*' &&
    month === '*' &&
    weekday === '*'
  ) {
    return {
      ...result,
      mode: 'minutes',
      everyN: Number(minute.substring(2)) || 1,
    };
  }

  // Every hour
  if (
    hour === '*' &&
    day === '*' &&
    month === '*' &&
    weekday === '*'
  ) {
    return {
      ...result,
      mode: 'hourly',
      time: `00:${pad(Number(minute) || 0)}`,
    };
  }

  // Weekly
  if (
    weekday !== '*' &&
    day === '*' &&
    month === '*'
  ) {
    return {
      ...result,
      mode: 'weekly',
      time: `${pad(Number(hour) || 0)}:${pad(Number(minute) || 0)}`,
      weekdays: weekday.split(','),
    };
  }

  // Monthly
  if (
    day !== '*' &&
    month === '*' &&
    weekday === '*'
  ) {
    const dayNumber = Number(day) || 1;

    return {
      ...result,
      mode: 'monthly',
      date: `${todayStr().slice(0, 7)}-${pad(dayNumber)}`,
      time: `${pad(Number(hour) || 0)}:${pad(Number(minute) || 0)}`,
    };
  }

  // "Once" cron
  //
  // Note:
  // A standard cron expression cannot distinguish
  // "once" from a yearly recurrence.
  //
  // We treat a specific day/month cron as "once"
  // when editing it.
  if (
    day !== '*' &&
    month !== '*' &&
    weekday === '*'
  ) {
    const year = new Date().getFullYear();

    return {
      ...result,
      mode: 'once',
      date: `${year}-${pad(Number(month) || 1)}-${pad(Number(day) || 1)}`,
      time: `${pad(Number(hour) || 0)}:${pad(Number(minute) || 0)}`,
    };
  }

  // Daily
  if (
    hour !== '*' &&
    day === '*' &&
    month === '*' &&
    weekday === '*'
  ) {
    return {
      ...result,
      mode: 'daily',
      time: `${pad(Number(hour) || 0)}:${pad(Number(minute) || 0)}`,
    };
  }

  return result;
};


// ─────────────────────────────────────────────────────────────────────────────
// Scheduler page
// ─────────────────────────────────────────────────────────────────────────────

export default function Scheduler() {
  const [rows, setRows] = useState([]);
  const [wfs, setWfs] = useState([]);

  const [loading, setLoading] = useState(true);

  const [open, setOpen] = useState(false);

  const [editing, setEditing] = useState(null);

  const [saving, setSaving] = useState(false);

  const [runningId, setRunningId] = useState(null);

  const [form, setForm] = useState(newForm());

  const [toast, notify] = useToast();


  // ───────────────────────────────────────────────────────────────────────────
  // Form helpers
  // ───────────────────────────────────────────────────────────────────────────

  const set = (patch) => {
    setForm((f) => ({
      ...f,
      ...patch,
    }));
  };


  const usesDate =
    form.mode === 'once' ||
    form.mode === 'monthly';

  const usesTime =
    form.mode !== 'minutes';

  const cron = toCron(form);


  // ───────────────────────────────────────────────────────────────────────────
  // Load schedules + workflows
  // ───────────────────────────────────────────────────────────────────────────

  const load = async () => {
    setLoading(true);

    const [s, w] = await Promise.allSettled([
      schedulerAPI.getAll(),
      workflowAPI.getAll(),
    ]);

    if (w.status === 'fulfilled') {
      setWfs(
        asList(
          w.value.data,
          'workflows',
          'items',
          'results',
          'data'
        )
      );
    } else {
      notify(
        errMsg(
          w.reason,
          'Failed to load workflows'
        ),
        'error'
      );
    }

    if (s.status === 'fulfilled') {
      setRows(
        asList(
          s.value.data,
          'schedules',
          'items',
          'results'
        )
      );
    } else {
      notify(
        errMsg(
          s.reason,
          'Failed to load schedules'
        ),
        'error'
      );
    }

    setLoading(false);
  };


  useEffect(() => {
    load();
  }, []); // eslint-disable-line


  // ───────────────────────────────────────────────────────────────────────────
  // Workflow name
  // ───────────────────────────────────────────────────────────────────────────

  const wfName = (id) => {
    const w = wfs.find(
      (x) => String(x.id) === String(id)
    );

    return w ? wfLabel(w) : id;
  };


  // ───────────────────────────────────────────────────────────────────────────
  // New schedule
  // ───────────────────────────────────────────────────────────────────────────

  const openNew = () => {
    setEditing(null);
    setForm(newForm());
    setOpen(true);
  };


  // ───────────────────────────────────────────────────────────────────────────
  // Edit schedule
  // ───────────────────────────────────────────────────────────────────────────

  const openEdit = (schedule) => {
    setEditing(schedule);
    setForm(cronToForm(schedule));
    setOpen(true);
  };


  // ───────────────────────────────────────────────────────────────────────────
  // Close modal
  // ───────────────────────────────────────────────────────────────────────────

  const closeModal = () => {
    if (saving) return;

    setOpen(false);
    setEditing(null);
    setForm(newForm());
  };


  // ───────────────────────────────────────────────────────────────────────────
  // Weekday toggle
  // ───────────────────────────────────────────────────────────────────────────

  const toggleDay = (value) => {
    setForm((f) => {
      const exists = f.weekdays.includes(value);

      return {
        ...f,
        weekdays: exists
          ? f.weekdays.filter((x) => x !== value)
          : [...f.weekdays, value],
      };
    });
  };


  // ───────────────────────────────────────────────────────────────────────────
  // Save / update
  // ───────────────────────────────────────────────────────────────────────────

  const save = async (e) => {
    e.preventDefault();

    if (!form.workflow) {
      return notify(
        'Select a workflow',
        'error'
      );
    }

    if (usesDate && !form.date) {
      return notify(
        'Pick a date',
        'error'
      );
    }

    if (usesTime && !form.time) {
      return notify(
        'Pick a time',
        'error'
      );
    }

    if (
      form.mode === 'weekly' &&
      form.weekdays.length === 0
    ) {
      return notify(
        'Pick at least one weekday',
        'error'
      );
    }

    if (
      form.mode === 'once' &&
      new Date(`${form.date}T${form.time}`) <= new Date()
    ) {
      return notify(
        'Pick a date and time in the future',
        'error'
      );
    }

    if (!cron) {
      return notify(
        'Invalid schedule',
        'error'
      );
    }

    setSaving(true);

    try {
      if (editing) {
        // Update existing schedule
        await schedulerAPI.patch(
          editing.id,
          {
            freq: 'custom',
            cron,
            timezone: form.timezone,
            enabled: form.enabled,
          }
        );

        notify('Schedule updated');
      } else {
        // Create schedule
        await schedulerAPI.upsert(
          form.workflow,
          {
            cron,
            timezone: form.timezone,
            enabled: form.enabled,
          }
        );

        notify('Schedule saved');
      }

      closeModal();
      await load();

    } catch (er) {
      notify(
        errMsg(
          er,
          editing
            ? 'Failed to update schedule'
            : 'Failed to save schedule'
        ),
        'error'
      );
    } finally {
      setSaving(false);
    }
  };


  // ───────────────────────────────────────────────────────────────────────────
  // Enable / disable
  // ───────────────────────────────────────────────────────────────────────────

  const toggle = async (schedule) => {
    const current =
      pick(
        schedule,
        ['enabled', 'is_active']
      ) !== false;

    try {
      await schedulerAPI.patch(
        schedule.id,
        {
          enabled: !current,
        }
      );

      setRows((rows) =>
        rows.map((row) =>
          row.id === schedule.id
            ? {
                ...row,
                enabled: !current,
              }
            : row
        )
      );

      notify(
        !current
          ? 'Schedule enabled'
          : 'Schedule disabled'
      );

    } catch (er) {
      notify(
        errMsg(
          er,
          'Failed to update schedule'
        ),
        'error'
      );
    }
  };


  // ───────────────────────────────────────────────────────────────────────────
  // Delete
  // ───────────────────────────────────────────────────────────────────────────

  const remove = async (schedule) => {
    const workflowName = wfName(
      schedule.workflow_id
    );

    if (
      !window.confirm(
        `Delete the schedule for "${workflowName}"?`
      )
    ) {
      return;
    }

    try {
      await schedulerAPI.delete(
        schedule.id
      );

      setRows((rows) =>
        rows.filter(
          (row) => row.id !== schedule.id
        )
      );

      notify('Schedule deleted');

    } catch (er) {
      notify(
        errMsg(
          er,
          'Failed to delete schedule'
        ),
        'error'
      );
    }
  };


  // ───────────────────────────────────────────────────────────────────────────
  // Run now
  // ───────────────────────────────────────────────────────────────────────────

  const runNow = async (schedule) => {
    const workflowName = wfName(
      schedule.workflow_id
    );

    const confirmed = window.confirm(
      `Run "${workflowName}" now?`
    );

    if (!confirmed) {
      return;
    }

    setRunningId(schedule.id);

    try {
      await schedulerAPI.run(
        schedule.id
      );

      notify(
        'Schedule run triggered'
      );

      await load();

    } catch (er) {
      notify(
        errMsg(
          er,
          'Failed to run schedule'
        ),
        'error'
      );
    } finally {
      setRunningId(null);
    }
  };


  // ───────────────────────────────────────────────────────────────────────────
  // Render
  // ───────────────────────────────────────────────────────────────────────────

  return (
    <div className="page">

      <PageHeader
        title="Schedules"
        subtitle="Run workflows automatically on a schedule"
      >
        <button
          className="btn btn-primary"
          onClick={openNew}
        >
          <Plus size={16} />
          New schedule
        </button>
      </PageHeader>


      {/* ─────────────────────────────────────────────────────────────────────
          Schedule list
      ───────────────────────────────────────────────────────────────────── */}

      {loading ? (
        <Spinner />

      ) : rows.length === 0 ? (

        <Empty
          icon={Clock}
          title="No schedules"
          text="Create a schedule, or add a Schedule Trigger node in the editor."
        />

      ) : (

        <div className="card flush">

          <table className="table">

            <thead>
              <tr>
                <th>Workflow</th>
                <th>Cron</th>
                <th>Last run</th>
                <th>Next run</th>
                <th>Active</th>
                <th>Actions</th>
              </tr>
            </thead>


            <tbody>

              {rows.map((schedule) => {

                const next = pick(
                  schedule,
                  [
                    'next_run_at',
                    'next_run',
                  ]
                );

                const enabled =
                  pick(
                    schedule,
                    [
                      'enabled',
                      'is_active',
                    ]
                  ) !== false;

                const running =
                  runningId === schedule.id;


                return (
                  <tr key={schedule.id}>

                    {/* Workflow */}
                    <td>
                      <b>
                        {wfName(
                          schedule.workflow_id
                        )}
                      </b>
                    </td>


                    {/* Cron */}
                    <td>
                      <code className="code-chip">
                        {pick(
                          schedule,
                          [
                            'cron_expression',
                            'cron',
                          ]
                        ) || '—'}
                      </code>
                    </td>


                    {/* Last run */}
                    <td>
                      {timeAgo(
                        pick(
                          schedule,
                          [
                            'last_run_at',
                            'last_run',
                          ]
                        )
                      )}
                    </td>


                    {/* Next run */}
                    <td>
                      {next
                        ? new Date(next).toLocaleString()
                        : '—'}
                    </td>


                    {/* Active */}
                    <td>
                      <label className="switch">

                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={() =>
                            toggle(schedule)
                          }
                        />

                        <span />

                      </label>
                    </td>


                    {/* Actions */}
                    <td className="right">

                      <div
                        style={{
                          display: 'flex',
                          gap: 6,
                          justifyContent: 'flex-end',
                        }}
                      >

                        {/* Edit */}
                        <button
                          type="button"
                          className="icon-btn"
                          title="Edit schedule"
                          onClick={() =>
                            openEdit(schedule)
                          }
                        >
                          <Pencil size={15} />
                        </button>


                        {/* Run now */}
                        <button
                          type="button"
                          className="icon-btn"
                          title="Run now"
                          disabled={running}
                          onClick={() =>
                            runNow(schedule)
                          }
                        >
                          <Play
                            size={15}
                            fill={
                              running
                                ? 'currentColor'
                                : 'none'
                            }
                          />
                        </button>


                        {/* Delete */}
                        <button
                          type="button"
                          className="icon-btn danger"
                          title="Delete schedule"
                          onClick={() =>
                            remove(schedule)
                          }
                        >
                          <Trash2 size={15} />
                        </button>

                      </div>

                    </td>

                  </tr>
                );
              })}

            </tbody>

          </table>

        </div>
      )}


      {/* ─────────────────────────────────────────────────────────────────────
          Create / Edit modal
      ───────────────────────────────────────────────────────────────────── */}

      {open && (

        <div
          className="modal-bg"
          onClick={closeModal}
        >

          <form
            className="modal"
            onClick={(e) =>
              e.stopPropagation()
            }
            onSubmit={save}
          >

            {/* Header */}
            <div className="modal-head">

              <h3>
                {editing
                  ? 'Edit schedule'
                  : 'New schedule'}
              </h3>

              <button
                type="button"
                className="icon-btn"
                onClick={closeModal}
                disabled={saving}
              >
                <X size={16} />
              </button>

            </div>


            {/* Workflow */}
            <div className="field">

              <label>
                Workflow
              </label>

              <select
                className="input"
                value={form.workflow}
                onChange={(e) =>
                  set({
                    workflow:
                      e.target.value,
                  })
                }
                disabled={Boolean(editing)}
              >

                <option value="">
                  {wfs.length
                    ? 'Select…'
                    : 'No workflows found'}
                </option>

                {wfs.map((w) => (
                  <option
                    key={w.id}
                    value={w.id}
                  >
                    {wfLabel(w)}
                  </option>
                ))}

              </select>

              {editing && (
                <small
                  style={{
                    opacity: 0.65,
                  }}
                >
                  Workflow cannot be changed
                  while editing. Create a new
                  schedule for another workflow.
                </small>
              )}

            </div>


            {/* Repeat */}
            <div className="field">

              <label>
                Repeat
              </label>

              <select
                className="input"
                value={form.mode}
                onChange={(e) =>
                  set({
                    mode: e.target.value,
                  })
                }
              >

                {MODES.map(
                  ([value, label]) => (
                    <option
                      key={value}
                      value={value}
                    >
                      {label}
                    </option>
                  )
                )}

              </select>

            </div>


            {/* Every N minutes */}
            {form.mode === 'minutes' && (

              <div className="field">

                <label>
                  Every (minutes)
                </label>

                <input
                  type="number"
                  min="1"
                  max="59"
                  className="input"
                  value={form.everyN}
                  onChange={(e) =>
                    set({
                      everyN:
                        e.target.value,
                    })
                  }
                />

              </div>
            )}


            {/* Weekly days */}
            {form.mode === 'weekly' && (

              <div className="field">

                <label>
                  Days
                </label>

                <div
                  style={{
                    display: 'flex',
                    gap: 6,
                    flexWrap: 'wrap',
                  }}
                >

                  {WEEKDAYS.map(
                    ([value, name]) => (

                      <button
                        key={value}
                        type="button"
                        className={`btn ${
                          form.weekdays.includes(
                            value
                          )
                            ? 'btn-primary'
                            : 'btn-ghost'
                        }`}
                        style={{
                          padding:
                            '4px 10px',
                        }}
                        onClick={() =>
                          toggleDay(value)
                        }
                      >
                        {name}
                      </button>

                    )
                  )}

                </div>

              </div>
            )}


            {/* Date */}
            {usesDate && (

              <div className="field">

                <label>
                  {form.mode === 'monthly'
                    ? 'Day of month'
                    : 'Date'}
                </label>

                <input
                  type="date"
                  className="input"
                  min={
                    form.mode === 'once'
                      ? todayStr()
                      : undefined
                  }
                  value={form.date}
                  onChange={(e) =>
                    set({
                      date:
                        e.target.value,
                    })
                  }
                />

                {form.mode === 'monthly' &&
                  Number(
                    (
                      form.date || ''
                    ).split('-')[2]
                  ) > 28 && (

                    <small
                      style={{
                        opacity: 0.7,
                      }}
                    >
                      Months without this
                      day will be skipped.
                    </small>

                  )}

              </div>
            )}


            {/* Time */}
            {usesTime && (

              <div className="field">

                <label>
                  {form.mode === 'hourly'
                    ? 'At minute'
                    : 'Time'}
                </label>

                <input
                  type="time"
                  className="input"
                  value={form.time}
                  onChange={(e) =>
                    set({
                      time:
                        e.target.value,
                    })
                  }
                />

              </div>
            )}


            {/* Timezone */}
            <div className="field">

              <label>
                Timezone
              </label>

              <select
                className="input"
                value={form.timezone}
                onChange={(e) =>
                  set({
                    timezone: e.target.value,
                  })
                }
              >

                <option value="UTC">
                  (UTC) UTC
                </option>

                {/* keep a saved value that isn't in the browser's list */}
                {!hasTimezone(form.timezone) && (
                  <option value={form.timezone}>
                    {form.timezone}
                  </option>
                )}

                {TIMEZONE_GROUPS.map(
                  ([region, zones]) => (
                    <optgroup
                      key={region}
                      label={region}
                    >
                      {zones.map((z) => (
                        <option
                          key={z.value}
                          value={z.value}
                        >
                          {z.label}
                        </option>
                      ))}
                    </optgroup>
                  )
                )}

              </select>

            </div>


            {/* Summary */}
            <div className="field">

              <label>
                Summary
              </label>

              <div>
                {describe(form)}
              </div>

              <code
                className="code-chip"
                style={{
                  display: 'inline-block',
                  marginTop: 6,
                }}
              >
                {cron}
              </code>

            </div>


            {/* Active */}
            <div className="field row">

              <label>
                Active
              </label>

              <label className="switch">

                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(e) =>
                    set({
                      enabled:
                        e.target.checked,
                    })
                  }
                />

                <span />

              </label>

            </div>


            {/* Footer */}
            <div className="modal-foot">

              <button
                type="button"
                className="btn btn-ghost"
                onClick={closeModal}
                disabled={saving}
              >
                Cancel
              </button>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={saving}
              >
                {saving
                  ? 'Saving...'
                  : editing
                    ? 'Update schedule'
                    : 'Save schedule'}
              </button>

            </div>

          </form>

        </div>
      )}


      {toast}

    </div>
  );
}