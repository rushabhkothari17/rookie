export const CATEGORY_ORDER = [
  "Zoho Express Setup",
  "Audit & Optimize",
  "Build & Automate",
  "Accounting on Zoho",
  "Ongoing Plans",
  "Migrations",
];

export const CATEGORY_SLUGS: Record<string, string> = {
  "Zoho Express Setup": "start-here",
  "Audit & Optimize": "audit-optimize",
  "Build & Automate": "build-automate",
  "Accounting on Zoho": "accounting-on-zoho",
  "Ongoing Plans": "ongoing-plans",
  Migrations: "migrations",
};

export const displayCategory = (category: string) =>
  category === "Start Here" ? "Zoho Express Setup" : category;

export const slugFromCategory = (category: string) => {
  const label = displayCategory(category);
  return CATEGORY_SLUGS[label] || label.toLowerCase().replace(/\s+/g, "-");
};

export const categoryFromSlug = (slug: string | null, available: string[]) => {
  if (!slug) {
    return available[0] || CATEGORY_ORDER[0];
  }
  const normalized = slug.toLowerCase();
  if (normalized === "start-here") {
    return "Zoho Express Setup";
  }
  const fromSlug = Object.entries(CATEGORY_SLUGS).find(
    ([, value]) => value === normalized,
  );
  if (fromSlug) {
    return fromSlug[0];
  }
  const directMatch = available.find(
    (category) => category.toLowerCase() === normalized,
  );
  return displayCategory(directMatch || available[0] || CATEGORY_ORDER[0]);
};
