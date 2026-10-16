import { LuLock } from "react-icons/lu";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import Panel from "../../components/ui/Panel";
import { usePage } from "../../context/PageContext";

export default function ForbiddenPage() {
  usePage("Access restricted");
  return (
    <Panel className="max-w-2xl">
      <EmptyState icon={LuLock} title="Access restricted" text="Your role does not include this area. Ask an administrator if you need access."
        action={<Button to="/" variant="primary">Go to the overview</Button>} />
    </Panel>
  );
}
