import { useCallback, useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import CommandPalette from "./CommandPalette";
import NetworkCheckModal from "./NetworkCheckModal";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

// "g" then a letter jumps to a page.
const JUMPS = { o: "/", a: "/alerts", d: "/devices", s: "/sites", t: "/tickets" };

export default function AppLayout() {
  const [drawer, setDrawer] = useState(false);
  const [palette, setPalette] = useState(false);
  const [check, setCheck] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const gPending = useRef(false);

  useEffect(() => { setDrawer(false); }, [location.pathname]);

  const onKey = useCallback((e) => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "") || document.activeElement?.isContentEditable;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette(true); return; }
    if (typing || e.ctrlKey || e.metaKey || e.altKey || document.querySelector('[aria-modal="true"]')) return;
    if (e.key === "/") { e.preventDefault(); setPalette(true); return; }
    if (gPending.current) {
      gPending.current = false;
      const to = JUMPS[e.key.toLowerCase()];
      if (to) navigate(to);
      return;
    }
    if (e.key.toLowerCase() === "g") { gPending.current = true; setTimeout(() => { gPending.current = false; }, 900); }
  }, [navigate]);

  useEffect(() => {
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onKey]);

  return (
    <div className="flex min-h-screen">
      <Sidebar mobileOpen={drawer} onNavigate={() => setDrawer(false)} />
      {drawer && <div className="fixed inset-0 z-40 bg-[#03121c]/50 lg:hidden" onClick={() => setDrawer(false)} aria-hidden />}
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setDrawer(true)} onSearch={() => setPalette(true)} onCheck={() => setCheck(true)} />
        <main className="mx-auto w-full max-w-[1600px] flex-1 px-3 py-5 sm:px-6 sm:py-6">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
      <NetworkCheckModal open={check} onClose={() => setCheck(false)} />
    </div>
  );
}
