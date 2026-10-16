/** Definition list: items = [[label, value], …]; falsy entries are skipped. */
export default function KeyValue({ items, className = "" }) {
  return (
    <dl className={`grid grid-cols-[minmax(90px,auto)_1fr] gap-x-4 gap-y-2 text-[13.5px] ${className}`}>
      {items.filter(Boolean).map(([k, v], i) => (
        <div key={`${k}-${i}`} className="contents">
          <dt className="text-ink-3">{k}</dt>
          <dd className="min-w-0 break-words">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
