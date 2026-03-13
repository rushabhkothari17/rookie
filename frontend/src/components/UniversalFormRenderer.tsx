/**
 * UniversalFormRenderer — single source of truth for rendering any form schema.
 *
 * Design: modern pill-shaped inputs with placeholders instead of labels,
 * asterisk suffix for required fields, staggered entrance animations, and
 * smooth focus transitions.
 *
 * Address handling:
 *   "flat" (default) — sub-fields as flat keys (line1, city, region, …)
 *   "json"           — address stored as JSON string at values[field.key]
 */

import { useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { AddressFieldRenderer } from "@/components/AddressFieldRenderer";
import { FormField } from "@/components/FormSchemaBuilder";
import { cn } from "@/lib/utils";

type AddressValue = {
  line1?: string; line2?: string; city?: string;
  region?: string; postal?: string; country?: string;
};

const ADDR_KEYS = ["line1", "line2", "city", "region", "postal", "country"] as const;

const PHONE_RE = /^[+\d][\d\s\-(). ]{3,49}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function validateField(key: string, val: string, required: boolean): string {
  if (!val) return required ? "This field is required" : "";
  if (key === "email" && !EMAIL_RE.test(val)) return "Enter a valid email address";
  if (key === "phone" && !PHONE_RE.test(val)) return "Enter a valid phone number";
  if (val.length > 100) return "Maximum 100 characters";
  return "";
}

/** Returns placeholder text — includes * suffix for required fields */
function ph(label: string, required: boolean): string {
  return required ? `${label} \u00A0*` : label;
}

const pillInput = (hasError: boolean) =>
  cn(
    "h-12 w-full rounded-full border bg-white/90 px-5 text-sm text-slate-900",
    "placeholder:text-slate-400 transition-all duration-200",
    "focus:outline-none focus:ring-0",
    hasError
      ? "border-red-400 focus:border-red-500 focus:shadow-[0_0_0_4px_rgba(239,68,68,0.08)]"
      : "border-slate-200 hover:border-slate-300 focus:border-slate-800 focus:bg-white [&:focus]:[animation:focusGlow_0.4s_cubic-bezier(0.16,1,0.3,1)_forwards]"
  );

const pillSelect = cn(
  "h-12 w-full rounded-full border border-slate-200 bg-white/90 px-5 text-sm",
  "hover:border-slate-300 data-[state=open]:border-slate-800",
  "focus:ring-0 focus:outline-none transition-all duration-200 [&>span]:line-clamp-1",
  "shadow-none"
);

const pillTextarea = (hasError: boolean) =>
  cn(
    "w-full rounded-3xl border bg-white/90 px-5 py-3.5 text-sm text-slate-900 resize-none",
    "placeholder:text-slate-400 transition-all duration-200",
    "focus:outline-none focus:ring-0",
    hasError
      ? "border-red-400 focus:border-red-500"
      : "border-slate-200 hover:border-slate-300 focus:border-slate-800 focus:bg-white focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
  );

interface Props {
  fields: FormField[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  compact?: boolean;
  partnerCode?: string;
  addressMode?: "flat" | "json";
}

/** Sample placeholder values for common field keys */
const SAMPLE_VALUES: Record<string, string> = {
  full_name:    "e.g. Jane Smith",
  company_name: "e.g. Acme Corp",
  email:        "e.g. jane@company.com",
  phone:        "e.g. +1 (555) 000-1234",
  job_title:    "e.g. Operations Manager",
  password:     "Min 10 chars · upper · number · symbol",
  first_name:   "e.g. Jane",
  last_name:    "e.g. Smith",
  website:      "e.g. https://acmecorp.com",
  notes:        "e.g. Referred by John, prefers email contact",
};

function samplePh(key: string, field: FormField): string {
  if (field.placeholder) return field.placeholder;           // admin-defined wins
  return SAMPLE_VALUES[key] ?? `e.g. ${field.label || key}`; // fallback to generic
}

/** Small uppercase label above a field */
function FieldLabel({ label, required }: { label: string; required?: boolean }) {
  return (
    <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em] block mb-2">
      {label}{required && <span className="text-red-400 ml-0.5"> *</span>}
    </label>
  );
}

export function UniversalFormRenderer({
  fields, values, onChange, compact = false, partnerCode, addressMode = "flat",
}: Props) {
  const enabled = fields.filter(f => f.enabled !== false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const handleChange = (key: string, newVal: string, required: boolean) => {
    if (["email", "phone", "full_name", "company_name", "job_title"].includes(key)) {
      const err = validateField(key, newVal, required);
      setFieldErrors(prev =>
        err ? { ...prev, [key]: err } : (() => { const n = { ...prev }; delete n[key]; return n; })()
      );
    }
    onChange(key, newVal);
  };

  const renderOne = (field: FormField, index = 0) => {
    const key = field.key;
    const val = values[key] || "";
    const tid = `ufr-field-${key}`;
    const err = fieldErrors[key] || "";

    // Entrance animation — stagger by index
    const animStyle: React.CSSProperties = {
      animation: `fadeSlideUp 0.4s cubic-bezier(0.16,1,0.3,1) ${index * 50}ms both`,
    };

    // ── Address block ─────────────────────────────────────────────────────
    if (field.type === "address") {
      let addrValue: AddressValue;
      if (addressMode === "json") {
        addrValue = (() => { try { return JSON.parse(val || "{}"); } catch { return {}; } })();
      } else {
        addrValue = {
          line1: values.line1 || "", line2: values.line2 || "",
          city: values.city || "", region: values.region || "",
          postal: values.postal || "", country: values.country || "",
        };
      }
      const handleAddrChange = (v: AddressValue) => {
        if (addressMode === "json") {
          onChange(key, JSON.stringify(v));
        } else {
          (ADDR_KEYS as readonly string[]).forEach(k => {
            const next = (v as any)[k] || "";
            const prev = (values as any)[k] || "";
            if (next !== prev) onChange(k, next);
          });
        }
      };
      return (
        <div key={field.id} style={animStyle}>
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

    // ── Textarea ─────────────────────────────────────────────────────────
    if (field.type === "textarea") {
      return (
        <div key={field.id} style={animStyle}>
          <FieldLabel label={field.label || key} required={field.required} />
          <textarea
            className={pillTextarea(!!err)}
            value={val}
            onChange={e => onChange(key, e.target.value)}
            placeholder={samplePh(key, field)}
            rows={compact ? 3 : 4}
            aria-label={field.label}
            data-testid={tid}
          />
          {err && <p className="mt-1.5 px-4 text-[11px] text-red-500" data-testid={`${tid}-error`}>{err}</p>}
        </div>
      );
    }

    // ── Select / Dropdown ────────────────────────────────────────────────
    if (field.type === "select") {
      return (
        <div key={field.id} style={animStyle}>
          <FieldLabel label={field.label || key} required={field.required} />
          <Select value={val} onValueChange={v => onChange(key, v)}>
            <SelectTrigger className={pillSelect} data-testid={tid} aria-label={field.label}>
              <SelectValue placeholder={field.placeholder || `Select ${field.label || key}…`} />
            </SelectTrigger>
            <SelectContent className="rounded-2xl border-slate-200 shadow-xl">
              {(field.options || []).map(opt => {
                const [lbl, v] = opt.includes("|") ? opt.split("|") : [opt, opt];
                return <SelectItem key={v} value={v} className="rounded-xl">{lbl}</SelectItem>;
              })}
            </SelectContent>
          </Select>
          {err && <p className="mt-1.5 px-4 text-[11px] text-red-500" data-testid={`${tid}-error`}>{err}</p>}
        </div>
      );
    }

    // ── Checkbox ─────────────────────────────────────────────────────────
    if (field.type === "checkbox") {
      return (
        <label
          key={field.id}
          style={animStyle}
          className="flex items-center gap-3 cursor-pointer group"
          data-testid={tid}
        >
          <Checkbox
            checked={val === "true"}
            onCheckedChange={c => onChange(key, c ? "true" : "false")}
            className="rounded-full h-5 w-5 border-slate-300 data-[state=checked]:bg-slate-900 data-[state=checked]:border-slate-900"
          />
          <span className="text-sm text-slate-600 group-hover:text-slate-900 transition-colors">
            {field.placeholder || field.label}
            {field.required && <span className="text-red-500 ml-0.5"> *</span>}
          </span>
        </label>
      );
    }

    // ── Default: text / email / tel / number / date / password ────────────
    const htmlType = (["email", "tel", "number", "date", "password"].includes(field.type))
      ? field.type as React.HTMLInputTypeAttribute
      : "text";

    return (
      <div key={field.id} style={animStyle}>
        <FieldLabel label={field.label || key} required={field.required} />
        <input
          type={htmlType}
          className={pillInput(!!err)}
          value={val}
          onChange={e => handleChange(key, e.target.value, field.required)}
          placeholder={samplePh(key, field)}
          required={field.required}
          aria-label={field.label}
          data-testid={tid}
          autoComplete={
            key === "email" ? "email" :
            key === "password" ? "new-password" :
            key === "full_name" ? "name" :
            key === "phone" ? "tel" : undefined
          }
        />
        {err && (
          <p className="mt-1.5 px-4 text-[11px] text-red-500" data-testid={`${tid}-error`}>{err}</p>
        )}
        {key === "password" && !err && (
          <p className="mt-1.5 px-4 text-[11px] text-slate-400">
            Min. 10 characters · uppercase · number · special character (!@#$%^&*)
          </p>
        )}
      </div>
    );
  };

  if (compact) {
    return (
      <div className="flex flex-col gap-4">
        {enabled.map((f, i) => renderOne(f, i))}
      </div>
    );
  }

  // Full layout: address full-width at its schema position; other fields in 2-col grid
  const addrIdx = enabled.findIndex(f => f.type === "address");
  const before    = addrIdx >= 0 ? enabled.slice(0, addrIdx) : enabled;
  const addrField = addrIdx >= 0 ? enabled[addrIdx] : null;
  const after     = addrIdx >= 0 ? enabled.slice(addrIdx + 1) : [];

  // Running index for consistent stagger across all fields
  let idx = 0;
  const grid = (flds: FormField[]) =>
    flds.length === 0 ? null : (
      <div className="grid gap-4 sm:grid-cols-2">
        {flds.map(f => {
          const i = idx++;
          return (
            <div key={f.id} className={f.type === "textarea" ? "sm:col-span-2" : ""}>
              {renderOne(f, i)}
            </div>
          );
        })}
      </div>
    );

  const addrI = idx;
  if (addrField) idx++;

  return (
    <div className="flex flex-col gap-4">
      {grid(before)}
      {addrField && renderOne(addrField, addrI)}
      {grid(after)}
    </div>
  );
}
