/**
 * Product Detail Page — 5 Layouts
 *
 * 1. standard    — 2-col: info left, sticky price right (default)
 * 2. quick_buy   — compact, price-first, minimal friction
 * 3. wizard      — guided step-by-step with progress bar
 * 4. application — insurance/enterprise: sidebar nav + section form
 * 5. showcase    — hero + live configurator with per-question price
 */
import { useState, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import SectionCard from "@/components/SectionCard";
import StickyPurchaseSummary from "@/components/StickyPurchaseSummary";
import ProductHero from "@/components/ProductHero";
import { ChevronRight, ChevronLeft, Check, Info, AlertTriangle } from "lucide-react";

// ── Shared types ───────────────────────────────────────────────────────────────

export interface LayoutProps {
  product: any;
  pricing: any;
  visibleIntakeQuestions: any[];
  intakeAnswers: Record<string, any>;
  setIntakeAnswers: (v: Record<string, any>) => void;
  isRFQ: boolean;
  ctaConfig: any;
  requiresStripePrice: boolean;
  ws: any;
  contactEmail: string;
  terms: any;
  scopeSection?: React.ReactNode;
  customSectionsNode?: React.ReactNode;
  faqsNode?: React.ReactNode;
  renderField: (q: any, val: any, onChange: (v: any) => void) => React.ReactNode;
}

// ── Shared: question label with tooltip ───────────────────────────────────────

function QuestionLabel({ q }: { q: any }) {
  const [tip, setTip] = useState(false);
  return (
    <label className="flex items-center gap-2 text-sm font-medium text-slate-700 mb-1.5">
      {q.label}
      {q.required && <span className="text-red-500 text-xs">*</span>}
      {q.tooltip_text && (
        <span className="relative inline-block" onMouseEnter={() => setTip(true)} onMouseLeave={() => setTip(false)}>
          <Info size={13} className="text-slate-400 cursor-help" />
          {tip && (
            <span className="absolute z-50 left-5 top-0 w-56 bg-slate-900 text-white text-xs rounded-lg p-2.5 shadow-xl pointer-events-none leading-relaxed">
              {q.tooltip_text}
            </span>
          )}
        </span>
      )}
    </label>
  );
}

function IntakeItem({ q, value, onChange, renderField }: { q: any; value: any; onChange: (v: any) => void; renderField: LayoutProps["renderField"]; }) {
  if (q.type === "html_block") {
    return (
      <div className="col-span-full py-2">
        {q.label && <h3 className="text-base font-semibold text-slate-800 mb-1">{q.label}</h3>}
        {q.content && <div className="text-sm text-slate-500 prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: q.content }} />}
      </div>
    );
  }
  return (
    <div>
      <QuestionLabel q={q} />
      {renderField(q, value, onChange)}
      {q.helper_text && <p className="text-xs text-slate-400 mt-1">{q.helper_text}</p>}
    </div>
  );
}

// ── Wizard helpers ─────────────────────────────────────────────────────────────

function buildWizardSteps(questions: any[]): { title: string; html?: string; questions: any[] }[] {
  if (!questions.length) return [{ title: "Details", questions: [] }];
  const steps: { title: string; html?: string; questions: any[] }[] = [];
  let cur: { title: string; html?: string; questions: any[] } = { title: "Step 1", questions: [] };
  for (const q of questions) {
    if (q.type === "html_block") {
      if (cur.questions.length > 0) { steps.push(cur); }
      cur = { title: q.label || `Step ${steps.length + 2}`, html: q.content, questions: [] };
    } else {
      cur.questions.push(q);
    }
  }
  steps.push(cur);
  return steps.length ? steps : [{ title: "Details", questions: questions }];
}

// ═══════════════════════════════════════════════════════════════════════════════
// Layout 1 — STANDARD (classic 2-col)
// ═══════════════════════════════════════════════════════════════════════════════

export function StandardLayout({ product, pricing, visibleIntakeQuestions, intakeAnswers, setIntakeAnswers, isRFQ, ctaConfig, requiresStripePrice, ws, contactEmail, terms, scopeSection, customSectionsNode, faqsNode, renderField }: LayoutProps) {
  const nonBlockQuestions = visibleIntakeQuestions.filter(q => q.type !== "html_block");
  const blockOrQuestions = visibleIntakeQuestions; // keep blocks as content separators
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 grid grid-cols-1 lg:grid-cols-3 gap-8">
      {/* Left — Product info */}
      <div className="lg:col-span-2 space-y-6">
        <ProductHero product={product} websiteConfig={ws} />
        {/* tag badge */}
        {product.tag && (
          <span className="inline-block bg-slate-100 text-slate-600 text-xs font-medium px-3 py-1 rounded-full">{product.tag}</span>
        )}

        {/* Intake questions */}
        {nonBlockQuestions.length > 0 && (
          <SectionCard title="Tell us about your project" testId="product-intake-section">
            <div className="space-y-5">
              {blockOrQuestions.map((q: any) => (
                <IntakeItem key={q.key || q.order} q={q} value={intakeAnswers[q.key]} renderField={renderField}
                  onChange={v => setIntakeAnswers({ ...intakeAnswers, [q.key]: v })} />
              ))}
            </div>
          </SectionCard>
        )}

        {scopeSection}
        {customSectionsNode}
        {faqsNode}
      </div>

      {/* Right — Sticky price panel */}
      <div className="lg:col-span-1">
        <div className="sticky top-6">
          <StickyPurchaseSummary pricing={pricing} cta={ctaConfig} disabled={requiresStripePrice || isRFQ && !ctaConfig.onClick}
            currency="£" isRFQ={isRFQ} product={product} terms={terms} />
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Layout 2 — QUICK BUY (minimal, price-first, fast checkout)
// ═══════════════════════════════════════════════════════════════════════════════

export function QuickBuyLayout({ product, pricing, visibleIntakeQuestions, intakeAnswers, setIntakeAnswers, isRFQ, ctaConfig, requiresStripePrice, ws, terms, renderField }: LayoutProps) {
  const [expanded, setExpanded] = useState(false);
  const questions = visibleIntakeQuestions.filter(q => q.type !== "html_block");
  const total = pricing?.total ?? 0;

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      {/* Compact header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div className="flex-1 min-w-0">
          {product.tag && <span className="inline-block bg-blue-50 text-[#1e40af] text-xs font-semibold px-2.5 py-0.5 rounded-full mb-2">{product.tag}</span>}
          <h1 className="text-2xl font-bold text-slate-900 leading-tight">{product.name}</h1>
          {product.tagline && <p className="text-slate-500 text-sm mt-1">{product.tagline}</p>}
        </div>
        {!isRFQ && (
          <div className="text-right shrink-0">
            <div className="text-3xl font-bold text-slate-900">£{total.toFixed(2)}</div>
            {product.is_subscription && <div className="text-xs text-slate-400 mt-0.5">per month</div>}
          </div>
        )}
        {isRFQ && (
          <div className="text-sm font-medium text-slate-500 bg-slate-100 px-3 py-1.5 rounded-lg">Price on request</div>
        )}
      </div>

      {/* Description toggle */}
      {product.description_long && (
        <div className="mb-6">
          <p className="text-sm text-slate-600 leading-relaxed">
            {expanded ? product.description_long : product.description_long.slice(0, 200) + (product.description_long.length > 200 ? "..." : "")}
          </p>
          {product.description_long.length > 200 && (
            <button onClick={() => setExpanded(!expanded)} className="text-xs text-[#1e40af] mt-1 hover:underline">
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
        </div>
      )}

      {/* Inline questions — compact single-column */}
      {questions.length > 0 && (
        <div className="bg-slate-50 rounded-xl border border-slate-200 p-5 space-y-4 mb-6">
          {questions.map((q: any) => (
            <div key={q.key}>
              <QuestionLabel q={q} />
              {renderField(q, intakeAnswers[q.key], v => setIntakeAnswers({ ...intakeAnswers, [q.key]: v }))}
              {q.helper_text && <p className="text-xs text-slate-400 mt-1">{q.helper_text}</p>}
            </div>
          ))}
        </div>
      )}

      {/* Price breakdown */}
      {pricing?.line_items?.length > 1 && (
        <div className="mb-4 space-y-1 text-xs text-slate-500 px-1">
          {pricing.line_items.map((item: any, i: number) => (
            <div key={i} className="flex justify-between">
              <span>{item.label}</span>
              <span className="font-mono">£{item.amount.toFixed(2)}</span>
            </div>
          ))}
          <div className="flex justify-between border-t border-slate-200 pt-1.5 font-semibold text-slate-900 text-sm">
            <span>Total</span><span className="font-mono">£{total.toFixed(2)}</span>
          </div>
        </div>
      )}

      {/* CTA */}
      {ctaConfig.href ? (
        <a href={ctaConfig.href} target="_blank" rel="noopener noreferrer">
          <Button size="lg" className="w-full bg-[#0f172a] hover:bg-[#1e293b] text-white">{ctaConfig.label}</Button>
        </a>
      ) : (
        <Button size="lg" onClick={ctaConfig.onClick} disabled={requiresStripePrice}
          className="w-full bg-[#0f172a] hover:bg-[#1e293b] text-white">
          {ctaConfig.label}
        </Button>
      )}

      {/* T&C */}
      {terms && (
        <p className="text-[11px] text-slate-400 text-center mt-3">
          By proceeding you agree to our{" "}
          <a href={`/terms/${terms.id}`} target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-600">
            Terms &amp; Conditions
          </a>
        </p>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Layout 3 — WIZARD (guided step-by-step)
// ═══════════════════════════════════════════════════════════════════════════════

export function WizardLayout({ product, pricing, visibleIntakeQuestions, intakeAnswers, setIntakeAnswers, isRFQ, ctaConfig, requiresStripePrice, ws, terms, renderField }: LayoutProps) {
  const steps = useMemo(() => buildWizardSteps(visibleIntakeQuestions), [visibleIntakeQuestions]);
  const [currentStep, setCurrentStep] = useState(0);
  const isLast = currentStep === steps.length - 1;
  const isReview = currentStep === steps.length; // virtual review step
  const total = pricing?.total ?? 0;

  const next = () => {
    if (isLast) { setCurrentStep(steps.length); }
    else setCurrentStep(s => Math.min(s + 1, steps.length));
  };
  const back = () => setCurrentStep(s => Math.max(s - 1, 0));

  const step = steps[currentStep];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Wizard header */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            {product.tag && <span className="text-xs font-semibold text-[#1e40af] bg-blue-50 px-2 py-0.5 rounded-full mr-2">{product.tag}</span>}
            <span className="font-semibold text-slate-900 text-base">{product.name}</span>
          </div>
          {!isRFQ && !isReview && (
            <div className="text-sm font-semibold text-slate-700 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg">
              Step {currentStep + 1} of {steps.length}
            </div>
          )}
        </div>

        {/* Progress bar */}
        <div className="max-w-3xl mx-auto px-6 pb-3 flex items-center gap-2">
          {steps.map((s, i) => (
            <div key={i} className="flex items-center gap-2 flex-1">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-all shrink-0 ${
                i < currentStep || isReview ? "bg-green-500 text-white" : i === currentStep ? "bg-[#0f172a] text-white" : "bg-slate-200 text-slate-400"
              }`}>
                {i < currentStep || isReview ? <Check size={12} /> : i + 1}
              </div>
              <span className={`text-xs truncate hidden sm:block ${i === currentStep && !isReview ? "font-semibold text-slate-800" : "text-slate-400"}`}>{s.title}</span>
              {i < steps.length - 1 && <div className="flex-1 h-px bg-slate-200 mx-1" />}
            </div>
          ))}
          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-all shrink-0 ml-2 ${isReview ? "bg-green-500 text-white" : "bg-slate-200 text-slate-400"}`}>
            {isReview ? <Check size={12} /> : "✓"}
          </div>
          <span className={`text-xs hidden sm:block ${isReview ? "font-semibold text-slate-800" : "text-slate-400"}`}>Review</span>
        </div>
      </div>

      {/* Step content */}
      <div className="max-w-3xl mx-auto px-6 py-8">
        {!isReview ? (
          <div className="bg-white rounded-xl border border-slate-200 p-7 shadow-sm">
            {step.html && (
              <div className="mb-5 p-4 bg-blue-50 rounded-lg border border-blue-100 text-sm text-blue-700 prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: step.html }} />
            )}
            <h2 className="text-xl font-bold text-slate-900 mb-6">{step.title}</h2>
            <div className="space-y-5">
              {step.questions.map((q: any) => (
                <div key={q.key}>
                  <QuestionLabel q={q} />
                  {renderField(q, intakeAnswers[q.key], v => setIntakeAnswers({ ...intakeAnswers, [q.key]: v }))}
                  {q.helper_text && <p className="text-xs text-slate-400 mt-1">{q.helper_text}</p>}
                </div>
              ))}
              {step.questions.length === 0 && (
                <p className="text-slate-400 italic text-sm">No questions in this step.</p>
              )}
            </div>
          </div>
        ) : (
          // Review step
          <div className="space-y-5">
            <div className="bg-white rounded-xl border border-slate-200 p-7 shadow-sm">
              <h2 className="text-xl font-bold text-slate-900 mb-5">Review your answers</h2>
              <div className="divide-y divide-slate-100">
                {steps.flatMap(s => s.questions).filter(q => intakeAnswers[q.key] != null && intakeAnswers[q.key] !== "").map((q: any) => (
                  <div key={q.key} className="py-3 flex justify-between text-sm">
                    <span className="text-slate-500 font-medium">{q.label}</span>
                    <span className="text-slate-900 font-semibold">{
                      Array.isArray(intakeAnswers[q.key]) ? intakeAnswers[q.key].join(", ") : String(intakeAnswers[q.key])
                    }</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Price summary card */}
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
              {pricing?.line_items?.length > 1 && (
                <div className="space-y-1.5 mb-4">
                  {pricing.line_items.map((item: any, i: number) => (
                    <div key={i} className="flex justify-between text-sm text-slate-600">
                      <span>{item.label}</span>
                      <span className="font-mono">£{item.amount.toFixed(2)}</span>
                    </div>
                  ))}
                  <div className="border-t border-slate-200 pt-2" />
                </div>
              )}
              <div className="flex items-center justify-between mb-5">
                <span className="text-lg font-semibold text-slate-700">Total</span>
                <span className="text-3xl font-bold text-slate-900">{isRFQ ? "Price on request" : `£${(pricing?.total ?? 0).toFixed(2)}`}</span>
              </div>
              {product.is_subscription && (
                <div className="text-xs text-[#1e40af] bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 mb-4">
                  Recurring subscription — billed monthly
                </div>
              )}
              {ctaConfig.href ? (
                <a href={ctaConfig.href} target="_blank" rel="noopener noreferrer">
                  <Button size="lg" className="w-full bg-[#0f172a] hover:bg-[#1e293b] text-white">{ctaConfig.label}</Button>
                </a>
              ) : (
                <Button size="lg" onClick={ctaConfig.onClick} disabled={requiresStripePrice}
                  className="w-full bg-[#0f172a] hover:bg-[#1e293b] text-white">{ctaConfig.label}</Button>
              )}
              {terms && (
                <p className="text-[11px] text-slate-400 text-center mt-3">
                  By proceeding you agree to our{" "}
                  <a href={`/terms/${terms.id}`} target="_blank" rel="noopener noreferrer" className="underline">Terms &amp; Conditions</a>
                </p>
              )}
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between mt-6">
          <Button variant="outline" onClick={back} disabled={currentStep === 0} className="flex items-center gap-2">
            <ChevronLeft size={16} /> Back
          </Button>
          {!isReview && (
            <Button onClick={next} className="bg-[#0f172a] hover:bg-[#1e293b] text-white flex items-center gap-2">
              {isLast ? "Review & Submit" : "Continue"} <ChevronRight size={16} />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Layout 4 — APPLICATION FORM (insurance/enterprise, sidebar nav)
// ═══════════════════════════════════════════════════════════════════════════════

export function ApplicationLayout({ product, pricing, visibleIntakeQuestions, intakeAnswers, setIntakeAnswers, isRFQ, ctaConfig, requiresStripePrice, ws, terms, renderField }: LayoutProps) {
  const sections = useMemo(() => buildWizardSteps(visibleIntakeQuestions), [visibleIntakeQuestions]);
  const [activeSection, setActiveSection] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const allAnswered = sections.every(s => s.questions.filter(q => q.required).every(q => !!intakeAnswers[q.key]));

  const completedSections = sections.map(s =>
    s.questions.filter(q => q.required).every(q => !!intakeAnswers[q.key]) && s.questions.some(q => q.required)
  );

  if (submitted) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="bg-white rounded-xl border border-slate-200 p-10 max-w-lg text-center shadow-sm">
          <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
            <Check size={28} className="text-green-600" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Application Submitted</h2>
          <p className="text-slate-500 text-sm">We've received your application and will be in touch shortly.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100">
      {/* Application header */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            {product.tag && <span className="text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full mr-2 border border-amber-200">{product.tag}</span>}
            <span className="font-bold text-slate-900">{product.name}</span>
            <span className="text-slate-400 ml-2 text-sm">— Application Form</span>
          </div>
          <div className="text-xs text-slate-400 hidden sm:block">
            {sections.filter((_, i) => completedSections[i]).length} of {sections.length} sections complete
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8 flex gap-6">
        {/* Left sidebar */}
        <div className="w-56 shrink-0 hidden md:block">
          <div className="bg-white rounded-xl border border-slate-200 p-2 space-y-0.5 sticky top-6">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-3 py-2">Sections</p>
            {sections.map((s, i) => (
              <button key={i} onClick={() => setActiveSection(i)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left transition-all ${
                  activeSection === i ? "bg-slate-900 text-white" : "hover:bg-slate-50 text-slate-700"
                }`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${
                  completedSections[i] ? "bg-green-500 text-white" : activeSection === i ? "bg-white/20 text-white" : "bg-slate-200 text-slate-500"
                }`}>
                  {completedSections[i] ? <Check size={10} /> : i + 1}
                </span>
                <span className="text-xs font-medium truncate">{s.title}</span>
              </button>
            ))}
            <div className="border-t border-slate-100 pt-1 mt-1">
              <button onClick={() => setActiveSection(sections.length)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left transition-all ${
                  activeSection === sections.length ? "bg-slate-900 text-white" : "hover:bg-slate-50 text-slate-700"
                }`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${
                  activeSection === sections.length ? "bg-white/20 text-white" : "bg-slate-200 text-slate-500"
                }`}>✓</span>
                <span className="text-xs font-medium">Summary</span>
              </button>
            </div>
          </div>
        </div>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          {activeSection < sections.length ? (
            <div className="bg-white rounded-xl border border-slate-200 p-7 shadow-sm">
              {sections[activeSection].html && (
                <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-100 text-sm text-blue-700"
                  dangerouslySetInnerHTML={{ __html: sections[activeSection].html! }} />
              )}
              <h2 className="text-2xl font-bold text-slate-900 mb-2">{sections[activeSection].title}</h2>
              <p className="text-sm text-slate-400 mb-8">Please complete all required fields in this section before moving on.</p>

              <div className="space-y-6">
                {sections[activeSection].questions.map((q: any) => (
                  <div key={q.key} className="border-b border-slate-100 pb-6 last:border-0 last:pb-0">
                    <QuestionLabel q={q} />
                    {renderField(q, intakeAnswers[q.key], v => setIntakeAnswers({ ...intakeAnswers, [q.key]: v }))}
                    {q.helper_text && <p className="text-xs text-slate-400 mt-1.5">{q.helper_text}</p>}
                  </div>
                ))}
              </div>

              <div className="flex justify-between mt-8">
                {activeSection > 0 ? (
                  <Button variant="outline" onClick={() => setActiveSection(s => s - 1)} className="flex items-center gap-2">
                    <ChevronLeft size={16} /> Previous
                  </Button>
                ) : <div />}
                <Button onClick={() => setActiveSection(s => Math.min(s + 1, sections.length))}
                  className="bg-[#0f172a] hover:bg-[#1e293b] text-white flex items-center gap-2">
                  {activeSection === sections.length - 1 ? "Review Application" : "Save & Continue"} <ChevronRight size={16} />
                </Button>
              </div>
            </div>
          ) : (
            // Summary + submit
            <div className="space-y-5">
              <div className="bg-white rounded-xl border border-slate-200 p-7 shadow-sm">
                <h2 className="text-2xl font-bold text-slate-900 mb-6">Review your application</h2>
                {!allAnswered && (
                  <div className="flex items-start gap-2.5 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg p-3.5 mb-5 text-sm">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                    Some required fields are incomplete. Please go back and fill them in.
                  </div>
                )}
                {sections.map((s, si) => (
                  <div key={si} className="mb-6">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-semibold text-slate-800">{s.title}</h3>
                      <button onClick={() => setActiveSection(si)} className="text-xs text-[#1e40af] hover:underline">Edit</button>
                    </div>
                    <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                      {s.questions.map((q: any) => (
                        <div key={q.key} className="flex flex-col">
                          <span className="text-xs text-slate-400">{q.label}</span>
                          <span className="text-sm font-medium text-slate-900">
                            {intakeAnswers[q.key] != null && intakeAnswers[q.key] !== ""
                              ? Array.isArray(intakeAnswers[q.key]) ? intakeAnswers[q.key].join(", ") : String(intakeAnswers[q.key])
                              : <span className="italic text-slate-300">Not answered</span>}
                          </span>
                        </div>
                      ))}
                    </div>
                    {si < sections.length - 1 && <div className="border-b border-slate-100 mt-5" />}
                  </div>
                ))}
              </div>

              {/* Price reveal */}
              <div className="bg-slate-900 text-white rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-slate-300 font-medium">Your quote</span>
                  {product.is_subscription && (
                    <span className="text-xs bg-blue-500/20 text-blue-300 border border-blue-500/30 px-2 py-0.5 rounded-full">Monthly subscription</span>
                  )}
                </div>
                {pricing?.line_items?.length > 1 && (
                  <div className="space-y-1.5 mb-4 text-sm">
                    {pricing.line_items.map((item: any, i: number) => (
                      <div key={i} className="flex justify-between text-slate-400">
                        <span>{item.label}</span><span>£{item.amount.toFixed(2)}</span>
                      </div>
                    ))}
                    <div className="border-t border-slate-700 pt-2" />
                  </div>
                )}
                <div className="flex items-end justify-between mb-6">
                  <span className="text-lg text-slate-300">Total</span>
                  <span className="text-4xl font-bold">{isRFQ ? "—" : `£${(pricing?.total ?? 0).toFixed(2)}`}</span>
                </div>
                {ctaConfig.href ? (
                  <a href={ctaConfig.href} target="_blank" rel="noopener noreferrer">
                    <Button size="lg" className="w-full bg-white text-slate-900 hover:bg-slate-100 font-semibold">{ctaConfig.label}</Button>
                  </a>
                ) : (
                  <Button size="lg" onClick={ctaConfig.onClick} disabled={requiresStripePrice || !allAnswered}
                    className="w-full bg-white text-slate-900 hover:bg-slate-100 font-semibold">{ctaConfig.label}</Button>
                )}
                {terms && (
                  <p className="text-[11px] text-slate-500 text-center mt-3">
                    By submitting you agree to our{" "}
                    <a href={`/terms/${terms.id}`} target="_blank" rel="noopener noreferrer" className="underline text-slate-400">Terms</a>
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Layout 5 — SHOWCASE + CONFIGURATOR (hero + live price calculator)
// ═══════════════════════════════════════════════════════════════════════════════

export function ShowcaseLayout({ product, pricing, visibleIntakeQuestions, intakeAnswers, setIntakeAnswers, isRFQ, ctaConfig, requiresStripePrice, ws, terms, customSectionsNode, faqsNode, renderField }: LayoutProps) {
  const questions = visibleIntakeQuestions.filter(q => q.type !== "html_block");
  const blocks = visibleIntakeQuestions;
  const total = pricing?.total ?? 0;
  const lineItems: any[] = pricing?.line_items ?? [];

  return (
    <div>
      {/* Hero — full width, impactful */}
      <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-[#1e3a6e] text-white">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <div className="max-w-3xl">
            {product.tag && <span className="inline-block text-[#60a5fa] text-xs font-semibold uppercase tracking-widest mb-4">{product.tag}</span>}
            <h1 className="text-4xl sm:text-5xl font-bold leading-tight mb-5">{product.name}</h1>
            {product.tagline && <p className="text-xl text-slate-300 mb-6">{product.tagline}</p>}
            {product.description_long && (
              <p className="text-slate-400 leading-relaxed max-w-2xl">{product.description_long}</p>
            )}
            {product.bullets?.length > 0 && (
              <ul className="mt-6 space-y-2">
                {product.bullets.map((b: string, i: number) => (
                  <li key={i} className="flex items-center gap-2.5 text-sm text-slate-300">
                    <Check size={14} className="text-emerald-400 shrink-0" /> {b}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* Configurator + Details — reversed 2-col */}
      <div className="max-w-7xl mx-auto px-6 py-10 grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* LEFT (60%) — live configurator */}
        <div className="lg:col-span-3 space-y-5">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="bg-slate-50 border-b border-slate-200 px-6 py-4 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">Configure your package</h2>
              {!isRFQ && (
                <div className="text-right">
                  <div className="text-2xl font-bold text-slate-900">£{total.toFixed(2)}</div>
                  {product.is_subscription && <div className="text-xs text-slate-400">/ month</div>}
                </div>
              )}
              {isRFQ && <div className="text-sm font-medium text-slate-400">Price on request</div>}
            </div>

            <div className="p-6 space-y-5">
              {blocks.map((q: any) => {
                if (q.type === "html_block") {
                  return (
                    <div key={q.key || q.order} className="py-1 border-t border-slate-100 pt-4">
                      {q.label && <h3 className="text-sm font-semibold text-slate-600 mb-1">{q.label}</h3>}
                      {q.content && <div className="text-xs text-slate-400 prose prose-xs max-w-none" dangerouslySetInnerHTML={{ __html: q.content }} />}
                    </div>
                  );
                }
                const item = lineItems.find((l: any) => l.label?.startsWith(q.label) || l.label?.includes(q.label));
                return (
                  <div key={q.key} className="flex items-start gap-4">
                    <div className="flex-1">
                      <QuestionLabel q={q} />
                      {renderField(q, intakeAnswers[q.key], v => setIntakeAnswers({ ...intakeAnswers, [q.key]: v }))}
                      {q.helper_text && <p className="text-xs text-slate-400 mt-1">{q.helper_text}</p>}
                    </div>
                    {/* Inline price contribution */}
                    {item && (
                      <div className="shrink-0 mt-6 text-right min-w-[70px]">
                        <span className="text-sm font-semibold text-[#1e40af]">+£{item.amount.toFixed(2)}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Price breakdown inside configurator */}
            {lineItems.length > 1 && (
              <div className="border-t border-slate-100 bg-slate-50 px-6 py-4">
                <div className="space-y-1 mb-3">
                  {lineItems.map((item: any, i: number) => (
                    <div key={i} className="flex justify-between text-xs text-slate-500">
                      <span>{item.label}</span>
                      <span className="font-mono">£{item.amount.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
                <div className="flex justify-between text-sm font-semibold text-slate-800 border-t border-slate-200 pt-2">
                  <span>Total</span>
                  <span className="font-mono">£{total.toFixed(2)}</span>
                </div>
              </div>
            )}

            <div className="px-6 pb-6">
              {ctaConfig.href ? (
                <a href={ctaConfig.href} target="_blank" rel="noopener noreferrer">
                  <Button size="lg" className="w-full mt-4 bg-[#0f172a] hover:bg-[#1e293b] text-white">{ctaConfig.label}</Button>
                </a>
              ) : (
                <Button size="lg" onClick={ctaConfig.onClick} disabled={requiresStripePrice}
                  className="w-full mt-4 bg-[#0f172a] hover:bg-[#1e293b] text-white">{ctaConfig.label}</Button>
              )}
              {terms && (
                <p className="text-[11px] text-slate-400 text-center mt-3">
                  By proceeding you agree to our{" "}
                  <a href={`/terms/${terms.id}`} target="_blank" rel="noopener noreferrer" className="underline">Terms &amp; Conditions</a>
                </p>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT (40%) — product details */}
        <div className="lg:col-span-2 space-y-5">
          {customSectionsNode}
          {faqsNode}
        </div>
      </div>
    </div>
  );
}
