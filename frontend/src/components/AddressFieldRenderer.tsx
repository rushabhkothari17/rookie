import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { type FormField, getAddressConfig } from "@/components/FormSchemaBuilder";

export type AddressValue = {
  line1?: string;
  line2?: string;
  city?: string;
  state?: string;
  postal?: string;
  country?: string;
};

interface Props {
  field: FormField;
  value: AddressValue;
  onChange: (v: AddressValue) => void;
  /** Optional partner code — when provided, scopes country list to partner's tax tables */
  partnerCode?: string;
  className?: string;
}

type Option = { value: string; label: string };

export function AddressFieldRenderer({ field, value, onChange, partnerCode, className }: Props) {
  const cfg = getAddressConfig(field);
  const [countries, setCountries] = useState<Option[]>([]);
  const [provinces, setProvinces] = useState<Option[]>([]);

  // Fetch countries from taxes module on mount
  useEffect(() => {
    const url = partnerCode
      ? `/utils/countries?partner_code=${encodeURIComponent(partnerCode)}`
      : "/utils/countries";
    api.get(url)
      .then(r => setCountries(r.data.countries || []))
      .catch(() => setCountries([{ value: "Canada", label: "Canada" }, { value: "USA", label: "United States" }]));
  }, [partnerCode]);

  // Fetch provinces when country changes
  useEffect(() => {
    const country = value.country || "";
    if (!country) { setProvinces([]); return; }
    api.get(`/utils/provinces?country_code=${encodeURIComponent(country)}`)
      .then(r => {
        const regs = r.data.regions || [];
        setProvinces(regs);
        // Clear state if not in the new list
        if (regs.length && value.state && !regs.find((p: Option) => p.value === value.state || p.label === value.state)) {
          onChange({ ...value, state: "" });
        }
      })
      .catch(() => setProvinces([]));
  }, [value.country]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (key: keyof AddressValue, v: string) => onChange({ ...value, [key]: v });

  return (
    <div className={`space-y-2 ${className ?? ""}`} data-testid={`address-field-${field.key}`}>
      {/* Line 1 */}
      {cfg.line1.enabled && (
        <div>
          <label className="text-[11px] text-slate-500 font-medium block mb-0.5">
            Line 1 {cfg.line1.required && <span className="text-red-500">*</span>}
          </label>
          <Input
            value={value.line1 || ""}
            onChange={e => set("line1", e.target.value)}
            placeholder={field.placeholder || "Street address"}
            required={cfg.line1.required}
            data-testid={`addr-line1-${field.key}`}
          />
        </div>
      )}

      {/* Line 2 */}
      {cfg.line2.enabled && (
        <div>
          <label className="text-[11px] text-slate-500 font-medium block mb-0.5">
            Line 2 {cfg.line2.required && <span className="text-red-500">*</span>}
          </label>
          <Input
            value={value.line2 || ""}
            onChange={e => set("line2", e.target.value)}
            placeholder="Apartment, suite, unit…"
            data-testid={`addr-line2-${field.key}`}
          />
        </div>
      )}

      {/* City + Postal in 2 col */}
      {(cfg.city.enabled || cfg.postal.enabled) && (
        <div className="grid grid-cols-2 gap-2">
          {cfg.city.enabled && (
            <div>
              <label className="text-[11px] text-slate-500 font-medium block mb-0.5">
                City {cfg.city.required && <span className="text-red-500">*</span>}
              </label>
              <Input
                value={value.city || ""}
                onChange={e => set("city", e.target.value)}
                placeholder="City"
                required={cfg.city.required}
                data-testid={`addr-city-${field.key}`}
              />
            </div>
          )}
          {cfg.postal.enabled && (
            <div>
              <label className="text-[11px] text-slate-500 font-medium block mb-0.5">
                Postal / ZIP {cfg.postal.required && <span className="text-red-500">*</span>}
              </label>
              <Input
                value={value.postal || ""}
                onChange={e => set("postal", e.target.value)}
                placeholder="Postal code"
                required={cfg.postal.required}
                data-testid={`addr-postal-${field.key}`}
              />
            </div>
          )}
        </div>
      )}

      {/* Country */}
      {cfg.country.enabled && (
        <div>
          <label className="text-[11px] text-slate-500 font-medium block mb-0.5">
            Country {cfg.country.required && <span className="text-red-500">*</span>}
          </label>
          {countries.length > 0 ? (
            <Select value={value.country || ""} onValueChange={v => set("country", v)}>
              <SelectTrigger data-testid={`addr-country-${field.key}`}>
                <SelectValue placeholder="Select country…" />
              </SelectTrigger>
              <SelectContent>
                {countries.map(c => (
                  <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Input
              value={value.country || ""}
              onChange={e => set("country", e.target.value)}
              placeholder="Country"
              data-testid={`addr-country-${field.key}`}
            />
          )}
        </div>
      )}

      {/* State / Province */}
      {cfg.state.enabled && (
        <div>
          <label className="text-[11px] text-slate-500 font-medium block mb-0.5">
            State / Province {cfg.state.required && <span className="text-red-500">*</span>}
          </label>
          {provinces.length > 0 ? (
            <Select value={value.state || ""} onValueChange={v => set("state", v)}>
              <SelectTrigger data-testid={`addr-state-${field.key}`}>
                <SelectValue placeholder="Select province / state…" />
              </SelectTrigger>
              <SelectContent>
                {provinces.map(p => (
                  <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Input
              value={value.state || ""}
              onChange={e => set("state", e.target.value)}
              placeholder="State / Province"
              required={cfg.state.required}
              data-testid={`addr-state-${field.key}`}
            />
          )}
        </div>
      )}
    </div>
  );
}
