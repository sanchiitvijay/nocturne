import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import ForbiddenPage from "../../pages/errors/ForbiddenPage";
import Spinner from "../ui/Spinner";

export function FullPageSpinner() {
  return <div className="grid min-h-screen place-items-center text-brand"><Spinner className="size-8" /></div>;
}

/** Signed-in only. People who must change their password are held on the account page. */
export function RequireAuth() {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === "loading") return <FullPageSpinner />;
  if (status !== "authed") {
    const next = location.pathname + location.search;
    return <Navigate to={`/login${next && next !== "/" ? `?next=${encodeURIComponent(next)}` : ""}`} replace />;
  }
  if (user.must_change && location.pathname !== "/account") return <Navigate to="/account?first=1" replace />;
  return <Outlet />;
}

/** Shows the page only when the role has `cap`. */
export function RequireCap({ cap, children }) {
  const { can } = useAuth();
  return can(cap) ? children : <ForbiddenPage />;
}
