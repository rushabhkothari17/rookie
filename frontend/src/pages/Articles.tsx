import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import TopNav from "@/components/TopNav";
import AppFooter from "@/components/AppFooter";
import { EmptyState } from "@/components/EmptyState";
import { SkeletonGrid } from "@/components/SkeletonCard";
import { useWebsite } from "@/contexts/WebsiteContext";
import api from "@/lib/api";
import { ArrowRight, Calendar } from "lucide-react";

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

      {/* Hero Banner — same style as Store page */}
      <div className="max-w-7xl mx-auto w-full px-6 pt-8">
        <section
          className="relative overflow-hidden rounded-3xl px-6 py-8 md:px-10 md:py-12 shadow-[0_30px_70px_rgba(15,23,42,0.15)] aa-grid-texture"
          style={{ backgroundColor: "var(--aa-primary)" }}
          data-testid="articles-hero"
        >
          <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full blur-3xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 10%, transparent)" }} />
          <div className="pointer-events-none absolute bottom-0 left-0 h-56 w-56 rounded-full blur-2xl" style={{ backgroundColor: "color-mix(in srgb, var(--aa-accent) 5%, transparent)" }} />
          <div className="relative space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="h-0.5 w-8 rounded-full" style={{ backgroundColor: "var(--aa-accent)" }} />
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                {ws.articles_hero_label || "Resources"}
              </p>
            </div>
            <h1 className="text-4xl font-bold text-white" data-testid="articles-hero-title">
              {ws.articles_hero_title || "Articles & Guides"}
            </h1>
            {ws.articles_hero_subtitle && (
              <p className="max-w-xl text-base text-slate-300" data-testid="articles-hero-subtitle">
                {ws.articles_hero_subtitle}
              </p>
            )}
          </div>
        </section>
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
                      ? "text-white"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                  style={!selectedCategory ? { backgroundColor: "var(--aa-primary)" } : undefined}
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
                        ? "text-white"
                        : "text-slate-600 hover:bg-slate-100"
                    }`}
                    style={selectedCategory === cat ? { backgroundColor: "var(--aa-primary)" } : undefined}
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
              <SkeletonGrid count={6} cols="grid-cols-1 sm:grid-cols-2 lg:grid-cols-3" />
            ) : paginated.length === 0 ? (
              <EmptyState
                icon="articles"
                title={selectedCategory ? `No articles in "${selectedCategory}"` : "No articles yet"}
                description="Check back soon for new guides and resources."
                data-testid="articles-empty-state"
              />
            ) : (
              <motion.div
                className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
                data-testid="articles-grid"
                variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}
                initial="hidden"
                animate="show"
              >
                {paginated.map((article) => (
                  <motion.button
                    key={article.id}
                    variants={{
                      hidden: { opacity: 0, y: 20 },
                      show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] } },
                    }}
                    onClick={() => navigate(`/articles/${article.id}`)}
                    className="rounded-xl border border-slate-200 hover:shadow-lg hover:border-slate-300 hover:-translate-y-1 transition-all duration-200 text-left flex flex-col overflow-hidden group"
                    style={{ backgroundColor: "var(--aa-card)", borderColor: "var(--aa-border)" }}
                    data-testid={`article-card-${article.id}`}
                  >
                    {/* Card top accent */}
                    <div className="h-1 transition-colors" style={{ backgroundColor: "var(--aa-primary)" }} />

                    <div className="p-5 flex flex-col flex-1">
                      {article.category && (
                        <span className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2">
                          {article.category}
                        </span>
                      )}
                      <h3 className="text-sm font-semibold mb-2 leading-snug line-clamp-2" style={{ color: "var(--aa-text)" }}>
                        {article.title}
                      </h3>
                      {article.content && (
                        <p className="text-xs leading-relaxed line-clamp-3 flex-1" style={{ color: "var(--aa-muted)" }}>
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
                        <span className="flex items-center gap-1 text-xs font-medium group-hover:gap-2 transition-all" style={{ color: "var(--aa-primary)" }}>
                          Read <ArrowRight size={11} />
                        </span>
                      </div>
                    </div>
                  </motion.button>
                ))}
              </motion.div>
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
