/**
 * Shared partner organisation creation form.
 * Used by both the Admin "New Partner Org" dialog (TenantsTab) and the public
 * /signup?type=partner page. Schema controls which optional fields are shown
 * on the public-facing page; the admin dialog always shows all fields.
 */
import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCountries, useProvinces } from "@/hooks/useCountries";
import { Building2, User, Mail, Lock, MapPin } from "lucide-react";
import { parseSchema, getAddressConfig } from "@/components/FormSchemaBuilder";

export interface PartnerOrgFormValue {
  name: string;
  admin_name: string;
  admin_email: string;
  admin_password: string;
  base_currency: string;
  address: {
    line1: string;
    line2: string;
    city: string;
    region: string;
    postal: string;
    country: string;
  };
}

interface Props {
  value: PartnerOrgFormValue;
  onChange: (v: PartnerOrgFormValue) => void;
  currencies: string[];
  /** JSON schema string from partner_signup_form_schema. When omitted all fields are shown. */
  schema?: string;
  /** When true uses icon-prefixed compact inputs (signup page style) */
  compact?: boolean;
  testIdPrefix?: string;
}

function isFieldEnabled(schema: string, key: string, defaultEnabled = true): boolean {
  if (!schema) return defaultEnabled;
  try {
    const fields = JSON.parse(schema);
    const f = fields.find((x: any) => x.key === key);
    if (!f) return defaultEnabled;
    return f.enabled !== false;
  } catch {
    return defaultEnabled;
  }
}

function getAddressCfg(schema: string) {
  if (!schema) return null;
  try {
    const fields = JSON.parse(schema);
    const f = fields.find((x: any) => x.key === "address");
    return f ? getAddressConfig(f) : null;
  } catch { return null; }
}

