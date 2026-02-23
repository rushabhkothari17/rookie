import { useState } from "react";
import { Info, X, ChevronDown, ChevronUp, ExternalLink, HelpCircle, Lightbulb } from "lucide-react";

// Guide content database
const GUIDES: Record<string, {
  title: string;
  description: string;
  tips?: string[];
  links?: { text: string; url: string }[];
}> = {
  // Customer Management
  "customer-status": {
    title: "Customer Statuses",
    description: "Active customers can log in and place orders. Inactive customers are blocked from accessing the platform but their data is preserved.",
    tips: [
      "Deactivate instead of deleting to preserve order history",
      "Inactive customers won't receive automated emails",
      "You can reactivate at any time"
    ]
  },
  "customer-payment-methods": {
    title: "Payment Methods",
    description: "Each customer can have card payments (Stripe) and/or direct debit (GoCardless) enabled. Payment methods determine checkout options.",
    tips: [
      "Enable both for maximum flexibility",
      "Direct debit is better for recurring subscriptions",
      "Card payments process immediately"
    ]
  },
  "customer-currency": {
    title: "Customer Currency",
    description: "Currency override affects how prices are displayed and charged for this customer. Leave blank to use their country's default currency.",
    tips: [
      "Currency is locked after first order",
      "Multi-currency requires Stripe or GoCardless configuration"
    ]
  },
  
  // Orders
  "order-lifecycle": {
    title: "Order Lifecycle",
    description: "Orders move through stages: Draft → Pending → Paid → Fulfilled. Failed payments remain in Pending until resolved.",
    tips: [
      "Draft orders can be edited before sending to customer",
      "Pending orders await payment confirmation",
      "Use 'Mark as Paid' for offline payments"
    ]
  },
  "order-refunds": {
    title: "Refund Process",
    description: "Refunds can be full or partial. Stripe refunds are processed immediately. GoCardless refunds may take 3-5 business days.",
    tips: [
      "Partial refunds keep the order status as Paid",
      "Full refunds change status to Refunded",
      "Document refund reason for records"
    ]
  },
  
  // Subscriptions
  "subscription-billing": {
    title: "Billing Cycles",
    description: "Subscriptions bill at intervals: monthly, quarterly, or annually. The billing date is based on subscription start date.",
    tips: [
      "Annual subscriptions can offer discounts",
      "Customers are notified before renewal",
      "Failed payments trigger retry attempts"
    ]
  },
  "subscription-proration": {
    title: "Proration",
    description: "When changing subscription tiers mid-cycle, proration calculates the fair amount based on days remaining.",
    tips: [
      "Upgrades are prorated and billed immediately",
      "Downgrades credit the next invoice",
      "Disable proration for simpler billing"
    ]
  },
  
  // Webhooks
  "webhook-signatures": {
    title: "Webhook Signatures",
    description: "Every webhook delivery includes an X-Webhook-Signature header (sha256=...). Verify this to ensure requests come from us.",
    tips: [
      "Use HMAC-SHA256 with your webhook secret",
      "Always verify before processing",
      "Reject requests with invalid signatures"
    ],
    links: [
      { text: "Verification code examples", url: "https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/verify" }
    ]
  },
  "webhook-retries": {
    title: "Retry Behavior",
    description: "Failed webhooks (non-2xx response or timeout) are retried: immediately, after 5 seconds, 30 seconds, then 2 minutes.",
    tips: [
      "Return 2xx quickly, process async if needed",
      "Timeout is 15 seconds",
      "Use idempotency keys to handle duplicates"
    ]
  },
  
  // API Keys
  "api-key-management": {
    title: "API Key Best Practices",
    description: "API keys provide full access to your tenant's data. Treat them like passwords - never expose in frontend code.",
    tips: [
      "Rotate keys periodically",
      "Use environment variables, not hardcoded values",
      "Create separate keys for different environments",
      "Revoke compromised keys immediately"
    ]
  },
  
  // Products & Catalog
  "product-pricing": {
    title: "Product Pricing",
    description: "Set base prices with optional variant pricing. Prices can be one-time or recurring (subscription).",
    tips: [
      "Use price tiers for volume discounts",
      "Tax-inclusive vs exclusive affects display",
      "Currency conversions use live rates"
    ]
  },
  "product-variants": {
    title: "Product Variants",
    description: "Variants let you offer the same product with different options (size, color, etc.) at different prices.",
    tips: [
      "Each variant can have its own SKU",
      "Stock is tracked per variant",
      "Combine options for complex products"
    ]
  },
  
  // User Management
  "user-roles": {
    title: "Role Permissions",
    description: "Super Admin: Full access. Admin: Customer & order management. Staff: View only. Customer: Self-service portal.",
    tips: [
      "Limit Super Admin access",
      "Use Staff role for support team",
      "Customers manage their own profile and orders"
    ]
  },
  
  // Store
  "store-seo": {
    title: "Store SEO",
    description: "Optimize your store for search engines with meta titles, descriptions, and structured data.",
    tips: [
      "Keep titles under 60 characters",
      "Descriptions should be 150-160 characters",
      "Use keywords naturally"
    ]
  }
};

