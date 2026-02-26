/**
 * WizardLayout — Step-by-step guided form with progress bar
 * Best for: Complex products with many intake questions, insurance applications
 */
import { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Check, RefreshCcw, FileText } from "lucide-react";
import type { LayoutProps, IntakeQuestion } from "./types";
import { QuestionLabel, renderIntakeField, ScopeIdBlock } from "./utils";

export default function WizardLayout({
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
  // Group questions by step_group or create auto-groups of 3-4 questions
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
    
    // Always add a review step at the end
    return sortedSteps.length > 0 ? sortedSteps : [];
  }, [visibleIntakeQuestions]);

  const [currentStep, setCurrentStep] = useState(0);
  const totalSteps = steps.length + 1; // +1 for review step
  const isReviewStep = currentStep === steps.length;
  const progress = ((currentStep + 1) / totalSteps) * 100;

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

  const formatCurrency = (amount: number) => {
    const symbol = currency === "USD" ? "$" : currency === "EUR" ? "€" : "£";
    return `${symbol}${amount.toFixed(2)}`;
  };

  return (
    <div className="max-w-3xl mx-auto" data-testid="wizard-layout">
      {/* Compact Header */}
      <div className="mb-6">
        <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">
          {product.category}
        </p>
        <h1 className="text-2xl font-bold text-slate-900">{product.name}</h1>
        {product.tagline && (
          <p className="text-slate-500 mt-1">{product.tagline}</p>
        )}
        {/* Tags */}
        {product.tag && (
          <div className="flex flex-wrap gap-2 mt-3">
            {product.tag.split(",").map((tag: string, i: number) => (
              <span key={i} className="px-3 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-full border border-blue-100" data-testid={`product-tag-${i}`}>
                {tag.trim()}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Description + Bullets (shown before steps) */}
      {(product.description_long || (product.bullets && product.bullets.length > 0)) && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-6">
          {product.description_long && (
            <p className="text-slate-600 text-sm leading-relaxed mb-4">{product.description_long}</p>
          )}
          {product.bullets && product.bullets.length > 0 && (
            <ul className="space-y-2">
              {product.bullets.map((bullet: string, i: number) => (
                <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-blue-500 shrink-0" />
                  {bullet}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Progress Bar */}
      <div className="mb-8">
        <div className="flex justify-between text-xs text-slate-500 mb-2">
          <span>Step {currentStep + 1} of {totalSteps}</span>
          <span>{Math.round(progress)}% complete</span>
        </div>
        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
          <div 
            className="h-full bg-blue-600 transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
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
                idx < currentStep
                  ? "bg-blue-600 text-white"
                  : idx === currentStep
                  ? "bg-blue-600 text-white ring-4 ring-blue-100"
                  : "bg-slate-100 text-slate-400"
              } ${idx <= currentStep ? "cursor-pointer hover:scale-110" : "cursor-not-allowed"}`}
              data-testid={`wizard-step-${idx}`}
            >
              {idx < currentStep ? <Check size={14} className="mx-auto" /> : idx + 1}
            </button>
          ))}
        </div>
      </div>

      {/* Step Content */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-6 min-h-[300px]">
        {isReviewStep ? (
          <div className="space-y-6" data-testid="wizard-review-step">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 mb-1">Review Your Selections</h2>
              <p className="text-sm text-slate-500">Please confirm your choices before proceeding</p>
            </div>
            
            {/* Summary of answers */}
            <div className="space-y-3">
              {visibleIntakeQuestions.filter(q => q.type !== "html_block").map(q => {
                const val = intakeAnswers[q.key];
                let displayVal = val;
                if (q.type === "boolean") displayVal = val === "yes" ? "Yes" : val === "no" ? "No" : "-";
                else if (q.type === "dropdown") {
                  const opt = q.options?.find(o => o.value === val);
                  displayVal = opt?.label || val;
                } else if (q.type === "multiselect" && Array.isArray(val)) {
                  displayVal = val.map(v => q.options?.find(o => o.value === v)?.label || v).join(", ");
                } else if (q.type === "date" && typeof val === "object") {
                  displayVal = `${val.from || ""} to ${val.to || ""}`;
                } else if (q.type === "file" && typeof val === "object") {
                  displayVal = val.filename || "-";
                }
                
                return (
                  <div key={q.key} className="flex justify-between py-2 border-b border-slate-100 last:border-0">
                    <span className="text-sm text-slate-600">{q.label}</span>
                    <span className="text-sm font-medium text-slate-900">{displayVal || "-"}</span>
                  </div>
                );
              })}
            </div>

            {/* Price Summary */}
            {pricing && (
              <div className="mt-6 p-4 bg-slate-50 rounded-xl">
                <div className="flex justify-between items-center">
                  <span className="font-medium text-slate-700">Total</span>
                  <span className="text-2xl font-bold text-slate-900">
                    {isRFQ ? "Price on request" : formatCurrency(pricing.total)}
                  </span>
                </div>
                {isSubscription && (
                  <div className="flex items-center gap-2 mt-2 text-sm text-blue-600">
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
                className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700"
                data-testid="terms-link"
              >
                <FileText size={14} />
                <span>View Terms & Conditions</span>
              </a>
            )}
          </div>
        ) : (
          <div className="space-y-6" data-testid={`wizard-step-${currentStep}-content`}>
            <div>
              <h2 className="text-lg font-semibold text-slate-900 mb-1">
                {currentStep === 0 ? "Let's get started" : `Step ${currentStep + 1}`}
              </h2>
              <p className="text-sm text-slate-500">
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
          <>
            <Button
              onClick={handleAddToCart}
              className="gap-2 bg-blue-600 hover:bg-blue-700"
              data-testid="wizard-submit-btn"
            >
              {scopeUnlock ? `Add to Cart — $${scopeUnlock.price}` : isRFQ ? "Submit Enquiry" : "Proceed to Checkout"}
              <ChevronRight size={16} />
            </Button>
          </>
        ) : (
          <Button
            onClick={() => setCurrentStep(s => s + 1)}
            disabled={!canProceed()}
            className="gap-2 bg-blue-600 hover:bg-blue-700"
            data-testid="wizard-next-btn"
          >
            Continue
            <ChevronRight size={16} />
          </Button>
        )}
      </div>

      {/* Custom Sections */}
      {(product.custom_sections || []).map((sec: any, i: number) => (
        <div key={sec.id || i} className="bg-white rounded-2xl border border-slate-200 p-6 mt-6">
          <h3 className="font-semibold text-slate-900 mb-3">{sec.name}</h3>
          {sec.content && (
            <p className="text-sm text-slate-600 leading-relaxed">{sec.content}</p>
          )}
        </div>
      ))}

      {/* FAQs */}
      {(product.faqs || []).length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mt-6">
          <h3 className="font-semibold text-slate-900 mb-4">FAQs</h3>
          <div className="space-y-4">
            {(product.faqs || []).map((faq: any, i: number) => (
              <div key={i} className="pb-4 border-b border-slate-100 last:border-0 last:pb-0">
                <p className="font-medium text-slate-900 mb-1">{faq.question}</p>
                <p className="text-sm text-slate-600">{faq.answer}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
