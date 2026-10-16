import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LuBookOpen, LuChevronDown, LuFileCode, LuLogOut, LuMoon, LuSun, LuUser } from "react-icons/lu";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../context/ThemeContext";

/** Avatar dropdown: account, theme, guide, API docs, sign out. */
export default function UserMenu() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);

  const name = user?.display_name || user?.username || "";
  const item = "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-ink hover:bg-hover hover:no-underline";
  const go = (to) => { setOpen(false); navigate(to); };
  const signOut = async () => { setOpen(false); await logout(); navigate("/login", { replace: true }); };

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open} aria-label="Account menu"
        className="flex items-center gap-1 rounded-full p-0.5 pr-1.5 hover:bg-hover">
        <span className="grid size-8 place-items-center rounded-full bg-brand text-[13px] font-bold text-on-brand">{name.slice(0, 1).toUpperCase()}</span>
        <LuChevronDown className="size-4 text-ink-3" aria-hidden />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-full z-50 mt-2 w-64 animate-rise rounded-xl border border-line bg-surface p-1.5 shadow-pop">
          <div className="border-b border-line px-3 pb-2.5 pt-1.5">
            <div className="truncate font-semibold">{name}</div>
            <div className="truncate text-xs text-ink-3"><span className="font-mono">{user?.username}</span> · {user?.role_label}</div>
          </div>
          <div className="py-1">
            <button type="button" role="menuitem" className={item} onClick={() => go("/account")}><LuUser className="size-4" />My account</button>
            <button type="button" role="menuitem" className={item} onClick={() => { toggleTheme(); setOpen(false); }}>
              {theme === "dark" ? <LuSun className="size-4" /> : <LuMoon className="size-4" />}{theme === "dark" ? "Day theme" : "Night theme"}
            </button>
            <a role="menuitem" className={item} href="/guide" target="_blank" rel="noreferrer" onClick={() => setOpen(false)}><LuBookOpen className="size-4" />Guide</a>
            <a role="menuitem" className={item} href="/api/docs" target="_blank" rel="noreferrer" onClick={() => setOpen(false)}><LuFileCode className="size-4" />API reference</a>
          </div>
          <div className="border-t border-line pt-1">
            <button type="button" role="menuitem" className={`${item} text-p1-ink`} onClick={signOut}><LuLogOut className="size-4" />Sign out</button>
          </div>
        </div>
      )}
    </div>
  );
}
