import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="space-y-4" data-testid="not-found">
      <h1 className="text-2xl font-semibold text-slate-900">Page not found</h1>
      <Link to="/store" className="text-sm text-blue-600" data-testid="not-found-link">
        Back to store
      </Link>
    </div>
  );
}
