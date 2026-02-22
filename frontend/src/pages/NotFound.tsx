import { Link } from "react-router-dom";
import { useWebsite } from "@/contexts/WebsiteContext";

export default function NotFound() {
  const ws = useWebsite();
  return (
    <div className="space-y-4" data-testid="not-found">
      <h1 className="text-2xl font-semibold text-slate-900">{ws.page_404_title}</h1>
      <Link to="/store" className="text-sm text-blue-600" data-testid="not-found-link">
        {ws.page_404_link_text}
      </Link>
    </div>
  );
}
