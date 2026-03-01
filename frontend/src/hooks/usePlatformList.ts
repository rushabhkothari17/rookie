import { useState, useEffect } from "react";
import api from "@/lib/api";

type ListCache = { values: string[]; fetching: Promise<string[]> | null };
const _caches: Record<string, ListCache> = {};

function getCache(slug: string): ListCache {
  if (!_caches[slug]) _caches[slug] = { values: [], fetching: null };
  return _caches[slug];
}

export function usePlatformList(slug: string, fallback: string[] = []) {
  const cache = getCache(slug);
  const [values, setValues] = useState<string[]>(cache.values.length ? cache.values : fallback);
  const [loading, setLoading] = useState(!cache.values.length);

  useEffect(() => {
    if (cache.values.length) { setValues(cache.values); setLoading(false); return; }
    if (!cache.fetching) {
      cache.fetching = api.get(`/platform/${slug}`)
        .then(r => { cache.values = r.data.values || fallback; return cache.values; })
        .catch(() => { cache.values = fallback; return fallback; })
        .finally(() => { cache.fetching = null; });
    }
    cache.fetching.then(list => { setValues(list); setLoading(false); });
  }, [slug]); // eslint-disable-line

  return { values, loading };
}

export function invalidatePlatformListCache(slug: string) {
  if (_caches[slug]) _caches[slug].values = [];
}