interface ContextualGuideProps {
  guideKey: string;
  variant?: "inline" | "tooltip" | "collapsible";
  className?: string;
}

export function ContextualGuide({ guideKey, variant = "inline", className = "" }: ContextualGuideProps) {
  const [expanded, setExpanded] = useState(false);
  const guide = GUIDES[guideKey];
  
  if (!guide) return null;
  
  // Tooltip variant - icon with hover
  if (variant === "tooltip") {
    return (
      <div className={`relative inline-block group ${className}`}>
        <HelpCircle size={14} className="text-slate-400 hover:text-slate-600 cursor-help" />
        <div className="absolute z-50 hidden group-hover:block bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-900 text-white text-xs rounded-lg shadow-xl">
          <p className="font-semibold mb-1">{guide.title}</p>
          <p className="text-slate-300 leading-relaxed">{guide.description}</p>
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-full border-4 border-transparent border-t-slate-900" />
        </div>
      </div>
    );
  }
  
  // Collapsible variant - expandable card
  if (variant === "collapsible") {
    return (
      <div className={`border border-blue-100 rounded-lg overflow-hidden ${className}`} data-testid={`guide-${guideKey}`}>
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-3 py-2 bg-blue-50 hover:bg-blue-100 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Lightbulb size={14} className="text-blue-500" />
            <span className="text-xs font-medium text-blue-700">{guide.title}</span>
          </div>
          {expanded ? (
            <ChevronUp size={14} className="text-blue-500" />
          ) : (
            <ChevronDown size={14} className="text-blue-500" />
          )}
        </button>
        {expanded && (
          <div className="px-3 py-2 bg-white text-xs text-slate-600 space-y-2">
            <p>{guide.description}</p>
            {guide.tips && (
              <ul className="list-disc list-inside space-y-0.5 text-slate-500">
                {guide.tips.map((tip, i) => <li key={i}>{tip}</li>)}
              </ul>
            )}
            {guide.links && (
              <div className="flex gap-2 pt-1">
                {guide.links.map((link, i) => (
                  <a
                    key={i}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:text-blue-700 inline-flex items-center gap-0.5"
                  >
                    {link.text} <ExternalLink size={10} />
                  </a>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }
  
  // Default inline variant - always visible info box
  return (
    <div className={`flex items-start gap-2 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2 ${className}`} data-testid={`guide-${guideKey}`}>
      <Info size={14} className="text-blue-500 mt-0.5 shrink-0" />
      <div className="text-xs text-blue-700">
        <p className="font-medium">{guide.title}</p>
        <p className="text-blue-600 mt-0.5">{guide.description}</p>
      </div>
    </div>
  );
}

// Export for direct access to guide data
export function getGuide(key: string) {
  return GUIDES[key];
}

// Quick help button that shows a guide in a modal/popover
interface QuickHelpProps {
  guideKey: string;
  label?: string;
}

export function QuickHelp({ guideKey, label }: QuickHelpProps) {
  const [show, setShow] = useState(false);
  const guide = GUIDES[guideKey];
  
  if (!guide) return null;
  
  return (
    <>
      <button
        onClick={() => setShow(true)}
        className="text-xs text-blue-500 hover:text-blue-700 inline-flex items-center gap-1"
      >
        <HelpCircle size={12} />
        {label || "Help"}
      </button>
      
      {show && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/30" onClick={() => setShow(false)} />
          <div className="relative z-10 w-full max-w-md bg-white rounded-xl shadow-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Lightbulb size={16} className="text-amber-500" />
                <h3 className="text-sm font-semibold text-slate-800">{guide.title}</h3>
              </div>
              <button onClick={() => setShow(false)} className="text-slate-400 hover:text-slate-600 p-1">
                <X size={16} />
              </button>
            </div>
            <div className="p-4 space-y-3">
              <p className="text-sm text-slate-600">{guide.description}</p>
              {guide.tips && (
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-1">Tips</p>
                  <ul className="list-disc list-inside space-y-0.5 text-xs text-slate-500">
                    {guide.tips.map((tip, i) => <li key={i}>{tip}</li>)}
                  </ul>
                </div>
              )}
              {guide.links && (
                <div className="flex flex-wrap gap-2 pt-2">
                  {guide.links.map((link, i) => (
                    <a
                      key={i}
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs bg-blue-50 text-blue-600 hover:bg-blue-100 px-2 py-1 rounded inline-flex items-center gap-1"
                    >
                      {link.text} <ExternalLink size={10} />
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
