// Presentation rules for domain values. Labels for severities, states, sources and roles come from the API
// (session lookups); these helpers only decide colours and fall back gracefully for values they do not know.
import { cap } from "./format";

export const sevColor = (s) => `var(--${String(s || "P3").toLowerCase()})`;
export const categoryColor = (c) => `var(--c-${c || "other"})`;

export const SEV_TONE = {
  P1: "bg-p1-bg text-p1-ink",
  P2: "bg-p2-bg text-p2-ink",
  P3: "bg-p3-bg text-p3-ink",
  P4: "bg-p4-bg text-p4-ink",
};

export const STATE_TONE = {
  new: "bg-brand-50 text-brand",
  acknowledged: "bg-warn-bg text-warn-ink",
  resolved: "bg-good-bg text-good-ink",
};

export const KIND_TONE = {
  INC: "bg-p1-bg text-p1-ink",
  RITM: "bg-brand-50 text-brand",
  TASK: "bg-p4-bg text-p4-ink",
  CHG: "bg-warn-bg text-warn-ink",
};
export const KIND_COLOR = { INC: "var(--p1)", RITM: "var(--brand)", TASK: "var(--p4)", CHG: "var(--warn)" };
export const kindColor = (k) => KIND_COLOR[k] || "var(--steel)";

const ROLE_LABELS = { ups: "UPS", "access point": "Access point", device: "Other device" };
export const roleLabel = (r) => ROLE_LABELS[r] || (r ? cap(r) : "Other device");

// Confidence and score meters share one scale.
export const scoreColor = (v, { high = 60, mid = 35 } = {}) => (v >= high ? "var(--good)" : v >= mid ? "var(--p3)" : "var(--p2)");
export const healthColor = (v) => (v >= 80 ? "var(--good)" : v >= 55 ? "var(--p3)" : v >= 30 ? "var(--p2)" : "var(--p1)");
