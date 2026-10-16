import { LuChevronLeft, LuChevronRight } from "react-icons/lu";

/** Page buttons with ellipses; hidden when everything fits on one page. */
export default function Pager({ total, page, size, onPage }) {
  const pages = Math.max(1, Math.ceil((total || 0) / (size || 1)));
  if (pages <= 1) return null;
  const nums = [...new Set([1, pages, page - 2, page - 1, page, page + 1, page + 2])].filter((p) => p >= 1 && p <= pages).sort((a, b) => a - b);
  const go = (p) => { onPage(p); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const btn = "inline-grid h-9 min-w-9 place-items-center rounded-lg border px-2 text-sm font-semibold transition-colors disabled:opacity-40";
  const items = [];
  nums.forEach((p, i) => {
    if (i && p - nums[i - 1] > 1) items.push(<span key={`gap${p}`} className="px-1 text-ink-3">…</span>);
    items.push(
      <button key={p} type="button" onClick={() => go(p)} aria-current={p === page ? "page" : undefined}
        className={`${btn} ${p === page ? "border-brand bg-brand text-on-brand" : "border-line bg-surface hover:bg-hover"}`}>
        {p}
      </button>,
    );
  });
  return (
    <nav className="mt-5 flex flex-wrap items-center justify-center gap-1.5" aria-label="Pages">
      <button type="button" className={`${btn} border-line bg-surface hover:bg-hover`} disabled={page <= 1} onClick={() => go(page - 1)} aria-label="Previous page">
        <LuChevronLeft className="size-4" />
      </button>
      {items}
      <button type="button" className={`${btn} border-line bg-surface hover:bg-hover`} disabled={page >= pages} onClick={() => go(page + 1)} aria-label="Next page">
        <LuChevronRight className="size-4" />
      </button>
    </nav>
  );
}
