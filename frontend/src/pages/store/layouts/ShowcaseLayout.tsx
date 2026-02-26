/**
 * ShowcaseLayout — Hero section focus with live calculator
 * Best for: Products with configurable pricing, visual appeal focus
 */
import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { 
  RefreshCcw, 
  FileText, 
  Star, 
  ArrowRight,
  Sparkles
} from "lucide-react";
import type { LayoutProps } from "./types";
import { QuestionLabel, renderIntakeField, ScopeIdBlock } from "./utils";

export default function ShowcaseLayout({
  product,
  pricing,
  intakeAnswers,
  setIntakeAnswers,
  visibleIntakeQuestions,
  handleAddToCart,
  isRFQ,
  isSubscription,
  termsUrl,
  currency,
  scopeId = "",
  setScopeId,
  handleValidateScopeId,
  scopeValidating,
  scopeError,
  scopeUnlock,
}: LayoutProps) {
  const formatCurrency = (amount: number) => {
    const symbol = currency === "USD" ? "$" : currency === "EUR" ? "€" : "£";
    return `${symbol}${amount.toFixed(2)}`;
  };

  // Separate pricing questions from info questions
  const { pricingQuestions, infoQuestions } = useMemo(() => {
    const pricing: typeof visibleIntakeQuestions = [];
    const info: typeof visibleIntakeQuestions = [];
    
    visibleIntakeQuestions.forEach(q => {
      if (q.affects_price || q.type === "number" || q.type === "formula") {
        pricing.push(q);
      } else if (q.type !== "html_block") {
        info.push(q);
      }
    });
    
    return { pricingQuestions: pricing, infoQuestions: info };
  }, [visibleIntakeQuestions]);

  return (
    <div data-testid="showcase-layout">
      {/* Hero Section */}
      <div className="relative bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 rounded-3xl overflow-hidden mb-8">
        <div className="absolute inset-0 opacity-30">
          <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500 rounded-full filter blur-3xl" />
          <div className="absolute bottom-0 left-0 w-96 h-96 bg-purple-500 rounded-full filter blur-3xl" />
        </div>
        
        <div className="relative z-10 p-8 lg:p-12">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles size={16} className="text-yellow-400" />
            <span className="text-xs font-medium text-yellow-400 uppercase tracking-wider">
              {product.category}
            </span>
          </div>
          
          <h1 className="text-3xl lg:text-5xl font-bold text-white mb-4">
            {product.name}
          </h1>
          
          {product.tagline && (
            <p className="text-lg lg:text-xl text-slate-300 max-w-2xl mb-8">
              {product.tagline}
            </p>
          )}

          {/* Tags */}
          {product.tag && (
            <div className="flex flex-wrap gap-2">
              {product.tag.split(",").map((tag, i) => (
                <span
                  key={i}
                  className="px-3 py-1 bg-white/10 text-white/80 text-xs font-medium rounded-full backdrop-blur-sm"
                  data-testid={`product-tag-${i}`}
                >
                  {tag.trim()}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid lg:grid-cols-[1fr_400px] gap-8">
        {/* Left: Product details */}
        <div className="space-y-8">
          {/* Description */}
          {product.description_long && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-4">About this product</h2>
              <div className="prose prose-sm max-w-none text-slate-600">
                <ReactMarkdown>{product.description_long}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* Highlights/Bullets */}
          {product.bullets && product.bullets.length > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-4">Key Features</h2>
              <div className="grid sm:grid-cols-2 gap-4">
                {product.bullets.map((bullet, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center shrink-0 mt-0.5">
                      <Star size={12} className="text-blue-600" />
                    </div>
                    <span className="text-sm text-slate-600">{bullet}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Info questions (non-pricing) */}
          {infoQuestions.length > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-4">Additional Information</h2>
              <div className="space-y-4">
                {infoQuestions.map(q => (
                  <div key={q.key} className="space-y-1.5" data-testid={`intake-field-${q.key}`}>
                    <QuestionLabel q={q} />
                    {q.helper_text && (
                      <p className="text-xs text-slate-400">{q.helper_text}</p>
                    )}
                    {renderIntakeField(
                      q,
                      intakeAnswers[q.key],
                      v => setIntakeAnswers(prev => ({ ...prev, [q.key]: v }))
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Custom sections */}
          {(product.custom_sections || []).map((sec, i) => (
            <div key={sec.id || i} className="bg-white rounded-2xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-4">{sec.name}</h2>
              {sec.content && (
                <div className="prose prose-sm max-w-none text-slate-600">
                  <ReactMarkdown>{sec.content}</ReactMarkdown>
                </div>
              )}
            </div>
          ))}

          {/* FAQs */}
          {(product.faqs || []).length > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-4">FAQs</h2>
              <div className="space-y-4">
                {(product.faqs || []).map((faq, i) => (
                  <details key={i} className="group">
                    <summary className="flex items-center justify-between cursor-pointer list-none py-3 border-b border-slate-100">
                      <span className="font-medium text-slate-900">{faq.question}</span>
                      <ArrowRight size={16} className="text-slate-400 transition-transform group-open:rotate-90" />
                    </summary>
                    <p className="py-3 text-slate-600">{faq.answer}</p>
                  </details>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Sticky Calculator */}
        <div className="lg:sticky lg:top-24 lg:self-start space-y-4">
          {/* Live Price Calculator */}
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-lg">
            <div className="bg-slate-50 px-6 py-4 border-b border-slate-100">
              <h3 className="font-semibold text-slate-900">Configure & Price</h3>
              <p className="text-xs text-slate-500">Adjust options to see live pricing</p>
            </div>

            <div className="p-6 space-y-4">
              {/* Pricing questions */}
              {pricingQuestions.map(q => (
                <div key={q.key} className="space-y-1.5" data-testid={`intake-field-${q.key}`}>
                  <QuestionLabel q={q} />
                  {renderIntakeField(
                    q,
                    intakeAnswers[q.key],
                    v => setIntakeAnswers(prev => ({ ...prev, [q.key]: v }))
                  )}
                </div>
              ))}

              {pricingQuestions.length === 0 && (
                <p className="text-sm text-slate-400 text-center py-4">
                  Fixed pricing - no configuration needed
                </p>
              )}
            </div>

            {/* Price display */}
            <div className="bg-gradient-to-r from-slate-900 to-slate-800 px-6 py-5">
              {pricing?.line_items && pricing.line_items.length > 1 && (
                <div className="space-y-1 mb-3 pb-3 border-b border-slate-700">
                  {pricing.line_items.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm">
                      <span className="text-slate-400">{item.label}</span>
                      <span className="text-slate-300">{formatCurrency(item.amount)}</span>
                    </div>
                  ))}
                </div>
              )}
              
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Total</span>
                <span className="text-2xl font-bold text-white">
                  {isRFQ ? "On request" : pricing ? formatCurrency(pricing.total) : "..."}
                </span>
              </div>
              
              {isSubscription && (
                <div className="flex items-center gap-2 mt-2 text-sm text-blue-400">
                  <RefreshCcw size={14} />
                  <span>Recurring subscription</span>
                </div>
              )}
            </div>

            {/* CTA */}
            <div className="p-6 pt-4">
              <Button
                onClick={handleAddToCart}
                size="lg"
                className="w-full h-12 bg-blue-600 hover:bg-blue-700 font-semibold"
                data-testid="showcase-cta"
              >
                {isRFQ ? "Request Quote" : "Add to Cart"}
                <ArrowRight size={16} className="ml-2" />
              </Button>

              {termsUrl && (
                <a
                  href={termsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 text-xs text-slate-400 hover:text-slate-600 mt-3"
                  data-testid="terms-link"
                >
                  <FileText size={12} />
                  <span>Terms & Conditions</span>
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
