import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import { RequireAuth, RequireCap } from "./components/layout/Guards";
import ProgressBar from "./components/ui/ProgressBar";
import { AuthProvider } from "./context/AuthContext";
import { LiveProvider } from "./context/LiveContext";
import { PageProvider } from "./context/PageContext";
import { ThemeProvider } from "./context/ThemeContext";
import { ToastProvider } from "./context/ToastContext";
import AdminPage from "./pages/admin/AdminPage";
import AlertsPage from "./pages/alerts/AlertsPage";
import AccountPage from "./pages/auth/AccountPage";
import LoginPage from "./pages/auth/LoginPage";
import DashboardPage from "./pages/dashboard/DashboardPage";
import DataStudioPage from "./pages/data/DataStudioPage";
import DevicePage from "./pages/devices/DevicePage";
import DevicesPage from "./pages/devices/DevicesPage";
import NotFoundPage from "./pages/errors/NotFoundPage";
import SimulatorPage from "./pages/simulator/SimulatorPage";
import SitePage from "./pages/sites/SitePage";
import SitesPage from "./pages/sites/SitesPage";
import TicketPage from "./pages/tickets/TicketPage";
import TicketsPage from "./pages/tickets/TicketsPage";
import TriagePage from "./pages/triage/TriagePage";

// Each route names the capability it needs (the same names as [permissions] in nocturne.toml).
const ROUTES = [
  { path: "/", cap: "view_dashboard", element: <DashboardPage /> },
  { path: "/alerts", cap: "view_alerts", element: <AlertsPage /> },
  { path: "/alerts/:id", cap: "investigate", element: <TriagePage /> },
  { path: "/devices", cap: "view_inventory", element: <DevicesPage /> },
  { path: "/devices/:id", cap: "view_inventory", element: <DevicePage /> },
  { path: "/sites", cap: "view_inventory", element: <SitesPage /> },
  { path: "/sites/:code", cap: "view_inventory", element: <SitePage /> },
  { path: "/tickets", cap: "view_tickets", element: <TicketsPage /> },
  { path: "/tickets/:number", cap: "view_tickets", element: <TicketPage /> },
  { path: "/simulator", cap: "simulate", element: <SimulatorPage /> },
  { path: "/data", cap: "ingest_data", element: <DataStudioPage /> },
  { path: "/admin", cap: "manage_users", element: <AdminPage /> },
];

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <ToastProvider>
          <AuthProvider>
            <LiveProvider>
              <PageProvider>
                <ProgressBar />
                <Routes>
                  <Route path="/login" element={<LoginPage />} />
                  <Route element={<RequireAuth />}>
                    <Route element={<AppLayout />}>
                      <Route path="/account" element={<AccountPage />} />
                      {ROUTES.map((r) => <Route key={r.path} path={r.path} element={<RequireCap cap={r.cap}>{r.element}</RequireCap>} />)}
                      <Route path="*" element={<NotFoundPage />} />
                    </Route>
                  </Route>
                </Routes>
              </PageProvider>
            </LiveProvider>
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
