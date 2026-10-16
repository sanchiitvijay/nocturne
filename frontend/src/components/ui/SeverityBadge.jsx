import { useLabels } from "../../context/AuthContext";
import { SEV_TONE } from "../../lib/domain";

/** "P1 Critical" style badge; `short` shows only the level. */
export default function SeverityBadge({ severity, short = false, className = "" }) {
  const labels = useLabels();
  if (!severity) return null;
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-bold ${SEV_TONE[severity] || "bg-surface-3 text-ink-2"} ${className}`}>
      {severity}{!short && labels.severity(severity) !== severity ? ` ${labels.severity(severity)}` : ""}
    </span>
  );
}
