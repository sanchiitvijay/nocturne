import { useState } from "react";
import { LuClock, LuKeyRound, LuUserPlus, LuUsers } from "react-icons/lu";
import { adminApi } from "../../api/endpoints";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import ErrorState from "../../components/ui/ErrorState";
import Fact from "../../components/ui/Fact";
import { Select } from "../../components/ui/Field";
import Panel from "../../components/ui/Panel";
import Pill from "../../components/ui/Pill";
import { SkeletonList } from "../../components/ui/Skeleton";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useAction } from "../../hooks/useAction";
import { stamp } from "../../lib/format";
import { AddUserModal, ResetPasswordModal } from "./UserFormModals";

function UserCard({ u, roles, isMe, onChanged, onReset }) {
  const toast = useToast();
  const [patch, busy] = useAction(async (body, message) => {
    await adminApi.editUser(u.id, body);
    toast(message, "ok");
    onChanged();
  });
  const name = u.display_name || u.username;
  return (
    <div className="flex gap-3 rounded-2xl border border-line p-4">
      <span className="grid size-10 flex-none place-items-center rounded-full bg-brand font-bold text-on-brand">{name.slice(0, 1).toUpperCase()}</span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div>
          <h3 className="truncate text-[15px]">{name}{isMe && <span className="ml-1.5 text-xs font-normal text-ink-3">(you)</span>}</h3>
          <div className="flex flex-wrap gap-x-3 text-xs text-ink-2"><span className="font-mono">{u.username}</span><span>{roles[u.role] || u.role}</span></div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone={u.active ? "good" : "bad"}>{u.active ? "Active" : "Disabled"}</Pill>
          {u.must_change ? <Pill>Must change password</Pill> : null}
          <Fact icon={LuClock}>{u.last_login_at ? `Last in ${stamp(u.last_login_at)}` : "Never signed in"}</Fact>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select aria-label={`Role for ${u.username}`} className="h-8 w-auto text-[13px]" value={u.role} disabled={busy}
            onChange={(e) => patch({ role: e.target.value }, "Role updated.")}>
            {Object.entries(roles).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
          <Button size="sm" disabled={busy || isMe} title={isMe ? "You cannot disable your own account" : undefined}
            onClick={() => patch({ active: !u.active }, u.active ? "Account disabled." : "Account enabled.")}>{u.active ? "Disable" : "Enable"}</Button>
          <Button size="sm" icon={LuKeyRound} onClick={() => onReset(u)}>Reset password</Button>
        </div>
      </div>
    </div>
  );
}

export default function UsersTab({ state }) {
  const { user: me } = useAuth();
  const { data, error, reload } = state;
  const [adding, setAdding] = useState(false);
  const [resetting, setResetting] = useState(null);
  const refresh = () => reload({ background: true });

  return (
    <Panel title="People" description="New accounts must change their password at first sign-in."
      actions={<Button size="sm" variant="primary" icon={LuUserPlus} disabled={!data} onClick={() => setAdding(true)}>Add person</Button>}>
      {error && !data ? <ErrorState error={error} onRetry={() => reload()} />
        : !data ? <SkeletonList className="h-36" />
          : data.users.length === 0 ? <EmptyState icon={LuUsers} title="No people yet" />
            : (
              <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
                {data.users.map((u) => <UserCard key={u.id} u={u} roles={data.roles} isMe={u.id === me.id} onChanged={refresh} onReset={setResetting} />)}
              </div>
            )}
      {data && <AddUserModal open={adding} onClose={() => setAdding(false)} roles={data.roles} onSaved={refresh} />}
      <ResetPasswordModal user={resetting} onClose={() => setResetting(null)} onSaved={refresh} />
    </Panel>
  );
}
