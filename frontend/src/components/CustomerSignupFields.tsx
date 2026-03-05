/**
 * CustomerSignupFields
 *
 * A single source of truth for rendering the customer signup / create-customer
 * form fields.  Both the public /signup page and the admin "Add Customer"
 * dialog import and use this component so they always show exactly the same
 * fields in exactly the same order as configured in
 * Auth & Pages > Customer Sign up (signup_form_schema).
 *
 * Field ordering:
 *   1. Schema fields rendered in ascending `order` value.
 *   2. Email + Password are "auth fields" (not in the schema) and are
 *      injected immediately after `full_name`.
 *   3. The `address` type field is rendered as a sub-form driven by its
 *      `address_config`.
 *
 * Props:
 *   schema        – parsed FormField[] already from signup_form_schema
 *   values        – flat Record of ALL field keys (email, password, line1 …)
 *   onChange      – (key, value) => void  – parent routes to the right state
 *   provinces     – list for state/province select (populated by parent)
 *   countries     – list for country select
 *   showPassword  – render password field (true on create, false on edit)
 *   compact       – true → compact dialog layout; false → full-page layout
 */

import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SearchableSelect } from "@/components/ui/searchable-select";
import { FormField, getAddressConfig } from "@/components/FormSchemaBuilder";
import { User, Mail, Lock, Phone, Briefcase, Building2, MapPin } from "lucide-react";

// ── Icon map for known standard fields ──────────────────────────────────────
const FIELD_ICONS: Record<string, React.ElementType> = {
  full_name:    User,
  email:        Mail,
  password:     Lock,
  phone:        Phone,
  job_title:    Briefcase,
  company_name: Building2,
};

// ── Build augmented field list (schema order + injected auth fields) ─────────
type AugmentedField = FormField | {
  id: string; key: string; label: string; type: string;
  required: boolean; placeholder: string; locked: boolean;
  enabled: boolean; options: string[]; order: number;
};

// Per-field character limits enforced on all signup/create-customer forms
const FIELD_MAX: Record<string, number> = {
  email: 50, company_name: 50, job_title: 50, phone: 50, full_name: 100,
};

function buildFields(schema: FormField[], showPassword: boolean): AugmentedField[] {
  const sorted = [...schema]
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
    .filter(f => f.enabled !== false);

  const email: AugmentedField = { id: "builtin_email",    key: "email",    label: "Email address",  type: "email",    required: true,  placeholder: "", locked: true, enabled: true, options: [], order: -1 };
  const pass:  AugmentedField = { id: "builtin_password", key: "password", label: "Password",        type: "password", required: true,  placeholder: "", locked: true, enabled: true, options: [], order: -1 };

  const fnIdx = sorted.findIndex(f => f.key === "full_name");
  const cnIdx = sorted.findIndex(f => f.key === "company_name");
  // Inject after company_name if it immediately follows full_name, else after full_name
  const insertAfterIdx = (cnIdx >= 0 && fnIdx >= 0 && cnIdx === fnIdx + 1) ? cnIdx : fnIdx;
  const insertAt = insertAfterIdx >= 0 ? insertAfterIdx + 1 : 0;

  const builtins: AugmentedField[] = showPassword ? [email, pass] : [email];
  return [...sorted.slice(0, insertAt), ...builtins, ...sorted.slice(insertAt)];
}

// ── Props ────────────────────────────────────────────────────────────────────
interface Props {
  schema:       FormField[];
  values:       Record<string, string>;
  onChange:     (key: string, value: string) => void;
  provinces:    { value: string; label: string }[];
  countries:    { value: string; label: string }[];
  showPassword?: boolean;
  compact?:     boolean;
}

// ── Sub-components ───────────────────────────────────────────────────────────
function Label({ children, compact }: { children: React.ReactNode; compact: boolean }) {
  return compact
    ? <label className="text-xs font-medium text-slate-600">{children}</label>
    : <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</label>;
}

