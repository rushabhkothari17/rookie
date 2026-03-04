/**
 * Fully schema-driven partner organisation creation form.
 * Used by both the Admin "New Partner Org" dialog (TenantsTab) and the public
 * /signup?type=partner page. Any field added in Auth & Pages → Partner Sign-Up
 * Page automatically appears in both places.
 */
import { useState, useEffect } from "react";
import { RequiredLabel } from "@/components/shared/RequiredLabel";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCountries, useProvinces } from "@/hooks/useCountries";
import { Building2, User, Mail, Lock, MapPin } from "lucide-react";
import { parseSchema, getAddressConfig, type FormField } from "@/components/FormSchemaBuilder";

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
  /** Any custom fields added via Auth & Pages schema builder */
  extra_fields: Record<string, string>;
}

// Default schema shown when no schema is stored yet
const DEFAULT_SCHEMA: FormField[] = [
  { id: "pf_org_name",    key: "org_name",       label: "Organization Name", type: "text",     required: true,  placeholder: "", options: [], locked: true,  enabled: true,  order: 0 },
  { id: "pf_admin_name",  key: "admin_name",     label: "Admin Full Name",   type: "text",     required: true,  placeholder: "", options: [], locked: true,  enabled: true,  order: 1 },
  { id: "pf_admin_email", key: "admin_email",    label: "Admin Email",       type: "email",    required: true,  placeholder: "", options: [], locked: true,  enabled: true,  order: 2 },
  { id: "pf_admin_pass",  key: "admin_password", label: "Password",          type: "password", required: true,  placeholder: "", options: [], locked: true,  enabled: true,  order: 3 },
  { id: "pf_currency",    key: "base_currency",  label: "Base Currency",     type: "select",   required: false, placeholder: "", options: [], locked: false, enabled: true,  order: 4 },
  { id: "pf_address",     key: "address",        label: "Organization Address","type": "address", required: false, placeholder: "", options: [], locked: false, enabled: true,  order: 5 },
];

// Keys that map directly to known value properties
const CORE_KEY_MAP: Record<string, keyof Omit<PartnerOrgFormValue, "address" | "extra_fields">> = {
  org_name:       "name",
  admin_name:     "admin_name",
  admin_email:    "admin_email",
  admin_password: "admin_password",
  base_currency:  "base_currency",
};

function getOrderedFields(schema: string): FormField[] {
  const fields = schema ? parseSchema(schema) : DEFAULT_SCHEMA;
  return [...fields].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
}

interface Props {
  value: PartnerOrgFormValue;
  onChange: (v: PartnerOrgFormValue) => void;
  currencies: string[];
  /** JSON schema string from partner_signup_form_schema */
  schema?: string;
  /** When true uses icon-prefixed compact inputs (public signup page style) */
  compact?: boolean;
  testIdPrefix?: string;
}

