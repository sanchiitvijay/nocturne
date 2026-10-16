const TONES = {
  good: "bg-good-bg text-good-ink before:bg-good",
  warning: "bg-warn-bg text-warn-ink before:bg-warn",
  critical: "bg-p1-bg text-p1-ink before:bg-p1",
  info: "bg-info-bg text-info-ink before:bg-brand",
};

/** Tinted note with a coloured edge: evidence, warnings, hints. */
export default function Signal({ tone = "info", children, className = "" }) {
  return (
    <div className={`relative overflow-hidden rounded-[10px] py-2.5 pl-4 pr-3 text-[13.5px] before:absolute before:inset-y-0 before:left-0 before:w-1 ${TONES[tone] || TONES.info} ${className}`}>
      {children}
    </div>
  );
}
