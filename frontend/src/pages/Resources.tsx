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

export default function Resources() {
  const navigate = useNavigate();
  const ws = useWebsite();
  const [resources, setResources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get("/resources/public");
        setResources(res.data.resources || []);
      } catch {
        setResources([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  useEffect(() => { setPage(1); }, [selectedCategory]);

  const categories = Array.from(new Set(resources.map((a) => a.category).filter(Boolean))).sort();
  const filtered = selectedCategory ? resources.filter((a) => a.category === selectedCategory) : resources;
  const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  const paginated = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  return (
    <div className="min-h-screen aa-bg flex flex-col">
      <TopNav />

      {/* Hero Banner — same style as Store page */}
      <div className="max-w-7xl mx-auto w-full px-6 pt-8">
        <section
          className="relative overflow-hidden rounded-3xl px-10 py-12 shadow-[0_30px_70px_rgba(15,23,42,0.15)]"
          style={{ backgroundColor: "var(--aa-primary)" }}
          data-testid="resources-hero"
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
            <h1 className="text-4xl font-bold text-white" data-testid="resources-hero-title">
              {ws.articles_hero_title || "Resources & Guides"}
            </h1>
            {ws.articles_hero_subtitle && (
              <p className="max-w-xl text-base text-slate-300" data-testid="resources-hero-subtitle">
                {ws.articles_hero_subtitle}
              </p>
            )}
          </div>
        </section>
      </div>

      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-8" data-testid="resources-page">
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
                  data-testid="resources-filter-all"
                >
                  <span>All</span>
                  <span className="text-xs font-normal opacity-60">{resources.length}</span>
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
                    data-testid={`resources-filter-${cat}`}
                  >
                    <span className="truncate">{cat}</span>
                    <span className="text-xs font-normal opacity-60 shrink-0 ml-2">
                      {resources.filter((a) => a.category === cat).length}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          {/* Resources Grid */}
          <div className="flex-1 min-w-0">
            {selectedCategory && (
              <div className="mb-5">
                <h2 className="text-xl font-bold text-slate-900">{selectedCategory}</h2>
                <p className="text-sm text-slate-400">{filtered.length} resource{filtered.length !== 1 ? "s" : ""}</p>
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
                <p className="text-slate-400 text-sm">No resources available yet.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="resources-grid">
                {paginated.map((resource) => (
                  <button
                    key={resource.id}
                    onClick={() => navigate(`/resources/${resource.id}`)}
                    className="rounded-xl border border-slate-200 bg-white hover:shadow-md hover:border-slate-300 transition-all text-left flex flex-col overflow-hidden group"
                    data-testid={`resource-card-${resource.id}`}
                  >
                    {/* Card top accent */}
                    <div className="h-1 transition-colors" style={{ backgroundColor: "var(--aa-primary)" }} />

                    <div className="p-5 flex flex-col flex-1">
                      {resource.category && (
                        <span className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2">
                          {resource.category}
                        </span>
                      )}
                      <h3 className="text-sm font-semibold text-slate-900 mb-2 leading-snug line-clamp-2">
                        {resource.title}
                      </h3>
                      {resource.content && (
                        <p className="text-xs text-slate-500 leading-relaxed line-clamp-3 flex-1">
                          {resource.content.replace(/[#*_`]/g, "").substring(0, 150)}
                        </p>
                      )}
                      <div className="mt-4 flex items-center justify-between">
                        {resource.created_at && (
                          <span className="flex items-center gap-1 text-xs text-slate-400">
                            <Calendar size={11} />
                            {formatDate(resource.created_at)}
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
              <div className="flex items-center justify-center gap-2 mt-8" data-testid="resources-pagination">
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