// ── Main component ───────────────────────────────────────────────────────────
export function CustomerSignupFields({
  schema, values, onChange, provinces, countries,
  showPassword = true, compact = false,
}: Props) {
  const fields = buildFields(schema, showPassword);

  const renderField = (field: AugmentedField) => {
    // ── Address block ────────────────────────────────────────────────────────
    if (field.key === "address") {
      const cfg = getAddressConfig(field as FormField);
      return (
        <div key="address" className={compact ? "space-y-2 border-t border-slate-100 pt-3" : "space-y-4"}>
          {compact
            ? <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{field.label}</p>
            : (
              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-slate-100" />
                <span className="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-1.5"><MapPin size={11} />{field.label}</span>
                <div className="h-px flex-1 bg-slate-100" />
              </div>
            )
          }
          <div className={compact ? "space-y-2" : "grid gap-4 sm:grid-cols-2"}>
            {cfg.line1.enabled && (
              <div className={compact ? "space-y-1" : `space-y-1.5 sm:col-span-2`}>
                {!compact && <Label compact={compact}>Street address{cfg.line1.required ? <span className="text-red-500"> *</span> : ""}</Label>}
                <Input value={values.line1 || ""} onChange={e => onChange("line1", e.target.value)} placeholder={compact ? `Line 1${cfg.line1.required ? " *" : ""}` : ""} maxLength={100} data-testid="signup-field-line1" />
              </div>
            )}
            {cfg.line2.enabled && (
              <div className={compact ? "space-y-1" : `space-y-1.5 sm:col-span-2`}>
                {!compact && <Label compact={compact}>Address line 2{!cfg.line2.required ? " (optional)" : <span className="text-red-500"> *</span>}</Label>}
                <Input value={values.line2 || ""} onChange={e => onChange("line2", e.target.value)} placeholder={compact ? `Line 2${cfg.line2.required ? " *" : " (optional)"}` : ""} maxLength={100} data-testid="signup-field-line2" />
              </div>
            )}
            {cfg.city.enabled && (
              <div className="space-y-1">
                {!compact && <Label compact={compact}>City{cfg.city.required ? <span className="text-red-500"> *</span> : ""}</Label>}
                <Input value={values.city || ""} onChange={e => onChange("city", e.target.value)} placeholder={compact ? `City${cfg.city.required ? " *" : ""}` : ""} maxLength={50} data-testid="signup-field-city" />
              </div>
            )}
            {cfg.state.enabled && (
              <div className="space-y-1">
                {!compact && <Label compact={compact}>State / Province{cfg.state.required ? <span className="text-red-500"> *</span> : ""}</Label>}
                {provinces.length > 0 ? (
                  <Select value={values.region || ""} onValueChange={v => onChange("region", v)}>
                    <SelectTrigger data-testid="signup-field-region-select"><SelectValue placeholder={compact ? `Province *` : "Select province / state"} /></SelectTrigger>
                    <SelectContent>{provinces.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
                  </Select>
                ) : (
                  <Input value={values.region || ""} onChange={e => onChange("region", e.target.value)} placeholder={compact ? `State / Province${cfg.state.required ? " *" : ""}` : ""} maxLength={50} data-testid="signup-field-region-input" />
                )}
              </div>
            )}
            {cfg.postal.enabled && (
              <div className="space-y-1">
                {!compact && <Label compact={compact}>Postal / ZIP{cfg.postal.required ? <span className="text-red-500"> *</span> : ""}</Label>}
                <Input value={values.postal || ""} onChange={e => onChange("postal", e.target.value)} placeholder={compact ? `Postal${cfg.postal.required ? " *" : ""}` : ""} maxLength={20} data-testid="signup-field-postal" />
              </div>
            )}
            {cfg.country.enabled && (
              <div className="space-y-1">
                {!compact && <Label compact={compact}>Country{cfg.country.required ? <span className="text-red-500"> *</span> : ""}</Label>}
                <SearchableSelect
                  value={values.country || undefined}
                  onValueChange={v => onChange("country", v)}
                  options={countries}
                  placeholder={compact ? `Country${cfg.country.required ? " *" : ""}…` : "Select country"}
                  searchPlaceholder="Search country…"
                  data-testid="signup-field-country"
                />
              </div>
            )}
          </div>
        </div>
      );
    }

    // ── Regular field ────────────────────────────────────────────────────────
    const Icon = FIELD_ICONS[field.key];
    const labelNode = (
      <Label compact={compact}>
        {!compact && Icon && <Icon size={12} className="text-slate-400 inline mr-1" />}
        {field.label}
        {field.required && <span className="text-red-500 ml-0.5">*</span>}
      </Label>
    );

    const inputEl = (() => {
      if (field.type === "textarea") {
        return (
          <Textarea
            value={values[field.key] || ""}
            onChange={e => onChange(field.key, e.target.value)}
            placeholder={field.placeholder}
            rows={2}
            className="text-sm resize-none"
            data-testid={`signup-field-${field.key}`}
          />
        );
      }
      if (field.type === "select") {
        return (
          <Select value={values[field.key] || ""} onValueChange={v => onChange(field.key, v)}>
            <SelectTrigger data-testid={`signup-field-${field.key}`}>
              <SelectValue placeholder={field.placeholder || "Select…"} />
            </SelectTrigger>
            <SelectContent>
              {(field.options || []).map(opt => {
                const [lbl, val] = opt.includes("|") ? opt.split("|") : [opt, opt];
                return <SelectItem key={val} value={val}>{lbl}</SelectItem>;
              })}
            </SelectContent>
          </Select>
        );
      }
      return (
        <Input
          type={field.type as React.HTMLInputTypeAttribute}
          value={values[field.key] || ""}
          onChange={e => onChange(field.key, e.target.value)}
          placeholder={field.placeholder || undefined}
          maxLength={FIELD_MAX[field.key]}
          data-testid={field.key === "email" ? "signup-email-input" : field.key === "password" ? "signup-password-input" : `signup-field-${field.key}`}
        />
      );
    })();

    return (
      <div key={field.id} className={compact ? "space-y-1" : "space-y-1.5"}>
        {labelNode}
        {inputEl}
        {field.key === "password" && (
          <p className="text-[11px] text-slate-400 mt-1">
            Min. 10 characters · at least one uppercase letter · one number · one special character (!@#$%^&*)
          </p>
        )}
      </div>
    );
  };

  if (compact) {
    return <div className="space-y-3">{fields.map(renderField)}</div>;
  }

  // Full-page: 2-column grid for non-address fields grouped together
  // Address sits full-width at its schema position
  const nonAddressFields = fields.filter(f => f.key !== "address");
  const addrField = fields.find(f => f.key === "address");
  const addrPos = fields.findIndex(f => f.key === "address");

  // Split into: fields before address, address, fields after address
  const beforeAddr = addrPos >= 0 ? fields.slice(0, addrPos).filter(f => f.key !== "address") : nonAddressFields;
  const afterAddr  = addrPos >= 0 ? fields.slice(addrPos + 1) : [];

  const renderGrid = (flds: AugmentedField[]) =>
    flds.length > 0 ? (
      <div className="grid gap-4 sm:grid-cols-2">
        {flds.map(f => (
          <div key={f.id} className={f.type === "textarea" ? "sm:col-span-2" : ""}>
            {renderField(f)}
          </div>
        ))}
      </div>
    ) : null;

  return (
    <div className="space-y-6">
      <p className="text-xs text-slate-400"><span className="text-red-500">*</span> Required field</p>
      {renderGrid(beforeAddr)}
      {addrField && renderField(addrField)}
      {renderGrid(afterAddr)}
    </div>
  );
}
