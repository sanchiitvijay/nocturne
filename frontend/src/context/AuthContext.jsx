import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { setCsrf, setUnauthorizedHandler } from "../api/client";
import { authApi, systemApi } from "../api/endpoints";

const AuthCtx = createContext(null);

/**
 * Session state for the whole app: the signed-in person (with permissions, navigation and UI lookups from
 * /api/auth/me) and the product metadata from /api/meta. status: "loading" | "anon" | "authed".
 */
export function AuthProvider({ children }) {
  const [meta, setMeta] = useState(null);
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");

  const refresh = useCallback(async () => {
    try {
      const me = await authApi.me();
      setCsrf(me.csrf);
      setUser(me);
      setStatus("authed");
      return me;
    } catch {
      setUser(null);
      setStatus("anon");
      return null;
    }
  }, []);

  useEffect(() => {
    systemApi.meta().then(setMeta).catch(() => setMeta(null));
    refresh();
    // Any 401 means the session ended (expired, signed out elsewhere, password reset): drop to the sign-in screen.
    setUnauthorizedHandler(() => { setUser(null); setStatus("anon"); });
    return () => setUnauthorizedHandler(null);
  }, [refresh]);

  useEffect(() => {
    if (meta?.name) document.title = meta.name;
  }, [meta]);

  const login = useCallback(async (username, password) => {
    const r = await authApi.login(username, password);
    setCsrf(r.csrf);
    await refresh();
    return r;
  }, [refresh]);

  const logout = useCallback(async () => {
    try { await authApi.logout(); } catch { /* signed out either way */ }
    setCsrf("");
    setUser(null);
    setStatus("anon");
  }, []);

  const can = useCallback((cap) => !!user?.permissions?.includes(cap), [user]);

  const value = useMemo(() => ({
    meta, user, status, can, login, logout, refresh, lookups: user?.lookups || {},
    appName: meta?.name || "",
  }), [meta, user, status, can, login, logout, refresh]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

 
export const useAuth = () => useContext(AuthCtx);

/** Severity/state/source labels from the server, with the raw value as fallback. */
 
export function useLabels() {
  const { lookups } = useAuth();
  return useMemo(() => ({
    severity: (s) => lookups.severities?.[s] || s || "",
    state: (s) => lookups.states?.[s] || s || "",
    source: (s) => lookups.sources?.[s] || s || "",
    role: (r) => lookups.roles?.[r] || r || "",
  }), [lookups]);
}
