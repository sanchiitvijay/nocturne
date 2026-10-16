import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useAuth } from "./AuthContext";

const PageCtx = createContext(null);

/** Heading and breadcrumbs shown in the top bar, set by each page. */
export function PageProvider({ children }) {
  const [header, setHeader] = useState({ title: "", crumbs: [] });
  const value = useMemo(() => ({ header, setHeader }), [header]);
  return <PageCtx.Provider value={value}>{children}</PageCtx.Provider>;
}

 
export const usePageHeader = () => useContext(PageCtx).header;

/** Sets the top-bar heading, optional breadcrumbs ([{label, to}]) and the browser tab title. */
 
export function usePage(title, crumbs = []) {
  const { setHeader } = useContext(PageCtx);
  const { appName } = useAuth();
  const crumbKey = JSON.stringify(crumbs);
  useEffect(() => {
    setHeader({ title, crumbs: JSON.parse(crumbKey) });
    document.title = [title, appName].filter(Boolean).join(" · ");
  }, [title, crumbKey, appName, setHeader]);
}
