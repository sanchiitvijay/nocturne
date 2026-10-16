import { useState } from "react";
import { LuPlay, LuTriangleAlert } from "react-icons/lu";
import { opsApi } from "../../api/endpoints";
import { useAuth } from "../../context/AuthContext";
import { useAction } from "../../hooks/useAction";
import ChecksResult from "../diagnostics/ChecksResult";
import Button from "../ui/Button";
import { Field, Input } from "../ui/Field";
import Modal from "../ui/Modal";
import Pill from "../ui/Pill";

/** Ad-hoc ping / traceroute / DNS / port check against a device IP or host name. */
export default function NetworkCheckModal({ open, onClose }) {
  const { lookups } = useAuth();
  const [host, setHost] = useState("");
  const [result, setResult] = useState(null);
  const [run, busy] = useAction(async () => setResult(await opsApi.diagnostics(host.trim())));
  const simulated = lookups.diagnostics_mode !== "live";

  return (
    <Modal open={open} onClose={onClose} title="Network check" width="max-w-2xl">
      <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); if (host.trim()) run(); }}>
        <Field label="Device IP or host name" htmlFor="nc-host" className="min-w-[220px] flex-1">
          <Input id="nc-host" className="font-mono" value={host} onChange={(e) => setHost(e.target.value)} placeholder="10.20.30.1" autoComplete="off" />
        </Field>
        <Button type="submit" variant="primary" icon={LuPlay} busy={busy} disabled={!host.trim()}>Run checks</Button>
      </form>
      <div className="mt-3">
        {simulated
          ? <Pill tone="warn" icon={LuTriangleAlert} title="Diagnostics mode is 'simulated' in nocturne.toml">Simulated results</Pill>
          : <Pill tone="good">Live from server</Pill>}
      </div>
      {result && <div className="mt-4"><ChecksResult checks={result} /></div>}
    </Modal>
  );
}
