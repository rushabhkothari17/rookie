/**
 * Centralised character limits — mirrors backend models.py constants exactly.
 * Single source of truth: update here AND in backend/models.py together.
 *
 * Categories (displayed on UI as category hints)
 * ──────────────────────────────────────────────
 * MICRO    (≤ 50)    : phone, postal, OTP, currency, country, hex colour
 * SHORT    (≤ 100)   : codes, nav labels, button text, titles, names
 * NOTE     (≤ 5 000) : notes, descriptions, FAQ answers
 * WEB_BODY (≤ 1 000) : website settings body copy (subtitles, messages, steps)
 * CONTENT  (≤ 500 K) : rich HTML bodies, terms, articles
 */

// ── MICRO ────────────────────────────────────────────────────────────────────
export const LIMIT_COUNTRY     = 10;
export const LIMIT_CURRENCY    = 10;
export const LIMIT_POSTAL      = 20;
export const LIMIT_COLOR       = 30;
export const LIMIT_PHONE       = 50;
export const LIMIT_OTP         = 6;

// ── SHORT / NAME — both capped at 100 ────────────────────────────────────────
export const LIMIT_CODE        = 100;   // promo/coupon codes, field keys
export const LIMIT_CARD_TAG    = 100;   // product card badge
export const LIMIT_CITY        = 100;   // city / region
export const LIMIT_REGION      = 100;
export const LIMIT_NAME        = 100;   // product/category/form/article names, titles, headings
export const LIMIT_FULL_NAME   = 100;   // full name
export const LIMIT_COMPANY     = 100;   // company name
export const LIMIT_JOB_TITLE   = 100;   // job title
export const LIMIT_ADDR_LINE   = 100;   // address line 1 / 2
export const LIMIT_SLUG        = 100;   // URL slug
export const LIMIT_SUBJECT     = 100;   // email subject lines
export const LIMIT_PRICE_ID    = 100;   // Stripe price ID
export const LIMIT_SECRET      = 500;   // webhook signing secret / GoCardless token (cryptographic)
export const LIMIT_URL         = 2_048; // any URL / external link
export const LIMIT_EMAIL       = 320;
export const LIMIT_PASSWORD    = 128;

// ── WEBSITE SETTINGS ─────────────────────────────────────────────────────────
// SHORT/NAME website fields use LIMIT_NAME (100) via Field default
export const LIMIT_WEB_BODY    = 1_000; // website body copy: subtitles, messages, instructions

// ── NOTE ─────────────────────────────────────────────────────────────────────
export const LIMIT_NOTE        = 5_000; // notes, descriptions, FAQ answers, promo notes

// ── CONTENT ──────────────────────────────────────────────────────────────────
export const LIMIT_CONTENT     = 500_000; // rich HTML: terms, email body, articles

// ── Form builder admin-configurable max limits ────────────────────────────────
export const LIMIT_FORM_SINGLE_LINE = 500;   // max a form builder admin can set for single_line
export const LIMIT_FORM_MULTI_LINE  = 10_000; // max a form builder admin can set for multi_line

// ─── CharCount component ─────────────────────────────────────────────────────
/**
 * Live "X/Y" character counter.
 * Hidden when current === 0. Amber at 80 %, red at 95 %.
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
