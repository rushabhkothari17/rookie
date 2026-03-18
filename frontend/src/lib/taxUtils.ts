/**
 * Shared tax calculation utilities for customer and partner orders/subscriptions.
 */

const COUNTRY_NAME_MAP: Record<string, string> = {
  "canada": "CA", "united states": "US", "united kingdom": "GB",
  "australia": "AU", "new zealand": "NZ", "ireland": "IE", "india": "IN",
  "germany": "DE", "france": "FR", "netherlands": "NL", "belgium": "BE",
  "spain": "ES", "italy": "IT", "portugal": "PT", "sweden": "SE",
  "norway": "NO", "denmark": "DK", "finland": "FI", "austria": "AT",
  "singapore": "SG", "south africa": "ZA", "brazil": "BR", "mexico": "MX",
  "japan": "JP", "china": "CN", "hong kong": "HK",
};

/** Normalize a country name or ISO code to a 2-letter ISO code */
export function resolveCountryCode(country?: string): string {
  if (!country) return "";
  const c = country.trim();
  if (c.length === 2) return c.toUpperCase();
  return COUNTRY_NAME_MAP[c.toLowerCase()] || c.toUpperCase();
}

export interface TaxResult {
  tax_name: string;
  tax_rate: string; // percentage string e.g. "13"
}

export interface ComputeTaxParams {
  taxEnabled: boolean;
  taxEntries: any[];
  overrideRules: any[];
  orgTaxCountry: string;  // ISO 2-letter
  orgTaxState: string;
  /** The user record (email, id, full_name) */
  user?: any;
  /** The customer record (id, user_id, company_name, tax_exempt) */
  customer?: any;
  /** The customer's billing address (country, region) */
  address?: any;
}

/**
 * Compute the correct tax for a customer order/subscription.
 * Priority: tax disabled > tax exempt > override rules > tax table (customer addr → org addr)
 */
export function computeCustomerTax(p: ComputeTaxParams): TaxResult {
  const NO_TAX: TaxResult = { tax_name: "No tax", tax_rate: "0" };

  // 1. Global tax disabled
  if (!p.taxEnabled) return NO_TAX;

  // 2. Customer tax exempt
  if (p.customer?.tax_exempt) return { tax_name: "Exempt", tax_rate: "0" };

  // 3. Evaluate override rules (sorted by priority desc)
  const sorted = [...(p.overrideRules || [])].sort((a, b) => (b.priority || 0) - (a.priority || 0));
  for (const rule of sorted) {
    if (!rule.enabled) continue;
    const conditions: any[] = rule.conditions || [];
    if (conditions.length === 0) continue; // skip rules with no conditions
    const allMatch = conditions.every((cond: any) => {
      const fieldMap: Record<string, string | undefined> = {
        email: p.user?.email,
        company_name: p.customer?.company_name,
        country: p.address?.country,
        state: p.address?.region,
      };
      const val = fieldMap[cond.field];
      switch (cond.operator) {
        case "equals":      return val?.toLowerCase() === cond.value?.toLowerCase();
        case "not_equals":  return val?.toLowerCase() !== cond.value?.toLowerCase();
        case "contains":    return !!val?.toLowerCase().includes(cond.value?.toLowerCase());
        case "not_contains":return !val?.toLowerCase().includes(cond.value?.toLowerCase());
        case "empty":       return !val;
        case "not_empty":   return !!val;
        default:            return false;
      }
    });
    if (allMatch) {
      const ratePercent = rule.tax_rate < 1
        ? parseFloat((rule.tax_rate * 100).toFixed(4))
        : rule.tax_rate;
      return { tax_name: rule.tax_name || "Tax", tax_rate: String(ratePercent) };
    }
  }

  // 4. Tax table lookup — use customer's address first, fall back to org address
  const rawCountry = p.address?.country || "";
  const rawRegion  = p.address?.region  || "";
  const country = rawCountry ? resolveCountryCode(rawCountry) : p.orgTaxCountry;
  const region  = rawRegion  ? rawRegion.toUpperCase() : p.orgTaxState?.toUpperCase();

  if (country) {
    const matches = (p.taxEntries || []).filter((e: any) =>
      e.country_code.toUpperCase() === country &&
      (!e.state_code || !region || e.state_code.toUpperCase() === region)
    );
    if (matches.length >= 1) {
      const best = matches.find((m: any) => m.state_code && region && m.state_code.toUpperCase() === region) || matches[0];
      const ratePercent = best.rate < 1 ? parseFloat((best.rate * 100).toFixed(4)) : best.rate;
      return { tax_name: best.label || "Tax", tax_rate: String(ratePercent) };
    }
  }

  return NO_TAX;
}
