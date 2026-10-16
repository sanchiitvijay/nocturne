import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { useToast } from "./ToastContext";

const LiveCtx = createContext(null);
const TOPICS = ["alert", "alert_state", "job", "data", "sim"];
// Pages that already show arriving alerts themselves, so no toast is needed there.
const QUIET_PATHS = ["/alerts", "/simulator"];

/** Server-Sent Events from /api/stream, fanned out to subscribers by topic. */
export function LiveProvider({ children }) {
  const { status } = useAuth();
  const toast = useToast();
  const location = useLocation();
  const [connected, setConnected] = useState(false);
  const [newCount, setNewCount] = useState(0);
  const listeners = useRef(new Map());
  const pathRef = useRef(location.pathname);
  pathRef.current = location.pathname;

  const subscribe = useCallback((topic, fn) => {
    const set = listeners.current.get(topic) || new Set();
    set.add(fn);
    listeners.current.set(topic, set);
    return () => set.delete(fn);
  }, []);

  useEffect(() => {
    if (status !== "authed" || !window.EventSource) return undefined;
    const es = new EventSource("/api/stream");
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    TOPICS.forEach((topic) => es.addEventListener(topic, (m) => {
      let data;
      try { data = JSON.parse(m.data); } catch { return; }
      if (topic === "alert") {
        setNewCount((n) => n + 1);
        const quiet = QUIET_PATHS.some((p) => pathRef.current === p);
        if (data.severity === "P1" && !quiet) {
          toast(`P1 ${data.name} on ${data.device_name || "a device"}`, "alert", { link: { to: `/alerts/${data.id}`, text: "Investigate" } });
        }
      }
      (listeners.current.get(topic) || []).forEach((fn) => fn(data));
    }));
    return () => { es.close(); setConnected(false); };
  }, [status, toast]);

  const resetNew = useCallback(() => setNewCount(0), []);
  const value = useMemo(() => ({ connected, newCount, resetNew, subscribe }), [connected, newCount, resetNew, subscribe]);
  return <LiveCtx.Provider value={value}>{children}</LiveCtx.Provider>;
}

 
export const useLive = () => useContext(LiveCtx);

/** Calls `handler` for every message on `topic`; the latest handler is always used. */
 
export function useLiveEvent(topic, handler) {
  const { subscribe } = useLive();
  const ref = useRef(handler);
  useEffect(() => { ref.current = handler; });
  useEffect(() => subscribe(topic, (d) => ref.current(d)), [subscribe, topic]);
}
