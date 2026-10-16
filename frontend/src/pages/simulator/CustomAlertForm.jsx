import { useEffect, useState } from "react";
import { LuZap } from "react-icons/lu";
import { opsApi } from "../../api/endpoints";
import Button from "../../components/ui/Button";
import { Field, FormError, Input, Select, Textarea } from "../../components/ui/Field";
import Panel from "../../components/ui/Panel";
import SeverityBadge from "../../components/ui/SeverityBadge";
import Signal from "../../components/ui/Signal";
import { useToast } from "../../context/ToastContext";
import { useDebouncedValue } from "../../hooks/useDebounce";
import { cap, compact } from "../../lib/format";
import DevicePicker from "./DevicePicker";

const DEVICE_TOKEN = "{device}";

export default function CustomAlertForm({ options }) {
  const toast = useToast();
  const [form, setForm] = useState({
    device: "", deviceId: null, ip: "", site: "", typeId: options.types[0] ? String(options.types[0].type_id) : "", name: "",
    message: "", severity: "", repeat: "1", gap: "600",
  });
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const sevKeys = Object.keys(options.severities || {}).sort();

  // Preview how the classification rules will treat this alert.
  const previewKey = useDebouncedValue(JSON.stringify([form.typeId, form.name, form.message, form.device]), 250);
  useEffect(() => {
    const [typeId, name, message, device] = JSON.parse(previewKey);
    if (!typeId && !name.trim()) { setPreview(null); return undefined; }
    let live = true;
    opsApi.preview({ type_id: typeId ? Number(typeId) : null, name: name.trim() || null, message: message.replaceAll(DEVICE_TOKEN, device || "DEVICE") })
      .then((p) => { if (live) setPreview(p); }).catch(() => { if (live) setPreview(null); });
    return () => { live = false; };
  }, [previewKey]);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.deviceId && !form.device.trim()) { setError("Pick a device or type a new device name."); return; }
    if (!form.typeId && !form.name.trim()) { setError("Pick an event type or type a custom event name."); return; }
    if (form.message.trim().length < 3) { setError("Write a message of at least 3 characters."); return; }
    const repeat = Number(form.repeat), gap = Number(form.gap);
    if (!Number.isInteger(repeat) || repeat < 1 || repeat > 50) { setError("Repeat must be a whole number from 1 to 50."); return; }
    if (!Number.isFinite(gap) || gap < 0 || gap > 60000) { setError("Gap must be between 0 and 60000 ms."); return; }
    setBusy(true);
    try {
      const r = await opsApi.customAlert({
        device_id: form.deviceId, device_name: form.deviceId ? null : form.device.trim(), ip: form.ip.trim() || null, site_code: form.site.trim() || null,
        type_id: form.typeId ? Number(form.typeId) : null, name: form.name.trim() || null, message: form.message,
        severity: form.severity || null, repeat, interval_ms: gap,
      });
      toast(`${r.created.length} custom alert${r.created.length > 1 ? "s" : ""} sent.`, "ok", { link: { to: `/alerts/${r.created[0].id}`, text: "Triage it" } });
    } catch (ex) {
      setError(ex.message);
    } finally {
      setBusy(false);
    }
  };

  const sev = form.severity || preview?.severity;
  const tone = sev === "P1" ? "critical" : sev === "P2" ? "warning" : "info";
  const actionable = preview && (preview.actionable || (form.severity && ["P1", "P2", "P3"].includes(form.severity)));

  return (
    <Panel title="Trigger a custom alert" description="Send one alert (or a burst) for any device, existing or new. The preview shows how the classification rules will treat it.">
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <FormError message={error} />
        <div className="grid gap-3 md:grid-cols-2">
          <DevicePicker value={form.device} deviceId={form.deviceId} onChange={(device, deviceId) => setForm((f) => ({ ...f, device, deviceId }))} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="IP (new device)" htmlFor="ca-ip"><Input id="ca-ip" className="font-mono" value={form.ip} onChange={set("ip")} placeholder="10.0.0.1" disabled={!!form.deviceId} /></Field>
            <Field label="Site (new device)" htmlFor="ca-site"><Input id="ca-site" value={form.site} onChange={set("site")} placeholder="0412" disabled={!!form.deviceId} /></Field>
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Event type" htmlFor="ca-type">
            <Select id="ca-type" value={form.typeId} onChange={set("typeId")}>
              <option value="">Choose a type…</option>
              {options.types.map((t) => <option key={t.type_id} value={t.type_id}>{t.type_id} {t.name} ({compact(t.n)})</option>)}
            </Select>
          </Field>
          <Field label="Or a custom event name" htmlFor="ca-name"><Input id="ca-name" value={form.name} onChange={set("name")} placeholder="e.g. High CPU Utilization" /></Field>
        </div>
        <Field label={<>Message <span className="font-normal text-ink-3">({DEVICE_TOKEN} is replaced with the device name)</span></>} htmlFor="ca-msg">
          <Textarea id="ca-msg" value={form.message} onChange={set("message")} placeholder={`${DEVICE_TOKEN} has stopped responding (Request Timed Out)`} />
        </Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Severity" htmlFor="ca-sev">
            <Select id="ca-sev" value={form.severity} onChange={set("severity")}>
              <option value="">Decide by rules</option>
              {sevKeys.map((s) => <option key={s} value={s}>{s} {options.severities[s]}</option>)}
            </Select>
          </Field>
          <Field label="Repeat" htmlFor="ca-rep"><Input id="ca-rep" type="number" min={1} max={50} value={form.repeat} onChange={set("repeat")} /></Field>
          <Field label="Gap (ms)" htmlFor="ca-gap"><Input id="ca-gap" type="number" min={0} max={60000} value={form.gap} onChange={set("gap")} /></Field>
        </div>
        <Signal tone={preview ? tone : "info"}>
          {preview ? (
            <span className="flex flex-wrap items-center gap-1">
              Will arrive as <b>{preview.name}</b>: <SeverityBadge severity={sev} /> in <b>{cap(preview.category)}</b>,
              {preview.transition ? <> a <b>{preview.transition}</b> transition</> : " no up/down transition"}, {actionable ? "actionable" : "treated as noise"}.
            </span>
          ) : "Pick an event type or name to preview the classification."}
        </Signal>
        <div><Button type="submit" variant="primary" icon={LuZap} busy={busy}>Send alert</Button></div>
      </form>
    </Panel>
  );
}
