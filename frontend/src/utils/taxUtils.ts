// Shared tax computation utility used across OrdersTab, PartnerOrdersTab, PartnerSubscriptionsTab

export interface TaxEntry {
  country_code: string;
  state_code?: string;
  label: string;
  rate: number; // stored as decimal, e.g. 0.13 for 13%
}

export interface OverrideRule {
  id?: string;
  name?: string;
  tax_name: string;
  tax_rate: number; // stored as decimal, e.g. 0.13 for 13%
  priority: number;
  conditions: Array<{ field: string; operator: string; value: string }>;
}

/** Address-like subject used for tax lookups */
export interface TaxSubject {
  country?: string;      // raw country name or 2-letter ISO code
  region?: string;       // state/province code or name
  email?: string;        // for override rule matching
  company_name?: string; // for override rule matching
}

export interface TaxResult {
  tax_name: string;
  tax_rate: string; // as percentage string, e.g. "13"
}

const COUNTRY_NAME_TO_ISO: Record<string, string> = {
  "canada": "CA", "united kingdom": "GB", "england": "GB", "scotland": "GB",
  "wales": "GB", "northern ireland": "GB", "united states": "US",
  "united states of america": "US", "usa": "US", "australia": "AU",
  "new zealand": "NZ", "ireland": "IE", "germany": "DE", "france": "FR",
  "spain": "ES", "italy": "IT", "netherlands": "NL", "belgium": "BE",
  "sweden": "SE", "norway": "NO", "denmark": "DK", "finland": "FI",
  "switzerland": "CH", "austria": "AT", "portugal": "PT", "poland": "PL",
  "india": "IN", "japan": "JP", "china": "CN", "south africa": "ZA",
  "singapore": "SG", "brazil": "BR", "mexico": "MX",
};

export function resolveCountryCode(country?: string): string {
  if (!country) return "";
  const trimmed = country.trim();
  if (trimmed.length === 2) return trimmed.toUpperCase();
  return COUNTRY_NAME_TO_ISO[trimmed.toLowerCase()] || trimmed.toUpperCase();
}

export const NO_TAX: TaxResult = { tax_name: "No tax", tax_rate: "0" };

function evalCondition(
  cond: { field: string; operator: string; value: string },
  subject: TaxSubject,
): boolean {
  const fieldMap: Record<string, string> = {
    country: resolveCountryCode(subject.country),
    state: (subject.region || "").toUpperCase(),
    email: (subject.email || "").toLowerCase(),
    company_name: (subject.company_name || "").toLowerCase(),
  };
  const fv = fieldMap[cond.field] || "";
  const cv = (cond.value || "").toLowerCase();
  switch (cond.operator) {
    case "equals":      return fv.toLowerCase() === cv;
    case "not_equals":  return fv.toLowerCase() !== cv;
    case "contains":    return fv.toLowerCase().includes(cv);
    case "not_contains":return !fv.toLowerCase().includes(cv);
    case "empty":       return !fv;
    case "not_empty":   return !!fv;
    default:            return false;
  }
}

/**
 * Compute the applicable tax for a given subject (customer or partner).
 *
 * Priority:
 *   1. Override rules (sorted by priority desc — first match wins)
 *   2. Tax table (address-based; state-specific entry preferred)
 *   3. No tax fallback
 */
export function computeTax(
  subject: TaxSubject,
  taxEntries: TaxEntry[],
  overrideRules: OverrideRule[],
): TaxResult {
  // 1. Override rules
  const sorted = [...overrideRules].sort((a, b) => (b.priority || 0) - (a.priority || 0));
  for (const rule of sorted) {
    const allMatch =
      rule.conditions.length === 0
        ? true
        : rule.conditions.every(c => evalCondition(c, subject));
    if (allMatch) {
      const ratePercent =
        rule.tax_rate < 1
          ? parseFloat((rule.tax_rate * 100).toFixed(4))
          : rule.tax_rate;
      return { tax_name: rule.tax_name, tax_rate: String(ratePercent) };
    }
  }

  // 2. Tax table lookup
  const countryCode = resolveCountryCode(subject.country);
  if (!countryCode) return NO_TAX;

  const region = (subject.region || "").toUpperCase();
  const matches = taxEntries.filter(
    e =>
      e.country_code.toUpperCase() === countryCode &&
      (!e.state_code || !region || e.state_code.toUpperCase() === region),
  );
  if (matches.length === 0) return NO_TAX;

  // Prefer state-specific match over country-level match
  const best =
    matches.find(
      m => m.state_code && region && m.state_code.toUpperCase() === region,
    ) || matches[0];
  const ratePercent =
    best.rate < 1 ? parseFloat((best.rate * 100).toFixed(4)) : best.rate;
  return { tax_name: best.label, tax_rate: String(ratePercent) };
}
