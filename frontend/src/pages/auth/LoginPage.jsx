import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { LuLogIn } from "react-icons/lu";
import Button from "../../components/ui/Button";
import { Field, FormError, Input } from "../../components/ui/Field";
import { useAuth } from "../../context/AuthContext";
import WaveCanvas from "./WaveCanvas";

/** Only follow a "next" that stays on this site ("//evil.com" and "/\evil.com" resolve elsewhere). */
function safeNext(next) {
  try {
    const u = new URL(next || "/", window.location.origin);
    return u.origin === window.location.origin ? u.pathname + u.search + u.hash : "/";
  } catch {
    return "/";
  }
}

export default function LoginPage() {
  const { status, meta, login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (status === "authed" && !busy) return <Navigate to={safeNext(params.get("next"))} replace />;

  const submit = async (e) => {
    e.preventDefault();
    if (!form.username.trim() || !form.password) { setError("Enter your username and password."); return; }
    setError("");
    setBusy(true);
    try {
      const r = await login(form.username.trim(), form.password);
      navigate(r.must_change ? "/account?first=1" : safeNext(params.get("next")), { replace: true });
    } catch (ex) {
      setError(ex.message);
      setBusy(false);
    }
  };
  const name = meta?.name || "";

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.15fr_1fr]">
      <section className="relative hidden flex-col justify-between overflow-hidden bg-[#00446a] p-12 text-white lg:flex">
        <WaveCanvas className="absolute inset-0 h-full w-full" />
        <img src="/static/img/ferguson-logo-white.png" alt={meta?.organisation || ""} className="relative h-9 w-auto self-start" />
        <div className="relative">
          <div className="text-[clamp(48px,7vw,96px)] font-extrabold leading-none tracking-[0.12em]" aria-label={name}>
            {name.split("").map((ch, i) => (
              <span key={i} className="inline-block animate-rise" style={{ animationDelay: `${120 + i * 70}ms` }}>{ch}</span>
            ))}
          </div>
          <p className="mt-6 max-w-md text-lg text-white/80">{meta?.tagline}</p>
        </div>
        <p className="relative text-sm text-white/60">{meta?.organisation}</p>
      </section>
      <section className="flex items-center justify-center p-6">
        <form onSubmit={submit} noValidate className="flex w-full max-w-sm flex-col gap-5">
          <img src="/static/img/ferguson-logo.png" alt={meta?.organisation || ""} className="h-8 w-auto self-start dark:hidden lg:hidden" />
          <div>
            <h1 className="text-2xl">Sign in</h1>
            <p className="mt-1.5 text-sm text-ink-3">Use your {name} account. Ask an administrator if you need one.</p>
          </div>
          <FormError message={error} />
          <Field label="Username" htmlFor="login-user">
            <Input id="login-user" name="username" autoComplete="username" autoFocus value={form.username}
              onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} />
          </Field>
          <Field label="Password" htmlFor="login-pass">
            <Input id="login-pass" name="password" type="password" autoComplete="current-password" value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
          </Field>
          <Button type="submit" variant="primary" icon={LuLogIn} busy={busy} className="h-11 justify-center">
            {busy ? "Signing in…" : "Sign in"}
          </Button>
          <p className="text-xs text-ink-3">{meta?.organisation}{meta?.organisation ? " · " : ""}Network Operations Center</p>
        </form>
      </section>
    </div>
  );
}
