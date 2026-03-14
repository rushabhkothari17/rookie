/**
 * Centralised character limits — mirrors backend models.py constants exactly.
 * Single source of truth: update here AND in backend/models.py together.
 *
 * Categories:
 *   MICRO      – tiny technical identifiers (country, postal, color, phone, OTP)
 *   CODE/NAME  – system codes, entity names, titles, headings (100)
 *   SHORT      – other single-line text (500)
 *   SUBJECT    – email subjects (500)
 *   NOTE       – multi-line notes (5,000)
 *   REASON     – brief reasons / cancel messages (1,000)
 *   CONTENT    – rich HTML bodies (500,000)
 *   WEB_TITLE  – website headings, nav labels, buttons (100)
 *   WEB_BODY   – website subtitles, descriptions, messages (500)
 *   URL        – full URLs (2,048)
 *   SECRET     – API keys / tokens / signing secrets (500)
 */

// ── MICRO ────────────────────────────────────────────────────────────────────
export const LIMIT_OTP         = 6;
export const LIMIT_COUNTRY     = 10;
export const LIMIT_CURRENCY    = 10;
export const LIMIT_POSTAL      = 20;
export const LIMIT_COLOR       = 30;
export const LIMIT_PHONE       = 50;

// ── CODE / NAME — both 100 ───────────────────────────────────────────────────
export const LIMIT_CODE        = 100;
export const LIMIT_NAME        = 100;
export const LIMIT_CARD_TAG    = 100;
export const LIMIT_CITY        = 100;
export const LIMIT_REGION      = 100;
export const LIMIT_FULL_NAME   = 100;
export const LIMIT_COMPANY     = 100;
export const LIMIT_JOB_TITLE   = 100;
export const LIMIT_ADDR_LINE   = 100;
export const LIMIT_SLUG        = 100;
export const LIMIT_PRICE_ID    = 100;   // Stripe price ID
export const LIMIT_WEB_TITLE   = 100;   // website headings, nav labels, button text

// ── SHORT / SUBJECT — both 500 ───────────────────────────────────────────────
export const LIMIT_SHORT       = 500;   // other single-line text
export const LIMIT_SUBJECT     = 500;   // email subject lines
export const LIMIT_WEB_BODY    = 500;   // website subtitles, descriptions, messages, instructions

// ── Auth ─────────────────────────────────────────────────────────────────────
export const LIMIT_EMAIL       = 320;
export const LIMIT_PASSWORD    = 128;

// ── URL / SECRET ─────────────────────────────────────────────────────────────
export const LIMIT_URL         = 2_048;
export const LIMIT_SECRET      = 500;   // API keys, tokens, signing secrets

// ── NOTE / REASON ────────────────────────────────────────────────────────────
export const LIMIT_NOTE        = 5_000;
export const LIMIT_REASON      = 1_000;

// ── CONTENT ──────────────────────────────────────────────────────────────────
export const LIMIT_CONTENT     = 500_000;

// ── Form builder admin-configurable max limits ────────────────────────────────
export const LIMIT_FORM_SINGLE_LINE = 500;
export const LIMIT_FORM_MULTI_LINE  = 5_000;

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
