import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import TopNav from "@/components/TopNav";
import api from "@/lib/api";

const CATEGORY_COLORS: Record<string, string> = {
  "Scope - Draft": "bg-amber-50 border-amber-200 text-amber-800",
  "Scope - Final Lost": "bg-red-50 border-red-200 text-red-800",
  "Scope - Final Won": "bg-green-50 border-green-200 text-green-800",
  Blog: "bg-blue-50 border-blue-200 text-blue-800",
  Help: "bg-indigo-50 border-indigo-200 text-indigo-800",
  Guide: "bg-purple-50 border-purple-200 text-purple-800",
  SOP: "bg-cyan-50 border-cyan-200 text-cyan-800",
  Other: "bg-slate-50 border-slate-200 text-slate-700",
};

const PER_PAGE = 9;

export default function Articles() {
  const navigate = useNavigate();
  const [articles, setArticles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get("/articles/public");
        setArticles(res.data.articles || []);
      } catch {
        setArticles([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // Reset page when filter changes
  useEffect(() => { setPage(1); }, [selectedCategory]);

  const categories = Array.from(new Set(articles.map((a) => a.category))).sort();

  const filtered = selectedCategory
    ? articles.filter((a) => a.category === selectedCategory)
    : articles;

  const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  const paginated = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  return (
    <div className="min-h-screen aa-bg">
      <TopNav />
      <main className="aa-container py-10">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold text-slate-900">Articles</h1>
          <p className="text-slate-500 text-sm">Guides, scopes, and resources from your consultant</p>
        </div>

        {/* Category filters */}
        <div className="flex flex-wrap gap-2" data-testid="articles-category-filters">
          <button
            onClick={() => setSelectedCategory(null)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
              !selectedCategory ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"
            }`}
            data-testid="articles-filter-all"
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat === selectedCategory ? null : cat)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                selectedCategory === cat ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"
              }`}
              data-testid={`articles-filter-${cat}`}
            >
              {cat}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-slate-400 text-sm py-8 text-center">Loading articles…</div>
        ) : filtered.length === 0 ? (
          <div className="text-slate-400 text-sm py-12 text-center" data-testid="articles-empty">
            No articles available yet.
          </div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 pt-4" data-testid="articles-list">
              {paginated.map((a) => (
                <button
                  key={a.id}
                  onClick={() => navigate(`/articles/${a.slug || a.id}`)}
                  className="text-left rounded-xl border border-slate-200 bg-white p-5 hover:shadow-md hover:border-slate-300 transition-all group"
                  data-testid={`article-card-${a.id}`}
                >
                  <div className="space-y-3">
                    <span className={`inline-block text-xs px-2 py-0.5 rounded-full border font-medium ${CATEGORY_COLORS[a.category] || CATEGORY_COLORS["Other"]}`}>
                      {a.category}
                    </span>
                    <h3 className="font-semibold text-slate-900 group-hover:text-slate-700 leading-tight">
                      {a.title}
                    </h3>
                    {a.price && (
                      <div className="text-sm font-semibold text-green-700">${a.price}</div>
                    )}
                    <div className="text-xs text-slate-400">
                      Updated {new Date(a.updated_at).toLocaleDateString()}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-2" data-testid="articles-pagination">
                <p className="text-sm text-slate-500">
                  Showing {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, filtered.length)} of {filtered.length} articles
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
                    data-testid="articles-prev-page"
                  >
                    Previous
                  </button>
                  <span className="text-sm text-slate-600 px-2">Page {page} of {totalPages}</span>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
                    data-testid="articles-next-page"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
