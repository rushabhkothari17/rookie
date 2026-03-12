/**
 * PartnerOrgForm
 *
 * Adapter component that maps the structured PartnerOrgFormValue to/from the flat
 * key-value format expected by UniversalFormRenderer.  All field rendering is
 * delegated to UniversalFormRenderer so the partner form always looks identical to
 * every other form in the application.
 *
 * Used by:
 *   - public /signup?type=partner page  (compact=true)
 *   - admin "New Partner Org" dialog     (compact=false / default)
 */

import { UniversalFormRenderer } from "@/components/UniversalFormRenderer";
import { parseSchema, type FormField } from "@/components/FormSchemaBuilder";

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
  extra_fields: Record<string, string>;
}

export const EMPTY_PARTNER_ORG: PartnerOrgFormValue = {
  name: "", admin_name: "", admin_email: "", admin_password: "",
  base_currency: "USD",
  address: { line1: "", line2: "", city: "", region: "", postal: "", country: "" },
  extra_fields: {},
};

// Default schema used when no schema is stored yet in settings
const DEFAULT_SCHEMA: FormField[] = [
  { id: "pf_org_name",    key: "org_name",       label: "Organization Name", type: "text",     required: true,  placeholder: "", options: [], locked: true,  enabled: true,  order: 0 },
  { id: "pf_admin_name",  key: "admin_name",     label: "Admin Full Name",   type: "text",     required: true,  placeholder: "", options: [], locked: true,  enabled: true,  order: 1 },
  { id: "pf_admin_email", key: "admin_email",    label: "Admin Email",       type: "email",    required: true,  placeholder: "", options: [], locked: true,  enabled: true,  order: 2 },
  { id: "pf_admin_pass",  key: "admin_password", label: "Password",          type: "password", required: true,  placeholder: "", options: [], locked: true,  enabled: true,  order: 3 },
  { id: "pf_currency",    key: "base_currency",  label: "Base Currency",     type: "select",   required: false, placeholder: "", options: [], locked: false, enabled: true,  order: 4 },
  { id: "pf_address",     key: "address",        label: "Organization Address", type: "address", required: false, placeholder: "", options: [], locked: false, enabled: true, order: 5 },
];

// Core schema keys → PartnerOrgFormValue field names
const CORE_KEY_MAP: Record<string, keyof Omit<PartnerOrgFormValue, "address" | "extra_fields">> = {
  org_name:       "name",
  admin_name:     "admin_name",
  admin_email:    "admin_email",
  admin_password: "admin_password",
  base_currency:  "base_currency",
};

const ADDR_KEYS = new Set(["line1", "line2", "city", "region", "postal", "country"]);

interface Props {
  value: PartnerOrgFormValue;
  onChange: (v: PartnerOrgFormValue) => void;
  currencies: string[];
  schema?: string;
  compact?: boolean;
  testIdPrefix?: string;
}

export function PartnerOrgForm({ value, onChange, currencies, schema = "", compact = false }: Props) {
  // Parse schema (fall back to defaults) and inject currency options
  const rawFields = schema ? parseSchema(schema) : DEFAULT_SCHEMA;
  const fields = rawFields
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
    .map(f => {
      if (f.key === "base_currency" && currencies.length > 0) {
        return { ...f, options: currencies.map(c => `${c}|${c}`) };
      }
      return f;
    });

  // Build flat values for UniversalFormRenderer
  const flatValues: Record<string, string> = {
    org_name:       value.name,
    admin_name:     value.admin_name,
    admin_email:    value.admin_email,
    admin_password: value.admin_password,
    base_currency:  value.base_currency,
    // address sub-fields
    line1:   value.address.line1,
    line2:   value.address.line2,
    city:    value.address.city,
    region:  value.address.region,
    postal:  value.address.postal,
    country: value.address.country,
    // extra / custom fields
    ...value.extra_fields,
  };

  const handleChange = (key: string, val: string) => {
    if (key in CORE_KEY_MAP) {
      onChange({ ...value, [CORE_KEY_MAP[key]]: val });
    } else if (ADDR_KEYS.has(key)) {
      onChange({ ...value, address: { ...value.address, [key]: val } });
    } else {
      onChange({ ...value, extra_fields: { ...value.extra_fields, [key]: val } });
    }
  };

  return (
    <UniversalFormRenderer
      fields={fields}
      values={flatValues}
      onChange={handleChange}
      compact={compact}
    />
  );
}
