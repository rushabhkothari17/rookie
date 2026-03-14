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

import { useState, useRef, useEffect, useCallback } from "react";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Tooltip, TooltipContent as _TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Info } from "lucide-react";
const TooltipContent = _TooltipContent as any;
import { AddressFieldRenderer } from "@/components/AddressFieldRenderer";
import { FormField } from "@/components/FormSchemaBuilder";
import type { VisibilityRuleSet } from "@/components/FormSchemaBuilder";
import { cn } from "@/lib/utils";

// ── Field-level visibility evaluation ─────────────────────────────────────────
function evalVisibility(rule: VisibilityRuleSet | null | undefined, values: Record<string, any>): boolean {
  if (!rule || !rule.groups?.length) return true;
  const evalGroup = (g: { logic: string; conditions: any[] }) => {
    if (!g.conditions.length) return true;
    const results = g.conditions.map(c => {
      const raw = values[c.depends_on];
      const a = String(raw ?? "").toLowerCase();
      const e = (c.value || "").toLowerCase();
      switch (c.operator) {
        case "equals":      return a === e;
        case "not_equals":  return a !== e;
        case "contains":    return a.includes(e);
        case "not_contains": return !a.includes(e);
        case "not_empty":   return !!a;
        case "empty":       return !a;
        default:            return true;
      }
    });
    return g.logic === "OR" ? results.some(Boolean) : results.every(Boolean);
  };
  const groupResults = rule.groups.map(g => evalGroup(g));
  return rule.top_logic === "OR" ? groupResults.some(Boolean) : groupResults.every(Boolean);
}

type AddressValue = {
  line1?: string; line2?: string; city?: string;
  region?: string; postal?: string; country?: string;
};

const ADDR_KEYS = ["line1", "line2", "city", "region", "postal", "country"] as const;

const PHONE_RE = /^[+\d][\d\s\-(). ]{3,49}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function validateField(key: string, val: string, required: boolean, maxLength?: number): string {
  if (!val) return required ? "This field is required" : "";
  if (key === "email" && !EMAIL_RE.test(val)) return "Enter a valid email address";
  if (key === "phone" && !PHONE_RE.test(val)) return "Enter a valid phone number";
  if (maxLength && val.length > maxLength) return `Maximum ${maxLength.toLocaleString()} characters`;
  return "";
}

/** Returns placeholder text — includes * suffix for required fields */
function ph(label: string, required: boolean): string {
  return required ? `${label} \u00A0*` : label;
}

const pillInput = (hasError: boolean, compact?: boolean) =>
  cn(
    compact ? "h-9" : "h-10",
    "w-full rounded-full border bg-white/90 px-5 text-sm text-slate-900",
    "placeholder:text-slate-400 transition-all duration-200",
    "focus:outline-none focus:ring-0",
    hasError
      ? "border-red-400 focus:border-red-500 focus:shadow-[0_0_0_4px_rgba(239,68,68,0.08)]"
      : "border-slate-200 hover:border-slate-300 focus:border-slate-800 focus:bg-white [&:focus]:[animation:focusGlow_0.4s_cubic-bezier(0.16,1,0.3,1)_forwards]"
  );

const pillSelect = (compact?: boolean) => cn(
  compact ? "h-9" : "h-10",
  "w-full rounded-full border border-slate-200 bg-white/90 px-5 text-sm",
  "hover:border-slate-300 data-[state=open]:border-slate-800",
  "focus:ring-0 focus:outline-none transition-all duration-200 [&>span]:line-clamp-1",
  "shadow-none"
);

const pillTextarea = (hasError: boolean) =>
  cn(
    "w-full rounded-3xl border bg-white/90 px-5 py-3 text-sm text-slate-900 resize-none",
    "placeholder:text-slate-400 transition-all duration-200",
    "focus:outline-none focus:ring-0",
    hasError
      ? "border-red-400 focus:border-red-500"
      : "border-slate-200 hover:border-slate-300 focus:border-slate-800 focus:bg-white focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
  );

