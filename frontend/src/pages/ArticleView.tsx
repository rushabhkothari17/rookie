import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "@/components/AppShell";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ChevronLeft } from "lucide-react";

export default function ArticleView() {
  const { articleId } = useParams();
  const navigate = useNavigate();
  const [article, setArticle] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get(`/articles/${articleId}`);
        setArticle(res.data.article);
      } catch (e: any) {
        setError(e.response?.data?.detail || "Article not found");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [articleId]);

  if (loading) {
    return (
      <AppShell activeCategory={null}>
        <div className="text-slate-400 text-sm py-12 text-center" data-testid="article-loading">Loading…</div>
      </AppShell>
    );
  }

  if (error || !article) {
    return (
      <AppShell activeCategory={null}>
        <div className="py-12 text-center space-y-4" data-testid="article-not-found">
          <p className="text-slate-500">{error || "Article not found"}</p>
          <Button variant="outline" onClick={() => navigate("/articles")}>
            <ChevronLeft size={14} className="mr-1" /> Back to Articles
          </Button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell activeCategory={null}>
      <div className="max-w-3xl mx-auto space-y-6" data-testid="article-view">
        <Button variant="ghost" className="gap-1 text-slate-500 -ml-2" onClick={() => navigate("/articles")} data-testid="article-back-btn">
          <ChevronLeft size={14} /> Back to Articles
        </Button>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 font-medium border border-slate-200">
              {article.category}
            </span>
            {article.price && (
              <span className="text-sm font-semibold text-green-700 bg-green-50 px-2.5 py-1 rounded-full border border-green-200">
                ${article.price}
              </span>
            )}
          </div>
          <h1 className="text-3xl font-bold text-slate-900 leading-tight" data-testid="article-title">
            {article.title}
          </h1>
          <p className="text-sm text-slate-400">
            Last updated {new Date(article.updated_at).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
          </p>
        </div>

        <div
          className="prose prose-slate max-w-none border-t border-slate-100 pt-6"
          data-testid="article-content"
          dangerouslySetInnerHTML={{ __html: article.content || "<p class='text-slate-400'>No content yet.</p>" }}
        />
      </div>
    </AppShell>
  );
}
