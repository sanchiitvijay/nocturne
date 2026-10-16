import { useState } from "react";
import { LuZap } from "react-icons/lu";
import AlertCard from "../../components/cards/AlertCard";
import EmptyState from "../../components/ui/EmptyState";
import Panel from "../../components/ui/Panel";
import Pill from "../../components/ui/Pill";
import { useLive, useLiveEvent } from "../../context/LiveContext";

const MAX = 80;

/** Every alert arriving on the stream while this page is open. */
export default function LiveFeed() {
  const { resetNew } = useLive();
  const [items, setItems] = useState([]);
  const [received, setReceived] = useState(0);
  useLiveEvent("alert", (e) => {
    setItems((xs) => [{ ...e, tickets: 0, repeats: 1 }, ...xs.filter((x) => x.id !== e.id)].slice(0, MAX));
    setReceived((n) => n + 1);
    resetNew();
  });
  return (
    <Panel className="xl:sticky xl:top-20" title="Live feed" description="Every alert arriving on the stream, from any source."
      actions={<Pill>{received} received</Pill>}>
      {items.length ? (
        <div className="flex max-h-[70vh] flex-col gap-1.5 overflow-y-auto pr-1">
          {items.map((e, i) => <AlertCard key={e.id} alert={e} compact fresh={i === 0} />)}
        </div>
      ) : <EmptyState icon={LuZap} title="Waiting for alerts" text="Start a scenario or send a custom alert." />}
    </Panel>
  );
}
