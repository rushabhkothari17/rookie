import { useEffect, useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MapPin } from "lucide-react";
import api from "@/lib/api";
import { type FormField, getAddressConfig } from "@/components/FormSchemaBuilder";
import { cn } from "@/lib/utils";

export type AddressValue = {
  line1?: string;
  line2?: string;
  city?: string;
  region?: string;
  postal?: string;
  country?: string;
};

interface Props {
  field: FormField;
  value: AddressValue;
  onChange: (v: AddressValue) => void;
  partnerCode?: string;
  compact?: boolean;
  className?: string;
}

type Option = { value: string; label: string };

const pillInput = (hasError = false, compact = false) =>
  cn(
    compact ? "h-9" : "h-10",
    "w-full rounded-full border px-5 text-sm transition-all duration-200",
    "bg-[var(--aa-card)] text-[var(--aa-text)] placeholder:text-[var(--aa-muted)]",
    "focus:outline-none focus:ring-0",
    hasError
      ? "border-red-400 focus:border-red-500"
      : "border-[var(--aa-border)] hover:border-[var(--aa-muted)] focus:border-[var(--aa-accent)] focus:bg-[var(--aa-surface)] focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
  );

const pillSelect = (compact = false) => cn(
  compact ? "h-9" : "h-10",
  "w-full rounded-full border px-5 text-sm",
  "bg-[var(--aa-card)] text-[var(--aa-text)] border-[var(--aa-border)]",
  "hover:border-[var(--aa-muted)] focus:border-[var(--aa-accent)] focus:ring-0 focus:outline-none",
  "transition-all duration-200 [&>span]:line-clamp-1"
);

