import { useEffect, useRef, useState } from "react";
import { inventoryApi } from "../../api/endpoints";
import { Field, Input } from "../../components/ui/Field";
import { useDebouncedValue } from "../../hooks/useDebounce";
import { roleIcon } from "../../lib/icons";

/** Type to search the inventory; picking a result selects that device, otherwise the text names a new one. */
export default function DevicePicker({ value, deviceId, onChange }) {
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  const term = useDebouncedValue(value.trim(), 200);

  useEffect(() => {
    if (deviceId || term.length < 2) { setResults([]); return undefined; }
    let live = true;
    inventoryApi.search(term).then((r) => { if (live) { setResults(r.devices); setOpen(true); } }).catch(() => { if (live) setResults([]); });
    return () => { live = false; };
  }, [term, deviceId]);

  useEffect(() => {
    const onDown = (e) => { if (!box.current?.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const hint = deviceId ? "Existing device selected." : value.trim() ? "Not in inventory yet: a new device will be created with this name."
    : "New devices get their site from the name (e.g. 0412-City-ST-SW01).";

  return (
    <div ref={box} className="relative">
      <Field label="Device" htmlFor="ca-dev" hint={hint}>
        <Input id="ca-dev" value={value} autoComplete="off" placeholder="Type a name or IP to search, or a new device name"
          onFocus={() => results.length && setOpen(true)}
          onChange={(e) => onChange(e.target.value, null)} />
      </Field>
      {open && results.length > 0 && (
        <div className="absolute inset-x-0 top-[68px] z-20 max-h-60 overflow-y-auto rounded-xl border border-line bg-surface p-1 shadow-pop" role="listbox">
          {results.map((d) => {
            const Icon = roleIcon(d.role);
            return (
              <button key={d.id} type="button" role="option" aria-selected={false}
                onClick={() => { onChange(d.name, d.id); setOpen(false); }}
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm hover:bg-hover">
                <Icon className="size-4 text-brand" /><span className="flex-1 truncate font-mono text-[13px]">{d.name}</span>
                <small className="font-mono text-xs text-ink-3">{d.ip || ""}</small>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
