export const CATEGORY_ORDER = [
  "Zoho Express Setup",
  "Migrate to Zoho",
  "Manages Services",
  "Build & Automate",
  "Accounting on Zoho",
  "Audit & Optimize",
];

export const CATEGORY_SLUGS: Record<string, string> = {
  "Zoho Express Setup": "start-here",
  "Migrate to Zoho": "migrations",
  "Manages Services": "ongoing-plans",
  "Build & Automate": "build-automate",
  "Accounting on Zoho": "accounting-on-zoho",
  "Audit & Optimize": "audit-optimize",
};

export const displayCategory = (category: string) => {
  if (category === "Start Here") return "Zoho Express Setup";
  if (category === "Migrations") return "Migrate to Zoho";
  if (category === "Ongoing Plans" || category === "Managed Services") {
    return "Manages Services";
  }
  return category;
};

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
  if (normalized === "migrations") {
    return "Migrate to Zoho";
  }
  if (normalized === "ongoing-plans") {
    return "Manages Services";
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
