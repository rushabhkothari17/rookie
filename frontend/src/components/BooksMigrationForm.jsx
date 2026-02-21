import { useEffect, useState } from "react";

const SOURCE_SYSTEMS = [
  { id: "quickbooks_online", label: "Quickbooks Online" },
  { id: "quickbooks_desktop", label: "Quickbooks Desktop" },
  { id: "sage_50_desktop", label: "Sage 50 (Desktop)" },
  { id: "sage_50_online", label: "Sage 50 (Online)" },
  { id: "netsuite", label: "Netsuite" },
  { id: "xero", label: "Xero" },
  { id: "freshbooks", label: "Freshbooks" },
  { id: "wave", label: "Wave" },
  { id: "spreadsheet", label: "Spreadsheet" },
];

const YEARS_OPTIONS = Array.from({ length: 20 }, (_, i) => ({
  value: String(i + 1),
  label: `${i + 1}Y + YTD`,
}));

const DATA_TYPES_GROUPS = [
  {
    heading: "Features",
    items: [
      { id: "price_list", label: "Price list", premium: true },
      { id: "multi_currency", label: "Multi currency", premium: true },
    ],
  },
  {
    heading: "Non Transactional data",
    items: [
      { id: "customers", label: "Customers" },
      { id: "vendors", label: "Vendors" },
      { id: "item_list", label: "Item list" },
      { id: "chart_of_accounts", label: "Chart of accounts" },
      { id: "tax_rates", label: "Tax rates" },
    ],
  },
  {
    heading: "Transactional data",
    items: [
      { id: "quotes", label: "Quotes" },
      { id: "sales_order", label: "Sales Order" },
      { id: "retainer_invoices", label: "Retainer Invoices" },
      { id: "invoices", label: "Invoices" },
      { id: "sales_receipts", label: "Sales Receipts" },
      { id: "payments_received", label: "Payments Received" },
      { id: "credit_notes", label: "Credit Notes" },
      { id: "purchase_orders", label: "Purchase Orders" },
      { id: "expenses", label: "Expenses" },
      { id: "vendor_bills", label: "Vendor Bills" },
      { id: "payments_made", label: "Payments Made" },
      { id: "vendor_credits", label: "Vendor Credits" },
      { id: "projects", label: "Projects", premium: true },
      { id: "timesheet", label: "Timesheet", premium: true },
      { id: "inventory_adjustments", label: "Inventory adjustments" },
      { id: "manual_journals", label: "Manual Journals" },
    ],
  },
];

const STANDARD_SOURCES = new Set(["quickbooks_online", "sage_50_online", "spreadsheet"]);
const PREMIUM_ITEMS = new Set(["price_list", "multi_currency", "projects", "timesheet"]);

function roundToNearest99(amount) {
  const low = Math.floor(amount / 100) * 100 - 1;
  const high = low + 100;
  return Math.abs(amount - high) <= Math.abs(amount - low) ? high : low;
}

export function calculateBooksMigrationPrice(inputs) {
  const yearsStr = String(inputs.years || "1").replace("+YTD", "").replace("Y", "").trim();
  const years = Math.max(1, parseInt(yearsStr) || 1);
  const dataTypes = Array.isArray(inputs.data_types) ? inputs.data_types : [];
  const hasPremium = dataTypes.some((d) => PREMIUM_ITEMS.has(d));
  const sourceSystem = inputs.source_system || "quickbooks_online";

  let base = 999;
  if (years > 1) {
    const extra = years - 1;
    const upTo5 = Math.min(extra, 4);
    const over5 = Math.max(0, extra - 4);
    base += upTo5 * 350 + over5 * 300;
  }
  if (hasPremium) base *= 1.5;
  if (!STANDARD_SOURCES.has(sourceSystem)) base *= 1.2;

  return roundToNearest99(base);
}

