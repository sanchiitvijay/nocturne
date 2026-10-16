import { useEffect, useState } from "react";
import { LuKeyRound, LuUserPlus } from "react-icons/lu";
import { adminApi } from "../../api/endpoints";
import Button from "../../components/ui/Button";
import { Field, FormError, Input, Select } from "../../components/ui/Field";
import Modal from "../../components/ui/Modal";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";

function passwordHint(min) {
  return min ? `At least ${min} characters, mixing letters, digits and symbols.` : "Mix letters, digits and symbols.";
}

export function AddUserModal({ open, onClose, roles, onSaved }) {
  const { lookups } = useAuth();
  const toast = useToast();
  const roleKeys = Object.keys(roles);
  const blank = { username: "", display_name: "", role: roleKeys[roleKeys.length - 1] || "", password: "" };
  const [form, setForm] = useState(blank);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (open) { setForm(blank); setError(""); } }, [open]);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e?.preventDefault();
    if (!form.username.trim() || !form.password) { setError("Enter a username and a temporary password."); return; }
    setBusy(true);
    setError("");
    try {
      await adminApi.createUser({ ...form, username: form.username.trim(), display_name: form.display_name.trim() || null });
      toast("Person added.", "ok");
      onSaved();
      onClose();
    } catch (ex) {
      setError(ex.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Add person"
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon={LuUserPlus} busy={busy} onClick={submit}>Add person</Button></>}>
      <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
        <FormError message={error} />
        <Field label="Username" htmlFor="nu-user"><Input id="nu-user" autoComplete="off" value={form.username} onChange={set("username")} /></Field>
        <Field label="Display name" htmlFor="nu-name"><Input id="nu-name" value={form.display_name} onChange={set("display_name")} /></Field>
        <Field label="Role" htmlFor="nu-role">
          <Select id="nu-role" value={form.role} onChange={set("role")}>{roleKeys.map((k) => <option key={k} value={k}>{roles[k]}</option>)}</Select>
        </Field>
        <Field label="Temporary password" htmlFor="nu-pass" hint={passwordHint(lookups.password_min_length)}>
          <Input id="nu-pass" type="password" autoComplete="new-password" value={form.password} onChange={set("password")} />
        </Field>
        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}

export function ResetPasswordModal({ user, onClose, onSaved }) {
  const { lookups } = useAuth();
  const toast = useToast();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setPassword(""); setError(""); }, [user]);

  const submit = async (e) => {
    e?.preventDefault();
    if (!password) { setError("Enter a temporary password."); return; }
    setBusy(true);
    setError("");
    try {
      await adminApi.resetPassword(user.id, password);
      toast("Password reset.", "ok");
      onSaved();
      onClose();
    } catch (ex) {
      setError(ex.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={!!user} onClose={onClose} title={user ? `Reset password for ${user.username}` : ""}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon={LuKeyRound} busy={busy} onClick={submit}>Reset</Button></>}>
      <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
        <p className="text-sm text-ink-3">They will be asked to change it at next sign-in, and their open sessions end now.</p>
        <FormError message={error} />
        <Field label="Temporary password" htmlFor="rp-pass" hint={passwordHint(lookups.password_min_length)}>
          <Input id="rp-pass" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
      </form>
    </Modal>
  );
}
