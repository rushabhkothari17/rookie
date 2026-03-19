/**
 * QuickBuyLayout — Compact, price-first, fast checkout
 * Best for: Simple products, subscriptions, one-click purchases
 */
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { ShoppingCart, RefreshCcw, FileText, Check } from "lucide-react";
import FaqAccordion from "@/components/FaqAccordion";
import type { LayoutProps } from "./types";
import { QuestionLabel, renderIntakeField, ScopeIdBlock, formatCurrency } from "./utils";
import { useWebsite } from "@/contexts/WebsiteContext";

export default function QuickBuyLayout({
  product,
  pricing,
  intakeAnswers,
  onIntakeChange,
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
  const ws = useWebsite();
  const cur = currency || "USD";

  const isEnquiry = product.pricing_type === "enquiry" || ((isRFQ || pricing?.is_enquiry) && product?.base_price == null);
  const isFree = !isEnquiry && pricing && pricing.total === 0;
  const isExternal = product.checkout_type === "external" || product.pricing_type === "external";

  const ctaLabel = scopeUnlock
    ? `${ws.sdp_cta_buy || "Add to cart"} — ${formatCurrency(scopeUnlock.price, cur)}`
    : isEnquiry
    ? (ws.sdp_cta_quote || "Request Quote")
    : isExternal
    ? "Continue to External Checkout"
    : isFree
    ? (ws.sdp_cta_free || "Get it free")
    : (ws.sdp_cta_buy || "Buy Now");

  return (
    <div className="max-w-xl mx-auto" data-testid="quick-buy-layout">
      {/* Price-first hero card */}
      <div
        className="rounded-3xl p-8 text-white mb-6"
        style={{ background: `linear-gradient(135deg, var(--aa-primary), color-mix(in srgb, var(--aa-primary) 80%, black))` }}
      >
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">{product.name}</h1>
          </div>
          {isSubscription && (
            <span
              className="px-3 py-1 text-xs font-medium rounded-full flex items-center gap-1"
              style={{ background: "rgba(255,255,255,0.15)", color: "rgba(255,255,255,0.9)" }}
            >
              <RefreshCcw size={12} />
              Subscription
            </span>
          )}
        </div>

        {product.tagline && (
          <p style={{ color: "rgba(255,255,255,0.75)" }} className="mb-6">{product.tagline}</p>
        )}

        {/* Price display */}
        <div className="border-t pt-6" style={{ borderColor: "rgba(255,255,255,0.2)" }}>
          {pricing ? (
            <div>
              <p className="text-xs uppercase tracking-wider mb-1" style={{ color: "rgba(255,255,255,0.55)" }}>
                {isEnquiry ? "Pricing" : isFree ? "Price" : "Total"}
              </p>
              <p className="text-4xl font-bold">
                {isEnquiry ? "On request" : isFree ? "Free" : formatCurrency(pricing.total, cur)}
              </p>
              {isSubscription && !isEnquiry && (
                <p className="text-sm mt-1" style={{ color: "rgba(255,255,255,0.55)" }}>per month</p>
              )}
            </div>
          ) : (
            <div className="animate-pulse">
              <div className="h-4 w-16 rounded mb-2" style={{ background: "rgba(255,255,255,0.15)" }} />
              <div className="h-10 w-32 rounded" style={{ background: "rgba(255,255,255,0.15)" }} />
            </div>
          )}
        </div>
      </div>

      {/* Quick features/bullets */}
      {product.bullets && product.bullets.length > 0 && (
        <div className="rounded-2xl border p-6 mb-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
          <h3 className="text-sm font-semibold mb-4" style={{ color: "var(--aa-text)" }}>
            {ws.sdp_features_title || "What's included"}
          </h3>
          <ul className="space-y-3">
            {product.bullets.map((bullet, i) => (
              <li key={i} className="flex items-start gap-3 text-sm" style={{ color: "var(--aa-muted)" }}>
                <Check size={16} className="mt-0.5 shrink-0" style={{ color: "var(--aa-success)" }} />
                {bullet}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Description */}
      {product.description_long && (
        <div className="rounded-2xl border p-6 mb-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--aa-text)" }}>
            {ws.sdp_about_title || "About this product"}
          </h3>
          <div className="prose prose-sm max-w-none" style={{ color: "var(--aa-muted)" }}>
            <ReactMarkdown>{product.description_long}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Intake form */}
      {visibleIntakeQuestions.length > 0 && (
        <div className="rounded-2xl border p-6 mb-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
          <h3 className="text-sm font-semibold mb-4" style={{ color: "var(--aa-text)" }}>
            {ws.sdp_intake_title || "Quick questions"}
          </h3>
          <div className="space-y-4">
            {visibleIntakeQuestions.map(q => (
              <div key={q.key} className="space-y-1.5" data-testid={`intake-field-${q.key}`}>
                {q.type !== "html_block" && <QuestionLabel q={q} />}
                {q.helper_text && q.type !== "html_block" && (
                  <p className="text-xs" style={{ color: "var(--aa-muted)" }}>{q.helper_text}</p>
                )}
                {renderIntakeField(q, intakeAnswers[q.key], v => onIntakeChange(q.key, v))}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Free product indicator */}
      {isFree && (
        <div
          className="flex items-center gap-2 p-3 rounded-xl border text-sm mb-4"
          style={{
            borderColor: "color-mix(in srgb, var(--aa-success) 30%, transparent)",
            background: "color-mix(in srgb, var(--aa-success) 10%, transparent)",
            color: "var(--aa-success)",
          }}
          data-testid="free-product-indicator"
        >
          <span>Free — no payment required</span>
        </div>
      )}

      {/* Subscription indicator */}
      {isSubscription && (
        <div
          className="flex items-center gap-2 p-3 rounded-xl border text-sm mb-4"
          style={{
            borderColor: "color-mix(in srgb, var(--aa-accent) 30%, transparent)",
            background: "color-mix(in srgb, var(--aa-accent) 10%, transparent)",
            color: "var(--aa-accent)",
          }}
          data-testid="subscription-indicator"
        >
          <RefreshCcw size={14} />
          <span>This is a recurring subscription</span>
        </div>
      )}

      {/* CTA Button */}
      <Button
        onClick={handleAddToCart}
        size="lg"
        className="w-full h-14 text-base font-semibold rounded-xl gap-2"
        style={{ background: "var(--aa-primary)", color: "var(--aa-primary-fg)" }}
        data-testid="quick-buy-cta"
      >
        <ShoppingCart size={20} />
        {ctaLabel}
      </Button>

      {/* Scope ID Override for enquiry products */}
      {isEnquiry && setScopeId && handleValidateScopeId && (
        <div className="mt-4">
          <ScopeIdBlock
            scopeId={scopeId}
            setScopeId={setScopeId}
            handleValidateScopeId={handleValidateScopeId}
            scopeValidating={scopeValidating}
            scopeError={scopeError}
            scopeUnlock={scopeUnlock}
          />
        </div>
      )}

      {/* Terms link */}
      {termsUrl && (
        <a
          href={termsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 text-xs mt-4 hover:opacity-70 transition-opacity"
          style={{ color: "var(--aa-muted)" }}
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
              className="px-3 py-1 text-xs rounded-full"
              style={{ background: "var(--aa-surface)", color: "var(--aa-muted)" }}
              data-testid={`product-tag-${i}`}
            >
              {tag.trim()}
            </span>
          ))}
        </div>
      )}

      {/* Custom Sections */}
      {(product.custom_sections || []).map((sec: any, i: number) => (
        <div
          key={sec.id || i}
          className="rounded-2xl border p-6 mt-4 text-left"
          style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}
        >
          <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--aa-text)" }}>{sec.name}</h3>
          {sec.content && (
            <div className="prose prose-sm max-w-none" style={{ color: "var(--aa-muted)" }}>
              <ReactMarkdown>{sec.content}</ReactMarkdown>
            </div>
          )}
          {sec.tags && sec.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {sec.tags.map((tag: string) => (
                <span key={tag} className="px-2 py-0.5 rounded-full text-xs" style={{ background: "var(--aa-surface)", color: "var(--aa-muted)" }}>
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}

      {/* FAQs */}
      <FaqAccordion
        faqs={product.faqs || []}
        title={ws.sdp_faqs_title || "FAQs"}
        testId="product-faqs"
      />
    </div>
  );
}
