import { LuSearch } from "react-icons/lu";

export default function EmptyState({ icon: Icon = LuSearch, title, text, action, className = "" }) {
  return (
    <div className={`flex flex-col items-center gap-2 px-4 py-10 text-center ${className}`}>
      <span className="grid size-12 place-items-center rounded-2xl bg-brand-50 text-brand"><Icon className="size-6" aria-hidden /></span>
      <h3 className="mt-1 text-base">{title}</h3>
      {text && <p className="max-w-md text-[13.5px] text-ink-3">{text}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
