/**
 * ApplicationLayout — Sidebar navigation with sections, enterprise feel
 * Best for: Complex B2B products, insurance applications, multi-section forms
 */
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  FileText, 
  HelpCircle, 
  ClipboardList, 
  CreditCard, 
  RefreshCcw,
  ChevronRight,
  CheckCircle2
} from "lucide-react";
import type { LayoutProps } from "./types";
import { QuestionLabel, renderIntakeField, ScopeIdBlock } from "./utils";

type Section = "overview" | "questions" | "pricing" | "faqs";

export default function ApplicationLayout({
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
  const [activeSection, setActiveSection] = useState<Section>("overview");

  const formatCurrency = (amount: number) => {
    const symbol = currency === "USD" ? "$" : currency === "EUR" ? "€" : "£";
    return `${symbol}${amount.toFixed(2)}`;
  };

  const sections: { id: Section; label: string; icon: React.ReactNode; completed?: boolean }[] = [
    { id: "overview", label: "Overview", icon: <FileText size={18} /> },
    { 
      id: "questions", 
      label: "Application Form", 
      icon: <ClipboardList size={18} />,
      completed: visibleIntakeQuestions.every(q => !q.required || intakeAnswers[q.key])
    },
    { id: "pricing", label: "Pricing & Checkout", icon: <CreditCard size={18} /> },
    { id: "faqs", label: "FAQs", icon: <HelpCircle size={18} /> },
  ];

  return (
    <div className="grid lg:grid-cols-[280px_1fr] gap-8" data-testid="application-layout">
      {/* Sidebar Navigation */}
      <div className="lg:sticky lg:top-24 lg:self-start">
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          {/* Product header in sidebar */}
          <div className="p-5 border-b border-slate-100 bg-slate-50">
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">
              {product.category}
            </p>
            <h2 className="font-semibold text-slate-900">{product.name}</h2>
            {isSubscription && (
              <span className="inline-flex items-center gap-1 mt-2 text-xs text-blue-600">
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
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-all ${
                  activeSection === sec.id
                    ? "bg-blue-50 text-blue-700"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
                data-testid={`nav-${sec.id}`}
              >
                <span className={activeSection === sec.id ? "text-blue-600" : "text-slate-400"}>
                  {sec.icon}
                </span>
                <span className="flex-1 text-sm font-medium">{sec.label}</span>
                {sec.completed && (
                  <CheckCircle2 size={16} className="text-green-500" />
                )}
              </button>
            ))}
          </nav>

          {/* Quick price preview */}
          {pricing && (
            <div className="p-5 border-t border-slate-100 bg-slate-50">
              <div className="flex justify-between items-center">
                <span className="text-sm text-slate-500">Total</span>
                <span className="font-bold text-slate-900">
                  {isRFQ ? "On request" : formatCurrency(pricing.total)}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="space-y-6">
        {/* Overview Section */}
        {activeSection === "overview" && (
          <div className="space-y-6" data-testid="section-overview">
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <h1 className="text-2xl font-bold text-slate-900 mb-2">{product.name}</h1>
              {product.tagline && (
                <p className="text-lg text-slate-500 mb-4">{product.tagline}</p>
              )}
              {/* Tags */}
              {product.tag && (
                <div className="flex flex-wrap gap-2 mb-6">
                  {product.tag.split(",").map((tag: string, i: number) => (
                    <span key={i} className="px-3 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-full border border-blue-100" data-testid={`product-tag-${i}`}>
                      {tag.trim()}
                    </span>
                  ))}
                </div>
              )}
              
              {product.description_long && (
                <div className="prose prose-sm max-w-none text-slate-600">
                  <ReactMarkdown>{product.description_long}</ReactMarkdown>
                </div>
              )}

              {product.bullets && product.bullets.length > 0 && (
                <ul className="mt-6 space-y-2">
                  {product.bullets.map((bullet, i) => (
                    <li key={i} className="flex items-start gap-2 text-slate-600">
                      <ChevronRight size={16} className="text-blue-500 mt-1 shrink-0" />
                      {bullet}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Custom sections */}
            {(product.custom_sections || []).map((sec, i) => (
              <div key={sec.id || i} className="bg-white rounded-2xl border border-slate-200 p-6">
                <h3 className="font-semibold text-slate-900 mb-3">{sec.name}</h3>
                {sec.content && (
                  <div className="prose prose-sm max-w-none text-slate-600">
                    <ReactMarkdown>{sec.content}</ReactMarkdown>
                  </div>
                )}
              </div>
            ))}

            <Button
              onClick={() => setActiveSection("questions")}
              className="w-full h-12 bg-blue-600 hover:bg-blue-700"
            >
              Start Application
              <ChevronRight size={16} className="ml-2" />
            </Button>
          </div>
        )}

        {/* Questions Section */}
        {activeSection === "questions" && (
          <div className="bg-white rounded-2xl border border-slate-200 p-6" data-testid="section-questions">
            <h2 className="text-xl font-bold text-slate-900 mb-1">Application Form</h2>
            <p className="text-sm text-slate-500 mb-6">
              Please complete all required fields to proceed
            </p>

            <div className="space-y-5">
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

            {visibleIntakeQuestions.length === 0 && (
              <p className="text-slate-400 text-center py-8">
                No additional information required for this product.
              </p>
            )}

            <div className="mt-8 pt-6 border-t border-slate-100">
              <Button
                onClick={() => setActiveSection("pricing")}
                className="w-full h-12 bg-blue-600 hover:bg-blue-700"
              >
                Continue to Pricing
                <ChevronRight size={16} className="ml-2" />
              </Button>
            </div>
          </div>
        )}

        {/* Pricing Section */}
        {activeSection === "pricing" && (
          <div className="space-y-6" data-testid="section-pricing">
            {/* Scope ID Entry (replaces old static notice) */}
            {(isRFQ || pricing?.is_enquiry) && setScopeId && handleValidateScopeId && (
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
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <h3 className="font-semibold text-slate-900 mb-4">Price Summary</h3>
              
              {pricing?.line_items && pricing.line_items.length > 0 && (
                <div className="space-y-2 mb-4 pb-4 border-b border-slate-100">
                  {pricing.line_items.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm">
                      <span className="text-slate-600">{item.label}</span>
                      <span className="text-slate-900">{formatCurrency(item.amount)}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex justify-between items-center">
                <span className="font-medium text-slate-900">Total</span>
                <span className="text-2xl font-bold text-slate-900">
                  {isRFQ && !scopeUnlock ? "On request" : formatCurrency(scopeUnlock?.price || pricing?.total || 0)}
                </span>
              </div>

              {isSubscription && (
                <div className="flex items-center gap-2 mt-3 text-sm text-blue-600">
                  <RefreshCcw size={14} />
                  <span>This is a recurring subscription</span>
                </div>
              )}
            </div>

            {/* Checkout button */}
            <Button
              onClick={handleAddToCart}
              size="lg"
              className="w-full h-14 text-base font-semibold bg-blue-600 hover:bg-blue-700"
              data-testid="checkout-btn"
            >
              {scopeUnlock ? `Add to Cart — $${scopeUnlock.price}` : isRFQ && !scopeUnlock ? "Submit Enquiry" : "Proceed to Checkout"}
            </Button>

            {termsUrl && (
              <a
                href={termsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 text-xs text-slate-500 hover:text-slate-700"
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
          <div className="bg-white rounded-2xl border border-slate-200 p-6" data-testid="section-faqs">
            <h2 className="text-xl font-bold text-slate-900 mb-6">Frequently Asked Questions</h2>
            
            {(product.faqs || []).length > 0 ? (
              <div className="space-y-6">
                {(product.faqs || []).map((faq, i) => (
                  <div key={i} className="pb-6 border-b border-slate-100 last:border-0 last:pb-0">
                    <h4 className="font-semibold text-slate-900 mb-2">{faq.question}</h4>
                    <p className="text-slate-600">{faq.answer}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-400 text-center py-8">
                No FAQs available for this product.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
