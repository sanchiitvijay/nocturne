import { LuLoaderCircle } from "react-icons/lu";

export default function Spinner({ className = "size-5" }) {
  return <LuLoaderCircle className={`animate-spin ${className}`} aria-label="Loading" />;
}
