import { Info, ExternalLink } from "lucide-react";

interface IntegrationGuideProps {
  provider: "resend" | "zoho_mail" | "zoho_crm" | "stripe" | "gocardless";
}

const GUIDES: Record<string, {
  title: string;
  steps: string[];
  links: { text: string; url: string }[];
  tips: string[];
}> = {
  resend: {
    title: "Resend Email Integration",
    steps: [
      "Create a free account at resend.com",
      "Go to Settings → API Keys",
      "Create a new API key with 'Sending access'",
      "Copy the key (starts with 're_')",
      "Add your verified domain or use onboarding@resend.dev for testing"
    ],
    links: [
      { text: "Resend Dashboard", url: "https://resend.com/api-keys" },
      { text: "Domain verification guide", url: "https://resend.com/docs/dashboard/domains/introduction" }
    ],
    tips: [
      "Free tier: 100 emails/day, 3,000/month",
      "Use a dedicated sending domain for better deliverability",
      "Verify your domain to avoid spam filters"
    ]
  },
  zoho_mail: {
    title: "Zoho Mail Integration",
    steps: [
      "Log in to Zoho API Console (api-console.zoho.com)",
      "Create a 'Server-based' application",
      "Add redirect URI: your-app-url/callback",
      "Add scope: ZohoMail.messages.ALL",
      "Copy Client ID and Client Secret",
      "Complete OAuth authorization to get access token"
    ],
    links: [
      { text: "Zoho API Console", url: "https://api-console.zoho.com/" },
      { text: "Zoho Mail API Docs", url: "https://www.zoho.com/mail/help/api/" }
    ],
    tips: [
      "Choose the correct data center (US, CA, EU, etc.)",
      "Access tokens expire - implement refresh token flow for production",
      "Server-based apps are required for backend integrations"
    ]
  },
  zoho_crm: {
    title: "Zoho CRM Integration",
    steps: [
      "Log in to Zoho API Console (api-console.zoho.com)",
      "Create a 'Server-based' application",
      "Add scopes: ZohoCRM.modules.ALL, ZohoCRM.settings.ALL",
      "Copy Client ID and Client Secret",
      "Complete OAuth to get access token"
    ],
    links: [
      { text: "Zoho API Console", url: "https://api-console.zoho.com/" },
      { text: "Zoho CRM API Docs", url: "https://www.zoho.com/crm/developer/docs/" }
    ],
    tips: [
      "Test with sandbox environment first",
      "Map fields carefully - some CRM fields are read-only",
      "Rate limits apply - batch your sync operations"
    ]
  },
  stripe: {
    title: "Stripe Payment Integration",
    steps: [
      "Log in to Stripe Dashboard",
      "Go to Developers → API keys",
      "Copy your Secret key (starts with 'sk_')",
      "For testing, use test mode keys (sk_test_)",
      "Set up webhooks for payment notifications"
    ],
    links: [
      { text: "Stripe Dashboard", url: "https://dashboard.stripe.com/apikeys" },
      { text: "Stripe Webhook Setup", url: "https://stripe.com/docs/webhooks" }
    ],
    tips: [
      "Never expose Secret keys in frontend code",
      "Use Publishable keys (pk_) for client-side only",
      "Test with Stripe's test card numbers"
    ]
  },
  gocardless: {
    title: "GoCardless Direct Debit",
    steps: [
      "Create a GoCardless account",
      "Go to Developers → Create access token",
      "Copy your access token",
      "Set up redirect flows for mandate creation",
      "Configure webhooks for payment status updates"
    ],
    links: [
      { text: "GoCardless Dashboard", url: "https://manage.gocardless.com/access-tokens" },
      { text: "API Documentation", url: "https://developer.gocardless.com/" }
    ],
    tips: [
      "Direct Debit takes 3-5 business days to clear",
      "Mandates need customer authorization",
      "Use sandbox environment for testing"
    ]
  }
};

export function IntegrationGuide({ provider }: IntegrationGuideProps) {
  const guide = GUIDES[provider];
  if (!guide) return null;

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs" data-testid={`integration-guide-${provider}`}>
      <div className="flex items-start gap-2">
        <Info size={14} className="text-blue-500 mt-0.5 shrink-0" />
        <div className="text-blue-700 space-y-2">
          <p className="font-semibold">{guide.title}</p>
          
          <div>
            <p className="font-medium mb-1">Setup Steps:</p>
            <ol className="list-decimal list-inside space-y-0.5 text-blue-600 ml-1">
              {guide.steps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            {guide.links.map((link, i) => (
              <a
                key={i}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 bg-blue-100 hover:bg-blue-200 text-blue-700 px-2 py-1 rounded transition-colors"
              >
                {link.text}
                <ExternalLink size={10} />
              </a>
            ))}
          </div>

          {guide.tips.length > 0 && (
            <div className="bg-blue-100/50 rounded p-2 mt-2">
              <p className="font-medium mb-1">Tips:</p>
              <ul className="list-disc list-inside space-y-0.5 text-blue-600">
                {guide.tips.map((tip, i) => (
                  <li key={i}>{tip}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Compact version for inline use
export function IntegrationHelpLink({ provider, text }: { provider: string; text: string }) {
  const urls: Record<string, string> = {
    resend: "https://resend.com/api-keys",
    zoho_mail: "https://api-console.zoho.com/",
    zoho_crm: "https://api-console.zoho.com/",
    stripe: "https://dashboard.stripe.com/apikeys",
    gocardless: "https://manage.gocardless.com/access-tokens"
  };

  const url = urls[provider];
  if (!url) return <span className="text-xs text-slate-400">{text}</span>;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-xs text-blue-500 hover:text-blue-700 inline-flex items-center gap-0.5"
    >
      {text}
      <ExternalLink size={10} />
    </a>
  );
}
