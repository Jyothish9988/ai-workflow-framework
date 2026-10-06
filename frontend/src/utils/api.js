import axios from 'axios';

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: API_BASE_URL, headers: { 'Content-Type': 'application/json' } });

// ---------- auth token handling ----------
export const setAuthToken = (token) => {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
    localStorage.setItem('authToken', token);
  } else {
    delete api.defaults.headers.common.Authorization;
    localStorage.removeItem('authToken');
  }
  window.dispatchEvent(new Event('auth-change'));
};

export const initializeAuth = () => {
  const t = localStorage.getItem('authToken');
  if (t) api.defaults.headers.common.Authorization = `Bearer ${t}`;
};

// Force logout on expired / invalid token
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && localStorage.getItem('authToken')) setAuthToken(null);
    return Promise.reject(err);
  }
);

// Backend often answers 200 with { error } — normalise into a thrown Error
const unwrap = (res) => {
  if (res?.data?.error) throw new Error(res.data.error);
  return res;
};

// FastAPI validation errors (422) come back as a list of { msg, loc } objects
export const errMsg = (e, fallback = 'Something went wrong') => {
  const d = e?.response?.data?.detail;
  if (Array.isArray(d)) return d.map((x) => x.msg).join('; ');
  return d?.toString?.() || e?.response?.data?.message || e?.message || fallback;
};

// ---------- auth ----------
export const authAPI = {
  register: (username, email, password) => api.post('/register', { username, email, password }).then(unwrap),
  login: (email, password) => api.post('/login', { email, password }).then(unwrap),
  logout: () => api.post('/logout'),
};

// ---------- workflows (collection routes use trailing slash to avoid 307 redirects) ----------
export const workflowAPI = {
  getAll: () => api.get('/workflows/'),
  getById: (id) => api.get(`/workflows/${id}`),
  create: (data) => api.post('/workflows/', data),
  update: (id, data) => api.patch(`/workflows/${id}`, data),
  delete: (id) => api.delete(`/workflows/${id}`),
  save: (id, nodes, edges) => api.post(`/workflows/${id}/save`, { nodes, edges }),
};

// ---------- executions (all scoped to a workflow on the backend) ----------
export const executionAPI = {
  execute: (wid) => api.post(`/workflows/${wid}/execute`),
  list: (wid, params = {}) => api.get(`/workflows/${wid}/executions`, { params: { limit: 50, ...params } }),
  stats: (wid) => api.get(`/workflows/${wid}/executions/stats`),
  get: (wid, id) => api.get(`/workflows/${wid}/executions/${id}`),
  nodes: (wid, id) => api.get(`/workflows/${wid}/executions/${id}/nodes`),
  remove: (wid, id) => api.delete(`/workflows/${wid}/executions/${id}`),
  cancel: (wid, id) => api.post(`/workflows/${wid}/executions/${id}/cancel`),
};

/** No global executions endpoint exists — aggregate across workflows. */
export const fetchAllExecutions = async (workflows, perWorkflow = 25) => {
  const lists = await Promise.all(
    workflows.map((w) =>
      executionAPI
        .list(w.id, { limit: perWorkflow })
        .then((r) => (r.data?.data || []).map((e) => ({ ...e, workflow_id: e.workflow_id || w.id, workflow_name: w.name })))
        .catch(() => [])
    )
  );
  return lists.flat().sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
};

// ---------- schedules ----------
// ScheduleCreate: { freq, cron, time, day, enabled }
export const scheduleBody = ({ cron, timezone = 'UTC', enabled = true }) => ({
  freq: 'custom',
  cron,
  timezone,
  enabled,
});

export const schedulerAPI = {
  getAll: () => api.get('/schedules/'),
  getByWorkflow: (wid) => api.get(`/schedules/workflow/${wid}`),
  upsert: (wid, data) => api.post(`/schedules/${wid}`, scheduleBody(data)),
  patch: (id, data) => api.patch(`/schedules/${id}`, data),
  delete: (id) => api.delete(`/schedules/${id}`),
  // Starts the schedule's workflow immediately; resolves { execution_id, status }
  run: (id) => api.post(`/schedules/${id}/run-now`),
};

 export const llmAPI = {
  list: () => api.get('/llm-connections/'),
  create: (data) => api.post('/llm-connections/', data),
  test: (data) => api.post('/llm-connections/test', data),
  remove: (id) => api.delete(`/llm-connections/${id}`),
  pullUrl: (model) => `${API_BASE_URL}/ollama/pull/${encodeURIComponent(model)}`,
};

export const integrationAPI = {
  list: () => api.get('/integrations/'),
  create: (data) => api.post('/integrations/', data),
  update: (id, data) => api.put(`/integrations/${id}`, data),
  remove: (id) => api.delete(`/integrations/${id}`),
  test: (id) => api.post(`/integrations/${id}/test`),
  testDraft: (data) => api.post('/integrations/test', data),
};


// ---------- node packages visible to every user (admin-uploaded .exe / .dll nodes) ----------
export const packageAPI = { list: () => api.get('/packages') };

// ---------- admin (backend enforces is_admin on every /admin route) ----------
const multipart = { headers: { 'Content-Type': 'multipart/form-data' } };
export const adminAPI = {
  me: () => api.get('/me'),
  stats: () => api.get('/admin/stats'),
  users: (params) => api.get('/admin/users', { params }),
  createUser: (data) => api.post('/admin/users', data),
  updateUser: (id, data) => api.patch(`/admin/users/${id}`, data),
  deleteUser: (id) => api.delete(`/admin/users/${id}`),
  runs: (params) => api.get('/admin/runs', { params }),
  runNodes: (id, includeData = false) => api.get(`/admin/runs/${id}/nodes`, { params: { include_data: includeData } }),
  terminateRun: (id) => api.post(`/admin/runs/${id}/terminate`),
  packages: () => api.get('/admin/packages'),
  createPackage: (body) => api.post('/admin/packages', body),   // { manifest, access, user_ids, is_active }
  updatePackage: (id, body) => api.put(`/admin/packages/${id}`, body),
  deletePackage: (id) => api.delete(`/admin/packages/${id}`),
};


export default api;