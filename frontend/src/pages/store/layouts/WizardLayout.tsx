/**
 * WizardLayout — Step-by-step guided form with progress bar
 * Best for: Complex products with many intake questions, insurance applications
 */
import { useState, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Check, RefreshCcw, FileText } from "lucide-react";
import FaqAccordion from "@/components/FaqAccordion";
import type { LayoutProps, IntakeQuestion } from "./types";
import { QuestionLabel, renderIntakeField, ScopeIdBlock, formatCurrency } from "./utils";
import { useWebsite } from "@/contexts/WebsiteContext";

export default function WizardLayout({
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

  // Group questions by step_group or create auto-groups of 3 questions
  const steps = useMemo(() => {
    const grouped = new Map<number, IntakeQuestion[]>();
    visibleIntakeQuestions.forEach((q, idx) => {
      const stepNum = q.step_group ?? Math.floor(idx / 3);
      if (!grouped.has(stepNum)) grouped.set(stepNum, []);
      grouped.get(stepNum)!.push(q);
    });
    const sortedSteps = Array.from(grouped.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([, questions]) => questions);
    return sortedSteps;
  }, [visibleIntakeQuestions]);

  const [currentStep, setCurrentStep] = useState(0);
  const totalSteps = steps.length + 1; // +1 for review step
  const isReviewStep = currentStep === steps.length;

  // Progress: 0% on first step, 100% on review step
  const progress = totalSteps > 1
    ? Math.round((currentStep / (totalSteps - 1)) * 100)
    : 100;

  const currentQuestions = steps[currentStep] || [];

  const canProceed = () => {
    if (isReviewStep) return true;
    return currentQuestions.every(q => {
      if (!q.required) return true;
      const val = intakeAnswers[q.key];
      if (val === undefined || val === null || val === "") return false;
      if (Array.isArray(val) && val.length === 0) return false;
      return true;
    });
  };

  const submitLabel = scopeUnlock
    ? `Add to cart — ${formatCurrency(scopeUnlock.price, cur)}`
    : isEnquiry
    ? (ws.sdp_cta_quote || "Submit Enquiry")
    : (ws.sdp_wizard_submit_btn || "Proceed to Checkout");

  return (
    <div className="max-w-3xl mx-auto" data-testid="wizard-layout">
      {/* Compact Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: "var(--aa-text)" }}>{product.name}</h1>
        {product.tagline && (
          <p className="mt-1" style={{ color: "var(--aa-muted)" }}>{product.tagline}</p>
        )}
        {product.tag && (
          <div className="flex flex-wrap gap-2 mt-3">
            {product.tag.split(",").map((tag: string, i: number) => (
              <span
                key={i}
                className="px-3 py-1 text-xs font-medium rounded-full border"
                style={{
                  background: "color-mix(in srgb, var(--aa-accent) 10%, transparent)",
                  color: "var(--aa-accent)",
                  borderColor: "color-mix(in srgb, var(--aa-accent) 25%, transparent)",
                }}
                data-testid={`product-tag-${i}`}
              >
                {tag.trim()}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Description + Bullets (shown before steps) */}
      {(product.description_long || (product.bullets && product.bullets.length > 0)) && (
        <div className="rounded-2xl border p-6 mb-6" style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}>
          {product.description_long && (
            <div className="prose prose-sm max-w-none mb-4" style={{ color: "var(--aa-muted)" }}>
              <ReactMarkdown>{product.description_long}</ReactMarkdown>
            </div>
          )}
          {product.bullets && product.bullets.length > 0 && (
            <ul className="space-y-2">
              {product.bullets.map((bullet: string, i: number) => (
                <li key={i} className="flex items-start gap-2 text-sm" style={{ color: "var(--aa-muted)" }}>
                  <span
                    className="mt-1.5 h-1.5 w-1.5 rounded-full shrink-0"
                    style={{ background: "var(--aa-accent)" }}
                  />
                  {bullet}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Progress Bar */}
      <div className="mb-8">
        <div className="flex justify-between text-xs mb-2" style={{ color: "var(--aa-muted)" }}>
          <span>Step {currentStep + 1} of {totalSteps}</span>
          <span>{progress}% complete</span>
        </div>
        <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--aa-surface)" }}>
          <div
            className="h-full transition-all duration-300 ease-out rounded-full"
            style={{ width: `${progress}%`, background: "var(--aa-primary)" }}
          />
        </div>
        {/* Step indicators */}
        <div className="flex justify-between mt-3">
          {Array.from({ length: totalSteps }).map((_, idx) => (
            <button
              key={idx}
              onClick={() => idx <= currentStep && setCurrentStep(idx)}
              disabled={idx > currentStep}
              className={`w-8 h-8 rounded-full text-xs font-medium transition-all ${
                idx <= currentStep ? "cursor-pointer hover:scale-110" : "cursor-not-allowed"
              }`}
              style={{
                background: idx < currentStep
                  ? "var(--aa-primary)"
                  : idx === currentStep
                  ? "var(--aa-primary)"
                  : "var(--aa-surface)",
                color: idx <= currentStep ? "var(--aa-primary-fg)" : "var(--aa-muted)",
                boxShadow: idx === currentStep ? `0 0 0 4px color-mix(in srgb, var(--aa-primary) 20%, transparent)` : "none",
              }}
              data-testid={`wizard-step-${idx}`}
            >
              {idx < currentStep ? <Check size={14} className="mx-auto" /> : idx + 1}
            </button>
          ))}
        </div>
      </div>

      {/* Step Content */}
      <div
        className="rounded-2xl border p-6 mb-6 min-h-[300px]"
        style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}
      >
        {isReviewStep ? (
          <div className="flex flex-col gap-8" data-testid="wizard-review-step">
            <div>
              <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--aa-text)" }}>
                {ws.sdp_wizard_review_title || "Review Your Selections"}
              </h2>
              <p className="text-sm" style={{ color: "var(--aa-muted)" }}>
                {ws.sdp_wizard_review_subtitle || "Please confirm your choices before proceeding"}
              </p>
            </div>

            {/* Summary of answers */}
            <div className="space-y-3">
              {visibleIntakeQuestions.filter(q => q.type !== "html_block").map(q => {
                const val = intakeAnswers[q.key];
                let displayVal: any = val;
                const valLower = String(val ?? "").toLowerCase();
                if (q.type === "boolean") {
                  displayVal = valLower === "yes" ? "Yes" : valLower === "no" ? "No" : "-";
                } else if (q.type === "dropdown") {
                  const opt = q.options?.find(o => o.value === val);
                  displayVal = opt?.label || val || "-";
                } else if (q.type === "multiselect" && Array.isArray(val)) {
                  displayVal = val.length > 0
                    ? val.map(v => q.options?.find(o => o.value === v)?.label || v).join(", ")
                    : "-";
                } else if (q.type === "date" && typeof val === "object" && val !== null) {
                  displayVal = `${val.from || ""} to ${val.to || ""}`;
                } else if (q.type === "file" && typeof val === "object" && val !== null) {
                  displayVal = val.filename || "-";
                } else {
                  displayVal = val || "-";
                }

                return (
                  <div
                    key={q.key}
                    className="flex justify-between py-2"
                    style={{ borderBottom: "1px solid var(--aa-border)" }}
                  >
                    <span className="text-sm" style={{ color: "var(--aa-muted)" }}>{q.label}</span>
                    <span className="text-sm font-medium" style={{ color: "var(--aa-text)" }}>{displayVal}</span>
                  </div>
                );
              })}
            </div>

            {/* Price Summary */}
            {pricing && (
              <div
                className="mt-6 p-4 rounded-xl"
                style={{ background: "var(--aa-surface)", border: "1px solid var(--aa-border)" }}
              >
                <div className="flex justify-between items-center">
                  <span className="font-medium" style={{ color: "var(--aa-text)" }}>
                    {ws.sdp_pricing_title || "Total"}
                  </span>
                  <span className="text-2xl font-bold" style={{ color: "var(--aa-text)" }}>
                    {isEnquiry ? "Price on request" : isFree ? "Free" : formatCurrency(pricing.total, cur)}
                  </span>
                </div>
                {isSubscription && (
                  <div className="flex items-center gap-2 mt-2 text-sm" style={{ color: "var(--aa-accent)" }}>
                    <RefreshCcw size={14} />
                    <span>Recurring subscription</span>
                  </div>
                )}
              </div>
            )}

            {termsUrl && (
              <a
                href={termsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-xs hover:opacity-70 transition-opacity"
                style={{ color: "var(--aa-muted)" }}
                data-testid="terms-link"
              >
                <FileText size={14} />
                <span>View Terms & Conditions</span>
              </a>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-8" data-testid={`wizard-step-${currentStep}-content`}>
            <div>
              <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--aa-text)" }}>
                {currentStep === 0
                  ? (ws.sdp_wizard_step_title || "Let's get started")
                  : `Step ${currentStep + 1}`}
              </h2>
              <p className="text-sm" style={{ color: "var(--aa-muted)" }}>
                {currentQuestions.length === 1
                  ? "Answer the question below to continue"
                  : `Answer the ${currentQuestions.length} questions below to continue`}
              </p>
            </div>

            <div className="space-y-5">
              {currentQuestions.map(q => (
                <div key={q.key} className="space-y-2" data-testid={`intake-field-${q.key}`}>
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
      </div>

      {/* Navigation */}
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => setCurrentStep(s => s - 1)}
          disabled={currentStep === 0}
          className="gap-2"
          data-testid="wizard-prev-btn"
        >
          <ChevronLeft size={16} />
          Back
        </Button>

        {isReviewStep ? (
          <Button
            onClick={handleAddToCart}
            className="gap-2"
            style={{ background: "var(--aa-primary)", color: "var(--aa-primary-fg)" }}
            data-testid="wizard-submit-btn"
          >
            {submitLabel}
            <ChevronRight size={16} />
          </Button>
        ) : (
          <Button
            onClick={() => setCurrentStep(s => s + 1)}
            disabled={!canProceed()}
            className="gap-2"
            style={{ background: "var(--aa-primary)", color: "var(--aa-primary-fg)" }}
            data-testid="wizard-next-btn"
          >
            Continue
            <ChevronRight size={16} />
          </Button>
        )}
      </div>

      {/* Scope ID override — shown on review step for enquiry products */}
      {isReviewStep && isEnquiry && setScopeId && handleValidateScopeId && (
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

      {/* Custom Sections */}
      {(product.custom_sections || []).map((sec: any, i: number) => (
        <div
          key={sec.id || i}
          className="rounded-2xl border p-6 mt-6"
          style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}
        >
          <h3 className="font-semibold mb-3" style={{ color: "var(--aa-text)" }}>{sec.name}</h3>
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
