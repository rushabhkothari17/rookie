/**
 * Category utilities — fully dynamic, no hardcoded service or product names.
 * Category names and display order come from the admin panel (database).
 */

/** Convert a category name to a URL-safe slug */
export function slugFromCategory(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** Find a category name that matches a URL slug from the available list */
export function categoryFromSlug(slug: string | null, available: string[]): string | null {
  if (!slug) return available[0] || null;
  const normalized = slug.toLowerCase();
  return available.find((c) => slugFromCategory(c) === normalized) || available[0] || null;
}

/** Return category name as-is — no hardcoded remapping */
export function displayCategory(name: string): string {
  return name || "";
}

// Keep for backward compatibility with any remaining imports
export const CATEGORY_ORDER: string[] = [];
