import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { LuBell, LuMapPin, LuSearch, LuTicket } from "react-icons/lu";
import { inventoryApi } from "../../api/endpoints";
import { useAuth } from "../../context/AuthContext";
import { useDebouncedValue } from "../../hooks/useDebounce";
import { roleIcon, navIcon } from "../../lib/icons";
import { stamp } from "../../lib/format";

/** Ctrl+K search across devices, sites, tickets and alerts, plus quick navigation. */
export default function CommandPalette({ open, onClose }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState(null);
  const [sel, setSel] = useState(0);
  const input = useRef(null);
  const listRef = useRef(null);
  const term = useDebouncedValue(q.trim(), 180);

  useEffect(() => {
    if (open) { setQ(""); setResults(null); setSel(0); setTimeout(() => input.current?.focus(), 20); }
  }, [open]);

  useEffect(() => {
    if (!open || term.length < 2) { setResults(null); return undefined; }
    let live = true;
    inventoryApi.search(term).then((r) => { if (live) { setResults(r); setSel(0); } }).catch(() => { if (live) setResults(null); });
    return () => { live = false; };
  }, [term, open]);

  const groups = useMemo(() => {
    if (!results) {
      const pages = (user?.nav || []).flatMap((s) => s.items).map((p) => ({ to: p.path, icon: navIcon(p.icon), name: p.label, meta: "" }));
      return [["Go to", pages]];
    }
    return [
      ["Devices", results.devices.map((d) => ({ to: `/devices/${d.id}`, icon: roleIcon(d.role), name: d.name, meta: d.ip || "" }))],
      ["Sites", results.sites.map((s) => ({ to: `/sites/${encodeURIComponent(s.code)}`, icon: LuMapPin, name: `${s.code} ${s.label || ""}`, meta: s.address || "" }))],
      ["Tickets", results.tickets.map((t) => ({ to: `/tickets/${encodeURIComponent(t.number)}`, icon: LuTicket, name: `${t.number} ${t.short_description || ""}`, meta: t.state || "" }))],
      ["Alerts", results.alerts.map((e) => ({ to: `/alerts/${e.id}`, icon: LuBell, name: `${e.name} on ${e.device_name || "—"}`, meta: `${e.severity} ${stamp(e.ts)}` }))],
    ].filter(([, items]) => items.length);
  }, [results, user]);
  const flat = groups.flatMap(([, items]) => items);

  useEffect(() => {
    listRef.current?.querySelector(`[data-idx="${sel}"]`)?.scrollIntoView({ block: "nearest" });
  }, [sel]);

  if (!open) return null;
  const go = (to) => { onClose(); navigate(to); };
  const onKey = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, flat.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Enter" && flat[sel]) { e.preventDefault(); go(flat[sel].to); }
    else if (e.key === "Escape") onClose();
  };

  let idx = -1;
  return createPortal(
    <div className="fixed inset-0 z-[75] flex items-start justify-center bg-[#03121c]/55 p-4 pt-[12vh] backdrop-blur-[2px]"
      role="dialog" aria-modal="true" aria-label="Search" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-xl animate-rise overflow-hidden rounded-2xl border border-line bg-surface shadow-pop">
        <div className="flex items-center gap-3 border-b border-line px-4">
          <LuSearch className="size-5 text-ink-3" aria-hidden />
          <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} aria-label="Search"
            placeholder="Search a device, IP, site code, ticket or alert…" autoComplete="off"
            className="h-14 flex-1 bg-transparent text-[15px] text-ink placeholder:text-ink-3 focus:outline-none" />
        </div>
        <div ref={listRef} className="max-h-[50vh] overflow-y-auto p-2">
          {groups.length === 0 && (
            <p className="px-4 py-8 text-center text-sm text-ink-3">No matches for “{q}”. Try a device name, an IP, a site code or a ticket number.</p>
          )}
          {groups.map(([title, items]) => (
            <div key={title}>
              <div className="px-3 pb-1 pt-2 text-[11px] font-bold uppercase tracking-wider text-ink-3">{title}</div>
              {items.map((it) => {
                idx += 1;
                const i = idx, Icon = it.icon;
                return (
                  <button key={`${title}-${it.to}`} type="button" data-idx={i} onMouseEnter={() => setSel(i)} onClick={() => go(it.to)}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm ${sel === i ? "bg-brand-50 text-brand" : "text-ink"}`}>
                    <Icon className="size-4 flex-none" aria-hidden />
                    <span className="min-w-0 flex-1 truncate">{it.name}</span>
                    <small className="max-w-[40%] truncate text-xs text-ink-3">{it.meta}</small>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-line bg-surface-2 px-4 py-2 text-[11.5px] text-ink-3">
          <span><Kbd>↑</Kbd> <Kbd>↓</Kbd> move</span><span><Kbd>Enter</Kbd> open</span><span><Kbd>Esc</Kbd> close</span>
          <span><Kbd>g</Kbd> then <Kbd>o</Kbd> <Kbd>a</Kbd> <Kbd>d</Kbd> <Kbd>s</Kbd> <Kbd>t</Kbd> to jump</span>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export function Kbd({ children }) {
  return <kbd className="rounded border border-line bg-surface px-1.5 py-px font-mono text-[10.5px] text-ink-2">{children}</kbd>;
}