export function PartnerOrgForm({ value, onChange, currencies, schema = "", compact = false, testIdPrefix = "" }: Props) {
  const countries = useCountries();
  const [country, setCountry] = useState(value.address.country || "");
  const provinces = useProvinces(country);

  // Keep local country in sync when value changes externally
  useEffect(() => { setCountry(value.address.country || ""); }, [value.address.country]);

  const set = (key: keyof Omit<PartnerOrgFormValue, "address">, val: string) =>
    onChange({ ...value, [key]: val });
  const setAddr = (key: string, val: string) =>
    onChange({ ...value, address: { ...value.address, [key]: val } });
  const setCountryAddr = (val: string) => {
    setCountry(val);
    onChange({ ...value, address: { ...value.address, country: val, region: "" } });
  };

  const showCurrency = isFieldEnabled(schema, "base_currency", true);
  const showAddress = isFieldEnabled(schema, "address", true);
  const addrCfg = getAddressCfg(schema);
  const sf = (key: string) => addrCfg ? (addrCfg as any)[key] : { enabled: true, required: false };

  const prefix = testIdPrefix ? `${testIdPrefix}-` : "";

  if (compact) {
    // Icon-prefixed minimal style (public signup page)
    return (
      <>
        <div className="relative">
          <Building2 className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
          <Input className="pl-9" placeholder="Organization name *" value={value.name} onChange={e => set("name", e.target.value)} required data-testid={`${prefix}org-name`} />
        </div>
        <div className="relative">
          <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
          <Input className="pl-9" placeholder="Your full name *" value={value.admin_name} onChange={e => set("admin_name", e.target.value)} required data-testid={`${prefix}admin-name`} />
        </div>
        <div className="relative">
          <Mail className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
          <Input className="pl-9" type="email" placeholder="Admin email address *" value={value.admin_email} onChange={e => set("admin_email", e.target.value)} required data-testid={`${prefix}admin-email`} />
        </div>
        <div className="relative">
          <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
          <Input className="pl-9" type="password" placeholder="Password * (min 10 chars, upper, lower, number, symbol)" value={value.admin_password} onChange={e => set("admin_password", e.target.value)} required data-testid={`${prefix}admin-password`} />
        </div>

        {showCurrency && (
          <Select value={value.base_currency} onValueChange={v => set("base_currency", v)}>
            <SelectTrigger className="w-full" data-testid={`${prefix}base-currency`}>
              <SelectValue placeholder="Select base currency" />
            </SelectTrigger>
            <SelectContent>
              {currencies.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>
        )}

        {showAddress && (
          <div className="pt-2 space-y-1">
            <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide flex items-center gap-1.5">
              <MapPin size={11} />Organization Address
            </p>
            {sf("line1").enabled && <Input placeholder={`Line 1${sf("line1").required ? " *" : " (optional)"}`} value={value.address.line1} onChange={e => setAddr("line1", e.target.value)} required={sf("line1").required} data-testid={`${prefix}addr-line1`} />}
            {sf("line2").enabled && <Input placeholder="Line 2 (optional)" value={value.address.line2} onChange={e => setAddr("line2", e.target.value)} data-testid={`${prefix}addr-line2`} />}
            {(sf("city").enabled || sf("postal").enabled) && (
              <div className="grid grid-cols-2 gap-1">
                {sf("city").enabled && <Input placeholder={`City${sf("city").required ? " *" : ""}`} value={value.address.city} onChange={e => setAddr("city", e.target.value)} required={sf("city").required} data-testid={`${prefix}addr-city`} />}
                {sf("postal").enabled && <Input placeholder={`Postal Code${sf("postal").required ? " *" : ""}`} value={value.address.postal} onChange={e => setAddr("postal", e.target.value)} required={sf("postal").required} data-testid={`${prefix}addr-postal`} />}
              </div>
            )}
            {sf("country").enabled && (
              <Select value={value.address.country} onValueChange={setCountryAddr}>
                <SelectTrigger data-testid={`${prefix}addr-country`}><SelectValue placeholder={`Country${sf("country").required ? " *" : ""}`} /></SelectTrigger>
                <SelectContent>{countries.map(c => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}</SelectContent>
              </Select>
            )}
            {sf("state").enabled && (
              provinces.length > 0 ? (
                <Select value={value.address.region} onValueChange={v => setAddr("region", v)}>
                  <SelectTrigger data-testid={`${prefix}addr-region-select`}><SelectValue placeholder="Province / State" /></SelectTrigger>
                  <SelectContent>{provinces.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
                </Select>
              ) : (
                <Input placeholder={`State / Province${sf("state").required ? " *" : ""}`} value={value.address.region} onChange={e => setAddr("region", e.target.value)} required={sf("state").required} data-testid={`${prefix}addr-region-input`} />
              )
            )}
          </div>
        )}
      </>
    );
  }

  // Non-compact style (admin dialog)
  return (
    <>
      <div className="space-y-1.5">
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Organization Name *</label>
        <Input placeholder="Acme Accounting" value={value.name} onChange={e => set("name", e.target.value)} required data-testid={`${prefix}org-name`} />
        <p className="text-xs text-slate-400">Partner code will be auto-generated from this name.</p>
      </div>

      <div className="pt-1 space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Admin Account</p>
        <Input placeholder="Full name *" value={value.admin_name} onChange={e => set("admin_name", e.target.value)} required data-testid={`${prefix}admin-name`} />
        <Input type="email" placeholder="Email address *" value={value.admin_email} onChange={e => set("admin_email", e.target.value)} required data-testid={`${prefix}admin-email`} />
        <Input type="password" placeholder="Password * (min 10 chars, upper, lower, number, symbol)" value={value.admin_password} onChange={e => set("admin_password", e.target.value)} required data-testid={`${prefix}admin-password`} />
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Base Currency</label>
        <Select value={value.base_currency} onValueChange={v => set("base_currency", v)}>
          <SelectTrigger className="w-full bg-white" data-testid={`${prefix}base-currency`}><SelectValue /></SelectTrigger>
          <SelectContent>{(currencies.length ? currencies : ["USD","CAD","EUR","GBP","AUD","INR","MXN"]).map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Organization Address</p>
        <Input placeholder="Line 1 *" value={value.address.line1} onChange={e => setAddr("line1", e.target.value)} required data-testid={`${prefix}addr-line1`} />
        <Input placeholder="Line 2 (optional)" value={value.address.line2} onChange={e => setAddr("line2", e.target.value)} data-testid={`${prefix}addr-line2`} />
        <div className="grid grid-cols-2 gap-2">
          <Input placeholder="City *" value={value.address.city} onChange={e => setAddr("city", e.target.value)} required data-testid={`${prefix}addr-city`} />
          <Input placeholder="Postal Code *" value={value.address.postal} onChange={e => setAddr("postal", e.target.value)} required data-testid={`${prefix}addr-postal`} />
        </div>
        <Select value={value.address.country} onValueChange={setCountryAddr}>
          <SelectTrigger data-testid={`${prefix}addr-country`}><SelectValue placeholder="Country *" /></SelectTrigger>
          <SelectContent>{countries.map(c => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}</SelectContent>
        </Select>
        {provinces.length > 0 ? (
          <Select value={value.address.region} onValueChange={v => setAddr("region", v)}>
            <SelectTrigger data-testid={`${prefix}addr-region-select`}><SelectValue placeholder="Province / State *" /></SelectTrigger>
            <SelectContent>{provinces.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
          </Select>
        ) : (
          <Input placeholder="State / Province *" value={value.address.region} onChange={e => setAddr("region", e.target.value)} required data-testid={`${prefix}addr-region-input`} />
        )}
      </div>
    </>
  );
}

export const EMPTY_PARTNER_ORG: PartnerOrgFormValue = {
  name: "", admin_name: "", admin_email: "", admin_password: "",
  base_currency: "USD",
  address: { line1: "", line2: "", city: "", region: "", postal: "", country: "" },
};
