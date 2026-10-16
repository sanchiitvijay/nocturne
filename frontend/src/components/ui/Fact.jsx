const TONES = { default: "text-ink-2", hot: "text-p1-ink", link: "text-link", good: "text-good-ink" };

/** Small inline fact with an icon (IP, site, ticket count…). */
export default function Fact({ icon: Icon, tone = "default", mono = false, children, title, className = "" }) {
  return (
    <span title={title} className={`inline-flex min-w-0 items-center gap-1 text-[12.5px] ${TONES[tone]} ${mono ? "font-mono" : ""} ${className}`}>
      {Icon && <Icon className="size-3.5 flex-none" aria-hidden />}
      <span className="truncate">{children}</span>
    </span>
  );
}
