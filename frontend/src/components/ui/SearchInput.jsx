import { useEffect, useState } from "react";
import { LuSearch } from "react-icons/lu";
import { useDebouncedCallback } from "../../hooks/useDebounce";
import { Input } from "./Field";

/** Search box that reports its value after the person pauses typing. */
export default function SearchInput({ value, onSearch, placeholder, label, delay = 300, className = "" }) {
  const [text, setText] = useState(value || "");
  const push = useDebouncedCallback(onSearch, delay);
  useEffect(() => { setText(value || ""); }, [value]);
  return (
    <div className={`relative min-w-[200px] flex-1 ${className}`}>
      <LuSearch className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
      <Input className="pl-9" value={text} aria-label={label || placeholder} placeholder={placeholder}
        onChange={(e) => { setText(e.target.value); push(e.target.value); }} />
    </div>
  );
}
