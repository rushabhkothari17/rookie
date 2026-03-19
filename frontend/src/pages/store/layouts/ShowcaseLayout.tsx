/**
 * ShowcaseLayout — Hero section focus with live calculator
 * Best for: Products with configurable pricing, visual appeal focus
 */
import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { RefreshCcw, FileText, Star, ArrowRight } from "lucide-react";
import FaqAccordion from "@/components/FaqAccordion";
import type { LayoutProps } from "./types";
import { QuestionLabel, renderIntakeField, ScopeIdBlock, formatCurrency } from "./utils";
import { useWebsite } from "@/contexts/WebsiteContext";

export default function ShowcaseLayout({
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
    ? `Add to Cart — ${formatCurrency(scopeUnlock.price, cur)}`
    : isEnquiry
    ? (ws.sdp_cta_quote || "Request Quote")
    : isExternal
    ? "Continue to External Checkout"
    : isFree
    ? (ws.sdp_cta_free || "Get it free")
    : (ws.sdp_cta_buy || "Add to Cart");

  // Separate pricing questions from info questions
  const { pricingQuestions, infoQuestions } = useMemo(() => {
    const pq: typeof visibleIntakeQuestions = [];
    const iq: typeof visibleIntakeQuestions = [];
    visibleIntakeQuestions.forEach(q => {
      if (q.affects_price || q.type === "number" || q.type === "formula") {
        pq.push(q);
      } else if (q.type !== "html_block") {
        iq.push(q);
      }
    });
    return { pricingQuestions: pq, infoQuestions: iq };
  }, [visibleIntakeQuestions]);

  return (
    <div data-testid="showcase-layout">
      {/* Hero Section */}
      <div
        className="relative rounded-3xl overflow-hidden mb-8"
        style={{ background: `linear-gradient(135deg, var(--aa-primary), color-mix(in srgb, var(--aa-primary) 70%, var(--aa-accent)))` }}
      >
        <div className="absolute inset-0 opacity-20">
          <div
            className="absolute top-0 right-0 w-96 h-96 rounded-full filter blur-3xl"
            style={{ background: "var(--aa-primary-fg)" }}
          />
          <div
            className="absolute bottom-0 left-0 w-96 h-96 rounded-full filter blur-3xl"
            style={{ background: "var(--aa-accent)" }}
          />
        </div>

        <div className="relative z-10 p-8 lg:p-12">
          <h1 className="text-3xl lg:text-5xl font-bold mb-4" style={{ color: "var(--aa-primary-fg)" }}>
            {product.name}
          </h1>
          {product.tagline && (
            <p className="text-lg lg:text-xl max-w-2xl mb-8" style={{ color: "rgba(255,255,255,0.8)" }}>
              {product.tagline}
            </p>
          )}
        </div>
      </div>

      <div className="grid lg:grid-cols-[1fr_400px] gap-8">
        {/* Left: Product details */}
        <div className="flex flex-col gap-8">
          {/* Description */}
          {product.description_long && (
            <div className="rounded-2xl border p-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
              <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--aa-text)" }}>
                {ws.sdp_about_title || "About this product"}
              </h2>
              <div className="prose prose-sm max-w-none" style={{ color: "var(--aa-muted)" }}>
                <ReactMarkdown>{product.description_long}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* Highlights/Bullets */}
          {product.bullets && product.bullets.length > 0 && (
            <div className="rounded-2xl border p-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
              <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--aa-text)" }}>
                {ws.sdp_key_features_title || "Key Features"}
              </h2>
              <div className="grid sm:grid-cols-2 gap-4">
                {product.bullets.map((bullet, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5"
                      style={{ background: "color-mix(in srgb, var(--aa-accent) 15%, transparent)" }}
                    >
                      <Star size={12} style={{ color: "var(--aa-accent)" }} />
                    </div>
                    <span className="text-sm" style={{ color: "var(--aa-muted)" }}>{bullet}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Info questions (non-pricing) */}
          {infoQuestions.length > 0 && (
            <div className="rounded-2xl border p-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
              <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--aa-text)" }}>
                {ws.sdp_additional_info_title || "Additional Information"}
              </h2>
              <div className="space-y-4">
                {infoQuestions.map(q => (
                  <div key={q.key} className="space-y-1.5" data-testid={`intake-field-${q.key}`}>
                    <QuestionLabel q={q} />
                    {q.helper_text && (
                      <p className="text-xs" style={{ color: "var(--aa-muted)" }}>{q.helper_text}</p>
                    )}
                    {renderIntakeField(q, intakeAnswers[q.key], v => onIntakeChange(q.key, v))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Custom sections */}
          {(product.custom_sections || []).map((sec, i) => (
            <div key={sec.id || i} className="rounded-2xl border p-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
              <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--aa-text)" }}>{sec.name}</h2>
              {sec.content && (
                <div className="prose prose-sm max-w-none" style={{ color: "var(--aa-muted)" }}>
                  <ReactMarkdown>{sec.content}</ReactMarkdown>
                </div>
              )}
              {sec.tags && sec.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {sec.tags.map(tag => (
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

        {/* Right: Sticky Calculator */}
        <div className="lg:sticky lg:top-24 lg:self-start space-y-4">
          {/* Live Price Calculator */}
          <div className="rounded-2xl border overflow-hidden shadow-lg" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
            <div className="px-6 py-4 border-b" style={{ background: "var(--aa-surface)", borderColor: "var(--aa-border)" }}>
              <h3 className="font-semibold" style={{ color: "var(--aa-text)" }}>
                {ws.sdp_configure_price_title || "Configure & Price"}
              </h3>
              <p className="text-xs mt-0.5" style={{ color: "var(--aa-muted)" }}>
                {ws.sdp_configure_price_subtitle || "Adjust options to see live pricing"}
              </p>
            </div>

            <div className="p-6 space-y-4">
              {/* Pricing questions */}
              {pricingQuestions.map(q => (
                <div key={q.key} className="space-y-1.5" data-testid={`intake-field-${q.key}`}>
                  <QuestionLabel q={q} />
                  {renderIntakeField(q, intakeAnswers[q.key], v => onIntakeChange(q.key, v))}
                </div>
              ))}

              {pricingQuestions.length === 0 && (
                <p className="text-sm text-center py-4" style={{ color: "var(--aa-muted)" }}>
                  Fixed pricing — no configuration needed
                </p>
              )}
            </div>

            {/* Price display */}
            <div
              className="px-6 py-5"
              style={{ background: `linear-gradient(135deg, var(--aa-primary), color-mix(in srgb, var(--aa-primary) 80%, black))` }}
            >
              {pricing?.line_items && pricing.line_items.length > 1 && (
                <div className="space-y-1 mb-3 pb-3" style={{ borderBottom: "1px solid rgba(255,255,255,0.15)" }}>
                  {pricing.line_items.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm">
                      <span style={{ color: "rgba(255,255,255,0.6)" }}>{item.label}</span>
                      <span style={{ color: "rgba(255,255,255,0.85)" }}>{formatCurrency(item.amount, cur)}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex justify-between items-center">
                <span style={{ color: "rgba(255,255,255,0.7)" }}>Total</span>
                <span className="text-2xl font-bold" style={{ color: "var(--aa-primary-fg)" }}>
                  {isEnquiry && !scopeUnlock
                    ? "On request"
                    : isFree
                    ? "Free"
                    : pricing
                    ? formatCurrency(scopeUnlock?.price ?? pricing.total, cur)
                    : "..."}
                </span>
              </div>

              {isSubscription && (
                <div className="flex items-center gap-2 mt-2 text-sm" style={{ color: "rgba(255,255,255,0.7)" }}>
                  <RefreshCcw size={14} />
                  <span>Recurring subscription</span>
                </div>
              )}
            </div>

            {/* CTA */}
            <div className="p-6 pt-4 space-y-3">
              {/* Free product indicator */}
              {isFree && (
                <div
                  className="flex items-center gap-2 p-3 rounded-xl border text-sm"
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

              <Button
                onClick={handleAddToCart}
                size="lg"
                className="w-full h-12 font-semibold"
                style={{ background: "var(--aa-primary)", color: "var(--aa-primary-fg)" }}
                data-testid="showcase-cta"
              >
                {ctaLabel}
                <ArrowRight size={16} className="ml-2" />
              </Button>

              {/* Scope ID override for enquiry products */}
              {isEnquiry && setScopeId && handleValidateScopeId && (
                <ScopeIdBlock
                  scopeId={scopeId}
                  setScopeId={setScopeId}
                  handleValidateScopeId={handleValidateScopeId}
                  scopeValidating={scopeValidating}
                  scopeError={scopeError}
                  scopeUnlock={scopeUnlock}
                />
              )}

              {termsUrl && (
                <a
                  href={termsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 text-xs mt-3 hover:opacity-70 transition-opacity"
                  style={{ color: "var(--aa-muted)" }}
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
