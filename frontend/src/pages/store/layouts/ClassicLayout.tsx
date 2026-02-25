/**
 * ClassicLayout — Standard two-column product page layout
 * Left: Product info, intake form, custom sections, FAQs
 * Right: Sticky price summary with live pricing
 */
import ReactMarkdown from "react-markdown";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { RefreshCcw, FileText } from "lucide-react";
import ProductHero from "@/components/ProductHero";
import StickyPurchaseSummary from "@/components/StickyPurchaseSummary";
import SectionCard from "@/components/SectionCard";
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
  // Build CTA config
  const ctaConfig = (() => {
    if (scopeUnlock) {
      return { label: `Add to cart - £${scopeUnlock.price}`, onClick: handleAddToCart };
    }
    if (isRFQ || pricing?.is_enquiry) {
      return { label: "Proceed to checkout", onClick: handleAddToCart };
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

        {/* Scope ID Unlock — for RFQ and enquiry products */}
        {(isRFQ || pricing?.is_enquiry || product.pricing_type === "enquiry") && (
          <SectionCard title="Unlock with Scope ID" testId="scope-id-card">
            <div className="space-y-3">
              <p className="text-sm text-slate-500">
                If you have received a finalized scope document, enter the Scope ID below to unlock pricing.
              </p>
              <div className="flex gap-2">
                <Input
                  value={scopeId}
                  onChange={e => setScopeId(e.target.value)}
                  placeholder="Enter Scope ID"
                  className="flex-1 font-mono text-sm"
                  data-testid="scope-id-input"
                />
                <Button
                  variant="outline"
                  onClick={handleValidateScopeId}
                  disabled={scopeValidating || !scopeId.trim()}
                  data-testid="scope-id-validate-btn"
                >
                  {scopeValidating ? "Checking..." : "Validate"}
                </Button>
              </div>
              {scopeError && (
                <p className="text-sm text-red-600" data-testid="scope-id-error">
                  {scopeError.includes("Invalid") ? "Invalid Scope Id" : scopeError}
                </p>
              )}
              {scopeUnlock && (
                <div className="rounded-lg bg-green-50 border border-green-200 p-3 space-y-1" data-testid="scope-id-success">
                  <p className="text-sm font-semibold text-green-800">Scope unlocked</p>
                  <p className="text-xs text-green-700">{scopeUnlock.title}</p>
                  <p className="text-sm font-bold text-green-800">£{scopeUnlock.price}</p>
                </div>
              )}
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
        {scopeUnlock ? (
          <StickyPurchaseSummary
            pricing={{
              subtotal: scopeUnlock.price,
              fee: 0,
              total: scopeUnlock.price,
            }}
            cta={ctaConfig}
            currency={currency}
            disabled={false}
          />
        ) : pricing ? (
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
              isRFQ={isRFQ || !!pricing?.is_enquiry}
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