export default function BooksMigrationForm({ onChange, initialValues = {}, websiteUrl = "https://www.automateaccounts.com" }) {
  const [sourceSystem, setSourceSystem] = useState(initialValues.source_system || "");
  const [accessConfirmed, setAccessConfirmed] = useState(initialValues.access_confirmed || "");
  const [zohoProducts, setZohoProducts] = useState(initialValues.zoho_products || "");
  const [years, setYears] = useState(initialValues.years || "1");
  const [dataTypes, setDataTypes] = useState(initialValues.data_types || []);
  const [otherData, setOtherData] = useState(initialValues.other_data || "");
  const [otherInfo, setOtherInfo] = useState(initialValues.other_info || "");
  const [companyName, setCompanyName] = useState(initialValues.company_name || "");

  const sourceLabel = SOURCE_SYSTEMS.find((s) => s.id === sourceSystem)?.label || "";

  const currentValues = {
    source_system: sourceSystem,
    access_confirmed: accessConfirmed,
    zoho_products: zohoProducts,
    years,
    data_types: dataTypes,
    other_data: otherData,
    other_info: otherInfo,
    company_name: companyName,
  };

  const price = calculateBooksMigrationPrice(currentValues);

  useEffect(() => {
    onChange({ inputs: currentValues, price, isComplete: isFormComplete() });
  }, [sourceSystem, accessConfirmed, zohoProducts, years, dataTypes, otherData, otherInfo, companyName]);

  function isFormComplete() {
    return !!sourceSystem && !!accessConfirmed && dataTypes.length > 0;
  }

  function toggleDataType(id) {
    setDataTypes((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
    );
  }

  return (
    <div className="space-y-6" data-testid="books-migration-form">
      {/* A: Source system */}
      <div className="space-y-2">
        <label className="block text-sm font-semibold text-slate-800">
          Which system do you want to migrate into Zoho Books from? <span className="text-red-500">*</span>
        </label>
        <select
          data-testid="bm-source-system"
          value={sourceSystem}
          onChange={(e) => { setSourceSystem(e.target.value); setAccessConfirmed(""); }}
          className={`w-full h-10 border rounded-lg px-3 text-sm bg-white text-slate-800 ${!sourceSystem ? "border-red-300" : "border-slate-300"}`}
        >
          <option value="">-- Select source system --</option>
          {SOURCE_SYSTEMS.map((s) => (
            <option key={s.id} value={s.id}>{s.label}</option>
          ))}
        </select>
      </div>

      {/* B: Access instructions */}
      {sourceSystem && (
        <div className="space-y-3 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-slate-700">
            Please follow{" "}
            <a
              href={websiteUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline font-medium"
              data-testid="bm-access-article-link"
            >
              this article
            </a>{" "}
            to know how to provide us access to your current accounting system.
          </p>
          <div className="space-y-2">
            <label className="block text-sm font-semibold text-slate-800">
              Have you provided us access to your {sourceLabel || "accounting system"} using the above instructions? <span className="text-red-500">*</span>
            </label>
            <p className="text-xs text-slate-500">
              You can always visit this website in future to provide us access to your current accounting system.
            </p>
            <select
              data-testid="bm-access-confirmed"
              value={accessConfirmed}
              onChange={(e) => setAccessConfirmed(e.target.value)}
              className={`w-full h-10 border rounded-lg px-3 text-sm bg-white text-slate-800 ${!accessConfirmed ? "border-red-300" : "border-slate-300"}`}
            >
              <option value="">-- Select --</option>
              <option value="yes">Yes</option>
              <option value="no_will_provide_later">No - Will provide later</option>
            </select>
            {accessConfirmed === "no_will_provide_later" && (
              <div className="bg-amber-50 border border-amber-300 rounded-md p-3 text-xs text-amber-800">
                <strong>Please note:</strong> Service delays can happen if you complete purchase without providing us the access.
              </div>
            )}
          </div>
        </div>
      )}

      {/* C: Zoho products */}
      <div className="space-y-2">
        <label className="block text-sm font-semibold text-slate-800">
          Do you use Zoho CRM, Projects, Desk or any other Zoho Product other than Zoho Books?
        </label>
        <p className="text-xs text-amber-700 font-medium">
          Your response impacts how the migration is planned — please answer carefully.
        </p>
        <input
          data-testid="bm-zoho-products"
          type="text"
          value={zohoProducts}
          onChange={(e) => setZohoProducts(e.target.value)}
          placeholder="e.g. Zoho CRM, Zoho Desk"
          className="w-full h-10 border border-slate-300 rounded-lg px-3 text-sm bg-white text-slate-800"
        />
      </div>

      {/* D: Years */}
      <div className="space-y-2">
        <label className="block text-sm font-semibold text-slate-800">
          How many years of data would you like to migrate? <span className="text-red-500">*</span>
        </label>
        <select
          data-testid="bm-years"
          value={years}
          onChange={(e) => setYears(e.target.value)}
          className="w-full h-10 border border-slate-300 rounded-lg px-3 text-sm bg-white text-slate-800"
        >
          {YEARS_OPTIONS.map((y) => (
            <option key={y.value} value={y.value}>{y.label}</option>
          ))}
        </select>
      </div>

      {/* E: Data types multi-select */}
      <div className="space-y-3">
        <label className="block text-sm font-semibold text-slate-800">
          What data are you looking to migrate? <span className="text-red-500">*</span>
        </label>
        {DATA_TYPES_GROUPS.map((group) => (
          <div key={group.heading} className="space-y-2">
            <p className="text-xs font-semibold uppercase text-slate-400 tracking-wide">{group.heading}</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
              {group.items.map((item) => (
                <label
                  key={item.id}
                  className={`flex items-center gap-2 cursor-pointer rounded-md px-2.5 py-1.5 text-xs border transition-colors ${
                    dataTypes.includes(item.id)
                      ? "bg-slate-900 text-white border-slate-900"
                      : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"
                  }`}
                >
                  <input
                    type="checkbox"
                    data-testid={`bm-data-type-${item.id}`}
                    checked={dataTypes.includes(item.id)}
                    onChange={() => toggleDataType(item.id)}
                    className="sr-only"
                  />
                  <span className="flex-1">{item.label}</span>
                  {item.premium && (
                    <span className="text-[9px] font-semibold bg-amber-100 text-amber-700 px-1 rounded">PREM</span>
                  )}
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* F: Other data */}
      <div className="space-y-2">
        <label className="block text-sm font-semibold text-slate-800">
          Any other data you would like to migrate?
        </label>
        <textarea
          data-testid="bm-other-data"
          value={otherData}
          onChange={(e) => setOtherData(e.target.value)}
          rows={2}
          placeholder="Describe any additional data..."
          className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white text-slate-800 resize-none"
        />
      </div>

      {/* G: Other info */}
      <div className="space-y-2">
        <label className="block text-sm font-semibold text-slate-800">
          Any other information that you would like us to know?
        </label>
        <textarea
          data-testid="bm-other-info"
          value={otherInfo}
          onChange={(e) => setOtherInfo(e.target.value)}
          rows={2}
          placeholder="Any additional context..."
          className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white text-slate-800 resize-none"
        />
      </div>

      {/* H: Company Name */}
      <div className="space-y-2">
        <label className="block text-sm font-semibold text-slate-800">
          Company Name
        </label>
        <input
          data-testid="bm-company-name"
          type="text"
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          placeholder="Your company name"
          className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white text-slate-800"
        />
      </div>

      {/* Pricing preview */}
      <div className="bg-slate-900 text-white rounded-xl p-4 flex items-center justify-between" data-testid="bm-price-preview">
        <div>
          <p className="text-xs text-slate-400">Estimated price</p>
          <p className="text-2xl font-bold">${price.toLocaleString()}</p>
          <p className="text-xs text-slate-400 mt-0.5">
            {years}Y + YTD
            {dataTypes.some((d) => PREMIUM_ITEMS.has(d)) ? " · Premium features" : ""}
            {!STANDARD_SOURCES.has(sourceSystem) && sourceSystem ? " · Complex source" : ""}
          </p>
        </div>
        {!isFormComplete() && (
          <p className="text-xs text-amber-400 max-w-[150px] text-right">
            Complete required fields to add to cart
          </p>
        )}
      </div>
    </div>
  );
}