interface Props {
  fields: FormField[];
  values: Record<string, string | File | null>;
  onChange: (key: string, value: string) => void;
  compact?: boolean;
  partnerCode?: string;
  addressMode?: "flat" | "json";
  /** Keys that render as read-only (e.g. "password" in edit forms) */
  readonlyKeys?: string[];
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
function FieldLabel({ label, required, tooltip }: { label: string; required?: boolean; tooltip?: string }) {
  return (
    <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em] flex items-center gap-1 mb-2">
      {label}{required && <span className="text-red-400 ml-0.5"> *</span>}
      {tooltip && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex items-center text-slate-300 hover:text-slate-500 cursor-help ml-0.5">
                <Info size={11} />
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-56 text-xs">{tooltip}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </label>
  );
}

/** Muted hint text shown below a field */
function HelperText({ text }: { text?: string }) {
  if (!text) return null;
  return <p className="mt-1 px-4 text-[11px] text-slate-400">{text}</p>;
}

// ── Signature Field Component ─────────────────────────────────────────────────
interface SigProps {
  field: FormField;
  values: Record<string, any>;
  onChange: (key: string, value: string) => void;
  animStyle: React.CSSProperties;
  compact?: boolean;
}

function SignatureField({ field, values, onChange, animStyle, compact }: SigProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [drawing, setDrawing] = useState(false);
  const [hasDrawing, setHasDrawing] = useState(false);
  const lastPos = useRef<{ x: number; y: number } | null>(null);
  const typedName = (values["signature_name"] as string) || "";

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.strokeStyle = "#1e293b";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }, []);

  const getPos = (e: React.MouseEvent | React.TouchEvent, canvas: HTMLCanvasElement) => {
    const rect = canvas.getBoundingClientRect();
    if ("touches" in e) {
      return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top };
    }
    return { x: (e as React.MouseEvent).clientX - rect.left, y: (e as React.MouseEvent).clientY - rect.top };
  };

  const startDraw = (e: React.MouseEvent | React.TouchEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    e.preventDefault();
    setDrawing(true);
    lastPos.current = getPos(e, canvas);
  };

  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    if (!drawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    e.preventDefault();
    const ctx = canvas.getContext("2d");
    if (!ctx || !lastPos.current) return;
    const pos = getPos(e, canvas);
    ctx.beginPath();
    ctx.moveTo(lastPos.current.x, lastPos.current.y);
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();
    lastPos.current = pos;
  };

  const stopDraw = () => {
    if (drawing) {
      setDrawing(false);
      setHasDrawing(true);
      const canvas = canvasRef.current;
      if (canvas) onChange("signature_data_url", canvas.toDataURL());
    }
    lastPos.current = null;
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasDrawing(false);
    onChange("signature_data_url", "");
  };

  return (
    <div style={animStyle} className="sm:col-span-2 space-y-3" data-testid="ufr-field-signature">
      <FieldLabel label={field.label || "Signature"} required={field.required} />
      {/* Canvas draw area */}
      <div className="relative rounded-2xl border-2 border-dashed border-slate-300 bg-white overflow-hidden" style={{ height: compact ? 100 : 140 }}>
        <canvas
          ref={canvasRef}
          width={600}
          height={compact ? 100 : 140}
          className="w-full h-full cursor-crosshair touch-none"
          onMouseDown={startDraw}
          onMouseMove={draw}
          onMouseUp={stopDraw}
          onMouseLeave={stopDraw}
          onTouchStart={startDraw}
          onTouchMove={draw}
          onTouchEnd={stopDraw}
          data-testid="signature-canvas"
        />
        {!hasDrawing && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <span className="text-sm text-slate-300 italic select-none">Draw your signature here</span>
          </div>
        )}
        <button
          type="button"
          onClick={clearCanvas}
          className="absolute top-2 right-2 text-[10px] text-slate-400 hover:text-red-500 bg-white border border-slate-200 rounded-lg px-2 py-0.5 transition-colors"
          data-testid="signature-clear-btn"
        >
          Clear
        </button>
      </div>
      {/* Typed name */}
      <div>
        <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em] block mb-2">
          Full Name (typed) <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          className="w-full rounded-full border border-slate-200 bg-white/90 px-5 h-10 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-slate-800 transition-all"
          value={typedName}
          onChange={e => onChange("signature_name", e.target.value)}
          placeholder="Type your full name to confirm"
          data-testid="signature-name-input"
        />
      </div>
    </div>
  );
}

