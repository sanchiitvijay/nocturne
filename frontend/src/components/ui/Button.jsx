import { Link } from "react-router-dom";
import Spinner from "./Spinner";

const VARIANTS = {
  primary: "bg-brand text-on-brand border-brand hover:bg-brand-600 hover:border-brand-600",
  ghost: "bg-surface text-ink border-line hover:bg-hover hover:border-line-strong",
  subtle: "bg-transparent text-ink-2 border-transparent hover:bg-hover hover:text-ink",
  danger: "bg-p1 text-white border-p1 hover:opacity-90",
  onBrand: "bg-white/10 text-white border-white/30 hover:bg-white/20",
};
const SIZES = {
  sm: "h-8 px-2.5 text-[13px] gap-1.5 rounded-lg",
  md: "h-10 px-3.5 text-sm gap-2 rounded-[10px]",
  icon: "size-10 justify-center rounded-[10px]",
  iconSm: "size-8 justify-center rounded-lg",
};

export function buttonClass({ variant = "ghost", size = "md", className = "" } = {}) {
  return `inline-flex flex-none items-center whitespace-nowrap border font-semibold transition-colors no-underline hover:no-underline
    disabled:cursor-not-allowed disabled:opacity-55 ${VARIANTS[variant] || VARIANTS.ghost} ${SIZES[size] || SIZES.md} ${className}`;
}

/**
 * Button with a busy state. Pass `to` for an in-app link, `href` for a plain link (downloads, server pages).
 */
export default function Button({ variant, size, icon: Icon, busy = false, disabled, className, children, to, href, type = "button", ...rest }) {
  const cls = buttonClass({ variant, size, className });
  const content = (
    <>
      {busy ? <Spinner className="size-4" /> : Icon ? <Icon className="size-4 flex-none" aria-hidden /> : null}
      {children}
    </>
  );
  if (to) return <Link to={to} className={cls} {...rest}>{content}</Link>;
  if (href) return <a href={href} className={cls} {...rest}>{content}</a>;
  return (
    <button type={type} className={cls} disabled={disabled || busy} aria-busy={busy || undefined} {...rest}>
      {content}
    </button>
  );
}
