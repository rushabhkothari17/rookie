/**
 * ApplicationLayout — Sidebar navigation with sections, enterprise feel
 * Best for: Complex B2B products, insurance applications, multi-section forms
 */
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import {
  FileText,
  HelpCircle,
  ClipboardList,
  CreditCard,
  RefreshCcw,
  ChevronRight,
  CheckCircle2,
} from "lucide-react";
import type { LayoutProps } from "./types";
import { QuestionLabel, renderIntakeField, ScopeIdBlock, formatCurrency } from "./utils";
import { useWebsite } from "@/contexts/WebsiteContext";

type AppSection = "overview" | "questions" | "pricing" | "faqs";

export default function ApplicationLayout({
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
  scopeUnlock,
  scopeId,
  setScopeId,
  handleValidateScopeId,
  scopeValidating,
  scopeError,
}: LayoutProps) {
  const ws = useWebsite();
  const cur = currency || "USD";
  const [activeSection, setActiveSection] = useState<AppSection>("overview");

  const isEnquiry = product.pricing_type === "enquiry" || ((isRFQ || pricing?.is_enquiry) && product?.base_price == null);
  const isFree = !isEnquiry && pricing && pricing.total === 0;

  const sections: { id: AppSection; label: string; icon: React.ReactNode; completed?: boolean }[] = [
    { id: "overview", label: ws.sdp_app_nav_overview || "Overview", icon: <FileText size={18} /> },
    {
      id: "questions",
      label: ws.sdp_app_nav_questions || "Application Form",
      icon: <ClipboardList size={18} />,
      completed: visibleIntakeQuestions.length > 0 && visibleIntakeQuestions.every(q => !q.required || !!intakeAnswers[q.key]),
    },
    { id: "pricing", label: ws.sdp_app_nav_pricing || "Pricing & Checkout", icon: <CreditCard size={18} /> },
    { id: "faqs", label: ws.sdp_app_nav_faqs || "FAQs", icon: <HelpCircle size={18} /> },
  ];

  const checkoutLabel = scopeUnlock
    ? `Add to Cart — ${formatCurrency(scopeUnlock.price, cur)}`
    : isEnquiry && !scopeUnlock
    ? (ws.sdp_cta_quote || "Submit Enquiry")
    : isFree
    ? (ws.sdp_cta_free || "Get it free")
    : "Proceed to Checkout";

  return (
    <div className="grid lg:grid-cols-[280px_1fr] gap-8" data-testid="application-layout">
      {/* Sidebar Navigation */}
      <div className="lg:sticky lg:top-24 lg:self-start">
        <div className="rounded-2xl border overflow-hidden" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
          {/* Product header in sidebar */}
          <div className="p-5 border-b" style={{ borderColor: "var(--aa-border)", background: "var(--aa-surface)" }}>
            <h2 className="font-semibold" style={{ color: "var(--aa-text)" }}>{product.name}</h2>
            {isSubscription && (
              <span className="inline-flex items-center gap-1 mt-2 text-xs" style={{ color: "var(--aa-accent)" }}>
                <RefreshCcw size={12} />
                Subscription
              </span>
            )}
          </div>

          {/* Navigation items */}
          <nav className="p-2">
            {sections.map(sec => (
              <button
                key={sec.id}
                onClick={() => setActiveSection(sec.id)}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-all"
                style={{
                  background: activeSection === sec.id
                    ? `color-mix(in srgb, var(--aa-primary) 10%, transparent)`
                    : "transparent",
                  color: activeSection === sec.id ? "var(--aa-primary)" : "var(--aa-muted)",
                }}
                data-testid={`nav-${sec.id}`}
              >
                <span style={{ color: activeSection === sec.id ? "var(--aa-primary)" : "var(--aa-muted)" }}>
                  {sec.icon}
                </span>
                <span className="flex-1 text-sm font-medium">{sec.label}</span>
                {sec.completed && (
                  <CheckCircle2 size={16} style={{ color: "var(--aa-success)" }} />
                )}
              </button>
            ))}
          </nav>

          {/* Quick price preview */}
          {pricing && (
            <div className="p-5 border-t" style={{ borderColor: "var(--aa-border)", background: "var(--aa-surface)" }}>
              <div className="flex justify-between items-center">
                <span className="text-sm" style={{ color: "var(--aa-muted)" }}>Total</span>
                <span className="font-bold" style={{ color: "var(--aa-text)" }}>
                  {isEnquiry && !scopeUnlock
                    ? "On request"
                    : isFree
                    ? "Free"
                    : formatCurrency(scopeUnlock?.price ?? pricing.total, cur)}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="space-y-8">
        {/* Overview Section */}
        {activeSection === "overview" && (
          <div className="space-y-8" data-testid="section-overview">
            <div className="rounded-2xl border p-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
              <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--aa-text)" }}>{product.name}</h1>
              {product.tagline && (
                <p className="text-lg mb-4" style={{ color: "var(--aa-muted)" }}>{product.tagline}</p>
              )}

              {product.description_long && (
                <div className="prose prose-sm max-w-none" style={{ color: "var(--aa-muted)" }}>
                  <ReactMarkdown>{product.description_long}</ReactMarkdown>
                </div>
              )}

              {product.bullets && product.bullets.length > 0 && (
                <ul className="mt-6 space-y-2">
                  {product.bullets.map((bullet, i) => (
                    <li key={i} className="flex items-start gap-2" style={{ color: "var(--aa-muted)" }}>
                      <ChevronRight size={16} className="mt-1 shrink-0" style={{ color: "var(--aa-accent)" }} />
                      {bullet}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Custom sections */}
            {(product.custom_sections || []).map((sec, i) => (
              <div key={sec.id || i} className="rounded-2xl border p-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
                <h3 className="font-semibold mb-3" style={{ color: "var(--aa-text)" }}>{sec.name}</h3>
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

            <Button
              onClick={() => setActiveSection("questions")}
              className="w-full h-12"
              style={{ background: "var(--aa-primary)", color: "var(--aa-primary-fg)" }}
              data-testid="app-start-btn"
            >
              {ws.sdp_app_start_btn || "Start Application"}
              <ChevronRight size={16} className="ml-2" />
            </Button>
          </div>
        )}

        {/* Questions Section */}
        {activeSection === "questions" && (
          <div className="rounded-2xl border p-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }} data-testid="section-questions">
            <h2 className="text-xl font-bold mb-1" style={{ color: "var(--aa-text)" }}>
              {ws.sdp_app_nav_questions || "Application Form"}
            </h2>
            <p className="text-sm mb-6" style={{ color: "var(--aa-muted)" }}>
              Please complete all required fields to proceed
            </p>

            <div className="space-y-5">
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

            {visibleIntakeQuestions.length === 0 && (
              <p className="text-center py-8" style={{ color: "var(--aa-muted)" }}>
                No additional information required for this product.
              </p>
            )}

            <div className="mt-8 pt-6" style={{ borderTop: "1px solid var(--aa-border)" }}>
              <Button
                onClick={() => setActiveSection("pricing")}
                className="w-full h-12"
                style={{ background: "var(--aa-primary)", color: "var(--aa-primary-fg)" }}
                data-testid="app-continue-btn"
              >
                {ws.sdp_app_continue_btn || "Continue to Pricing"}
                <ChevronRight size={16} className="ml-2" />
              </Button>
            </div>
          </div>
        )}

        {/* Pricing Section */}
        {activeSection === "pricing" && (
          <div className="space-y-8" data-testid="section-pricing">
            {/* Scope ID Entry for enquiry products */}
            {isEnquiry && setScopeId && handleValidateScopeId && (
              <ScopeIdBlock
                scopeId={scopeId || ""}
                setScopeId={setScopeId}
                handleValidateScopeId={handleValidateScopeId}
                scopeValidating={scopeValidating}
                scopeError={scopeError}
                scopeUnlock={scopeUnlock}
              />
            )}

            {/* Price breakdown */}
            <div className="rounded-2xl border p-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
              <h3 className="font-semibold mb-4" style={{ color: "var(--aa-text)" }}>
                {ws.sdp_pricing_title || "Price Summary"}
              </h3>

              {product?.show_price_breakdown && pricing?.line_items && pricing.line_items.length > 0 && (
                <div className="space-y-2 mb-4 pb-4" style={{ borderBottom: "1px solid var(--aa-border)" }}>
                  {pricing.line_items.map((item: any, i: number) => (
                    <div key={i} className="flex justify-between text-sm">
                      <span style={{ color: "var(--aa-muted)" }}>{item.label}</span>
                      <span style={{ color: "var(--aa-text)" }}>{formatCurrency(item.amount, cur)}</span>
                    </div>
                  ))}
                  {product?.price_rounding && (
                    <p className="text-[11px] mt-1" style={{ color: "var(--aa-muted)" }}>
                      * Total rounded to the nearest {product.price_rounding}
                    </p>
                  )}
                </div>
              )}

              <div className="flex justify-between items-center">
                <span className="font-medium" style={{ color: "var(--aa-text)" }}>Total</span>
                <span className="text-2xl font-bold" style={{ color: "var(--aa-text)" }}>
                  {isEnquiry && !scopeUnlock
                    ? "On request"
                    : isFree
                    ? "Free"
                    : formatCurrency(scopeUnlock?.price ?? pricing?.total ?? 0, cur)}
                </span>
              </div>

              {isSubscription && (
                <div className="flex items-center gap-2 mt-3 text-sm" style={{ color: "var(--aa-accent)" }}>
                  <RefreshCcw size={14} />
                  <span>This is a recurring subscription</span>
                </div>
              )}

              {isFree && (
                <div
                  className="flex items-center gap-2 mt-3 p-3 rounded-xl border text-sm"
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
            </div>

            {/* Checkout button */}
            <Button
              onClick={handleAddToCart}
              size="lg"
              className="w-full h-14 text-base font-semibold"
              style={{ background: "var(--aa-primary)", color: "var(--aa-primary-fg)" }}
              data-testid="checkout-btn"
            >
              {checkoutLabel}
            </Button>

            {termsUrl && (
              <a
                href={termsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 text-xs hover:opacity-70 transition-opacity"
                style={{ color: "var(--aa-muted)" }}
                data-testid="terms-link"
              >
                <FileText size={14} />
                <span>View Terms & Conditions</span>
              </a>
            )}
          </div>
        )}

        {/* FAQs Section */}
        {activeSection === "faqs" && (
          <div className="rounded-2xl border p-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }} data-testid="section-faqs">
            <h2 className="text-xl font-bold mb-6" style={{ color: "var(--aa-text)" }}>
              {ws.sdp_faqs_title || "Frequently Asked Questions"}
            </h2>

            {(product.faqs || []).length > 0 ? (
              <div className="space-y-6">
                {(product.faqs || []).map((faq, i) => (
                  <div key={i} className="pb-6 last:pb-0" style={{ borderBottom: "1px solid var(--aa-border)" }}>
                    <h4 className="font-semibold mb-2" style={{ color: "var(--aa-text)" }}>{faq.question}</h4>
                    <p style={{ color: "var(--aa-muted)" }}>{faq.answer}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center py-8" style={{ color: "var(--aa-muted)" }}>
                No FAQs available for this product.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
