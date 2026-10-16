import { useState } from "react";
import { LuChevronDown, LuDownload, LuHash, LuLayoutGrid, LuList, LuMapPin, LuMessageSquare, LuNetwork, LuServer, LuX } from "react-icons/lu";
import Button from "../../components/ui/Button";
import { Chip, ChipRow } from "../../components/ui/Chip";
import { Select } from "../../components/ui/Field";
import SearchFilters from "../../components/ui/SearchFilters";
import Segmented from "../../components/ui/Segmented";
import { useAuth, useLabels } from "../../context/AuthContext";
import { categoryColor, sevColor } from "../../lib/domain";
import { cap, pad2 } from "../../lib/format";

const SORTS = [["newest", "Newest first"], ["oldest", "Oldest first"], ["severity", "Most severe first"]];
const SHOW = [["1", "Actionable"], ["", "Everything"], ["0", "Noise"]];
const FACETS = ["severity", "category", "state", "source"];

const SEARCH_FIELDS = [
  { id: "text", label: "Message text", placeholder: "Search alert text…", icon: LuMessageSquare },
  { id: "event_id", label: "Event ID", placeholder: "Event ID", icon: LuHash, numeric: true },
  { id: "device", label: "Device", placeholder: "Device name", icon: LuServer },
  { id: "ip", label: "IP address", placeholder: "IP, e.g. 10.14", icon: LuNetwork },
  { id: "site", label: "Site code", placeholder: "Site, e.g. 0412", icon: LuMapPin },
];

/** Keys to show for a facet: the known order (if any), plus anything selected or counted. */
function facetKeys(facet = {}, selected = [], order) {
  const keys = new Set([...Object.keys(facet), ...selected]);
  if (order) return [...order.filter((k) => keys.has(k)), ...[...keys].filter((k) => !order.includes(k))];
  return [...keys].sort((a, b) => (facet[b] || 0) - (facet[a] || 0));
}

export default function AlertFilters({ filters, setFilters, facets, view, setView, exportHref }) {
  const { lookups, can } = useAuth();
  const labels = useLabels();
  const activeFacets = FACETS.reduce((n, k) => n + filters[k].length, 0);
  const [showFacets, setShowFacets] = useState(activeFacets > 0);

  const toggle = (key, value) => {
    const cur = filters[key];
    setFilters({ [key]: cur.includes(value) ? cur.filter((x) => x !== value) : [...cur, value], page: 1 });
  };
  const facetRow = (key, label, order, swatch, text) => (
    <ChipRow label={label}>
      {facetKeys(facets?.[key], filters[key], order).map((k) => (
        <Chip key={k} on={filters[key].includes(k)} onClick={() => toggle(key, k)} swatch={swatch?.(k)} count={facets?.[key]?.[k] || 0}>{text(k)}</Chip>
      ))}
    </ChipRow>
  );
  const pins = [
    filters.device_id && ["device_id", `Device #${filters.device_id}`],
    filters.type_id && ["type_id", `Event type ${filters.type_id}`],
    filters.hour !== "" && ["hour", `Hour ${pad2(filters.hour)}:00`],
  ].filter(Boolean);

  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-3 sm:p-4">
      <SearchFilters fields={SEARCH_FIELDS} values={Object.fromEntries(SEARCH_FIELDS.map((f) => [f.id, filters[f.id]]))}
        onChange={(v) => setFilters({ ...v, q: "", page: 1 })} />

      <div className="flex flex-wrap items-center gap-2">
        <Segmented size="sm" label="Time window" value={filters.window} onChange={(w) => setFilters({ window: w, page: 1 })}
          options={(lookups.windows || []).map((w) => ({ value: w.id, label: w.label }))} />
        <Segmented size="sm" label="Show" value={filters.actionable} onChange={(v) => setFilters({ actionable: v, page: 1 })}
          options={SHOW.map(([v, l]) => ({ value: v, label: l }))} />
        <button type="button" onClick={() => setShowFacets((s) => !s)} aria-expanded={showFacets}
          className={`inline-flex h-8 items-center gap-1.5 rounded-[10px] border px-3 text-[13px] font-semibold transition-colors ${
            showFacets || activeFacets ? "border-brand-200 bg-brand-50 text-brand" : "border-line bg-surface text-ink-2 hover:text-ink"}`}>
          Severity &amp; more
          {activeFacets > 0 && <span className="grid h-5 min-w-5 place-items-center rounded-full bg-brand px-1 text-[11px] text-on-brand">{activeFacets}</span>}
          <LuChevronDown className={`size-4 transition-transform ${showFacets ? "rotate-180" : ""}`} aria-hidden />
        </button>
        <div className="ml-auto flex items-center gap-2">
          <Select className="h-8 w-auto text-[13px]" aria-label="Sort" value={filters.sort} onChange={(e) => setFilters({ sort: e.target.value, page: 1 })}>
            {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </Select>
          <Segmented size="sm" label="Layout" value={view} onChange={setView}
            options={[{ value: "cards", label: "", icon: LuLayoutGrid, title: "Cards" }, { value: "compact", label: "", icon: LuList, title: "Compact list" }]} />
          {can("export_data") && <Button size="sm" href={exportHref} icon={LuDownload} download>Export</Button>}
        </div>
      </div>

      {showFacets && (
        <div className="flex flex-col gap-2 border-t border-line pt-3">
          {facetRow("severity", "Severity", Object.keys(lookups.severities || {}), sevColor, (k) => `${k} ${labels.severity(k)}`)}
          {facetRow("category", "Category", null, categoryColor, cap)}
          {facetRow("state", "State", Object.keys(lookups.states || {}), null, labels.state)}
          {facetRow("source", "Source", Object.keys(lookups.sources || {}), null, labels.source)}
        </div>
      )}
      {pins.length > 0 && (
        <ChipRow label="Pinned">
          {pins.map(([k, l]) => <Chip key={k} on onClick={() => setFilters({ [k]: "", page: 1 })} trailing={LuX} title="Remove this filter">{l}</Chip>)}
        </ChipRow>
      )}
    </section>
  );
}
