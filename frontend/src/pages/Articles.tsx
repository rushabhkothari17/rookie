import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import TopNav from "@/components/TopNav";
import AppFooter from "@/components/AppFooter";
import { useWebsite } from "@/contexts/WebsiteContext";
import api from "@/lib/api";
import { ArrowRight, BookOpen, Calendar } from "lucide-react";

const PER_PAGE = 9;

function formatDate(dateStr: string) {
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return dateStr;
  }
}

export default function Articles() {
  const navigate = useNavigate();
  const ws = useWebsite();
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

  useEffect(() => { setPage(1); }, [selectedCategory]);

  const categories = Array.from(new Set(articles.map((a) => a.category).filter(Boolean))).sort();
  const filtered = selectedCategory ? articles.filter((a) => a.category === selectedCategory) : articles;
  const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  const paginated = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  return (
    <div className="min-h-screen aa-bg flex flex-col">
      <TopNav />

      {/* Hero Banner — matches store style */}
      <div className="bg-slate-900 text-white py-10 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center gap-2 mb-3">
            <div className="h-px w-6 bg-red-500" />
            <span className="text-xs font-semibold uppercase tracking-widest text-red-400">
              {ws.articles_hero_label}
            </span>
          </div>
          <h1 className="text-4xl font-bold text-white tracking-tight">{ws.articles_hero_title}</h1>
          {ws.articles_hero_subtitle && (
            <p className="mt-2 text-slate-400 text-sm max-w-xl">{ws.articles_hero_subtitle}</p>
          )}
        </div>
      </div>

      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-8" data-testid="articles-page">
        <div className="flex gap-8">
          {/* Left Sidebar */}
          <aside className="w-52 shrink-0">
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-3">BROWSE</p>
            <ul className="space-y-1">
              <li>
                <button
                  onClick={() => setSelectedCategory(null)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-between ${
                    !selectedCategory
                      ? "bg-slate-900 text-white"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                  data-testid="articles-filter-all"
                >
                  <span>All</span>
                  <span className="text-xs font-normal opacity-60">{articles.length}</span>
                </button>
              </li>
              {categories.map((cat) => (
                <li key={cat}>
                  <button
                    onClick={() => setSelectedCategory(cat === selectedCategory ? null : cat)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-between ${
                      selectedCategory === cat
                        ? "bg-slate-900 text-white"
                        : "text-slate-600 hover:bg-slate-100"
                    }`}
                    data-testid={`articles-filter-${cat}`}
                  >
                    <span className="truncate">{cat}</span>
                    <span className="text-xs font-normal opacity-60 shrink-0 ml-2">
                      {articles.filter((a) => a.category === cat).length}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          {/* Articles Grid */}
          <div className="flex-1 min-w-0">
            {selectedCategory && (
              <div className="mb-5">
                <h2 className="text-xl font-bold text-slate-900">{selectedCategory}</h2>
                <p className="text-sm text-slate-400">{filtered.length} article{filtered.length !== 1 ? "s" : ""}</p>
              </div>
            )}

            {loading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="rounded-xl border border-slate-200 bg-white h-48 animate-pulse" />
                ))}
              </div>
            ) : paginated.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="h-12 w-12 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                  <BookOpen size={20} className="text-slate-400" />
                </div>
                <p className="text-slate-400 text-sm">No articles available yet.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="articles-grid">
                {paginated.map((article) => (
                  <button
                    key={article.id}
                    onClick={() => navigate(`/articles/${article.id}`)}
                    className="rounded-xl border border-slate-200 bg-white hover:shadow-md hover:border-slate-300 transition-all text-left flex flex-col overflow-hidden group"
                    data-testid={`article-card-${article.id}`}
                  >
                    {/* Card top accent */}
                    <div className="h-1 bg-slate-900 group-hover:bg-red-500 transition-colors" />

                    <div className="p-5 flex flex-col flex-1">
                      {article.category && (
                        <span className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2">
                          {article.category}
                        </span>
                      )}
                      <h3 className="text-sm font-semibold text-slate-900 mb-2 leading-snug line-clamp-2">
                        {article.title}
                      </h3>
                      {article.content && (
                        <p className="text-xs text-slate-500 leading-relaxed line-clamp-3 flex-1">
                          {article.content.replace(/[#*_`]/g, "").substring(0, 150)}
                        </p>
                      )}
                      <div className="mt-4 flex items-center justify-between">
                        {article.created_at && (
                          <span className="flex items-center gap-1 text-xs text-slate-400">
                            <Calendar size={11} />
                            {formatDate(article.created_at)}
                          </span>
                        )}
                        <span className="flex items-center gap-1 text-xs font-medium text-slate-700 group-hover:text-slate-900 transition-colors">
                          Read <ArrowRight size={11} />
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8" data-testid="articles-pagination">
                <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                  className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 disabled:opacity-40 hover:bg-slate-50 transition-colors">
                  Previous
                </button>
                <span className="text-xs text-slate-500">{page} / {totalPages}</span>
                <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                  className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 disabled:opacity-40 hover:bg-slate-50 transition-colors">
                  Next
                </button>
              </div>
            )}
          </div>
        </div>
      </main>

      <AppFooter />
    </div>
  );
}
