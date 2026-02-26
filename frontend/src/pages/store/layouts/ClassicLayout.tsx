/**
 * ClassicLayout — Standard two-column product page layout
 * Left: Product info, intake form, custom sections, FAQs
 * Right: Sticky price summary with live pricing
 */
import ReactMarkdown from "react-markdown";
import { RefreshCcw, FileText, Key, Check } from "lucide-react";
import ProductHero from "@/components/ProductHero";
import StickyPurchaseSummary from "@/components/StickyPurchaseSummary";
import SectionCard from "@/components/SectionCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import type { LayoutProps } from "./types";
import { QuestionLabel, renderIntakeField } from "./utils";

export default function ClassicLayout({
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
  scopeUnlock,
  scopeId,
  setScopeId,
  handleValidateScopeId,
  scopeValidating,
  scopeError,
}: LayoutProps) {
  // Determine if product is free (price=0) or enquiry
  const isFree = !isRFQ && pricing && pricing.total === 0;
  const isEnquiry = isRFQ || pricing?.is_enquiry || product.pricing_type === "enquiry";
  
  // Build CTA config
  const ctaConfig = (() => {
    if (isEnquiry) {
      if (scopeUnlock) {
        return { label: `Add to cart — $${scopeUnlock.price}`, onClick: handleAddToCart };
      }
      return { label: "Proceed to checkout", onClick: handleAddToCart };
    }
    if (isFree) {
      return { label: "Get it free", onClick: handleAddToCart };
    }
    return { label: "Add to cart", onClick: handleAddToCart };
  })();

  return (
    <div className="grid gap-8 lg:grid-cols-[1.4fr_0.9fr]" data-testid="classic-layout">
      {/* Left Column */}
      <div className="flex flex-col gap-6">
        <ProductHero product={product} />

        {/* Product Tags */}
        {product.tag && (
          <div className="flex flex-wrap gap-2">
            {product.tag.split(",").map((tag, i) => (
              <span
                key={i}
                className="px-3 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-full border border-blue-100"
                data-testid={`product-tag-${i}`}
              >
                {tag.trim()}
              </span>
            ))}
          </div>
        )}

        {/* Intake Questions */}
        {visibleIntakeQuestions.length > 0 && (
          <SectionCard title="Tell us about your project" testId="product-intake-section">
            <div className="space-y-4">
              {visibleIntakeQuestions.map(q => (
                <div key={q.key} className="space-y-1.5" data-testid={`intake-field-${q.key}`}>
                  {q.type !== "html_block" && <QuestionLabel q={q} />}
                  {q.helper_text && q.type !== "html_block" && (
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
          </SectionCard>
        )}

        {/* Custom sections */}
        {(product.custom_sections || []).map((sec, i) => (
          <SectionCard
            key={sec.id || i}
            title={sec.name}
            testId={`custom-section-${i}`}
            icon={sec.icon}
            iconColor={sec.icon_color}
          >
            {sec.content ? (
              <div className="prose prose-sm max-w-none text-slate-600 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5">
                <ReactMarkdown>{sec.content}</ReactMarkdown>
              </div>
            ) : (
              <span className="text-slate-400 italic">No content added yet.</span>
            )}
            {sec.tags && sec.tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {sec.tags.map(tag => (
                  <span key={tag} className="px-2 py-0.5 bg-slate-100 rounded-full text-xs text-slate-500">
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </SectionCard>
        ))}

        {/* FAQs */}
        {(product.faqs || []).length > 0 && (
          <SectionCard title="FAQs" testId="product-faqs">
            <div className="space-y-5" data-testid="product-faqs-list">
              {(product.faqs || []).map((item, i) => (
                <div key={i} className="space-y-1">
                  <p className="font-semibold text-slate-800">{item.question}</p>
                  <p className="text-slate-500 leading-relaxed">{item.answer}</p>
                </div>
              ))}
            </div>
          </SectionCard>
        )}
      </div>

      {/* Right Column - Sticky Summary */}
      <div>
        {pricing ? (
          <div className="space-y-4">
            <StickyPurchaseSummary
              pricing={{
                subtotal: pricing.subtotal,
                fee: pricing.fee,
                total: pricing.total,
                line_items: pricing.line_items,
              }}
              cta={ctaConfig}
              currency={currency}
              isRFQ={isEnquiry}
              disabled={false}
            />

            {/* Subscription indicator */}
            {isSubscription && (
              <div
                className="flex items-center gap-2 p-3 rounded-xl border border-blue-100 bg-blue-50 text-sm text-blue-700"
                data-testid="subscription-indicator"
              >
                <RefreshCcw size={16} />
                <span>This is a recurring subscription</span>
              </div>
            )}

            {/* Free product indicator */}
            {isFree && (
              <div
                className="flex items-center gap-2 p-3 rounded-xl border border-green-100 bg-green-50 text-sm text-green-700"
                data-testid="free-product-indicator"
              >
                <span>Free - no payment required</span>
              </div>
            )}

            {/* Terms & Conditions link */}
            {termsUrl && (
              <a
                href={termsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 justify-center transition-colors"
                data-testid="terms-link"
              >
                <FileText size={14} />
                <span>View Terms & Conditions</span>
              </a>
            )}
          </div>
        ) : (
          <div
            className="rounded-3xl border border-slate-100 bg-white p-6 text-sm text-slate-400"
            data-testid="product-summary-loading"
          >
            Calculating pricing...
          </div>
        )}
      </div>
    </div>
  );
}
