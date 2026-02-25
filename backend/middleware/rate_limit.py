"""Rate limiting middleware — in-memory, per-IP.

NOTE: For multi-pod / high-traffic deployments, replace with Redis-backed
rate limiting (e.g. slowapi + Redis, or API gateway-level rate limits).
Current implementation is per-process; each pod enforces independently.
"""
from __future__ import annotations

import json
from collections import defaultdict
from time import time
from typing import Dict, List, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# (max_requests, window_seconds)  — applied by path prefix (longest match wins)
RATE_LIMITS: Dict[str, Tuple[int, int]] = {
    "/api/auth/login":                         (10, 60),    # 10 per minute per IP
    "/api/auth/partner-login":                 (10, 60),    # 10 per minute per IP
    "/api/auth/customer-login":                (10, 60),    # 10 per minute per IP
    "/api/auth/register-partner":              (20, 60),    # 20 per minute (self-service partner reg)
    "/api/auth/register":                      (5, 60),     # 5 per minute (customer reg)
    "/api/auth/forgot-password":               (20, 300),   # 20 per 5 min
    "/api/auth/resend-verification-email":     (3, 300),    # 3 per 5 min
    "/api/auth/reset-password":                (5, 300),
    "/api/checkout/session":                   (15, 60),    # 15 per minute
    "/api/checkout/bank-transfer":             (15, 60),
    "/api/orders/scope-request":               (20, 60),    # 20 per minute
    "/api/admin/api-keys":                     (10, 60),    # 10 per minute
    "/api/admin/import":                       (5, 60),     # 5 per minute
    "/api/admin/export":                       (20, 60),    # 20 per minute
}

# Global public read endpoints — generous limits for high-volume access
PUBLIC_RATE_LIMIT: Tuple[int, int] = (120, 60)  # 120 per minute per IP


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding-window rate limiter, keyed by (client_ip, path_prefix)."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._store: Dict[str, List[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        # Honour X-Forwarded-For from trusted proxies (Kubernetes ingress)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _check(self, key: str, max_req: int, window: int) -> bool:
        """Returns True if the request is ALLOWED; False if rate-limited."""
        now = time()
        bucket = self._store[key]
        # Evict expired entries
        self._store[key] = [t for t in bucket if now - t < window]
        if len(self._store[key]) >= max_req:
            return False
        self._store[key].append(now)
        return True

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only rate-limit API paths
        path = request.url.path
        if not path.startswith("/api"):
            return await call_next(request)

        ip = self._get_client_ip(request)

        # Find the most-specific (longest) matching prefix
        matched_prefix = None
        for prefix in RATE_LIMITS:
            if path.startswith(prefix):
                if matched_prefix is None or len(prefix) > len(matched_prefix):
                    matched_prefix = prefix

        if matched_prefix:
            max_req, window = RATE_LIMITS[matched_prefix]
            key = f"{ip}:{matched_prefix}"
        else:
            # Apply generous default limit to all other /api routes
            max_req, window = PUBLIC_RATE_LIMIT
            key = f"{ip}:public"

        if not self._check(key, max_req, window):
            return Response(
                content=json.dumps({"detail": "Rate limit exceeded. Please slow down and try again."}),
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(window)},
            )

        return await call_next(request)
