import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Runs `fn` whenever `deps` change and keeps the latest result. Results of superseded calls are dropped, so a slow
 * response never overwrites a newer one. `reload({ background: true })` refreshes without clearing the data.
 */
export function useAsync(fn, deps = [], { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled });
  const seq = useRef(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback(async ({ background = false } = {}) => {
    const id = ++seq.current;
    if (!background) setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fnRef.current({ background });
      if (id === seq.current) setState({ data, error: null, loading: false });
      return data;
    } catch (error) {
      if (id === seq.current && error?.name !== "AbortError") setState((s) => ({ ...s, error, loading: false }));
      return undefined;
    }
  }, []);

  useEffect(() => {
    if (enabled) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, run, ...deps]);

  const setData = useCallback((update) => setState((s) => ({ ...s, data: typeof update === "function" ? update(s.data) : update })), []);
  return { ...state, reload: run, setData };
}
