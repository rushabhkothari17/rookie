import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MapPin } from "lucide-react";
import api from "@/lib/api";
import { type FormField, getAddressConfig } from "@/components/FormSchemaBuilder";

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

  const lbl = (text: string, required: boolean) => (
    <label className={`block mb-0.5 ${compact ? "text-xs text-slate-600 font-medium" : "text-[11px] text-slate-500 font-medium"}`}>
      {text}{required && <span className="text-red-500 ml-0.5">*</span>}
    </label>
  );

  return (
    <div className={`space-y-2 ${className ?? ""}`} data-testid={`address-field-${field.key}`}>
      {/* Section header */}
      {!compact && (
        <div className="flex items-center gap-3 pt-1 pb-1">
          <div className="h-px flex-1 bg-slate-100" />
          <span className="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
            <MapPin size={11} />{field.label}
          </span>
          <div className="h-px flex-1 bg-slate-100" />
        </div>
      )}
      {compact && (
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{field.label}</p>
      )}

      {/* Line 1 */}
      {cfg.line1.enabled && (
        <div>
          {lbl("Line 1", cfg.line1.required)}
          <Input value={value.line1 || ""} onChange={e => set("line1", e.target.value)}
            placeholder="Street address" required={cfg.line1.required}
            data-testid={`addr-line1-${field.key}`} />
        </div>
      )}

      {/* Line 2 */}
      {cfg.line2.enabled && (
        <div>
          {lbl("Line 2", cfg.line2.required)}
          <Input value={value.line2 || ""} onChange={e => set("line2", e.target.value)}
            placeholder="Apartment, suite, unit…"
            data-testid={`addr-line2-${field.key}`} />
        </div>
      )}

      {/* City */}
      {cfg.city.enabled && (
        <div>
          {lbl("City", cfg.city.required)}
          <Input value={value.city || ""} onChange={e => set("city", e.target.value)}
            placeholder="City" required={cfg.city.required}
            data-testid={`addr-city-${field.key}`} />
        </div>
      )}

      {/* Country — must come before State/Province so province dropdown loads correctly */}
      {cfg.country.enabled && (
        <div>
          {lbl("Country", cfg.country.required)}
          {countries.length > 0 ? (
            <Select value={value.country || ""} onValueChange={v => set("country", v)}>
              <SelectTrigger data-testid={`addr-country-${field.key}`}>
                <SelectValue placeholder="Select country…" />
              </SelectTrigger>
              <SelectContent>
                {countries.map(c => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
              </SelectContent>
            </Select>
          ) : (
            <Input value={value.country || ""} onChange={e => set("country", e.target.value)}
              placeholder="Country" data-testid={`addr-country-input-${field.key}`} />
          )}
        </div>
      )}

      {/* State / Province — after Country so dropdown can be populated */}
      {cfg.state.enabled && (
        <div>
          {lbl("State / Province", cfg.state.required)}
          {provinces.length > 0 ? (
            <Select value={value.region || ""} onValueChange={v => set("region", v)}>
              <SelectTrigger data-testid={`addr-region-${field.key}`}>
                <SelectValue placeholder="Select province / state…" />
              </SelectTrigger>
              <SelectContent>
                {provinces.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
              </SelectContent>
            </Select>
          ) : (
            <Input value={value.region || ""} onChange={e => set("region", e.target.value)}
              placeholder="State / Province" required={cfg.state.required}
              data-testid={`addr-region-input-${field.key}`} />
          )}
        </div>
      )}

      {/* Postal / ZIP */}
      {cfg.postal.enabled && (
        <div>
          {lbl("Postal / ZIP", cfg.postal.required)}
          <Input value={value.postal || ""} onChange={e => set("postal", e.target.value)}
            placeholder="Postal code" required={cfg.postal.required}
            data-testid={`addr-postal-${field.key}`} />
        </div>
      )}
    </div>
  );
}
