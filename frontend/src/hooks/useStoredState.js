import { useCallback, useState } from "react";

/** A preference kept in localStorage; falls back to memory when storage is blocked. */
export function useStoredState(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? initial : JSON.parse(raw);
    } catch {
      return initial;
    }
  });
  const set = useCallback((next) => {
    setValue((prev) => {
      const v = typeof next === "function" ? next(prev) : next;
      try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* storage unavailable */ }
      return v;
    });
  }, [key]);
  return [value, set];
}
