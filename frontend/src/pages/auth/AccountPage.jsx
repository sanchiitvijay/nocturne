import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { LuKeyRound } from "react-icons/lu";
import { authApi } from "../../api/endpoints";
import Button from "../../components/ui/Button";
import { Field, FormError, Input } from "../../components/ui/Field";
import KeyValue from "../../components/ui/KeyValue";
import Panel from "../../components/ui/Panel";
import Pill from "../../components/ui/Pill";
import Signal from "../../components/ui/Signal";
import { useAuth } from "../../context/AuthContext";
import { usePage } from "../../context/PageContext";
import { useToast } from "../../context/ToastContext";
import { humanize } from "../../lib/format";

const EMPTY = { current: "", next: "", repeat: "" };

export default function AccountPage() {
  usePage("My account");
  const { user, lookups, refresh, appName } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const min = lookups.password_min_length;

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.current || !form.next) { setError("Fill in your current and new password."); return; }
    if (form.next !== form.repeat) { setError("The new passwords don't match."); return; }
    setBusy(true);
    try {
      await authApi.changePassword(form.current, form.next);
      toast("Password changed.", "ok");
      setForm(EMPTY);
      await refresh();
      if (params.get("first")) navigate("/", { replace: true });
    } catch (ex) {
      setError(ex.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid max-w-5xl gap-4 md:grid-cols-2">
      <Panel title="Profile">
        <KeyValue items={[
          ["Username", <span className="font-mono">{user.username}</span>],
          ["Name", user.display_name || "—"],
          ["Role", user.role_label],
          ["Can do", <div className="flex flex-wrap gap-1">{user.permissions.map((p) => <Pill key={p}>{humanize(p)}</Pill>)}</div>],
        ]} />
      </Panel>
      <Panel title="Change password"
        description={user.must_change ? null : `Use at least ${min} characters with a mix of letters, digits and symbols.`}>
        {user.must_change && <Signal tone="warning" className="mb-4">Set your own password before using {appName}.</Signal>}
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <FormError message={error} />
          <Field label="Current password" htmlFor="pw-cur"><Input id="pw-cur" type="password" autoComplete="current-password" value={form.current} onChange={set("current")} /></Field>
          <Field label="New password" htmlFor="pw-new" hint={min ? `At least ${min} characters.` : undefined}>
            <Input id="pw-new" type="password" autoComplete="new-password" value={form.next} onChange={set("next")} />
          </Field>
          <Field label="Repeat new password" htmlFor="pw-rep"><Input id="pw-rep" type="password" autoComplete="new-password" value={form.repeat} onChange={set("repeat")} /></Field>
          <div><Button type="submit" variant="primary" icon={LuKeyRound} busy={busy}>Change password</Button></div>
        </form>
      </Panel>
    </div>
  );
}
