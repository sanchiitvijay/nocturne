import { useAuth } from "../../context/AuthContext";

/** Severity levels in order (P1 first), from the server's labels. */
export function useSeverityKeys() {
  const { lookups } = useAuth();
  return Object.keys(lookups.severities || {}).sort();
}
