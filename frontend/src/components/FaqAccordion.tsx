/**
 * FaqAccordion — Collapsible FAQ section with keyword search/filter.
 * Used across all product layouts. Fully compatible with light and dark CSS variable themes.
 */
import { useState, useMemo } from "react";
import { ChevronDown, Search, X } from "lucide-react";

interface FaqItem {
  question: string;
  answer: string;
}

interface FaqAccordionProps {
  faqs: FaqItem[];
  title?: string;
  testId?: string;
  /** Pass false to render without the card wrapper */
  card?: boolean;
}

export default function FaqAccordion({
  faqs,
  title = "Frequently Asked Questions",
  testId = "product-faqs",
  card = true,
}: FaqAccordionProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [search, setSearch] = useState("");

  const filteredFaqs = useMemo(() => {
    if (!search.trim()) return faqs;
    const q = search.toLowerCase();
    return faqs.filter(
      f =>
        f.question.toLowerCase().includes(q) ||
        f.answer.toLowerCase().includes(q)
    );
  }, [faqs, search]);

  if (!faqs || faqs.length === 0) return null;

  const toggle = (i: number) => setOpenIndex(openIndex === i ? null : i);

  const highlight = (text: string) => {
    if (!search.trim()) return text;
    const regex = new RegExp(`(${search.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
    const parts = text.split(regex);
    return parts.map((part, j) =>
      regex.test(part) ? (
        <mark
          key={j}
          style={{
            background: "color-mix(in srgb, var(--aa-accent) 25%, transparent)",
            color: "inherit",
            borderRadius: "2px",
            padding: "0 1px",
          }}
        >
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  const content = (
    <>
      {/* Search bar — only shown when there are >= 4 FAQs */}
      {faqs.length >= 4 && (
        <div
          className="relative mb-4"
          data-testid={`${testId}-search-wrapper`}
        >
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            style={{ color: "var(--aa-muted)" }}
          />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search FAQs…"
            className="h-8 w-full rounded-full border pl-8 pr-8 text-sm outline-none transition-all duration-200"
            style={{
              background: "var(--aa-surface)",
              borderColor: search ? "var(--aa-accent)" : "var(--aa-border)",
              color: "var(--aa-text)",
              boxShadow: search
                ? "0 0 0 3px color-mix(in srgb, var(--aa-accent) 12%, transparent)"
                : "none",
            }}
            data-testid={`${testId}-search`}
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 opacity-50 hover:opacity-100 transition-opacity"
              style={{ color: "var(--aa-muted)" }}
              aria-label="Clear search"
            >
              <X size={12} />
            </button>
          )}
        </div>
      )}

      {/* FAQ list */}
      <div data-testid={`${testId}-list`}>
        {filteredFaqs.length === 0 ? (
          <p
            className="text-sm py-6 text-center"
            style={{ color: "var(--aa-muted)" }}
          >
            No FAQs match "{search}"
          </p>
        ) : (
          filteredFaqs.map((faq, i) => {
            const isOpen = openIndex === i;
            return (
              <div key={i} style={{ borderBottom: "1px solid var(--aa-border)" }}>
                <button
                  type="button"
                  onClick={() => toggle(i)}
                  className="w-full flex items-center justify-between py-4 text-sm font-semibold text-left transition-opacity hover:opacity-70"
                  style={{ color: "var(--aa-text)", background: "transparent", border: "none" }}
                  aria-expanded={isOpen}
                  data-testid={`faq-item-${i}-trigger`}
                >
                  <span>{highlight(faq.question)}</span>
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
                    {highlight(faq.answer)}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </>
  );

  if (!card) return content;

  return (
    <div
      className="rounded-2xl border p-6"
      style={{ background: "var(--aa-card)", borderColor: "var(--aa-border)" }}
      data-testid={testId}
    >
      <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--aa-text)" }}>
        {title}
      </h2>
      {content}
    </div>
  );
}