export function AddressFieldRenderer({ field, value, onChange, partnerCode, compact = false, className }: Props) {
  const cfg = getAddressConfig(field);
  const [countries, setCountries] = useState<Option[]>([]);
  const [provinces, setProvinces] = useState<Option[]>([]);

  useEffect(() => {
    const url = partnerCode
      ? `/utils/countries?partner_code=${encodeURIComponent(partnerCode)}`
      : "/utils/countries";
    api.get(url)
      .then(r => setCountries(r.data.countries || []))
      .catch(() => setCountries([{ value: "Canada", label: "Canada" }, { value: "USA", label: "United States" }]));
  }, [partnerCode]);

  useEffect(() => {
    const country = value.country || "";
    if (!country) { setProvinces([]); return; }
    api.get(`/utils/provinces?country_code=${encodeURIComponent(country)}`)
      .then(r => {
        const regs = r.data.regions || [];
        setProvinces(regs);
        if (regs.length && value.region && !regs.find((p: Option) => p.value === value.region || p.label === value.region)) {
          onChange({ ...value, region: "" });
        }
      })
      .catch(() => setProvinces([]));
  }, [value.country]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (key: keyof AddressValue, v: string) => onChange({ ...value, [key]: v });
  const ph = (label: string, required: boolean) => required ? `${label} *` : label;

  return (
    <div className={cn("flex flex-col gap-4", className)} data-testid={`address-field-${field.key}`}>
      {/* Section header */}
      {!compact ? (
        <div className="flex items-center gap-3 py-1">
          <div className="h-px flex-1 bg-gradient-to-r from-transparent via-slate-200 to-transparent" />
          <span className="text-[10px] tracking-[0.2em] uppercase text-slate-400 flex items-center gap-1.5">
            <MapPin size={10} />{field.label}
          </span>
          <div className="h-px flex-1 bg-gradient-to-r from-transparent via-slate-200 to-transparent" />
        </div>
      ) : (
        <p className="text-[10px] tracking-[0.2em] uppercase text-slate-400 flex items-center gap-1.5">
          <MapPin size={10} />{field.label}
        </p>
      )}

      {/* Line 1 */}
      {cfg.line1.enabled && (
        <div className="flex flex-col gap-2">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em]">
            Street Address{cfg.line1.required && <span className="text-red-400 ml-0.5"> *</span>}
          </label>
          <input
            className={pillInput(false, compact)}
            value={value.line1 || ""}
            onChange={e => set("line1", e.target.value)}
            placeholder="e.g. 123 Main Street"
            required={cfg.line1.required}
            data-testid={`addr-line1-${field.key}`}
          />
        </div>
      )}

      {/* Line 2 */}
      {cfg.line2.enabled && (
        <div className="flex flex-col gap-2">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em]">
            Address Line 2{cfg.line2.required && <span className="text-red-400 ml-0.5"> *</span>}
          </label>
          <input
            className={pillInput(false, compact)}
            value={value.line2 || ""}
            onChange={e => set("line2", e.target.value)}
            placeholder="e.g. Suite 400, Apt 2B"
            data-testid={`addr-line2-${field.key}`}
          />
        </div>
      )}

      {/* City */}
      {cfg.city.enabled && (
        <div className="flex flex-col gap-2">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em]">
            City{cfg.city.required && <span className="text-red-400 ml-0.5"> *</span>}
          </label>
          <input
            className={pillInput(false, compact)}
            value={value.city || ""}
            onChange={e => set("city", e.target.value.replace(/[0-9]/g, ""))}
            placeholder="e.g. Toronto"
            required={cfg.city.required}
            data-testid={`addr-city-${field.key}`}
          />
        </div>
      )}

      {/* Country — before State/Province */}
      {cfg.country.enabled && (
        <div className="flex flex-col gap-2">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em]">
            Country{cfg.country.required && <span className="text-red-400 ml-0.5"> *</span>}
          </label>
          {countries.length > 0 ? (
            <Select value={value.country || ""} onValueChange={v => set("country", v)}>
              <SelectTrigger className={pillSelect(compact)} data-testid={`addr-country-${field.key}`}>
                <SelectValue placeholder="Select country…" />
              </SelectTrigger>
              <SelectContent className="rounded-2xl border-slate-200 shadow-xl">
                {countries.map(c => <SelectItem key={c.value} value={c.value} className="rounded-xl">{c.label}</SelectItem>)}
              </SelectContent>
            </Select>
          ) : (
            <input
              className={pillInput(false, compact)}
              value={value.country || ""}
              onChange={e => set("country", e.target.value)}
              placeholder="e.g. Canada"
              data-testid={`addr-country-input-${field.key}`}
            />
          )}
        </div>
      )}

      {/* State / Province — after Country */}
      {cfg.state.enabled && (
        <div className="flex flex-col gap-2">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em]">
            State / Province{cfg.state.required && <span className="text-red-400 ml-0.5"> *</span>}
          </label>
          {provinces.length > 0 ? (
            <Select value={value.region || ""} onValueChange={v => set("region", v)}>
              <SelectTrigger className={pillSelect(compact)} data-testid={`addr-region-${field.key}`}>
                <SelectValue placeholder="Select state / province…" />
              </SelectTrigger>
              <SelectContent className="rounded-2xl border-slate-200 shadow-xl">
                {provinces.map(p => <SelectItem key={p.value} value={p.value} className="rounded-xl">{p.label}</SelectItem>)}
              </SelectContent>
            </Select>
          ) : (
            <input
              className={pillInput(false, compact)}
              value={value.region || ""}
              onChange={e => set("region", e.target.value)}
              placeholder="e.g. Ontario"
              required={cfg.state.required}
              data-testid={`addr-region-input-${field.key}`}
            />
          )}
        </div>
      )}

      {/* Postal / ZIP */}
      {cfg.postal.enabled && (
        <div className="flex flex-col gap-2">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.1em]">
            Postal / ZIP Code{cfg.postal.required && <span className="text-red-400 ml-0.5"> *</span>}
          </label>
          <input
            className={pillInput(false, compact)}
            value={value.postal || ""}
            onChange={e => set("postal", e.target.value)}
            placeholder="e.g. M5V 3A8"
            required={cfg.postal.required}
            data-testid={`addr-postal-${field.key}`}
          />
        </div>
      )}
    </div>
  );
}
