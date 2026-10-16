import { LuCheck, LuRotateCcw, LuShieldCheck } from "react-icons/lu";
import Button from "../../components/ui/Button";

/** Floating bar for acting on the selected alerts. */
export default function BulkBar({ count, busy, onApply, onClear }) {
  if (!count) return null;
  return (
    <div className="fixed inset-x-3 bottom-4 z-40 mx-auto flex max-w-3xl animate-rise flex-wrap items-center gap-2 rounded-2xl border border-line bg-surface p-3 shadow-pop sm:inset-x-6">
      <b className="mr-2 text-sm">{count} selected</b>
      <Button size="sm" icon={LuCheck} disabled={busy} onClick={() => onApply("acknowledged")}>Acknowledge</Button>
      <Button size="sm" icon={LuShieldCheck} disabled={busy} onClick={() => onApply("resolved")}>Resolve</Button>
      <Button size="sm" icon={LuRotateCcw} disabled={busy} onClick={() => onApply("new")}>Reopen</Button>
      <span className="flex-1" />
      <Button size="sm" variant="subtle" onClick={onClear}>Clear selection</Button>
    </div>
  );
}
