import { LuHistory, LuSettings, LuShield, LuUsers } from "react-icons/lu";
import { adminApi } from "../../api/endpoints";
import Segmented from "../../components/ui/Segmented";
import { useAuth } from "../../context/AuthContext";
import { usePage } from "../../context/PageContext";
import { useAsync } from "../../hooks/useAsync";
import { useUrlState } from "../../hooks/useUrlState";
import AuditTab from "./AuditTab";
import RolesTab from "./RolesTab";
import SettingsTab from "./SettingsTab";
import UsersTab from "./UsersTab";

const TABS = [
  { value: "users", label: "People", icon: LuUsers },
  { value: "roles", label: "Roles", icon: LuShield },
  { value: "audit", label: "Audit trail", icon: LuHistory, cap: "view_audit" },
  { value: "settings", label: "Settings", icon: LuSettings, cap: "view_settings" },
];

export default function AdminPage() {
  usePage("Admin");
  const { can } = useAuth();
  const tabs = TABS.filter((t) => !t.cap || can(t.cap));
  const [{ tab }, setUrl] = useUrlState({ tab: "users" });
  const current = tabs.some((t) => t.value === tab) ? tab : "users";
  const users = useAsync(() => adminApi.users(), []);

  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-x-auto"><Segmented label="Admin sections" options={tabs} value={current} onChange={(t) => setUrl({ tab: t })} /></div>
      {current === "users" && <UsersTab state={users} />}
      {current === "roles" && <RolesTab state={users} />}
      {current === "audit" && <AuditTab />}
      {current === "settings" && <SettingsTab />}
    </div>
  );
}
