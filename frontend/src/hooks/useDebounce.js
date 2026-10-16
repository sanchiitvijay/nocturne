import { useEffect, useMemo, useRef, useState } from "react";

export function useDebouncedValue(value, ms = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

/** Stable debounced callback that always calls the latest `fn`. */
export function useDebouncedCallback(fn, ms = 300) {
  const fnRef = useRef(fn);
  const timer = useRef(null);
  useEffect(() => { fnRef.current = fn; });
  useEffect(() => () => clearTimeout(timer.current), []);
  return useMemo(() => (...args) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => fnRef.current(...args), ms);
  }, [ms]);
}
