import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * Filter state kept in the URL so views can be bookmarked and shared. `schema` maps each key to its default;
 * array defaults make the key a comma-separated list. Updates replace the history entry.
 */
export function useUrlState(schema) {
  const [params, setParams] = useSearchParams();
  const key = JSON.stringify(schema);

  const state = useMemo(() => {
    const out = {};
    Object.entries(schema).forEach(([k, def]) => {
      const raw = params.get(k);
      if (Array.isArray(def)) out[k] = raw === null ? def : raw.split(",").filter(Boolean);
      else if (typeof def === "number") out[k] = raw === null || Number.isNaN(Number(raw)) ? def : Number(raw);
      else out[k] = raw === null ? def : raw;
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, key]);

  const update = useCallback((patch) => {
    setParams((prev) => {
      const current = {};
      Object.keys(schema).forEach((k) => { if (prev.has(k)) current[k] = prev.get(k); });
      const resolved = typeof patch === "function" ? patch(state) : patch;
      const next = new URLSearchParams();
      Object.entries({ ...current, ...resolved }).forEach(([k, v]) => {
        const def = schema[k];
        const value = Array.isArray(v) ? v.join(",") : v === null || v === undefined ? "" : String(v);
        const defValue = Array.isArray(def) ? def.join(",") : String(def ?? "");
        if (value !== defValue) next.set(k, value);
      });
      return next;
    }, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setParams, state, key]);

  return [state, update];
}
