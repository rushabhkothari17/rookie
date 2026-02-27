import { useEffect, useState } from "react";
import api from "@/lib/api";

export type CountryOption = { value: string; label: string };

const _fallback: CountryOption[] = [
  { value: "Canada", label: "Canada" },
  { value: "USA", label: "United States" },
];

/** Fetches countries from the taxes module (/api/utils/countries).
 *  Optionally scope to a partner via partnerCode. Falls back to CA+US if API fails. */
export function useCountries(partnerCode?: string): CountryOption[] {
  const [countries, setCountries] = useState<CountryOption[]>([]);
  useEffect(() => {
    const url = partnerCode
      ? `/utils/countries?partner_code=${encodeURIComponent(partnerCode)}`
      : "/utils/countries";
    api.get(url)
      .then(r => setCountries(r.data.countries || _fallback))
      .catch(() => setCountries(_fallback));
  }, [partnerCode]);
  return countries;
}

/** Fetches provinces / states for the given country from /api/utils/provinces.
 *  Returns an empty array for countries without configured sub-regions. */
export function useProvinces(country: string): CountryOption[] {
  const [provinces, setProvinces] = useState<CountryOption[]>([]);
  useEffect(() => {
    if (!country) { setProvinces([]); return; }
    api.get(`/utils/provinces?country_code=${encodeURIComponent(country)}`)
      .then(r => setProvinces(r.data.regions || []))
      .catch(() => setProvinces([]));
  }, [country]);
  return provinces;
}
