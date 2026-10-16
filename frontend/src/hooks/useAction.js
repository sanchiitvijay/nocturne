import { useCallback, useRef, useState } from "react";
import { useToast } from "../context/ToastContext";

/**
 * Wraps a user action (button, form submit): tracks `busy`, prevents double submits and turns API errors into a
 * toast instead of an uncaught rejection. Returns the action's result, or undefined when it failed.
 */
export function useAction(fn, { errorToast = true } = {}) {
  const [busy, setBusy] = useState(false);
  const running = useRef(false);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const toast = useToast();

  const run = useCallback(async (...args) => {
    if (running.current) return undefined;
    running.current = true;
    setBusy(true);
    try {
      return await fnRef.current(...args);
    } catch (e) {
      if (errorToast) toast(e?.message || "Something went wrong.", "error");
      return undefined;
    } finally {
      running.current = false;
      setBusy(false);
    }
  }, [toast, errorToast]);

  return [run, busy];
}