export function PartnerOrgForm({ value, onChange, currencies, schema = "", compact = false, testIdPrefix = "" }: Props) {
  const countries = useCountries();
  const [country, setCountry] = useState(value.address.country || "");
  const provinces = useProvinces(country);

  useEffect(() => { setCountry(value.address.country || ""); }, [value.address.country]);

  const setCore = (key: keyof Omit<PartnerOrgFormValue, "address" | "extra_fields">, val: string) =>
    onChange({ ...value, [key]: val });
  const setAddr = (key: string, val: string) =>
    onChange({ ...value, address: { ...value.address, [key]: val } });
  const setCountryAddr = (val: string) => {
    setCountry(val);
    onChange({ ...value, address: { ...value.address, country: val, region: "" } });
  };
  const setExtra = (key: string, val: string) =>
    onChange({ ...value, extra_fields: { ...value.extra_fields, [key]: val } });

  const prefix = testIdPrefix ? `${testIdPrefix}-` : "";
  const fields = getOrderedFields(schema);
  const enabledFields = fields.filter(f => f.enabled !== false);

  const renderField = (field: FormField) => {
    const tid = `${prefix}${field.key.replace(/_/g, "-")}`;

    // ── Address block ────────────────────────────────────────────────────
    if (field.key === "address") {
      const addrCfg = schema ? getAddressConfig(field) : {
        line1: { enabled: true, required: true },
        line2: { enabled: true, required: false },
        city:  { enabled: true, required: true },
        state: { enabled: true, required: false },
        postal: { enabled: true, required: true },
        country: { enabled: true, required: true },
      };
      const sf = (k: string) => (addrCfg as any)[k] ?? { enabled: true, required: false };

      return (
        <div key={field.id} className={compact ? "pt-2 space-y-1" : "space-y-1.5"}>
          {compact
            ? <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide flex items-center gap-1.5"><MapPin size={11} />Organization Address</p>
            : <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Organization Address</p>
          }
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
      );
    }

    // ── Currency select ──────────────────────────────────────────────────
    if (field.key === "base_currency") {
      return (
        <div key={field.id} className={compact ? undefined : "space-y-1.5"}>
          {!compact && <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Base Currency</label>}
          <Select value={value.base_currency} onValueChange={v => setCore("base_currency", v)}>
            <SelectTrigger className="w-full" data-testid={tid}>
              <SelectValue placeholder="Select base currency" />
            </SelectTrigger>
            <SelectContent>
              {(currencies.length ? currencies : ["USD","CAD","EUR","GBP","AUD","INR","MXN"]).map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      );
    }

    // ── Core identity fields ─────────────────────────────────────────────
    if (field.key in CORE_KEY_MAP) {
      const stateKey = CORE_KEY_MAP[field.key];
      const inputType = field.key === "admin_email" ? "email" : field.key === "admin_password" ? "password" : "text";
      const req = field.required !== false;

      const inputPlaceholder = field.placeholder ||
        (field.key === "org_name" ? `${field.label}${req ? " *" : ""}` :
         field.key === "admin_password" ? `${field.label}${req ? " *" : ""} (min 10 chars, upper, lower, number, symbol)` :
         `${field.label}${req ? " *" : ""}`);

      if (compact) {
        const Icon = field.key === "org_name" ? Building2 : field.key === "admin_name" ? User : field.key === "admin_email" ? Mail : Lock;
        return (
          <div key={field.id} className="relative">
            <Icon className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 pointer-events-none" />
            <Input className="pl-9" type={inputType} placeholder={inputPlaceholder} value={value[stateKey]} onChange={e => setCore(stateKey, e.target.value)} required={req} data-testid={tid} />
          </div>
        );
      }

      // Admin dialog: group name + admin account visually
      if (field.key === "org_name") {
        return (
          <div key={field.id} className="space-y-1.5">
            <RequiredLabel className="font-semibold uppercase tracking-wide text-slate-500">{field.label}</RequiredLabel>
            <Input placeholder="Acme Accounting" value={value.name} onChange={e => setCore("name", e.target.value)} required data-testid={tid} />
            <p className="text-xs text-slate-400">Partner code will be auto-generated from this name.</p>
          </div>
        );
      }
      // Render admin_name as section header for the group
      if (field.key === "admin_name") {
        return (
          <div key={field.id} className="pt-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Admin Account</p>
            <Input placeholder={`${field.label} *`} value={value.admin_name} onChange={e => setCore("admin_name", e.target.value)} required data-testid={tid} />
          </div>
        );
      }

      return (
        <Input key={field.id} type={inputType} placeholder={inputPlaceholder} value={value[stateKey]} onChange={e => setCore(stateKey, e.target.value)} required={req} data-testid={tid} />
      );
    }

    // ── Custom / extra fields ────────────────────────────────────────────
    const extraVal = value.extra_fields[field.key] || "";
    const req = field.required;
    const placeholder = field.placeholder || `${field.label}${req ? " *" : ""}`;

    if (field.type === "select" && field.options?.length > 0) {
      return (
        <div key={field.id} className={compact ? undefined : "space-y-1.5"}>
          {!compact && <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">{field.label}{req ? "" : " (optional)"}</label>}
          <Select value={extraVal} onValueChange={v => setExtra(field.key, v)}>
            <SelectTrigger data-testid={tid}><SelectValue placeholder={placeholder} /></SelectTrigger>
            <SelectContent>{field.options.map(opt => <SelectItem key={opt} value={opt}>{opt}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      );
    }

    if (field.type === "textarea") {
      return (
        <div key={field.id} className={compact ? undefined : "space-y-1.5"}>
          {!compact && <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">{field.label}{req ? <span className="text-red-500"> *</span> : ""}</label>}
          <Textarea placeholder={placeholder} value={extraVal} onChange={e => setExtra(field.key, e.target.value)} required={req} data-testid={tid} rows={3} />
        </div>
      );
    }

    // Default: text/email/tel/number/date/password inputs
    const htmlType = (["email","tel","number","date","password"].includes(field.type)) ? field.type : "text";
    if (compact) {
      return (
        <Input key={field.id} type={htmlType} placeholder={placeholder} value={extraVal} onChange={e => setExtra(field.key, e.target.value)} required={req} data-testid={tid} />
      );
    }
    return (
      <div key={field.id} className="space-y-1.5">
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">{field.label}{req ? <span className="text-red-500"> *</span> : " (optional)"}</label>
        <Input type={htmlType} placeholder={placeholder} value={extraVal} onChange={e => setExtra(field.key, e.target.value)} required={req} data-testid={tid} />
      </div>
    );
  };

  return <>{enabledFields.map(renderField)}</>;
}

export const EMPTY_PARTNER_ORG: PartnerOrgFormValue = {
  name: "", admin_name: "", admin_email: "", admin_password: "",
  base_currency: "USD",
  address: { line1: "", line2: "", city: "", region: "", postal: "", country: "" },
  extra_fields: {},
};
