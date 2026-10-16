import { useState } from "react";
import { LuArrowDown, LuArrowUp, LuCheck, LuClock, LuRotateCcw, LuShieldCheck } from "react-icons/lu";
import Button from "../../components/ui/Button";
import { Field, Textarea } from "../../components/ui/Field";
import Modal from "../../components/ui/Modal";
import Pill from "../../components/ui/Pill";
import SeverityBadge from "../../components/ui/SeverityBadge";
import { useAuth, useLabels } from "../../context/AuthContext";
import { STATE_TONE, sevColor } from "../../lib/domain";
import { categoryIcon } from "../../lib/icons";
import { cap, date, time } from "../../lib/format";

export default function TriageHero({ event: e, busy, onState, children }) {
  const { can } = useAuth();
  const labels = useLabels();
  const [resolving, setResolving] = useState(false);
  const [note, setNote] = useState("");
  const CatIcon = categoryIcon(e.category);

  const resolve = async () => {
    const ok = await onState("resolved", note.trim() || null);
    if (ok) { setResolving(false); setNote(""); }
  };

  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-surface">
      <div className="h-1.5" style={{ background: sevColor(e.severity) }} />
      <div className="flex flex-wrap items-start gap-4 p-4 sm:p-6">
        <div className="min-w-0 flex-1">
          <div className="mb-2.5 flex flex-wrap items-center gap-2">
            <SeverityBadge severity={e.severity} />
            <Pill icon={CatIcon}>{cap(e.category)}</Pill>
            {e.transition === "down" && <Pill tone="bad" icon={LuArrowDown}>Down transition</Pill>}
            {e.transition === "up" && <Pill tone="good" icon={LuArrowUp}>Recovery</Pill>}
            <Pill tone={STATE_TONE[e.state]}>{labels.state(e.state)}{e.owner ? ` by ${e.owner}` : ""}</Pill>
            {e.source !== "import" && <Pill tone={e.source === "simulation" ? "striped" : "dashed"}>{labels.source(e.source)}</Pill>}
            {!e.actionable && <Pill title="Category or severity marks this as noise">Noise</Pill>}
          </div>
          <h1 className="text-[clamp(20px,2.4vw,28px)]">{e.name}</h1>
          <div className="mt-1 text-sm text-ink-2">
            <span className="font-mono">{e.device_name || "No device"}</span>
            {e.ip && <> <span className="text-ink-3">at</span> <span className="font-mono">{e.ip}</span></>}
            {e.site_code && <> <span className="text-ink-3">in site</span> {e.site_code}{e.site_label ? ` ${e.site_label}` : ""}</>}
          </div>
          {e.message && <p className="mt-3 rounded-xl bg-surface-2 p-3 font-mono text-[13px] text-ink-2">{e.message}</p>}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-ink-3">
            <span className="flex items-center gap-1"><LuClock className="size-4" />{e.ts ? `${date(e.ts)} at ${time(e.ts)}` : "Time unknown"}</span>
            {e.status_label && <span>Node status {e.status_label}</span>}
            <span>Event ID {e.source_id}</span>
          </div>
          {e.state_note && <p className="mt-2 text-[13px] text-ink-2"><b>Note:</b> {e.state_note}</p>}
        </div>
        {can("update_alert_state") && (
          <div className="flex flex-wrap gap-2">
            {e.state !== "acknowledged" && e.state !== "resolved" && (
              <Button variant="primary" icon={LuCheck} disabled={busy} onClick={() => onState("acknowledged")}>Acknowledge</Button>
            )}
            {e.state !== "resolved" && <Button icon={LuShieldCheck} disabled={busy} onClick={() => setResolving(true)}>Resolve</Button>}
            {e.state !== "new" && <Button variant="subtle" icon={LuRotateCcw} disabled={busy} onClick={() => onState("new")}>Reopen</Button>}
          </div>
        )}
      </div>
      <div className="px-4 pb-3 sm:px-6">{children}</div>
      <Modal open={resolving} onClose={() => setResolving(false)} title="Resolve alert"
        footer={<>
          <Button onClick={() => setResolving(false)}>Cancel</Button>
          <Button variant="primary" icon={LuShieldCheck} busy={busy} onClick={resolve}>Resolve</Button>
        </>}>
        <p className="mb-3 text-sm text-ink-3">Add what fixed it. Notes help the next analyst.</p>
        <Field label="Resolution note (optional)" htmlFor="resolve-note">
          <Textarea id="resolve-note" value={note} onChange={(ev) => setNote(ev.target.value)} placeholder="What was done to fix it" />
        </Field>
      </Modal>
    </section>
  );
}
