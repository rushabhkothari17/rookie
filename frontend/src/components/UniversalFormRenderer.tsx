/**
 * UniversalFormRenderer — the single source of truth for rendering any form schema.
 *
 * Every form in the application (customer signup, partner signup, profile,
 * scope/quote modals) uses this component so that field rendering is always
 * identical and driven entirely by the FormSchemaBuilder schema.
 *
 * Address handling:
 *   default ("flat") — address sub-fields are stored as flat keys in `values`:
 *     values.line1, values.line2, values.city, values.region, values.postal, values.country
 *   "json"           — address stored as JSON string at values[field.key]
 *                      (used by dynamic forms like scope/quote modals in ProductDetail)
 *
 * Canonical address field order (enforced by AddressFieldRenderer):
 *   Line 1 → Line 2 → City → Country → State/Province → Postal
 */

import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { AddressFieldRenderer } from "@/components/AddressFieldRenderer";
import { FormField } from "@/components/FormSchemaBuilder";

type AddressValue = {
  line1?: string; line2?: string; city?: string;
  region?: string; postal?: string; country?: string;
};

const ADDR_KEYS = ["line1", "line2", "city", "region", "postal", "country"] as const;

interface Props {
  fields: FormField[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  /** compact=true for dialogs; false (default) for full-page forms */
  compact?: boolean;
  /** Scope country/province lists to a specific partner's tax tables */
  partnerCode?: string;
  /**
   * "flat"  – address sub-fields live as flat keys (line1, city, …) in values   [default]
   * "json"  – address stored as JSON string at values[field.key]
   */
  addressMode?: "flat" | "json";
}

function FieldLabel({ field, compact }: { field: FormField; compact: boolean }) {
  if (compact) {
    return (
      <label className="block mb-0.5 text-xs text-slate-600 font-medium">
        {field.label}{field.required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
    );
  }
  return (
    <label className="block mb-0.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
      {field.label}{field.required && <span className="text-red-500 ml-0.5">*</span>}
    </label>
  );
}

export function UniversalFormRenderer({
  fields,
  values,
  onChange,
  compact = false,
  partnerCode,
  addressMode = "flat",
}: Props) {
  const enabled = fields.filter(f => f.enabled !== false);

  const renderOne = (field: FormField) => {
    const key = field.key;
    const val = values[key] || "";
    const tid = `ufr-field-${key}`;

    // ── Address block ───────────────────────────────────────────────────────
    if (field.type === "address") {
      let addrValue: AddressValue;

      if (addressMode === "json") {
        addrValue = (() => { try { return JSON.parse(val || "{}"); } catch { return {}; } })();
      } else {
        addrValue = {
          line1:   values.line1   || "",
          line2:   values.line2   || "",
          city:    values.city    || "",
          region:  values.region  || "",
          postal:  values.postal  || "",
          country: values.country || "",
        };
      }

      const handleAddrChange = (v: AddressValue) => {
        if (addressMode === "json") {
          onChange(key, JSON.stringify(v));
        } else {
          ADDR_KEYS.forEach(k => onChange(k, v[k] || ""));
        }
      };

      return (
        <div key={field.id}>
          <AddressFieldRenderer
            field={field}
            value={addrValue}
            onChange={handleAddrChange}
            partnerCode={partnerCode}
            compact={compact}
          />
        </div>
      );
    }

    // ── Textarea ────────────────────────────────────────────────────────────
    if (field.type === "textarea") {
      return (
        <div key={field.id} className="space-y-1">
          <FieldLabel field={field} compact={compact} />
          <Textarea
            value={val}
            onChange={e => onChange(key, e.target.value)}
            placeholder={field.placeholder}
            rows={3}
            className="text-sm resize-none"
            data-testid={tid}
          />
        </div>
      );
    }

    // ── Select / Dropdown ───────────────────────────────────────────────────
    if (field.type === "select") {
      return (
        <div key={field.id} className="space-y-1">
          <FieldLabel field={field} compact={compact} />
          <Select value={val} onValueChange={v => onChange(key, v)}>
            <SelectTrigger data-testid={tid}>
              <SelectValue placeholder={field.placeholder || "Select…"} />
            </SelectTrigger>
            <SelectContent>
              {(field.options || []).map(opt => {
                const [lbl, v] = opt.includes("|") ? opt.split("|") : [opt, opt];
                return <SelectItem key={v} value={v}>{lbl}</SelectItem>;
              })}
            </SelectContent>
          </Select>
        </div>
      );
    }

    // ── Checkbox ────────────────────────────────────────────────────────────
    if (field.type === "checkbox") {
      return (
        <label key={field.id} className="flex items-center gap-2 cursor-pointer" data-testid={tid}>
          <Checkbox
            checked={val === "true"}
            onCheckedChange={c => onChange(key, c ? "true" : "false")}
          />
          <span className="text-sm text-slate-600">{field.placeholder || field.label}</span>
        </label>
      );
    }

    // ── Default: text / email / tel / number / date / password ──────────────
    const htmlType = (["email", "tel", "number", "date", "password"].includes(field.type))
      ? field.type as React.HTMLInputTypeAttribute
      : "text";

    return (
      <div key={field.id} className="space-y-1">
        <FieldLabel field={field} compact={compact} />
        <Input
          type={htmlType}
          value={val}
          onChange={e => onChange(key, e.target.value)}
          placeholder={field.placeholder || undefined}
          required={field.required}
          data-testid={tid}
        />
        {key === "password" && (
          <p className="text-[11px] text-slate-400 mt-0.5">
            Min. 10 characters · at least one uppercase · one number · one special character (!@#$%^&*)
          </p>
        )}
      </div>
    );
  };

  if (compact) {
    return <div className="space-y-3">{enabled.map(renderOne)}</div>;
  }

  // Full layout: non-address fields in a 2-col grid; address block sits full-width
  // at its schema-defined position.
  const addrIdx = enabled.findIndex(f => f.type === "address");
  const before    = addrIdx >= 0 ? enabled.slice(0, addrIdx) : enabled;
  const addrField = addrIdx >= 0 ? enabled[addrIdx] : null;
  const after     = addrIdx >= 0 ? enabled.slice(addrIdx + 1) : [];

  const grid = (flds: FormField[]) =>
    flds.length === 0 ? null : (
      <div className="grid gap-4 sm:grid-cols-2">
        {flds.map(f => (
          <div key={f.id} className={f.type === "textarea" ? "sm:col-span-2" : ""}>
            {renderOne(f)}
          </div>
        ))}
      </div>
    );

  return (
    <div className="space-y-4">
      {grid(before)}
      {addrField && renderOne(addrField)}
      {grid(after)}
    </div>
  );
}
