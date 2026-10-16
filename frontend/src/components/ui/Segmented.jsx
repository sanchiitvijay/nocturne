/** Single-choice button group. options: [{value, label, icon, title}] */
export default function Segmented({ options, value, onChange, label, size = "md", tone = "default" }) {
  const onBrand = tone === "onBrand";
  return (
    <div role="group" aria-label={label} className={`inline-flex flex-none rounded-[10px] border p-0.5 ${onBrand ? "border-white/25 bg-white/10" : "border-line bg-surface-2"}`}>
      {options.map((o) => {
        const active = o.value === value;
        const Icon = o.icon;
        return (
          <button
            key={o.value}
            type="button"
            title={o.title || (typeof o.label === "string" ? o.label : undefined)}
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={`inline-flex items-center gap-1.5 rounded-lg font-semibold transition-colors ${size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-[13px]"} ${
              active
                ? onBrand ? "bg-white text-[#00446a]" : "bg-surface text-brand shadow-sm ring-1 ring-line"
                : onBrand ? "text-white/80 hover:text-white" : "text-ink-2 hover:text-ink"
            }`}
          >
            {Icon && <Icon className="size-4" aria-hidden />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
