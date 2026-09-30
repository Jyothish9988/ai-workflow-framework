import {
  Play, Globe, Mail, Bot, GitBranch, Split, Timer, Repeat, MessageSquare, Send, Pencil, Braces, Type,
  Calendar, CircleDot, Hash, Regex, Wand2, OctagonX, SkipForward, Inbox,
} from 'lucide-react';

export const CATEGORIES = [
  { id: 'trigger', label: 'Triggers' },
  { id: 'flow', label: 'Flow' },
  { id: 'data', label: 'Data Transformation' },
  { id: 'ai', label: 'AI' },
  { id: 'app', label: 'Apps & Integrations' },
];

const f = (key, label, type = 'text', extra = {}) => ({ key, label, type, ...extra });
const opts = (...a) => a.map((x) => (typeof x === 'string' ? { value: x, label: x } : x));
const HTTP = opts('GET', 'POST', 'PUT', 'PATCH', 'DELETE');
const body = f('body', 'Body (JSON)', 'code', { placeholder: '{ "key": "{{ $json.value }}" }' });

export const NODES = {
  // ---- Trigger (engine requires exactly one `start`)
  start: { label: 'Start', cat: 'trigger', icon: Play, color: '#ff6d5a', trigger: true,
    desc: 'Entry point. Choose "schedule" to run on a cron (synced to Schedules).',
    fields: [f('triggerType', 'Trigger type', 'select', { options: opts('manual', 'schedule'), default: 'manual' }),
      f('cron', 'Cron expression', 'text', { default: '0 9 * * *', show: (d) => d.triggerType === 'schedule' }),
      f('preset', 'Preset', 'select', { sync: 'cron', show: (d) => d.triggerType === 'schedule', options: opts({ value: '', label: 'Custom' }, { value: '* * * * *', label: 'Every minute' }, { value: '*/15 * * * *', label: 'Every 15 minutes' }, { value: '0 * * * *', label: 'Every hour' }, { value: '0 9 * * *', label: 'Every day 09:00' }, { value: '0 9 * * 1', label: 'Every Monday 09:00' }) }),
      f('enabled', 'Schedule active', 'toggle', { default: true, show: (d) => d.triggerType === 'schedule' })],
    summary: (d) => (d.triggerType === 'schedule' ? d.cron || '0 9 * * *' : 'manual') },
 
    // ---- Flow
  if: { label: 'IF', cat: 'flow', icon: GitBranch, color: '#00b894', desc: 'Branch on a condition',
    outputs: () => [{ id: 'true', label: 'true' }, { id: 'false', label: 'false' }],
    fields: [f('field', 'Context path', 'text', { placeholder: 'http.status' }),
      f('operator', 'Operator', 'select', { default: 'equals', options: opts('equals', 'not_equals', 'contains', 'starts_with', 'ends_with', 'greater_than', 'less_than', 'between', 'is_empty', 'is_not_empty') }),
      f('value', 'Value', 'text', { show: (d) => !['is_empty', 'is_not_empty'].includes(d.operator) }),
      f('value2', 'Value 2 (upper bound)', 'text', { show: (d) => d.operator === 'between' })],
    summary: (d) => `${d.field || '…'} ${d.operator || 'equals'} ${d.value ?? ''}` },
  switch: { label: 'Switch', cat: 'flow', icon: Split, color: '#00a884', desc: 'Route to one of many outputs',
    outputs: (d) => [...(d.rules?.length ? d.rules : ['']).map((r, i) => ({ id: `case_${i}`, label: r || `Case ${i + 1}` })), { id: 'fallback', label: 'fallback' }],
    fields: [f('value', 'Value to match', 'text', { placeholder: '{{http.body.type}}' }), f('rules', 'Cases (exact match)', 'list', { add: 'Add case' })],
    summary: (d) => `${(d.rules || []).length || 1} case(s)` },
  loop: { label: 'Loop', cat: 'flow', icon: Repeat, color: '#6c5ce7', desc: 'Repeat the body N times or for each item of a list',
    outputs: () => [{ id: 'body', label: 'loop' }, { id: 'exit', label: 'done' }],
    fields: [f('loopType', 'Mode', 'select', { options: opts({ value: 'times', label: 'Repeat N times' }, { value: 'forEach', label: 'For each item' }), default: 'times' }),
      f('count', 'Times', 'number', { default: 3, show: (d) => d.loopType !== 'forEach' }),
      f('itemsVar', 'List path', 'text', { placeholder: 'http.body.items', show: (d) => d.loopType === 'forEach' }),
      f('iterVar', 'Current item variable', 'text', { default: 'loop.item' })],
    summary: (d) => (d.loopType === 'forEach' ? `each ${d.itemsVar || 'item'}` : `${d.count ?? 3}×`) },
  wait: { label: 'Wait', cat: 'flow', icon: Timer, color: '#636e72', desc: 'Pause the workflow',
    fields: [f('seconds', 'Amount', 'number', { default: 5 }), f('unit', 'Unit', 'select', { options: opts('seconds', 'minutes', 'hours'), default: 'seconds' })],
    summary: (d) => `${d.seconds ?? 5} ${d.unit || 'seconds'}` },
  break: { label: 'Break', cat: 'flow', icon: OctagonX, color: '#e17055', desc: 'Exit the enclosing loop', outputs: () => [], fields: [], summary: () => 'exit loop' },
  continue: { label: 'Continue', cat: 'flow', icon: SkipForward, color: '#fdcb6e', desc: 'Skip to the next loop iteration', outputs: () => [], fields: [], summary: () => 'next iteration' },
  noop: { label: 'No-op / Merge', cat: 'flow', icon: CircleDot, color: '#b2bec3', desc: 'Pass-through; also a join point after IF branches', fields: [], summary: () => 'pass-through' },
 
 
  // ---- Data
  http_request: { label: 'HTTP Request', cat: 'data', icon: Globe, color: '#2d7ff9', desc: 'Call any REST API. Result: http.status, http.body, http.headers',
    fields: [f('method', 'Method', 'select', { options: opts('GET', 'POST', 'PUT', 'PATCH', 'DELETE'), default: 'GET' }), f('url', 'URL', 'text', { placeholder: 'https://api.example.com/endpoint' }),
      f('headers', 'Headers (JSON)', 'code', { rows: 3, placeholder: '{"Authorization": "Bearer …"}' }),
      f('body', 'Body (JSON)', 'code', { placeholder: '{"key": "{{message.text}}"}', show: (d) => ['POST', 'PUT', 'PATCH', 'DELETE'].includes(d.method) })],
    summary: (d) => `${d.method || 'GET'} ${d.url || ''}` },
  transform: { label: 'Transform', cat: 'data', icon: Wand2, color: '#f0932b', desc: 'Python expression over `input` (the context). Result: transform.result',
    fields: [f('expression', 'Expression', 'code', { rows: 4, placeholder: "input['http']['body']['count'] * 2" })], summary: (d) => d.expression || 'expression' },
  messagebox: { label: 'Message', cat: 'data', icon: MessageSquare, color: '#0abde3', desc: 'Store a message. Result: message.text',
    fields: [f('message', 'Message', 'textarea', { rows: 3, placeholder: 'Hello {{http.body.name}}' })], summary: (d) => d.message || 'message' },
  set: { label: 'Set Fields', cat: 'data', icon: Pencil, color: '#10ac84', desc: 'Write values into the context (dotted keys allowed)',
    fields: [f('fields', 'Fields', 'kv', { add: 'Add field', keyLabel: 'key (e.g. user.name)', valueLabel: 'value' })], summary: (d) => `${(d.fields || []).length} field(s)` },
  json: { label: 'JSON', cat: 'data', icon: Braces, color: '#ee5253', desc: 'Parse / stringify / extract from a context value',
    fields: [f('operation', 'Operation', 'select', { options: opts('parse', 'stringify', 'extract'), default: 'parse' }), f('source', 'Source path', 'text', { placeholder: 'http.body' }),
      f('path', 'Path', 'text', { placeholder: 'items[0].id', show: (d) => d.operation === 'extract' }), f('outputVar', 'Save to', 'text', { default: 'json.result' })],
    summary: (d) => d.operation || 'parse' },
  text: { label: 'Text Template', cat: 'data', icon: Type, color: '#5f27cd', desc: 'Build text from variables',
    fields: [f('template', 'Template', 'textarea', { rows: 5, placeholder: 'Hi {{user.name}}' }), f('outputVar', 'Save to', 'text', { default: 'text.output' })], summary: (d) => d.outputVar || 'text.output' },
  regex: { label: 'Regex', cat: 'data', icon: Regex, color: '#c56cf0', desc: 'Match or replace text',
    fields: [f('source', 'Text', 'text', { placeholder: '{{http.body}}' }), f('pattern', 'Pattern', 'text', { placeholder: '(\\d+)' }),
      f('mode', 'Mode', 'select', { options: opts('match', 'match_all', 'replace'), default: 'match' }), f('replacement', 'Replacement', 'text', { show: (d) => d.mode === 'replace' }), f('outputVar', 'Save to', 'text', { default: 'regex.result' })],
    summary: (d) => d.pattern || 'pattern' },
  datetime: { label: 'Date & Time', cat: 'data', icon: Calendar, color: '#e58e26', desc: 'Current time, add or subtract',
    fields: [f('operation', 'Operation', 'select', { options: opts('now', 'add', 'subtract', 'format'), default: 'now' }), f('value', 'ISO date (blank = now)', 'text', { show: (d) => d.operation !== 'now' }),
      f('amount', 'Amount', 'number', { show: (d) => ['add', 'subtract'].includes(d.operation) }), f('unit', 'Unit', 'select', { options: opts('minutes', 'hours', 'days', 'weeks'), default: 'days', show: (d) => ['add', 'subtract'].includes(d.operation) }),
      f('format', 'Format (strftime)', 'text', { default: '%Y-%m-%d %H:%M:%S' }), f('outputVar', 'Save to', 'text', { default: 'datetime.result' })],
    summary: (d) => d.operation || 'now' },
 
 
    // ---- AI
  aiagent: { label: 'AI Agent', cat: 'ai', icon: Bot, color: '#a55eea', desc: 'Prompt an LLM connection. Result: ai.output (or your variable)',
    fields: [f('connectionId', 'LLM connection', 'llm'), f('systemPrompt', 'System prompt', 'textarea', { rows: 3, default: 'You are a helpful assistant.' }), f('userMessage', 'User message', 'textarea', { rows: 5, placeholder: 'Summarise: {{http.body}}' }),
      f('temperature', 'Temperature', 'number', { default: 0.7, step: 0.1 }), f('maxTokens', 'Max tokens', 'number', { default: 1024 }),
      f('responseFormat', 'Response format', 'select', { options: opts('text', 'json'), default: 'text' }), f('jsonSchema', 'JSON schema', 'code', { show: (d) => d.responseFormat === 'json' }),
      f('outputVar', 'Save to', 'text', { default: 'ai.output' }), f('onError', 'On error', 'select', { options: opts('throw', 'continue', 'fallback'), default: 'throw' }), f('fallbackText', 'Fallback text', 'text', { show: (d) => d.onError === 'fallback' })],
    summary: (d) => d.outputVar || 'ai.output' },
  
  
    // ---- Apps
  email: { label: 'Send Email', cat: 'app', icon: Mail, color: '#ea4b71', desc: 'Email step (the engine currently simulates sending)',
    fields: [f('to', 'To', 'text'), f('subject', 'Subject', 'text'), f('body', 'Body', 'textarea', { rows: 5 })], summary: (d) => d.to || 'no recipient' },
  slack: { label: 'Slack', cat: 'app', icon: Hash, color: '#4a154b', desc: 'Post via incoming webhook',
    fields: [f('webhookUrl', 'Webhook URL', 'secret'), f('text', 'Message', 'textarea', { rows: 4 })], summary: () => 'webhook' },
  discord: { label: 'Discord', cat: 'app', icon: MessageSquare, color: '#5865f2', desc: 'Post via Discord webhook',
    fields: [f('webhookUrl', 'Webhook URL', 'secret'), f('username', 'Bot name', 'text'), f('text', 'Message', 'textarea', { rows: 4 })], summary: (d) => d.username || 'webhook' },
  telegram: { label: 'Telegram', cat: 'app', icon: Send, color: '#229ed9', desc: 'Send a Telegram message',
    fields: [f('botToken', 'Bot token', 'secret'), f('chatId', 'Chat ID', 'text'), f('text', 'Message', 'textarea', { rows: 4 })], summary: (d) => d.chatId || 'chat' },

  gmail_read: { label: 'Gmail: Read', cat: 'app', icon: Inbox, color: '#ea4335',
    desc: 'Read emails that match the filters. Result: gmail.messages (use Loop → For each)',
    fields: [
      f('connectionId', 'Gmail connection', 'integration', { app: 'gmail' }),
      f('from', 'From address contains', 'text', { placeholder: 'boss@company.com' }),
      f('to', 'To address contains', 'text'),
      f('subjectContains', 'Subject contains', 'text', { placeholder: 'invoice' }),
      f('bodyContains', 'Body contains', 'text'),
      f('newerThan', 'Received within', 'select', { default: '', options: opts({ value: '', label: 'Any time' }, { value: '1d', label: 'Last 24 hours' }, { value: '7d', label: 'Last 7 days' }, { value: '30d', label: 'Last 30 days' }) }),
      f('unreadOnly', 'Unread only', 'toggle'),
      f('hasAttachment', 'Has attachment', 'toggle'),
      f('extraQuery', 'Extra Gmail search (advanced)', 'text', { placeholder: 'label:important' }),
      f('folder', 'Folder', 'text', { default: 'INBOX' }),
      f('limit', 'Max emails (up to 50)', 'number', { default: 10 }),
      f('markRead', 'Mark as read after reading', 'toggle'),
      f('downloadAttachments', 'Download attachments', 'toggle'),
      f('outputVar', 'Save to', 'text', { default: 'gmail.messages' })],
    summary: (d) => d.from || d.subjectContains || `latest ${d.limit || 10}` },
  gmail_send: { label: 'Gmail: Send', cat: 'app', icon: Mail, color: '#d93025', desc: 'Send an email, optionally with attachments',
    fields: [
      f('connectionId', 'Gmail connection', 'integration', { app: 'gmail' }),
      f('to', 'To (comma separated)', 'text', { placeholder: '{{email.from}}' }),
      f('cc', 'CC', 'text'), f('bcc', 'BCC', 'text'),
      f('subject', 'Subject', 'text', { placeholder: 'Re: {{email.subject}}' }),
      f('body', 'Body', 'textarea', { rows: 6, placeholder: '{{ai.output}}' }),
      f('html', 'Body is HTML', 'toggle'),
      f('attachments', 'Attachment file paths', 'list', { add: 'Add file path' }),
      f('attachmentsVar', 'Attachments from list (context path)', 'text', { placeholder: 'email.attachments' })],
    summary: (d) => d.to || 'no recipient' },
};

export const getDef = (type) => NODES[type] || NODES.noop;
export const getOutputs = (type, data) => {
  const d = getDef(type);
  return d.outputs ? d.outputs(data || {}) : [{ id: 'main' }];
};
export const defaultData = (type) => {
  const data = {};
  getDef(type).fields.forEach((fl) => { if (fl.default !== undefined) data[fl.key] = fl.default; });
  return data;
};
