import { Fragment } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LuChevronRight, LuMenu, LuSearch, LuTerminal } from "react-icons/lu";
import { useAuth } from "../../context/AuthContext";
import { useLive } from "../../context/LiveContext";
import { usePageHeader } from "../../context/PageContext";
import { Kbd } from "./CommandPalette";
import UserMenu from "./UserMenu";

export default function Topbar({ onMenu, onSearch, onCheck }) {
  const { can } = useAuth();
  const { connected, newCount, resetNew } = useLive();
  const { title, crumbs } = usePageHeader();
  const navigate = useNavigate();
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

  return (
    <header className="sticky top-0 z-40 flex h-16 items-center gap-2 border-b border-line bg-surface/90 px-3 backdrop-blur sm:gap-3 sm:px-6">
      <button type="button" onClick={onMenu} className="grid size-10 place-items-center rounded-[10px] text-ink-2 hover:bg-hover lg:hidden" aria-label="Open navigation">
        <LuMenu className="size-5" />
      </button>
      <div className="flex min-w-0 flex-1 items-center gap-1.5 text-sm">
        {crumbs.map((c) => (
          <Fragment key={c.to}>
            <Link to={c.to} className="hidden truncate text-ink-3 sm:inline">{c.label}</Link>
            <LuChevronRight className="hidden size-4 flex-none text-ink-3 sm:inline" aria-hidden />
          </Fragment>
        ))}
        <strong className="truncate text-[15px]">{title}</strong>
      </div>
      <button type="button" onClick={onSearch} aria-label="Search everything"
        className="flex h-10 items-center gap-2 rounded-[10px] border border-line bg-surface-2 px-3 text-sm text-ink-3 hover:border-line-strong md:w-72">
        <LuSearch className="size-4" />
        <span className="hidden flex-1 text-left md:inline">Search devices, sites, tickets…</span>
        <span className="hidden md:inline"><Kbd>{isMac ? "⌘" : "Ctrl"} K</Kbd></span>
      </button>
      {can("run_diagnostics") && (
        <button type="button" onClick={onCheck} title="Run a network check" aria-label="Run a network check"
          className="grid size-10 place-items-center rounded-[10px] text-ink-2 hover:bg-hover">
          <LuTerminal className="size-5" />
        </button>
      )}
      <button type="button" title={connected ? "Live alert stream connected: select to see the newest alerts" : "Live stream reconnecting…"}
        onClick={() => { resetNew(); navigate("/alerts?window=24h"); }}
        className="flex h-10 items-center gap-2 rounded-full border border-line px-3 text-[13px] font-semibold text-ink-2 hover:bg-hover">
        <span className={`size-2.5 rounded-full ${connected ? "animate-ping-soft bg-good" : "bg-line-strong"}`} />
        <span className="hidden sm:inline">Live</span>
        {newCount > 0 && <b className="grid h-5 min-w-5 place-items-center rounded-full bg-p1 px-1.5 text-[11px] text-white">{newCount}</b>}
      </button>
      <UserMenu />
    </header>
  );
}
