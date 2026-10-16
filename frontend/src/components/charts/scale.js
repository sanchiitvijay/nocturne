// Shared chart maths.

/** A round axis maximum at or above `max`. */
export function niceMax(max) {
  if (max <= 5) return 5;
  const p = 10 ** Math.floor(Math.log10(max));
  const m = max / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
}

/** Bar with a rounded data end and a square baseline. */
export function barPath(x, y, w, h, r = 4) {
  r = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

export const axisText = { fill: "var(--text-3)", fontSize: 11 };
export const gridLine = { stroke: "var(--border)", strokeWidth: 1 };
export const baseLine = { stroke: "var(--border-strong)", strokeWidth: 1 };
