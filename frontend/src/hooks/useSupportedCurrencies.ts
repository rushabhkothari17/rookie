import { useState, useEffect } from "react";
import api from "@/lib/api";

let _cache: string[] | null = null;
let _fetching: Promise<string[]> | null = null;

export function useSupportedCurrencies() {
  const [currencies, setCurrencies] = useState<string[]>(_cache || []);
  const [loading, setLoading] = useState(!_cache);

  useEffect(() => {
    if (_cache) { setCurrencies(_cache); setLoading(false); return; }
    if (!_fetching) {
      _fetching = api.get("/platform/supported-currencies")
        .then(r => { _cache = r.data.currencies || []; return _cache!; })
        .catch(() => { _cache = ["AUD","CAD","EUR","GBP","INR","MXN","USD"]; return _cache!; })
        .finally(() => { _fetching = null; });
    }
    _fetching.then(list => { setCurrencies(list); setLoading(false); });
  }, []);

  return { currencies, loading };
}

/** Invalidate cache so next useSupportedCurrencies call re-fetches. */
export function invalidateCurrencyCache() {
  _cache = null;
}
