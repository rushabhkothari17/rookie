/**
 * Centralised character limits — mirrors backend models.py constants exactly.
 * Any change here MUST be reflected in backend/models.py and vice-versa.
 *
 * Categories
 * ----------
 * MICRO   (≤ 50)   : phone, postal, currency, country, colour hex
 * SHORT   (≤ 200)  : names, titles, slugs, email subjects, price IDs, API keys
 * NAME    (≤ 500)  : product/category/form/article names
 * NOTE    (≤ 5 000): notes, short descriptions, FAQ answers, promo notes
 * CONTENT (≤ 500 000): rich HTML bodies, terms, articles
 */

// ── MICRO ────────────────────────────────────────────────────────────────────
export const LIMIT_COUNTRY   = 10;
export const LIMIT_CURRENCY  = 10;
export const LIMIT_POSTAL    = 20;
export const LIMIT_COLOR     = 30;
export const LIMIT_PHONE     = 50;

// ── SHORT ────────────────────────────────────────────────────────────────────
export const LIMIT_CODE      = 100;   // promo/coupon codes, field keys
export const LIMIT_CARD_TAG  = 100;   // product card badge
export const LIMIT_CITY      = 100;   // city / region
export const LIMIT_REGION    = 100;
export const LIMIT_FULL_NAME = 200;
export const LIMIT_COMPANY   = 200;
export const LIMIT_JOB_TITLE = 200;
export const LIMIT_ADDR_LINE = 200;   // address line 1 / 2
export const LIMIT_SLUG      = 200;
export const LIMIT_SUBJECT   = 200;   // email subject lines
export const LIMIT_PRICE_ID  = 200;   // Stripe price ID
export const LIMIT_SECRET    = 500;   // webhook signing secret / GoCardless token
export const LIMIT_URL       = 2_048; // any URL / external link
export const LIMIT_EMAIL     = 320;
export const LIMIT_PASSWORD  = 128;

// ── NAME ─────────────────────────────────────────────────────────────────────
export const LIMIT_NAME      = 500;   // product / category / form / terms title

// ── WEBSITE SETTINGS (backend validator caps at 1 000 for most fields) ───────
export const LIMIT_WEB_TEXT  = 1_000;

// ── NOTE ─────────────────────────────────────────────────────────────────────
export const LIMIT_NOTE      = 5_000; // notes, descriptions, FAQ answers, promo notes

// ── CONTENT ──────────────────────────────────────────────────────────────────
export const LIMIT_CONTENT   = 500_000; // rich HTML: terms, email body, articles

// ─── CharCount component ─────────────────────────────────────────────────────
/**
 * Displays a live "X/Y" character counter.
 * Hidden when current === 0. Turns amber at 80 %, red at 95 %.
 */
export function CharCount({
  current,
  max,
}: {
  current: number;
  max: number;
}) {
  if (!current) return null;
  const pct = current / max;
  const cls =
    pct > 0.95
      ? "text-red-500"
      : pct > 0.8
      ? "text-amber-500"
      : "text-slate-400";
  return (
    <span className={`text-[11px] font-mono tabular-nums ${cls}`}>
      {current.toLocaleString()}/{max.toLocaleString()}
    </span>
  );
}
