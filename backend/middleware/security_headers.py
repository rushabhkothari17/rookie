"""Security headers middleware — sets OWASP-recommended HTTP security headers."""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Reflected XSS filter (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Limit referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permissions policy — disable unused features
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # Remove server fingerprint
        response.headers.pop("server", None)
        response.headers.pop("Server", None)
        return response
