import { NavLink, Link } from "react-router-dom";
import { LuPanelLeft } from "react-icons/lu";
import { useAuth } from "../../context/AuthContext";
import { useLive } from "../../context/LiveContext";
import { useTheme } from "../../context/ThemeContext";
import { navIcon } from "../../lib/icons";

/** Main navigation. Sections and pages come from the server for the signed-in role. */
export default function Sidebar({ mobileOpen, onNavigate }) {
  const { user, meta } = useAuth();
  const { newCount } = useLive();
  const { mini, toggleSidebar, theme } = useTheme();
  const logo = theme === "dark" ? "/static/img/ferguson-logo-white.png" : "/static/img/ferguson-logo.png";
  const collapsed = mini && !mobileOpen;

  return (
    <aside aria-label="Main navigation"
      className={`fixed inset-y-0 left-0 z-50 flex flex-none flex-col border-r border-line bg-surface transition-[width,transform] duration-200 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
        mobileOpen ? "translate-x-0 shadow-pop" : "-translate-x-full"} ${collapsed ? "w-[72px]" : "w-[248px]"}`}>
      <Link to="/" onClick={onNavigate} className={`flex h-16 flex-none items-center gap-3 border-b border-line text-ink hover:no-underline ${collapsed ? "justify-center px-0" : "px-5"}`}
        aria-label={`${meta?.name || ""} home`}>
        {collapsed
          ? <img src="/static/img/ferguson-mark.png" alt="" className="size-8" />
          : <span className="flex min-w-0 flex-col gap-1">
              {/* The logo is ~8:1, so it sits above the product name; side by side it left no room for the name. */}
              <img src={logo} alt={meta?.organisation || ""} className="h-3.5 w-auto self-start" />
              <b className="text-[17px] font-extrabold leading-none tracking-[0.16em] text-ink">{meta?.name}</b>
              <small className="truncate text-[11px] leading-tight text-ink-3" title={meta?.tagline}>{meta?.tagline}</small>
            </span>}
      </Link>
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {(user?.nav || []).map((section) => (
          <div key={section.title} className="mb-4">
            {!collapsed && <div className="mb-1.5 px-3 text-[11px] font-bold uppercase tracking-[0.12em] text-ink-3">{section.title}</div>}
            {section.items.map((item) => {
              const Icon = navIcon(item.icon);
              return (
                <NavLink key={item.id} to={item.path} end={item.path === "/"} onClick={onNavigate} title={item.label}
                  className={({ isActive }) => `relative mb-0.5 flex items-center gap-3 rounded-[10px] py-2.5 text-sm font-semibold hover:no-underline ${
                    collapsed ? "justify-center px-0" : "px-3"} ${isActive ? "bg-brand-50 text-brand" : "text-ink-2 hover:bg-hover hover:text-ink"}`}>
                  <Icon className="size-[18px] flex-none" aria-hidden />
                  {!collapsed && <span>{item.label}</span>}
                  {item.id === "alerts" && newCount > 0 && (
                    <b className={`grid h-5 min-w-5 place-items-center rounded-full bg-p1 px-1.5 text-[11px] text-white ${collapsed ? "absolute right-1 top-0.5" : "ml-auto"}`}>{newCount}</b>
                  )}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="hidden border-t border-line p-3 lg:block">
        <button type="button" onClick={toggleSidebar} title={collapsed ? "Expand the sidebar" : "Collapse the sidebar"}
          className={`flex w-full items-center gap-3 rounded-[10px] py-2 text-[13px] font-semibold text-ink-3 hover:bg-hover hover:text-ink ${collapsed ? "justify-center" : "px-3"}`}>
          <LuPanelLeft className={`size-[18px] ${collapsed ? "-scale-x-100" : ""}`} aria-hidden />
          {!collapsed && "Collapse sidebar"}
        </button>
      </div>
    </aside>
  );
}
