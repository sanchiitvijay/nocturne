// Number, date and duration formatting. Timestamps arrive from the API as "YYYY-MM-DD HH:MM:SS" (server local time).

const nf = new Intl.NumberFormat();
const compactNf = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 });

export const num = (n) => (n === null || n === undefined || Number.isNaN(n) ? "—" : nf.format(n));
export const compact = (n) => (n === null || n === undefined ? "—" : n >= 10000 ? compactNf.format(n) : nf.format(n));
export const pad2 = (n) => String(n).padStart(2, "0");
export const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");
export const humanize = (s) => String(s ?? "").replace(/_/g, " ");
export const plural = (n, word, many = `${word}s`) => `${num(n)} ${n === 1 ? word : many}`;

export function parseTs(ts) {
  if (!ts) return null;
  const d = new Date(String(ts).replace(" ", "T"));
  return Number.isNaN(d.getTime()) ? null : d;
}

export const time = (ts) => (ts ? String(ts).slice(11, 19) || "—" : "—");
export const hhmm = (ts) => (ts ? String(ts).slice(11, 16) : "");

export function date(ts) {
  const d = parseTs(ts);
  if (!d) return "—";
  const sameYear = d.getFullYear() === new Date().getFullYear();
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: sameYear ? undefined : "numeric" });
}

export const stamp = (ts) => (ts ? `${date(ts)}, ${hhmm(ts)}` : "—");
export const span = (r) => (r && r.first ? `${date(r.first)} – ${date(r.last)}` : "—");

export function age(seconds) {
  if (seconds === null || seconds === undefined) return "";
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  return `${Math.floor(seconds / 86400)} d ago`;
}

export function dur(minutes) {
  if (minutes === null || minutes === undefined) return "—";
  if (minutes < 1) return `${Math.round(minutes * 60)} s`;
  if (minutes < 90) return `${Math.round(minutes)} min`;
  if (minutes < 60 * 48) return `${(minutes / 60).toFixed(minutes < 600 ? 1 : 0)} h`;
  return `${Math.round(minutes / 1440)} d`;
}

export const pct = (part, whole) => (whole ? Math.round((100 * (part || 0)) / whole) : 0);

// Anonymised exports carry numeric-only addresses; those are hidden rather than shown as noise.
export const address = (a) => (a && /[A-Za-z]{3,}/.test(a) ? a : "");
