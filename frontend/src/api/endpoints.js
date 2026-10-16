// Every backend endpoint the app uses, grouped like the FastAPI routers (app/api/*.py).
import { qs, request } from "./client";

const enc = encodeURIComponent;

export const systemApi = {
  meta: () => request("/api/meta", { background: true }),
};

export const authApi = {
  me: () => request("/api/auth/me", { background: true }),
  login: (username, password) => request("/api/auth/login", { method: "POST", body: { username, password } }),
  logout: () => request("/api/auth/logout", { method: "POST" }),
  changePassword: (current, next) => request("/api/auth/password", { method: "POST", body: { current, new: next } }),
};

export const alertsApi = {
  list: (params, opts) => request(`/api/alerts${qs(params)}`, opts),
  exportUrl: (params) => `/api/alerts/export.csv${qs(params)}`,
  detail: (id, opts) => request(`/api/alerts/${id}`, opts),
  analysis: (id) => request(`/api/alerts/${id}/analysis`),
  history: (id) => request(`/api/alerts/${id}/history`),
  checks: (id) => request(`/api/alerts/${id}/checks`, { method: "POST" }),
  recommendation: (id) => request(`/api/alerts/${id}/recommendation`),
  askAi: (id, refresh = false) => request(`/api/alerts/${id}/ai`, { method: "POST", body: { refresh } }),
  setState: (id, state, note = null) => request(`/api/alerts/${id}/state`, { method: "POST", body: { state, note } }),
  bulkState: (ids, state) => request("/api/alerts/bulk-state", { method: "POST", body: { ids, state } }),
  feedback: (id, verdict, ticketNumber = null) =>
    request(`/api/alerts/${id}/feedback`, { method: "POST", body: { verdict, ticket_number: ticketNumber } }),
};

export const inventoryApi = {
  overview: (params, opts) => request(`/api/insights/overview${qs(params)}`, opts),
  devices: (params) => request(`/api/devices${qs(params)}`),
  device: (id) => request(`/api/devices/${enc(id)}`),
  sites: (params) => request(`/api/sites${qs(params)}`),
  site: (code) => request(`/api/sites/${enc(code)}`),
  tickets: (params) => request(`/api/tickets${qs(params)}`),
  ticket: (number) => request(`/api/tickets/${enc(number)}`),
  search: (q, opts) => request(`/api/search${qs({ q })}`, { background: true, ...opts }),
};

export const opsApi = {
  diagnostics: (host) => request("/api/diagnostics", { method: "POST", body: { host } }),
  simOptions: () => request("/api/sim/options"),
  simRun: (body) => request("/api/sim/run", { method: "POST", body }),
  simStop: () => request("/api/sim/stop", { method: "POST" }),
  customAlert: (body) => request("/api/sim/custom", { method: "POST", body }),
  preview: (body) => request("/api/sim/preview", { method: "POST", body, background: true }),
};

export const dataApi = {
  summary: (opts) => request("/api/data/summary", opts),
  upload: (files) => {
    const form = new FormData();
    [...files].forEach((f) => form.append("files", f));
    return request("/api/data/uploads", { method: "POST", form });
  },
  jobs: (opts) => request("/api/data/jobs", opts),
  job: (id) => request(`/api/data/jobs/${enc(id)}`),
  runJob: (id, body) => request(`/api/data/jobs/${enc(id)}/run`, { method: "POST", body }),
  cancelJob: (id) => request(`/api/data/jobs/${enc(id)}/cancel`, { method: "POST" }),
  deleteJob: (id) => request(`/api/data/jobs/${enc(id)}`, { method: "DELETE" }),
  rejectsUrl: (id) => `/api/data/jobs/${enc(id)}/rejects.csv`,
  catalog: (opts) => request("/api/data/catalog", opts),
  editType: (typeId, body) => request(`/api/data/catalog/${enc(typeId)}`, { method: "PUT", body }),
  resync: () => request("/api/data/resync", { method: "POST" }),
  purges: () => request("/api/data/purges"),
  purge: (scope, confirm) => request("/api/data/purge", { method: "POST", body: { scope, confirm } }),
};

export const adminApi = {
  users: () => request("/api/admin/users"),
  createUser: (body) => request("/api/admin/users", { method: "POST", body }),
  editUser: (id, body) => request(`/api/admin/users/${id}`, { method: "PATCH", body }),
  resetPassword: (id, password) => request(`/api/admin/users/${id}/reset`, { method: "POST", body: { password } }),
  audit: (params) => request(`/api/admin/audit${qs(params)}`),
  settings: () => request("/api/admin/settings"),
};
