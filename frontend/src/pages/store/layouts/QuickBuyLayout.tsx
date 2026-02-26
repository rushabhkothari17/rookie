/**
 * QuickBuyLayout — Compact, price-first, fast checkout
 * Best for: Simple products, subscriptions, one-click purchases
 */
import { Button } from "@/components/ui/button";
import { ShoppingCart, RefreshCcw, FileText, Check } from "lucide-react";
import type { LayoutProps } from "./types";
import { QuestionLabel, renderIntakeField, ScopeIdBlock } from "./utils";

export default function QuickBuyLayout({
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

  const hasQuestions = visibleIntakeQuestions.length > 0;
  const isFree = !isRFQ && pricing && pricing.total === 0;
  const isEnquiry = isRFQ || pricing?.is_enquiry || product.pricing_type === "enquiry";

  // CTA label — update when scope unlocked
  const ctaLabel = scopeUnlock
    ? `Add to Cart — $${scopeUnlock.price}`
    : isEnquiry ? "Request Quote" : isFree ? "Get it Free" : "Buy Now";

  return (
    <div className="max-w-xl mx-auto" data-testid="quick-buy-layout">
      {/* Price-first hero card */}
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-8 text-white mb-6">
        <div className="flex items-start justify-between mb-6">
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">
              {product.category}
            </p>
            <h1 className="text-2xl font-bold">{product.name}</h1>
          </div>
          {isSubscription && (
            <span className="px-3 py-1 bg-blue-500/20 text-blue-300 text-xs font-medium rounded-full flex items-center gap-1">
              <RefreshCcw size={12} />
              Subscription
            </span>
          )}
        </div>

        {product.tagline && (
          <p className="text-slate-300 mb-6">{product.tagline}</p>
        )}

        {/* Price display */}
        <div className="border-t border-slate-700 pt-6">
          {pricing ? (
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">
                {isEnquiry ? "Pricing" : isFree ? "Price" : "Total"}
              </p>
              <p className="text-4xl font-bold">
                {isEnquiry ? "On request" : isFree ? "Free" : formatCurrency(pricing.total)}
              </p>
              {isSubscription && !isRFQ && (
                <p className="text-sm text-slate-400 mt-1">per month</p>
              )}
            </div>
          ) : (
            <div className="animate-pulse">
              <div className="h-4 w-16 bg-slate-700 rounded mb-2" />
              <div className="h-10 w-32 bg-slate-700 rounded" />
            </div>
          )}
        </div>
      </div>

      {/* Quick features/bullets */}
      {product.bullets && product.bullets.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-6">
          <h3 className="text-sm font-semibold text-slate-900 mb-4">What's included</h3>
          <ul className="space-y-3">
            {product.bullets.slice(0, 5).map((bullet, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-slate-600">
                <Check size={16} className="text-green-500 mt-0.5 shrink-0" />
                {bullet}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Description */}
      {product.description_long && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-6">
          <h3 className="text-sm font-semibold text-slate-900 mb-3">About this product</h3>
          <p className="text-sm text-slate-600 leading-relaxed">{product.description_long}</p>
        </div>
      )}

      {/* Minimal intake form (if any) */}
      {hasQuestions && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-6">
          <h3 className="text-sm font-semibold text-slate-900 mb-4">Quick questions</h3>
          <div className="space-y-4">
            {visibleIntakeQuestions.slice(0, 4).map(q => (
              <div key={q.key} className="space-y-1.5" data-testid={`intake-field-${q.key}`}>
                {q.type !== "html_block" && <QuestionLabel q={q} />}
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

      {/* CTA Button */}
      <Button
        onClick={handleAddToCart}
        size="lg"
        className="w-full h-14 text-base font-semibold bg-blue-600 hover:bg-blue-700 rounded-xl gap-2"
        data-testid="quick-buy-cta"
      >
        <ShoppingCart size={20} />
        {ctaLabel}
      </Button>

      {/* Terms link */}
      {termsUrl && (
        <a
          href={termsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 text-xs text-slate-400 hover:text-slate-600 mt-4"
          data-testid="terms-link"
        >
          <FileText size={12} />
          <span>Terms & Conditions</span>
        </a>
      )}

      {/* Product tags */}
      {product.tag && (
        <div className="flex flex-wrap justify-center gap-2 mt-6">
          {product.tag.split(",").map((tag, i) => (
            <span
              key={i}
              className="px-3 py-1 bg-slate-100 text-slate-500 text-xs rounded-full"
              data-testid={`product-tag-${i}`}
            >
              {tag.trim()}
            </span>
          ))}
        </div>
      )}

      {/* Custom Sections */}
      {(product.custom_sections || []).map((sec: any, i: number) => (
        <div key={sec.id || i} className="bg-white rounded-2xl border border-slate-200 p-6 mt-4 text-left">
          <h3 className="text-sm font-semibold text-slate-900 mb-3">{sec.name}</h3>
          {sec.content && (
            <p className="text-sm text-slate-600 leading-relaxed">{sec.content}</p>
          )}
        </div>
      ))}

      {/* FAQs */}
      {(product.faqs || []).length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mt-4 text-left">
          <h3 className="text-sm font-semibold text-slate-900 mb-4">FAQs</h3>
          <div className="space-y-4">
            {(product.faqs || []).map((faq: any, i: number) => (
              <div key={i} className="pb-4 border-b border-slate-100 last:border-0 last:pb-0">
                <p className="text-sm font-medium text-slate-900 mb-1">{faq.question}</p>
                <p className="text-sm text-slate-600">{faq.answer}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
