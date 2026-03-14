/**
 * FaqAccordion — Collapsible FAQ section used across all product layouts.
 * Uses Radix Accordion for smooth animated expand/collapse.
 * Fully compatible with both light and dark CSS variable themes.
 */
import { useState } from "react";
import { ChevronDown } from "lucide-react";

interface FaqItem {
  question: string;
  answer: string;
}

interface FaqAccordionProps {
  faqs: FaqItem[];
  title?: string;
  testId?: string;
  card?: boolean;
}

export default function FaqAccordion({
  faqs,
  title = "Frequently Asked Questions",
  testId = "product-faqs",
  card = true,
}: FaqAccordionProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  if (!faqs || faqs.length === 0) return null;

  const toggle = (i: number) => setOpenIndex(openIndex === i ? null : i);

  const content = (
    <div data-testid={`${testId}-list`}>
      {faqs.map((faq, i) => {
        const isOpen = openIndex === i;
        return (
          <div
            key={i}
            style={{ borderBottom: "1px solid var(--aa-border)" }}
          >
            <button
              type="button"
              onClick={() => toggle(i)}
              className="w-full flex items-center justify-between py-4 text-sm font-semibold text-left transition-opacity hover:opacity-70"
              style={{ color: "var(--aa-text)", background: "transparent", border: "none" }}
              aria-expanded={isOpen}
              data-testid={`faq-item-${i}-trigger`}
            >
              <span>{faq.question}</span>
              <ChevronDown
                size={16}
                className="shrink-0 transition-transform duration-200"
                style={{
                  color: "var(--aa-muted)",
                  transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
                }}
              />
            </button>
            {isOpen && (
              <div
                className="pb-4 text-sm leading-relaxed animate-in fade-in slide-in-from-top-1 duration-150"
                style={{ color: "var(--aa-muted)" }}
                data-testid={`faq-item-${i}-content`}
              >
                {faq.answer}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  if (!card) return content;

  return (
    <div
      className="rounded-2xl border p-6"
      style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}
      data-testid={testId}
    >
      <h2 className="text-lg font-semibold mb-2" style={{ color: "var(--aa-text)" }}>
        {title}
      </h2>
      {content}
    </div>
  );
}
