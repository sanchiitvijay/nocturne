import { useEffect, useState } from "react";
import { LuSlidersHorizontal, LuX } from "react-icons/lu";
import { useDebouncedCallback } from "../../hooks/useDebounce";

/**
 * A compact row of search fields that filter as you type. The first `primary` fields are always shown;
 * the rest sit behind "More filters" and open automatically when one of them already holds a value.
 */
export default function SearchFilters({ fields, values, onChange, primary = 2, delay = 300, children }) {
  const [local, setLocal] = useState(values);
  const push = useDebouncedCallback(onChange, delay);
  const hidden = fields.slice(primary);
  const hiddenActive = hidden.filter((f) => values[f.id]).length;
  const [open, setOpen] = useState(hiddenActive > 0);

  // Re-sync only when the committed values really change (e.g. back button, a link), not on every parent render.
  const committed = JSON.stringify(values);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setLocal(values); if (hiddenActive) setOpen(true); }, [committed]);

  const type = (id, value) => {
    const next = { ...local, [id]: value };
    setLocal(next);
    push(next);
  };
  // Apply at once, and re-arm the debounce with the same value so a keystroke still pending cannot land afterwards.
  const commit = (next) => { setLocal(next); onChange(next); push(next); };
  const anyActive = fields.some((f) => local[f.id]);
  const shown = open ? fields : fields.slice(0, primary);

  return (
    <div className="flex flex-wrap items-center gap-2">
      {shown.map((f, i) => (
        <label key={f.id} className={`relative w-full sm:w-auto sm:flex-1 ${i === 0 ? "sm:min-w-[220px] sm:max-w-[320px]" : "sm:min-w-[150px] sm:max-w-[220px]"}`}>
          <span className="sr-only">{f.label}</span>
          {f.icon && <f.icon className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-3" aria-hidden />}
          <input
            value={local[f.id] || ""}
            onChange={(e) => type(f.id, e.target.value)}
            placeholder={f.placeholder || f.label}
            title={f.label}
            inputMode={f.numeric ? "numeric" : undefined}
            className={`h-9 w-full rounded-[10px] border bg-surface pr-8 text-[13px] text-ink placeholder:text-ink-3 transition-colors focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus/25 ${
              f.icon ? "pl-8" : "pl-3"} ${local[f.id] ? "border-brand-200" : "border-line"}`}
          />
          {local[f.id] && (
            <button type="button" onClick={() => commit({ ...local, [f.id]: "" })} aria-label={`Clear ${f.label}`} title={`Clear ${f.label}`}
              className="absolute right-1.5 top-1/2 grid size-6 -translate-y-1/2 place-items-center rounded-md text-ink-3 hover:bg-hover hover:text-ink">
              <LuX className="size-3.5" />
            </button>
          )}
        </label>
      ))}
      {hidden.length > 0 && (
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
          className={`inline-flex h-9 items-center gap-1.5 rounded-[10px] border px-3 text-[13px] font-semibold transition-colors ${
            open ? "border-brand-200 bg-brand-50 text-brand" : "border-line bg-surface text-ink-2 hover:border-line-strong hover:text-ink"}`}>
          <LuSlidersHorizontal className="size-4" aria-hidden />
          {open ? "Fewer fields" : "More fields"}
          {!open && hiddenActive > 0 && <span className="grid h-5 min-w-5 place-items-center rounded-full bg-brand px-1 text-[11px] text-on-brand">{hiddenActive}</span>}
        </button>
      )}
      {anyActive && (
        <button type="button" onClick={() => commit(Object.fromEntries(fields.map((f) => [f.id, ""])))}
          className="h-9 rounded-[10px] px-2 text-[13px] font-semibold text-ink-3 hover:text-ink">
          Clear
        </button>
      )}
      {children}
    </div>
  );
}
