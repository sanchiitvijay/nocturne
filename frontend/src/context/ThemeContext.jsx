import { createContext, useCallback, useContext, useMemo, useState } from "react";

const ThemeCtx = createContext(null);
const root = document.documentElement;

function store(key, value) {
  try { localStorage.setItem(key, value); } catch { /* storage unavailable */ }
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => root.getAttribute("data-theme") || "light");
  const [mini, setMini] = useState(() => root.getAttribute("data-side") === "mini");

  const toggleTheme = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      store("nocturne-theme", next);
      return next;
    });
  }, []);

  const toggleSidebar = useCallback(() => {
    setMini((m) => {
      const next = !m;
      if (next) root.setAttribute("data-side", "mini"); else root.removeAttribute("data-side");
      store("nocturne-side", next ? "mini" : "full");
      return next;
    });
  }, []);

  const value = useMemo(() => ({ theme, toggleTheme, mini, toggleSidebar }), [theme, toggleTheme, mini, toggleSidebar]);
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>;
}

 
export const useTheme = () => useContext(ThemeCtx);
