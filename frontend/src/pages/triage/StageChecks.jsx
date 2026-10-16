import ChecksResult from "../../components/diagnostics/ChecksResult";
import Signal from "../../components/ui/Signal";

export default function StageChecks({ checks, error }) {
  if (error) return <Signal>{error}</Signal>;
  if (!checks) return null;
  return <ChecksResult checks={checks} />;
}