export function UniversalFormRenderer({
  fields, values, onChange, compact = false, partnerCode, addressMode = "flat", readonlyKeys = [],
}: Props) {
  const enabled = fields.filter(f => f.enabled !== false && evalVisibility(f.show_when, values));
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const handleChange = (key: string, newVal: string, required: boolean, maxLength?: number) => {
    if (["email", "phone", "full_name", "company_name", "job_title"].includes(key)) {
      const err = validateField(key, newVal, required, maxLength);
      setFieldErrors(prev =>
        err ? { ...prev, [key]: err } : (() => { const n = { ...prev }; delete n[key]; return n; })()
      );
    }
    onChange(key, newVal);
  };

  const renderOne = (field: FormField, index = 0, isCompact = compact) => {
    const key = field.key;
    const val = (values[key] as string) || "";
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
        addrValue = (() => { try { return JSON.parse((val as string) || "{}"); } catch { return {}; } })();
      } else {
        addrValue = {
          line1: (values.line1 as string) || "", line2: (values.line2 as string) || "",
          city: (values.city as string) || "", region: (values.region as string) || "",
          postal: (values.postal as string) || "", country: (values.country as string) || "",
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
          <FieldLabel label={field.label || key} required={field.required} tooltip={field.tooltip_text} />
          <textarea
            className={pillTextarea(!!err)}
            value={val}
            onChange={e => onChange(key, e.target.value)}
            placeholder={samplePh(key, field)}
            rows={compact ? 3 : 4}
            maxLength={field.max_length || undefined}
            aria-label={field.label}
            data-testid={tid}
          />
          {field.max_length && (() => {
            const str = val as string;
            if (!str.length) {
              return <p className="mt-0.5 px-4 text-[10px] text-slate-400">Max {field.max_length.toLocaleString()} chars</p>;
            }
            const pct = str.length / field.max_length;
            const cls = pct > 0.95 ? "text-red-500" : pct > 0.8 ? "text-amber-500" : "text-slate-400";
            return <p className={`mt-0.5 px-4 text-[10px] text-right ${cls}`}>{str.length.toLocaleString()}/{field.max_length.toLocaleString()}</p>;
          })()}
          <HelperText text={field.helper_text} />
          {err && <p className="mt-1.5 px-4 text-[11px] text-red-500" data-testid={`${tid}-error`}>{err}</p>}
        </div>
      );
    }

    // ── Select / Dropdown ────────────────────────────────────────────────
    if (field.type === "select") {
      return (
        <div key={field.id} style={animStyle}>
          <FieldLabel label={field.label || key} required={field.required} tooltip={field.tooltip_text} />
          <Select value={val} onValueChange={v => onChange(key, v)}>
            <SelectTrigger className={pillSelect(isCompact)} data-testid={tid} aria-label={field.label}>
              <SelectValue placeholder={field.placeholder || `Select ${field.label || key}…`} />
            </SelectTrigger>
            <SelectContent className="rounded-2xl border-slate-200 shadow-xl">
              {(field.options || []).map(opt => {
                const [lbl, v] = opt.includes("|") ? opt.split("|") : [opt, opt];
                return <SelectItem key={v} value={v} className="rounded-xl">{lbl}</SelectItem>;
              })}
            </SelectContent>
          </Select>
          <HelperText text={field.helper_text} />
          {err && <p className="mt-1.5 px-4 text-[11px] text-red-500" data-testid={`${tid}-error`}>{err}</p>}
        </div>
      );
    }

    // ── Checkbox ─────────────────────────────────────────────────────────
    if (field.type === "checkbox") {
      return (
        <div key={field.id} style={animStyle}>
          <label className="flex items-center gap-3 cursor-pointer group" data-testid={tid}>
            <Checkbox
              checked={val === "true"}
              onCheckedChange={c => onChange(key, c ? "true" : "false")}
              className="rounded-full h-5 w-5 border-slate-300 data-[state=checked]:bg-slate-900 data-[state=checked]:border-slate-900"
            />
            <span className="text-sm text-slate-600 group-hover:text-slate-900 transition-colors flex items-center gap-1">
              {field.placeholder || field.label}
              {field.required && <span className="text-red-500 ml-0.5"> *</span>}
              {field.tooltip_text && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="inline-flex items-center text-slate-300 hover:text-slate-500 cursor-help ml-0.5">
                        <Info size={11} />
                      </span>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-56 text-xs">{field.tooltip_text}</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </span>
          </label>
          <HelperText text={field.helper_text} />
        </div>
      );
    }

    // ── File Upload ────────────────────────────────────────────────────────
    if (field.type === "file") {
      const fileVal = values[key] as File | null | undefined;
      const fileSizeErr = fileVal && field.max_file_size_mb
        ? (fileVal.size > field.max_file_size_mb * 1024 * 1024 ? `File must be under ${field.max_file_size_mb} MB` : null)
        : null;
      const displayErr = fileSizeErr || err;
      return (
        <div key={field.id} style={animStyle}>
          <FieldLabel label={field.label || key} required={field.required} tooltip={field.tooltip_text} />
          <label
            className={`flex items-center gap-3 cursor-pointer rounded-xl border px-4 py-3 text-sm transition-all ${displayErr ? "border-red-300 bg-red-50" : "border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50"}`}
            style={{ backgroundColor: "var(--aa-card)", borderColor: displayErr ? undefined : "var(--aa-border)" }}
            data-testid={tid}
          >
            <input
              type="file"
              className="hidden"
              required={field.required}
              onChange={e => {
                const file = e.target.files?.[0] ?? null;
                onChange(key, file as any);
                if (file && field.max_file_size_mb && file.size > field.max_file_size_mb * 1024 * 1024) {
                  // trigger validation error handled above
                }
              }}
            />
            <span className="text-xs font-medium px-2.5 py-1 rounded-full" style={{ backgroundColor: "color-mix(in srgb, var(--aa-primary) 10%, transparent)", color: "var(--aa-primary)" }}>
              Choose file
            </span>
            <span className="text-slate-400 text-xs truncate">
              {fileVal ? fileVal.name : (field.placeholder || "No file chosen")}
            </span>
          </label>
          {field.max_file_size_mb && (
            <p className="mt-0.5 px-4 text-[10px] text-slate-400">Max size: {field.max_file_size_mb} MB</p>
          )}
          <HelperText text={field.helper_text} />
          {displayErr && <p className="mt-1.5 px-4 text-[11px] text-red-500" data-testid={`${tid}-error`}>{displayErr}</p>}
        </div>
      );
    }

    // ── Terms & Conditions ─────────────────────────────────────────────────
    if (field.type === "terms_conditions") {
      return (
        <div key={field.id} style={animStyle} className="sm:col-span-2">
          <FieldLabel label={field.label || "Terms & Conditions"} required={field.required} />
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 max-h-48 overflow-y-auto text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">
            {(field as any).terms_text || "Please read the terms and conditions carefully before signing."}
          </div>
          {field.required && <p className="mt-1.5 text-[11px] text-slate-500 px-1">You must sign below to agree to these terms.</p>}
        </div>
      );
    }

    // ── Signature ─────────────────────────────────────────────────────────
    if (field.type === "signature") {
      return (
        <SignatureField
          key={field.id}
          field={field}
          values={values}
          onChange={onChange}
          animStyle={animStyle}
          compact={compact}
        />
      );
    }

    // ── Read-only field (e.g. password in admin edit forms) ──────────────────
    if ((readonlyKeys as string[]).includes(key)) {      return (
        <div key={field.id} style={animStyle}>
          <FieldLabel label={field.label || key} required={false} />
          <div className="relative">
            <input
              type="password"
              className={`${pillInput(false, isCompact)} cursor-not-allowed opacity-50 select-none`}
              value="••••••••••"
              readOnly
              tabIndex={-1}
              aria-label={field.label}
              data-testid={tid}
            />
            <span className="absolute inset-y-0 right-3 flex items-center text-[10px] text-slate-400 pointer-events-none select-none">locked</span>
          </div>
          <p className="mt-1.5 px-4 text-[11px] text-slate-400">Use "Send Password Reset Link" to let the user change their password.</p>
        </div>
      );
    }

    // ── Default: text / email / tel / number / date / password ────────────
    // For date fields with non-ISO format, use text input with pattern
    const isCustomDateFormat = field.type === "date" && field.date_format && field.date_format !== "YYYY-MM-DD";
    const htmlType = isCustomDateFormat
      ? "text"
      : (["email", "tel", "number", "date", "password"].includes(field.type))
        ? field.type as React.HTMLInputTypeAttribute
        : "text";

    const datePattern = isCustomDateFormat
      ? field.date_format!.replace("YYYY", "\\d{4}").replace("MM", "\\d{2}").replace("DD", "\\d{2}")
      : undefined;
    const datePlaceholder = isCustomDateFormat ? field.date_format : samplePh(key, field);

    return (
      <div key={field.id} style={animStyle}>
        <FieldLabel label={field.label || key} required={field.required} tooltip={field.tooltip_text} />
        <input
          type={htmlType}
          className={pillInput(!!err, isCompact)}
          value={val}
          onChange={e => handleChange(key, e.target.value, field.required, field.max_length)}
          placeholder={datePlaceholder || samplePh(key, field)}
          required={field.required}
          maxLength={field.max_length || undefined}
          min={field.min_value !== undefined ? String(field.min_value) : undefined}
          max={field.max_value !== undefined ? String(field.max_value) : undefined}
          pattern={datePattern}
          aria-label={field.label}
          data-testid={tid}
          autoComplete={
            key === "email" ? "email" :
            key === "password" ? "new-password" :
            key === "full_name" ? "name" :
            key === "phone" ? "tel" : undefined
          }
        />
        {field.max_length && !["number","date"].includes(field.type) && (() => {
          const str = val as string;
          if (!str.length) {
            return <p className="mt-0.5 px-4 text-[10px] text-slate-400">Max {field.max_length.toLocaleString()} chars</p>;
          }
          const pct = str.length / field.max_length;
          const cls = pct > 0.95 ? "text-red-500" : pct > 0.8 ? "text-amber-500" : "text-slate-400";
          return <p className={`mt-0.5 px-4 text-[10px] text-right ${cls}`}>{str.length.toLocaleString()}/{field.max_length.toLocaleString()}</p>;
        })()}
        {field.type === "number" && (field.min_value !== undefined || field.max_value !== undefined) && (
          <p className="mt-0.5 px-4 text-[10px] text-slate-400">
            {field.min_value !== undefined && field.max_value !== undefined
              ? `Range: ${field.min_value} – ${field.max_value}`
              : field.min_value !== undefined ? `Min: ${field.min_value}`
              : `Max: ${field.max_value}`}
          </p>
        )}
        {isCustomDateFormat && (
          <p className="mt-0.5 px-4 text-[10px] text-slate-400">Format: {field.date_format}</p>
        )}
        <HelperText text={field.helper_text} />
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
          const fullWidth = f.type === "textarea" || f.type === "terms_conditions" || f.type === "signature";
          return (
            <div key={f.id} className={fullWidth ? "sm:col-span-2" : ""}>
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
