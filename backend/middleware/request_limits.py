"""
Request size and pagination guard middleware.

RequestBodySizeLimitMiddleware:
    Rejects JSON/form bodies larger than MAX_BODY_BYTES (default 10 MB) before
    the route handler reads them, preventing memory exhaustion attacks.
    File-upload routes have their own per-route size checks so they are excluded.

PaginationCapMiddleware:
    Silently caps `limit` and `per_page` query params to MAX_PAGE_SIZE (500).
    Prevents authenticated users from requesting unbounded DB dumps in one call.
"""
from __future__ import annotations

import json
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# 10 MB — reasonable ceiling for any JSON body; file uploads are excluded
MAX_BODY_BYTES = 10 * 1024 * 1024

# Hard cap on per-page / limit query parameters
MAX_PAGE_SIZE = 500

# Routes that accept large binary uploads — excluded from body-size check
_UPLOAD_PREFIXES = (
    "/api/admin/upload-logo",
    "/api/admin/upload-favicon",
    "/api/admin/import",
    "/api/admin/upload",
    "/api/uploads/",
    "/api/documents/",
)


class RequestBodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject bodies larger than MAX_BODY_BYTES for non-upload routes."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Skip file-upload routes — they enforce their own limits
        if any(path.startswith(p) for p in _UPLOAD_PREFIXES):
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_BODY_BYTES:
                    return Response(
                        content=json.dumps({"detail": "Request body too large (max 10 MB)"}),
                        status_code=413,
                        media_type="application/json",
                    )
            except ValueError:
                pass  # malformed header — let FastAPI handle it

        return await call_next(request)


class PaginationCapMiddleware(BaseHTTPMiddleware):
    """Cap `limit` and `per_page` query params to MAX_PAGE_SIZE."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        params = dict(request.query_params)
        modified = False

        for key in ("limit", "per_page", "page_size"):
            if key in params:
                try:
                    val = int(params[key])
                    if val > MAX_PAGE_SIZE:
                        params[key] = str(MAX_PAGE_SIZE)
                        modified = True
                    elif val < 1:
                        params[key] = "1"
                        modified = True
                except ValueError:
                    pass

        if modified:
            from urllib.parse import urlencode
            new_qs = urlencode(params).encode("utf-8")
            # Mutate the ASGI scope so FastAPI reads the capped values
            request.scope["query_string"] = new_qs

        return await call_next(request)
