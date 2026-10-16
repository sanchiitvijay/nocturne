// Thin fetch wrapper: session cookie, CSRF header on writes, uniform errors, and a global in-flight counter
// that drives the top progress bar.

let csrf = document.querySelector('meta[name="csrf"]')?.content || "";
let onUnauthorized = null;
let inflight = 0;
const inflightListeners = new Set();

export const setCsrf = (token) => { csrf = token || ""; };
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

export function subscribeInflight(fn) {
  inflightListeners.add(fn);
  return () => inflightListeners.delete(fn);
}
function bump(delta) {
  inflight = Math.max(0, inflight + delta);
  inflightListeners.forEach((fn) => fn(inflight));
}

export class ApiError extends Error {
  constructor(message, status = 0, data = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

/** Query string from an object; skips empty values and joins arrays with commas (the API's multi-value format). */
export function qs(params = {}) {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length)) return;
    p.set(k, Array.isArray(v) ? v.join(",") : String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : "";
}

/**
 * @param {string} path
 * @param {{method?: string, body?: unknown, form?: FormData, background?: boolean, signal?: AbortSignal}} options
 * background: true keeps the progress bar still (live refreshes, polling, type-ahead).
 */
export async function request(path, { method = "GET", body, form, background = false, signal } = {}) {
  const headers = {};
  const init = { method, headers, credentials: "same-origin", signal };
  if (method !== "GET") headers["X-CSRF-Token"] = csrf;
  if (form) init.body = form;
  else if (body !== undefined) {
    init.body = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }
  if (!background) bump(1);
  try {
    let res;
    try {
      res = await fetch(path, init);
    } catch (e) {
      if (e.name === "AbortError") throw e;
      throw new ApiError("The server could not be reached. Check your connection and try again.");
    }
    const type = res.headers.get("content-type") || "";
    const data = type.includes("json") ? await res.json().catch(() => null) : await res.text();
    if (res.status === 401 && onUnauthorized) onUnauthorized();
    if (!res.ok) {
      const message = (data && typeof data === "object" && data.error) || `Request failed (${res.status}).`;
      throw new ApiError(message, res.status, data);
    }
    return data;
  } finally {
    if (!background) bump(-1);
  }
}
