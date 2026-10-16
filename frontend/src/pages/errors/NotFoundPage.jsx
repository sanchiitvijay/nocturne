import { LuSearch } from "react-icons/lu";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import Panel from "../../components/ui/Panel";
import { usePage } from "../../context/PageContext";

export default function NotFoundPage({ title = "Not found", text = "That page does not exist. Check the address or use search." }) {
  usePage(title);
  return (
    <Panel className="max-w-2xl">
      <EmptyState icon={LuSearch} title={title} text={text} action={<Button to="/" variant="primary">Go to the overview</Button>} />
    </Panel>
  );
}
