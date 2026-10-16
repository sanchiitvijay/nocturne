const TONES = {
  neutral: "bg-surface-3 text-ink-2",
  brand: "bg-brand-50 text-brand",
  good: "bg-good-bg text-good-ink",
  bad: "bg-p1-bg text-p1-ink",
  warn: "bg-warn-bg text-warn-ink",
  orange: "bg-p2-bg text-p2-ink",
  dashed: "bg-brand-50 text-brand border border-dashed border-brand-200",
  striped: "text-ink-2 border border-line bg-[repeating-linear-gradient(135deg,var(--surface-3)_0_6px,var(--surface)_6px_12px)]",
};

export default function Pill({ tone = "neutral", className = "", icon: Icon, children, title, ...rest }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone] || tone} ${className}`} {...rest}>
      {Icon && <Icon className="size-3.5" aria-hidden />}
      {children}
    </span>
  );
}
