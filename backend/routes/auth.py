"""Authentication routes: register, verify-email, login, /me.
Supports multi-tenant login via partner_code.
HttpOnly cookie support for enhanced security.
JWT refresh token support for seamless session management.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Header, Response, Request

from core.helpers import make_id, now_iso
from core.security import (
    pwd_context, create_access_token, create_refresh_token, 
    get_current_user, decode_token, ACCESS_TOKEN_EXPIRE_MINUTES
)
from core.tenant import resolve_tenant, DEFAULT_TENANT_ID, PLATFORM_ROLE
from db.session import db
from models import (
    RegisterRequest, LoginRequest, PartnerLoginRequest, CustomerLoginRequest,
    VerifyEmailRequest, UpdateProfileRequest, ResendVerificationRequest,
)
from pydantic import BaseModel
from services.audit_service import AuditService, create_audit_log
import os

router = APIRouter(prefix="/api", tags=["auth"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_FAILED_ATTEMPTS = 10
LOCKOUT_MINUTES = 15
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax")
TOKEN_EXPIRY_HOURS = 1  # Access token expiry (1 hour)


# ---------------------------------------------------------------------------
# Password complexity helper
# ---------------------------------------------------------------------------
def _validate_password_complexity(password: str) -> Optional[str]:
    """Return an error message if the password is too weak, else None."""
    if len(password) < 10:
        return "Password must be at least 10 characters long"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number"
    if not re.search(r"[^A-Za-z0-9]", password):
        return "Password must contain at least one special character"
    return None


# ---------------------------------------------------------------------------
# Brute-force lockout helpers
# ---------------------------------------------------------------------------
async def _check_and_record_failed_login(user_id: str) -> None:
    """Increment failed attempts. Raise 429 if account should be locked."""
    now = datetime.now(timezone.utc)
    lockout_until = now + timedelta(minutes=LOCKOUT_MINUTES)
    await db.users.update_one(
        {"id": user_id},
        {
            "$inc": {"failed_login_attempts": 1},
            "$set": {"last_failed_login": now.isoformat()},
        },
    )
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "failed_login_attempts": 1})
    attempts = user.get("failed_login_attempts", 0) if user else 0
    if attempts >= MAX_FAILED_ATTEMPTS:
        await db.users.update_one(
            {"id": user_id}, {"$set": {"lockout_until": lockout_until.isoformat()}}
        )


async def _check_lockout(user: Dict[str, Any]) -> None:
    """Raise 429 if the user is currently locked out."""
    lockout_until = user.get("lockout_until")
    if not lockout_until:
        return
    try:
        lockout_dt = datetime.fromisoformat(lockout_until)
        if lockout_dt.tzinfo is None:
            lockout_dt = lockout_dt.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) < lockout_dt:
            raise HTTPException(
                status_code=429,
                detail=f"Account temporarily locked due to too many failed login attempts. Try again after {lockout_until[:16].replace('T', ' ')} UTC, or ask an admin to unlock your account.",
            )
    except HTTPException:
        raise
    except Exception:
        pass


async def _reset_failed_login(user_id: str) -> None:
    """Reset failed attempts counter after successful login."""
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"failed_login_attempts": 0, "lockout_until": None}},
    )


def _set_auth_cookie(response: Response, token: str, refresh_token: Optional[str] = None):
    """Set HttpOnly authentication cookies for access and refresh tokens."""
    # Access token cookie (short-lived)
    response.set_cookie(
        key="aa_access_token",
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    # Refresh token cookie (long-lived)
    if refresh_token:
        response.set_cookie(
            key="aa_refresh_token",
            value=refresh_token,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            max_age=30 * 24 * 3600,  # 30 days
            path="/api/auth"  # Only sent to auth endpoints
        )


def _clear_auth_cookie(response: Response):
    """Clear authentication cookies on logout."""
    response.delete_cookie(
        key="aa_access_token",
        path="/",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE
    )
    response.delete_cookie(
        key="aa_refresh_token",
        path="/api/auth",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE
    )


@router.get("/")
async def root():
    return {"message": "Automate Accounts API"}


# ---------------------------------------------------------------------------
# Helper: verify user credentials and build JWT
# ---------------------------------------------------------------------------

async def _authenticate(email: str, password: str, tenant_id: Optional[str], expected_roles: list):
    """Verify credentials and return a JWT token. Raises HTTPException on failure."""
    # First try exact tenant match
    query: Dict[str, Any] = {"email": email.lower()}
    if tenant_id:
        query["tenant_id"] = tenant_id

    user = await db.users.find_one(query, {"_id": 0})
    # For platform_admin, also try null tenant_id
    if not user and tenant_id:
        user = await db.users.find_one({"email": email.lower(), "tenant_id": None}, {"_id": 0})
        # Only accept if they are platform admin
        if user and user.get("role") != PLATFORM_ROLE:
            user = None
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Lockout check (before password verification to give consistent timing)
    await _check_lockout(user)

    if not pwd_context.verify(password, user.get("password_hash", "")):
        await _check_and_record_failed_login(user["id"])
        await AuditService.log(
            action="LOGIN_FAILED",
            description=f"Failed login attempt for: {user['email']}",
            entity_type="User",
            entity_id=user["id"],
            actor_type="unknown",
            actor_email=user["email"],
            source="api",
            meta_json={"tenant_id": user.get("tenant_id")},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_verified"):
        raise HTTPException(status_code=403, detail="Email verification required")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact your administrator.")

    role = user.get("role", "customer")
    if expected_roles and role not in expected_roles:
        raise HTTPException(status_code=403, detail="Access denied for this login type")

    # Successful login — reset lockout counter
    await _reset_failed_login(user["id"])

    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "tenant_id": user.get("tenant_id"),
        "is_admin": user.get("is_admin", False),
        "token_version": user.get("token_version", 0),
    })
    refresh_token = create_refresh_token(user["id"])
    await AuditService.log(
        action="USER_LOGIN",
        description=f"User login: {user['email']}",
        entity_type="User",
        entity_id=user["id"],
        actor_type="admin" if user.get("is_admin") else "user",
        actor_email=user["email"],
        source="api",
        meta_json={"role": role, "tenant_id": user.get("tenant_id")},
    )
    return {"token": token, "refresh_token": refresh_token, "role": role, "tenant_id": user.get("tenant_id"), "must_change_password": user.get("must_change_password", False)}


# ---------------------------------------------------------------------------
# Partner Login (admin/staff users for a tenant)
# ---------------------------------------------------------------------------

@router.post("/auth/partner-login")
async def partner_login(payload: PartnerLoginRequest, response: Response):
    """Login for partner organization users (super_admin, admin, staff).
    Requires partner_code to identify the tenant.
    Sets HttpOnly cookies with JWT access and refresh tokens.
    """
    # automate-accounts is reserved for platform administration — partner login is blocked
    if payload.partner_code.strip().lower() == DEFAULT_TENANT_ID:
        raise HTTPException(
            status_code=403,
            detail="This code is reserved for platform administration. Please use the Platform Admin login portal."
        )
    tenant = await resolve_tenant(payload.partner_code)
    partner_roles = ["partner_super_admin", "partner_admin", "partner_staff",
                     "platform_admin", "super_admin", "admin"]
    result = await _authenticate(payload.email, payload.password, tenant["id"], partner_roles)
    _set_auth_cookie(response, result["token"], result.get("refresh_token"))
    # Don't expose refresh token in response body
    return {
        "token": result["token"],
        "role": result["role"],
        "tenant_id": result["tenant_id"],
        "must_change_password": result.get("must_change_password", False),
    }


# ---------------------------------------------------------------------------
# Customer Login (customers scoped to a tenant)
# ---------------------------------------------------------------------------

@router.post("/auth/customer-login")
async def customer_login(payload: CustomerLoginRequest, response: Response):
    """Login for customers belonging to a specific partner organization.
    Requires partner_code to identify the tenant.
    Sets HttpOnly cookies with JWT access and refresh tokens.
    """
    if payload.partner_code.strip().lower() == DEFAULT_TENANT_ID:
        raise HTTPException(status_code=403, detail="This code is reserved for platform administration. Please use your organization's partner code.")
    tenant = await resolve_tenant(payload.partner_code)
    # Any non-admin user is a customer
    query: Dict[str, Any] = {"email": payload.email.lower(), "tenant_id": tenant["id"]}
    user = await db.users.find_one(query, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Lockout check
    await _check_lockout(user)

    # Admin accounts must use partner login — check before password to surface clear guidance
    if user.get("is_admin") or user.get("role") in ("partner_super_admin", "partner_admin", "partner_staff"):
        raise HTTPException(status_code=403, detail="Admin accounts must use /api/auth/partner-login")

    if not pwd_context.verify(payload.password, user.get("password_hash", "")):
        await _check_and_record_failed_login(user["id"])
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_verified"):
        raise HTTPException(status_code=403, detail="Email not verified")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact your administrator.")

    await _reset_failed_login(user["id"])
    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "role": user.get("role", "customer"),
        "tenant_id": tenant["id"],
        "is_admin": False,
        "token_version": user.get("token_version", 0),
    })
    refresh_token = create_refresh_token(user["id"])
    await AuditService.log(
        action="CUSTOMER_LOGIN",
        description=f"Customer login: {user['email']}",
        entity_type="User",
        entity_id=user["id"],
        actor_type="user",
        actor_email=user["email"],
        source="api",
        meta_json={"tenant_id": tenant["id"]},
    )
    _set_auth_cookie(response, token, refresh_token)
    return {"token": token, "role": "customer", "tenant_id": tenant["id"]}


# ---------------------------------------------------------------------------
# Domain-Based Login (no partner_code required for custom domains)
# ---------------------------------------------------------------------------

class DomainLoginRequest(BaseModel):
    email: str
    password: str


@router.post("/auth/domain-login")
async def domain_login(
    payload: DomainLoginRequest,
    request: Request,
    response: Response
):
    """
    Login using the request's Origin/Referer domain to identify the tenant.
    
    This allows partners with custom domains (e.g., billing.company.com) to 
    serve customers without requiring partner_code in the login form.
    """
    from core.tenant import resolve_tenant_by_domain
    
    # Get domain from Origin or Referer header
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    
    domain = None
    if origin:
        # Extract domain from origin (e.g., https://billing.company.com -> billing.company.com)
        domain = origin.replace("https://", "").replace("http://", "").split("/")[0]
    elif referer:
        domain = referer.replace("https://", "").replace("http://", "").split("/")[0]
    
    if not domain:
        raise HTTPException(status_code=400, detail="Could not determine domain. Use partner-login instead.")
    
    # Try to resolve tenant by domain
    tenant = await resolve_tenant_by_domain(domain)
    
    if not tenant:
        raise HTTPException(
            status_code=400,
            detail="This domain is not configured for any organization. Please use the main login page."
        )
    
    # Now authenticate the user for this tenant
    query: Dict[str, Any] = {"email": payload.email.lower(), "tenant_id": tenant["id"]}
    user = await db.users.find_one(query, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    await _check_lockout(user)
    
    if not pwd_context.verify(payload.password, user.get("password_hash", "")):
        await _check_and_record_failed_login(user["id"])
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_verified"):
        raise HTTPException(status_code=403, detail="Email verification required")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact your administrator.")
    
    await _reset_failed_login(user["id"])
    
    # Determine role - this endpoint works for both customers and admins on custom domains
    role = user.get("role", "customer")
    is_admin = user.get("is_admin", False)
    
    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "tenant_id": tenant["id"],
        "is_admin": is_admin,
        "token_version": user.get("token_version", 0),
    })
    refresh_token = create_refresh_token(user["id"])
    
    await AuditService.log(
        action="DOMAIN_LOGIN",
        description=f"Domain login: {user['email']} via {domain}",
        entity_type="User",
        entity_id=user["id"],
        actor_type="admin" if is_admin else "user",
        actor_email=user["email"],
        source="api",
        meta_json={"tenant_id": tenant["id"], "domain": domain},
    )
    
    _set_auth_cookie(response, token, refresh_token)
    return {
        "token": token,
        "role": role,
        "tenant_id": tenant["id"],
        "tenant_name": tenant.get("name"),
        "is_admin": is_admin
    }


@router.get("/auth/domain-info")
async def get_domain_info(request: Request):
    """
    Get tenant info for the current domain (for customizing login pages).
    Returns tenant name, branding, etc. if domain is configured.
    """
    from core.tenant import resolve_tenant_by_domain
    
    origin = request.headers.get("origin", "")
    domain = origin.replace("https://", "").replace("http://", "").split("/")[0] if origin else None
    
    if not domain:
        return {"is_custom_domain": False}
    
    tenant = await resolve_tenant_by_domain(domain)
    
    if not tenant:
        return {"is_custom_domain": False}
    
    # Get branding settings for tenant
    branding = await db.settings.find_one(
        {"tenant_id": tenant["id"], "key": "branding"},
        {"_id": 0, "value_json": 1}
    )
    
    return {
        "is_custom_domain": True,
        "tenant_name": tenant.get("name"),
        "tenant_code": tenant.get("code"),
        "branding": branding.get("value_json") if branding else None
    }


# ---------------------------------------------------------------------------
# Logout (clears HttpOnly cookie)
# ---------------------------------------------------------------------------

@router.post("/auth/logout")
async def logout(response: Response):
    """Logout by clearing the HttpOnly authentication cookie."""
    _clear_auth_cookie(response)
    return {"success": True, "message": "Logged out successfully"}


# ---------------------------------------------------------------------------
# Token Refresh (get new access token using refresh token)
# ---------------------------------------------------------------------------

@router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    """Get a new access token using the refresh token.
    Refresh token can be in HttpOnly cookie or request body.
    """
    # Get refresh token from cookie or body
    refresh_token_value = request.cookies.get("aa_refresh_token")
    if not refresh_token_value:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        refresh_token_value = body.get("refresh_token")
    
    if not refresh_token_value:
        raise HTTPException(status_code=401, detail="Refresh token required")
    
    try:
        payload = decode_token(refresh_token_value, token_type="refresh")
    except HTTPException:
        _clear_auth_cookie(response)  # Clear invalid cookies
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token. Please login again.")
    
    user_id = payload.get("sub")
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive")
    
    # Create new access token
    new_access_token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "role": user.get("role", "customer"),
        "tenant_id": user.get("tenant_id"),
        "is_admin": user.get("is_admin", False),
        "token_version": user.get("token_version", 0),
    })
    
    # Set new access token cookie
    response.set_cookie(
        key="aa_access_token",
        value=new_access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    
    return {"token": new_access_token, "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60}


# ---------------------------------------------------------------------------
# Legacy login (backward compat — platform super admin and existing sessions)
# ---------------------------------------------------------------------------

@router.post("/auth/login")
async def login(payload: LoginRequest, response: Response):
    """Legacy login endpoint. If partner_code provided, routes to tenant-scoped auth.
    Without partner_code, only platform_admin can log in.
    Sets HttpOnly cookie with JWT token.
    """
    if payload.partner_code:
        # Route to tenant-scoped login — validate partner code first, then delegate
        await resolve_tenant(payload.partner_code)
        if payload.login_type == "customer":
            cust_payload = CustomerLoginRequest(
                partner_code=payload.partner_code,
                email=payload.email,
                password=payload.password,
            )
            return await customer_login(cust_payload, response)
        else:
            partner_payload = PartnerLoginRequest(
                partner_code=payload.partner_code,
                email=payload.email,
                password=payload.password,
            )
            return await partner_login(partner_payload, response)

    # No partner_code: platform super admin only
    user = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Lockout check
    await _check_lockout(user)

    if not pwd_context.verify(payload.password, user.get("password_hash", "")):
        await _check_and_record_failed_login(user["id"])
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_verified"):
        raise HTTPException(status_code=403, detail="Email verification required")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact your administrator.")
    if user.get("role") != PLATFORM_ROLE and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Partner code required. Please use the Partner Login tab.")

    await _reset_failed_login(user["id"])
    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "role": user.get("role", "admin"),
        "tenant_id": user.get("tenant_id"),
        "is_admin": user.get("is_admin", False),
        "token_version": user.get("token_version", 0),
    })
    await AuditService.log(
        action="USER_LOGIN",
        description=f"Platform login: {user['email']}",
        entity_type="User",
        entity_id=user["id"],
        actor_type="admin",
        actor_email=user["email"],
        source="api",
        meta_json={"role": user.get("role")},
    )
    return {"token": token, "role": user.get("role"), "tenant_id": user.get("tenant_id")}


# ---------------------------------------------------------------------------
# Public: get tenant info by partner code (for login prefill)
# ---------------------------------------------------------------------------

@router.get("/tenant-info")
async def get_tenant_info(
    code: Optional[str] = None,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """Public endpoint to verify a partner code or API key and return tenant display name."""
    # Resolve from X-API-Key header when no code provided
    if not code and x_api_key:
        import hashlib
        key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
        key_doc = await db.api_keys.find_one({"key_hash": key_hash, "is_active": True}, {"_id": 0, "tenant_id": 1})
        # Note: no plaintext fallback — all keys are stored as hashes only
        if not key_doc:
            raise HTTPException(status_code=401, detail="Invalid API key")
        tid = key_doc["tenant_id"]
        if tid == DEFAULT_TENANT_ID:
            return {"tenant": {"name": "Platform Administration", "code": DEFAULT_TENANT_ID, "is_platform": True}}
        tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "id": 1, "name": 1, "code": 1, "status": 1})
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        if tenant.get("status") != "active":
            raise HTTPException(status_code=403, detail="Organization is inactive")
        return {"tenant": {"name": tenant["name"], "code": tenant["code"], "is_platform": False}}
    if not code:
        raise HTTPException(status_code=400, detail="Partner code or X-API-Key is required")
    # automate-accounts is the reserved platform admin code — not a regular tenant
    if code.strip().lower() == DEFAULT_TENANT_ID:
        return {"tenant": {"name": "Platform Administration", "code": DEFAULT_TENANT_ID, "is_platform": True}}
    tenant = await db.tenants.find_one({"code": code.lower()}, {"_id": 0, "id": 1, "name": 1, "code": 1, "status": 1})
    if not tenant:
        raise HTTPException(status_code=404, detail="Partner code not found")
    if tenant.get("status") != "active":
        raise HTTPException(status_code=403, detail="Organization is inactive")
    return {"tenant": {"name": tenant["name"], "code": tenant["code"], "is_platform": False}}


async def _seed_new_tenant(tenant_id: str, tenant_name: str, now: str, base_currency: str = "USD") -> None:
    """Provision a brand-new tenant with generic sample data (no other-tenant references)."""
    # 1. Website settings — generic, no Automate Accounts content
    await db.website_settings.insert_one({
        "tenant_id": tenant_id,
        "store_name": tenant_name,
        "hero_label": "STOREFRONT",
        "hero_title": "Our Services",
        "hero_subtitle": "Choose from our range of professional services tailored to your business needs.",
        "login_title": "Welcome back",
        "login_subtitle": "Sign in to your account to continue.",
        "login_portal_label": "Customer Portal",
        "login_btn_text": "Sign In",
        "register_title": "Create your account",
        "register_subtitle": f"Join {tenant_name} and get access to our full range of professional services.",
        "signup_label": "Get Started",
        "signup_form_title": "Create your account",
        "signup_form_subtitle": "Fill in your details to create your account and get started.",
        "signup_btn_text": "Create Account",
        "verify_email_label": "Verify Email",
        "verify_email_title": "Enter your code",
        "verify_email_subtitle": "We sent a 6-digit verification code to your email address.",
        "portal_label": "Customer Portal",
        "portal_title": "My Account",
        "portal_subtitle": "Track your orders, subscriptions, and manage your account.",
        "profile_label": "My Profile",
        "profile_title": "Account Details",
        "profile_subtitle": "Update your contact details.",
        "contact_email": "",
        "contact_phone": "",
        "contact_address": "",
        "footer_tagline": f"Professional services by {tenant_name}.",
        "footer_copyright": f"© {tenant_name}. All rights reserved.",
        "footer_about_title": "About Us",
        "footer_about_text": f"Welcome to {tenant_name}. We provide expert services to help your business grow.",
        "footer_nav_title": "Navigation",
        "footer_contact_title": "Contact",
        "footer_social_title": "Follow Us",
        "nav_store_label": "Services",
        "nav_articles_label": "Resources",
        "nav_portal_label": "My Account",
        "social_twitter": "",
        "social_linkedin": "",
        "social_facebook": "",
        "social_instagram": "",
        "social_youtube": "",
        "quote_form_title": "Request a Quote",
        "quote_form_subtitle": "Fill in your details and we'll get back to you with a custom quote.",
        "quote_form_response_time": "We'll respond within 1–2 business days.",
        "scope_form_title": "Request Scope",
        "scope_form_subtitle": "Tell us about your project and we'll get back to you with a detailed scope.",
        "email_from_name": tenant_name,
        "email_article_subject_template": "Article: {{article_title}}",
        "email_article_cta_text": "View Article",
        "email_article_footer_text": "Your consultant has shared this document with you.",
        "email_verification_subject": "Verify your email address",
        "email_verification_body": "Your verification code is: {{code}}. This code expires in 24 hours.",
        "articles_hero_label": "Resources",
        "articles_hero_title": "Articles & Guides",
        "articles_hero_subtitle": "Tips, guides, and updates from our team.",
        "checkout_partner_enabled": False,
        "checkout_extra_schema": "[]",
        "checkout_sections": "[]",
        "payment_gocardless_label": "Bank Transfer (Direct Debit)",
        "payment_gocardless_description": "No processing fee. We'll set up a direct debit from your account.",
        "payment_stripe_label": "Card Payment",
        "payment_stripe_description": "Pay securely by credit or debit card. A processing fee applies.",
        "msg_cart_empty": "Your cart is empty. Browse our services to get started.",
        "msg_terms_not_accepted": "Please read and accept the Terms & Conditions to proceed.",
        "msg_quote_success": "Thank you! Your quote request has been received.",
        "msg_scope_success": "Thank you! Your scope request has been received.",
        "msg_no_payment_methods": "No payment methods are currently available. Please contact support.",
        "created_at": now,
        "updated_at": now,
    })

    # 2. App settings (empty, tenant fills in integration keys themselves)
    await db.app_settings.insert_one({
        "tenant_id": tenant_id,
        "store_name": tenant_name,
        "primary_color": "#2563eb",
        "secondary_color": "#1e40af",
        "accent_color": "#3b82f6",
        "created_at": now,
        "updated_at": now,
    })

    # 3. Default product category
    cat_id = make_id()
    await db.categories.insert_one({
        "id": cat_id,
        "tenant_id": tenant_id,
        "name": "General Services",
        "description": "General professional services.",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    })

    # 4. Sample product
    prod_id = make_id()
    await db.products.insert_one({
        "id": prod_id,
        "tenant_id": tenant_id,
        "name": "Sample Service",
        "tagline": "Professional service tailored to your business — update this tagline.",
        "description": "This is a sample service. Edit or replace it from the Admin > Catalog panel.",
        "description_long": "<p>This is the full description for your sample service. Update this text to explain what your service includes, who it's for, and why clients should choose you.</p><p>You can include multiple paragraphs, key benefits, and any other details that help potential customers make a decision.</p>",
        "card_description": "A professional service designed to help your business grow. Click to learn more.",
        "bullets": "Expert team with years of experience\nFast turnaround and clear communication\nTailored to your specific needs\nOngoing support included",
        "faqs": '[{"question": "How do I get started?", "answer": "Simply click the button above to place an order or request a quote, and our team will be in touch within 1–2 business days."}, {"question": "What is included in this service?", "answer": "Full details are described above. If you have any questions, please contact us directly."}, {"question": "Can I customise this service?", "answer": "Absolutely. We tailor every engagement to the client\'s specific requirements."}]',
        "category": "General Services",
        "is_active": True,
        "currency": base_currency,
        "pricing_type": "fixed",
        "base_price": 99.00,
        "billing_period": "one_time",
        "created_at": now,
        "updated_at": now,
    })

    # 5. Sample article
    article_id = make_id()
    await db.articles.insert_one({
        "id": article_id,
        "tenant_id": tenant_id,
        "title": "Welcome to Your Knowledge Base",
        "slug": "welcome-to-your-knowledge-base",
        "category": "Blog",
        "content": "<h2>Welcome!</h2><p>This is a sample article. You can edit or delete it from the Admin &gt; Articles panel. Use articles to share guides, SOPs, and updates with your customers.</p>",
        "visibility": "all",
        "status": "published",
        "created_at": now,
        "updated_at": now,
    })

    # 6. Default Terms & Conditions
    terms_id = make_id()
    await db.terms_and_conditions.insert_one({
        "id": terms_id,
        "tenant_id": tenant_id,
        "title": "Terms & Conditions",
        "content": f"<h2>Terms & Conditions</h2><p>These are the default Terms & Conditions for {tenant_name}. Please update this document from Admin &gt; Terms &amp; Conditions before going live.</p><h3>1. Acceptance of Terms</h3><p>By accessing or using our services, you agree to be bound by these Terms & Conditions.</p><h3>2. Services</h3><p>We reserve the right to modify or discontinue any service at any time.</p><h3>3. Payment</h3><p>Payment is due in accordance with the pricing schedule agreed at time of purchase.</p><h3>4. Governing Law</h3><p>These terms shall be governed by the applicable laws of your jurisdiction.</p>",
        "is_default": True,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })

    # 7. Seed all default email templates (includes order_placed, subscription_created, etc.)
    from services.email_service import EmailService
    await EmailService.ensure_seeded(db, tenant_id)

    # 8. Default intake form with T&C
    intake_schema = [
        {
            "id": "if_full_name", "key": "full_name", "label": "Full Name",
            "type": "text", "required": True, "placeholder": "e.g. Jane Smith",
            "options": [], "locked": True, "enabled": True, "order": 0,
        },
        {
            "id": "if_company", "key": "company_name", "label": "Company / Organisation",
            "type": "text", "required": False, "placeholder": "e.g. Acme Corp",
            "options": [], "locked": True, "enabled": True, "order": 1,
        },
        {
            "id": "if_heard", "key": "how_did_you_hear", "label": "How did you hear about us?",
            "type": "select", "required": False, "placeholder": "",
            "options": ["Google / Search", "Social Media", "Referral", "Other"],
            "locked": False, "enabled": True, "order": 2,
        },
        {
            "id": "if_tc", "key": "terms_conditions", "label": "Terms & Conditions",
            "type": "terms_conditions",
            "terms_text": f"By signing below, you confirm that you have read and agree to {tenant_name}'s terms of service and privacy policy. You acknowledge that all information provided is accurate and complete.",
            "required": True, "placeholder": "",
            "options": [], "locked": False, "enabled": True, "order": 3,
        },
        {
            "id": "if_sig", "key": "signature", "label": "Signature",
            "type": "signature", "required": True, "placeholder": "",
            "options": [], "locked": True, "enabled": True, "order": 4,
        },
    ]
    import json as _json
    await db.intake_forms.insert_one({
        "id": make_id(),
        "tenant_id": tenant_id,
        "name": "Client Intake Questionnaire",
        "description": "Complete this form before your first purchase. This helps us understand your needs.",
        "schema": _json.dumps(intake_schema),
        "is_enabled": True,
        "auto_approve": False,
        "allow_skip_signature": False,
        "visibility_rules": [],
        "customer_ids": [],
        "created_by": "system",
        "created_at": now,
        "updated_at": now,
    })


@router.post("/auth/register-partner")
async def register_partner(payload: Dict[str, Any] = Body(...)):
    """Self-service partner organization registration with OTP email verification.
    Stores data in pending_partner_registrations collection ONLY.
    Nothing is written to users or tenants until /auth/verify-partner-email succeeds.
    """
    import re as _re

    name = payload.get("name", "").strip()
    admin_name = payload.get("admin_name", "").strip()
    admin_email = payload.get("admin_email", "").strip().lower()
    admin_password = payload.get("admin_password", "")
    base_currency = payload.get("base_currency", "USD").strip().upper() or "USD"
    address = payload.get("address", {})
    extra_fields = payload.get("extra_fields", {})
    if not isinstance(extra_fields, dict):
        extra_fields = {}

    # ── Field presence ───────────────────────────────────────────────────────
    if not all([name, admin_name, admin_email, admin_password]):
        raise HTTPException(status_code=400, detail="All fields are required")

    # ── Character limits ─────────────────────────────────────────────────────
    if len(name) > 100:
        raise HTTPException(status_code=400, detail="Organization name must be 100 characters or fewer")
    if len(admin_name) > 50:
        raise HTTPException(status_code=400, detail="Admin name must be 50 characters or fewer")
    if len(admin_email) > 50:
        raise HTTPException(status_code=400, detail="Admin email must be 50 characters or fewer")

    # ── Email format ─────────────────────────────────────────────────────────
    if not _re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$', admin_email):
        raise HTTPException(status_code=400, detail="Invalid email address format")

    # ── Password complexity ──────────────────────────────────────────────────
    pw_error = _validate_password_complexity(admin_password)
    if pw_error:
        raise HTTPException(status_code=400, detail=pw_error)

    # ── Address (optional, but if partially filled must be complete) ──────────
    if any(str(address.get(f, "")).strip() for f in ["line1", "city", "postal", "country", "region"]):
        mandatory_addr = ["line1", "city", "postal", "country", "region"]
        missing = [f for f in mandatory_addr if not str(address.get(f, "")).strip()]
        if missing:
            raise HTTPException(status_code=400, detail=f"Address fields required: {', '.join(missing)}")

    # ── Currency ─────────────────────────────────────────────────────────────
    supported = await db.platform_settings.find_one({"_id_key": "supported_currencies"})
    valid_currencies = supported.get("values", ["USD","CAD","EUR","AUD","GBP","INR","MXN"]) if supported else ["USD","CAD","EUR","AUD","GBP","INR","MXN"]
    if base_currency not in valid_currencies:
        base_currency = "USD"

    # ── Email uniqueness: block if already a verified user ───────────────────
    verified_user = await db.users.find_one({"email": admin_email, "is_verified": True}, {"_id": 0, "id": 1})
    if verified_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # ── Handle pending re-registration (update existing pending record) ───────
    pending_clean = {
        "admin_name": admin_name,
        "password_hash": pwd_context.hash(admin_password),
        "name": name,
        "base_currency": base_currency,
        "address": {k: str(address.get(k, "")).strip() for k in ["line1","line2","city","region","postal","country"]},
        "extra_fields": extra_fields,
    }
    existing_pending = await db.pending_partner_registrations.find_one({"email": admin_email}, {"_id": 0, "id": 1})
    if existing_pending:
        verification_code = f"{secrets.randbelow(999999):06d}"
        await db.pending_partner_registrations.update_one(
            {"email": admin_email},
            {"$set": {**pending_clean, "verification_code": verification_code,
                      "verification_attempts": 0, "locked_until": None}},
        )
    else:
        verification_code = f"{secrets.randbelow(999999):06d}"
        await db.pending_partner_registrations.insert_one({
            "id": make_id(),
            "email": admin_email,
            **pending_clean,
            "verification_code": verification_code,
            "verification_attempts": 0,
            "locked_until": None,
            "created_at": now_iso(),
        })

    # ── Send OTP email ────────────────────────────────────────────────────────
    from services.email_service import EmailService
    email_result = await EmailService.send(
        trigger="partner_verification",
        recipient=admin_email,
        variables={
            "admin_name": admin_name,
            "customer_name": admin_name,       # legacy alias in case template uses it
            "partner_org_name": payload.get("name", ""),
            "customer_email": admin_email,
            "verification_code": verification_code,
        },
        db=db, tenant_id=None,
    )
    if email_result.get("status") == "mocked":
        import logging
        logging.getLogger("auth").warning("[DEV] Partner pending email mocked for %s — OTP: %s", admin_email, verification_code)

    return {"message": "Verification required"}


@router.post("/auth/verify-partner-email")
async def verify_partner_email(payload: Dict[str, Any] = Body(...)):
    """Verify partner OTP, then create tenant + user. Called after /auth/register-partner."""
    email = (payload.get("email") or "").strip().lower()
    code = (payload.get("code") or "").strip()
    if not email or not code:
        raise HTTPException(status_code=400, detail="Email and code are required")

    pending = await db.pending_partner_registrations.find_one({"email": email}, {"_id": 0})
    if not pending:
        raise HTTPException(status_code=404, detail="No pending registration found for this email")

    # Lockout check
    if pending.get("locked_until"):
        try:
            locked = datetime.fromisoformat(pending["locked_until"].replace("Z", "+00:00"))
            if datetime.now(timezone.utc) < locked:
                raise HTTPException(status_code=429, detail="Too many attempts. Please request a new code.")
        except (ValueError, TypeError):
            pass

    if pending.get("verification_code") != code:
        attempts = pending.get("verification_attempts", 0) + 1
        update: Dict[str, Any] = {"verification_attempts": attempts}
        if attempts >= 5:
            update["locked_until"] = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        await db.pending_partner_registrations.update_one({"email": email}, {"$set": update})
        raise HTTPException(status_code=400, detail="Invalid code")

    # ── Valid OTP — generate unique partner code ──────────────────────────────
    org_name = pending.get("name", "")
    base_code = re.sub(r'[^\w\s-]', '', org_name.lower().strip())
    base_code = re.sub(r'[\s_]+', '-', base_code)
    base_code = re.sub(r'-+', '-', base_code).strip('-')[:30] or "partner"
    code_candidate = base_code
    counter = 1
    while await db.tenants.find_one({"code": code_candidate}) or code_candidate == DEFAULT_TENANT_ID:
        code_candidate = f"{base_code}-{counter}"
        counter += 1

    # ── Create tenant ─────────────────────────────────────────────────────────
    tenant_id = make_id()
    now = now_iso()
    address = pending.get("address", {})
    await db.tenants.insert_one({
        "id": tenant_id,
        "name": org_name,
        "code": code_candidate,
        "status": "active",
        "base_currency": pending.get("base_currency", "USD"),
        "address": address,
        "extra_fields": pending.get("extra_fields", {}),
        "created_at": now,
        "updated_at": now,
    })

    # ── Seed tenant defaults ──────────────────────────────────────────────────
    await _seed_new_tenant(tenant_id, org_name, now, base_currency=pending.get("base_currency", "USD"))

    # ── Assign free trial plan ────────────────────────────────────────────────
    try:
        free_trial = await db.plans.find_one({"is_default": True}, {"_id": 0})
        if free_trial:
            limits = {k: v for k, v in free_trial.items() if k.startswith("max_")}
            await db.tenants.update_one({"id": tenant_id}, {"$set": {
                "license": {"plan_id": free_trial["id"], "plan_name": free_trial["name"],
                             "assigned_at": now, **limits}
            }})
            # ── Create partner subscription + order for the free plan ──────────
            sub_count = await db.partner_subscriptions.count_documents({})
            sub_number = f"PS-{datetime.now(timezone.utc).strftime('%Y')}-{(sub_count + 1):04d}"
            sub_id = make_id()
            await db.partner_subscriptions.insert_one({
                "id": sub_id,
                "subscription_number": sub_number,
                "partner_id": tenant_id,
                "partner_name": org_name,
                "plan_id": free_trial["id"],
                "plan_name": free_trial["name"],
                "description": f"Initial plan — {free_trial['name']}",
                "amount": 0.0,
                "currency": pending.get("base_currency", "USD"),
                "billing_interval": "monthly",
                "status": "active",
                "payment_method": "manual",
                "processor_id": None,
                "stripe_subscription_id": None,
                "start_date": now[:10],
                "next_billing_date": None,
                "term_months": None,
                "auto_cancel_on_termination": False,
                "contract_end_date": None,
                "reminder_days": None,
                "cancelled_at": None,
                "internal_note": "Auto-created on partner signup",
                "created_by": "system",
                "payment_url": None,
                "created_at": now,
                "updated_at": now,
            })
            ord_count = await db.partner_orders.count_documents({})
            ord_number = f"PO-{datetime.now(timezone.utc).strftime('%Y')}-{(ord_count + 1):04d}"
            ord_id = make_id()
            await db.partner_orders.insert_one({
                "id": ord_id,
                "order_number": ord_number,
                "partner_id": tenant_id,
                "partner_name": org_name,
                "plan_id": free_trial["id"],
                "plan_name": free_trial["name"],
                "description": f"Initial setup — {free_trial['name']}",
                "amount": 0.0,
                "currency": pending.get("base_currency", "USD"),
                "status": "paid",
                "payment_method": "manual",
                "processor_id": None,
                "invoice_date": now[:10],
                "due_date": None,
                "paid_at": now,
                "internal_note": "Auto-created on partner signup",
                "created_by": "system",
                "payment_url": None,
                "created_at": now,
                "updated_at": now,
            })
    except Exception:
        pass

    # ── Create partner_super_admin user ───────────────────────────────────────
    user_id = make_id()
    await db.users.insert_one({
        "id": user_id,
        "email": email,
        "password_hash": pending["password_hash"],
        "full_name": pending.get("admin_name", ""),
        "company_name": org_name,
        "job_title": "",
        "phone": "",
        "is_admin": True,
        "is_verified": True,
        "role": "partner_super_admin",
        "tenant_id": tenant_id,
        "is_active": True,
        "created_at": now,
    })

    # ── Clean up pending record ───────────────────────────────────────────────
    await db.pending_partner_registrations.delete_one({"email": email})

    await create_audit_log(entity_type="tenant", entity_id=tenant_id, action="partner_activated",
                           actor=email, details={"name": org_name, "code": code_candidate})

    return {"message": "Verified", "partner_code": code_candidate}
# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@router.post("/auth/register")
async def register(payload: RegisterRequest, partner_code: Optional[str] = None):
    import re as _re

    # Email format + length
    if not _re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$', payload.email.strip()):
        raise HTTPException(status_code=400, detail="Invalid email address format")
    if len(payload.email.strip()) > 50:
        raise HTTPException(status_code=400, detail="Email must be 50 characters or fewer")

    # Field length limits
    full_name = payload.get_full_name()
    if not full_name.strip():
        raise HTTPException(status_code=400, detail="Name is required (provide full_name or first_name/last_name)")
    if len(full_name) > 50:
        raise HTTPException(status_code=400, detail="Full name must be 50 characters or fewer")
    if len(payload.company_name or "") > 50:
        raise HTTPException(status_code=400, detail="Company name must be 50 characters or fewer")
    if len(payload.job_title or "") > 50:
        raise HTTPException(status_code=400, detail="Job title must be 50 characters or fewer")

    # Phone format (digits, spaces, +, -, (, ) only; min 5 digits when provided)
    phone = (payload.phone or "").strip()
    if phone:
        if not _re.match(r'^[+\d][\d\s\-().]{3,49}$', phone):
            raise HTTPException(status_code=400, detail="Invalid phone number format")
        if len(phone) > 50:
            raise HTTPException(status_code=400, detail="Phone must be 50 characters or fewer")

    # Password complexity check
    pw_error = _validate_password_complexity(payload.password)
    if pw_error:
        raise HTTPException(status_code=400, detail=pw_error)

    # Support partner_code from either query param or request body
    effective_partner_code = partner_code or payload.partner_code

    # Block registration under the reserved platform admin code
    if effective_partner_code and effective_partner_code.strip().lower() == DEFAULT_TENANT_ID:
        raise HTTPException(status_code=403, detail="This code is reserved for platform administration. Customer registration is not available under this code.")

    # Resolve tenant
    if effective_partner_code:
        tenant = await resolve_tenant(effective_partner_code)
        tenant_id = tenant["id"]
    else:
        tenant_id = DEFAULT_TENANT_ID

    existing = await db.users.find_one(
        {"email": payload.email.lower(), "tenant_id": tenant_id},
        {"_id": 0},
    )
    if existing:
        if existing.get("is_verified"):
            raise HTTPException(status_code=400, detail="Email already registered")
        # Unverified account — update with fresh data and resend OTP
        verification_code = f"{secrets.randbelow(999999):06d}"
        hashed = pwd_context.hash(payload.password)
        await db.users.update_one(
            {"id": existing["id"]},
            {"$set": {
                "password_hash": hashed,
                "full_name": full_name,
                "job_title": payload.job_title,
                "company_name": payload.company_name,
                "phone": payload.phone,
                "verification_code": verification_code,
                "verification_attempts": 0,
                "verification_locked_until": None,
                "pending_address": {
                    "line1": payload.address.line1,
                    "line2": payload.address.line2 or "",
                    "city": payload.address.city,
                    "region": payload.address.region,
                    "postal": payload.address.postal,
                    "country": payload.address.country,
                },
                **({"profile_meta": payload.profile_meta} if payload.profile_meta else {}),
            }},
        )
        from services.email_service import EmailService
        email_result = await EmailService.send(
            trigger="verification",
            recipient=payload.email.lower(),
            variables={
                "customer_name": full_name,
                "customer_email": payload.email.lower(),
                "verification_code": verification_code,
            },
            db=db,
            tenant_id=tenant_id,
        )
        if email_result.get("status") == "mocked":
            import logging
            logging.getLogger("auth").warning(
                "[DEV] Email mocked for %s — OTP: %s", payload.email.lower(), verification_code
            )
        return {"message": "Verification required"}

    user_id = make_id()
    verification_code = f"{secrets.randbelow(999999):06d}"
    hashed = pwd_context.hash(payload.password)

    user_doc = {
        "id": user_id,
        "email": payload.email.lower(),
        "password_hash": hashed,
        "full_name": full_name,
        "job_title": payload.job_title,
        "company_name": payload.company_name,
        "phone": payload.phone,
        "is_verified": False,
        "is_admin": False,
        "role": "customer",
        "tenant_id": tenant_id,
        "verification_code": verification_code,
        "created_at": now_iso(),
        # Store address + profile_meta until email is verified; moved to customers/addresses on verify
        "pending_address": {
            "line1": payload.address.line1,
            "line2": payload.address.line2 or "",
            "city": payload.address.city,
            "region": payload.address.region,
            "postal": payload.address.postal,
            "country": payload.address.country,
        },
    }
    if payload.profile_meta:
        user_doc["profile_meta"] = payload.profile_meta
    await db.users.insert_one(user_doc)

    from services.email_service import EmailService
    email_result = await EmailService.send(
        trigger="verification",
        recipient=payload.email.lower(),
        variables={
            "customer_name": full_name,
            "customer_email": payload.email.lower(),
            "verification_code": verification_code,
        },
        db=db,
        tenant_id=tenant_id,
    )
    # Log OTP to server console when email is mocked (no Resend key configured)
    if email_result.get("status") == "mocked":
        import logging
        logging.getLogger("auth").warning(
            "[DEV] Email mocked for %s — OTP: %s", payload.email.lower(), verification_code
        )

    await AuditService.log(
        action="USER_REGISTERED",
        description=f"New user registered (pending verification): {payload.email}",
        entity_type="User",
        entity_id=user_id,
        actor_type="user",
        actor_email=payload.email.lower(),
        source="customer_ui",
        meta_json={"company_name": payload.company_name, "tenant_id": tenant_id},
    )
    return {"message": "Verification required"}


@router.post("/auth/resend-verification-email")
async def resend_verification_email(payload: ResendVerificationRequest):
    email = payload.email.lower()

    # ── Check pending_partner_registrations first (partner pre-verification) ──
    pending = await db.pending_partner_registrations.find_one({"email": email}, {"_id": 0})
    if pending:
        verification_code = f"{secrets.randbelow(999999):06d}"
        await db.pending_partner_registrations.update_one(
            {"email": email},
            {"$set": {"verification_code": verification_code, "verification_attempts": 0, "locked_until": None}},
        )
        from services.email_service import EmailService
        email_result = await EmailService.send(
            trigger="verification",
            recipient=email,
            variables={"customer_name": pending.get("admin_name", ""), "customer_email": email, "verification_code": verification_code},
            db=db, tenant_id=None,
        )
        if email_result.get("status") == "mocked":
            import logging
            logging.getLogger("auth").warning("[DEV] Partner pending resend mocked for %s — OTP: %s", email, verification_code)
        return {"message": "Verification email resent"}

    # ── Fall back to users collection (customer unverified accounts) ──────────
    query: Dict[str, Any] = {"email": email}
    if payload.partner_code:
        try:
            tenant = await resolve_tenant(payload.partner_code)
            query["tenant_id"] = tenant["id"]
        except Exception:
            pass  # Invalid code — fall back to unscoped lookup
    user = await db.users.find_one(query, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("is_verified"):
        return {"message": "Already verified"}
    verification_code = f"{secrets.randbelow(999999):06d}"
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"verification_code": verification_code}},
    )
    from services.email_service import EmailService
    email_result = await EmailService.send(
        trigger="verification",
        recipient=user["email"],
        variables={
            "customer_name": user.get("full_name", ""),
            "customer_email": user["email"],
            "verification_code": verification_code,
        },
        db=db,
        tenant_id=user.get("tenant_id"),
    )
    await create_audit_log(
        entity_type="user", entity_id=user["id"],
        action="verification_resent", actor=user["email"], details={},
    )
    if email_result.get("status") == "mocked":
        import logging
        logging.getLogger("auth").warning(
            "[DEV] Email mocked for %s — OTP: %s", user["email"], verification_code
        )
    return {"message": "Verification email resent"}


@router.post("/auth/verify-email")
async def verify_email(payload: VerifyEmailRequest):
    # Support token-based verification (single JWT string)
    if payload.token and not payload.email and not payload.code:
        try:
            from core.security import decode_token
            claims = decode_token(payload.token)
            email_from_token = claims.get("email")
            code_from_token = claims.get("code")
            if not email_from_token or not code_from_token:
                raise HTTPException(status_code=400, detail="Invalid or expired verification token")
            # Reconstruct payload-like data
            resolve_email = email_from_token
            resolve_code = code_from_token
            resolve_partner_code = claims.get("partner_code")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    elif payload.email and payload.code:
        resolve_email = payload.email
        resolve_code = payload.code
        resolve_partner_code = payload.partner_code
    else:
        raise HTTPException(status_code=400, detail="Provide either 'token' or both 'email' and 'code'")

    # Scope by tenant when partner_code is provided — prevents cross-tenant ambiguity
    query: Dict[str, Any] = {"email": resolve_email.lower()}
    if resolve_partner_code:
        try:
            tenant = await resolve_tenant(resolve_partner_code)
            query["tenant_id"] = tenant["id"]
        except Exception:
            pass  # Invalid code — fall back to unscoped lookup
    user = await db.users.find_one(query, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("is_verified"):
        return {"message": "Already verified"}
    
    # SECURITY: Track verification attempts to prevent brute-force
    verification_attempts = user.get("verification_attempts", 0)
    verification_locked_until = user.get("verification_locked_until")
    
    # Check if locked out
    if verification_locked_until:
        try:
            locked_until = datetime.fromisoformat(verification_locked_until.replace("Z", "+00:00"))
            if datetime.now(locked_until.tzinfo) < locked_until:
                raise HTTPException(status_code=429, detail="Too many verification attempts. Try again later.")
        except (ValueError, TypeError):
            pass  # Invalid date format, continue
    
    if user.get("verification_code") != resolve_code:
        # Increment attempt counter
        new_attempts = verification_attempts + 1
        update = {"$set": {"verification_attempts": new_attempts}}
        
        # Lock after 5 failed attempts for 15 minutes
        if new_attempts >= 5:
            lock_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            update["$set"]["verification_locked_until"] = lock_until
            await db.users.update_one({"id": user["id"]}, update)
            raise HTTPException(status_code=429, detail="Too many verification attempts. Try again in 15 minutes.")
        
        await db.users.update_one({"id": user["id"]}, update)
        raise HTTPException(status_code=400, detail="Invalid code")
    
    # Valid code - clear verification state and create customer records
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"is_verified": True, "verification_code": None, "verification_attempts": 0, "verification_locked_until": None},
         "$unset": {"pending_address": ""}},
    )

    # Create customer + address records now that email is verified
    existing_customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    if not existing_customer:
        customer_id = make_id()
        await db.customers.insert_one({
            "id": customer_id,
            "user_id": user["id"],
            "tenant_id": user.get("tenant_id"),
            "company_name": user.get("company_name", ""),
            "phone": user.get("phone", ""),
            "allow_bank_transfer": True,
            "allow_card_payment": False,
            "stripe_customer_id": None,
            "zoho_crm_contact_id": None,
            "zoho_books_contact_id": None,
            "created_at": now_iso(),
        })
        pending_address = user.get("pending_address") or {}
        if pending_address:
            await db.addresses.insert_one({
                "id": make_id(),
                "customer_id": customer_id,
                "tenant_id": user.get("tenant_id"),
                "line1": pending_address.get("line1", ""),
                "line2": pending_address.get("line2", ""),
                "city": pending_address.get("city", ""),
                "region": pending_address.get("region", ""),
                "postal": pending_address.get("postal", ""),
                "country": pending_address.get("country", ""),
            })
        # Webhook: customer.registered (fired here, after verified)
        from services.webhook_service import dispatch_event as _wh_dispatch
        await _wh_dispatch("customer.registered", {
            "id": customer_id,
            "email": user["email"],
            "full_name": user.get("full_name", ""),
            "company": user.get("company_name", ""),
            "phone": user.get("phone", ""),
            "country": pending_address.get("country", ""),
            "created_at": now_iso(),
        }, user.get("tenant_id"))

    await db.email_outbox.insert_one({
        "id": make_id(),
        "to": payload.email.lower(),
        "subject": "Welcome",
        "body": "Your email has been verified.",
        "type": "welcome",
        "status": "MOCKED",
        "created_at": now_iso(),
    })
    await create_audit_log(entity_type="user", entity_id=user["id"], action="email_verified", actor=payload.email.lower(), details={})

    # ── Partner activation ────────────────────────────────────────────────────
    if user.get("role") == "partner_super_admin":
        tenant = await db.tenants.find_one({"id": user.get("tenant_id")}, {"_id": 0, "code": 1, "id": 1})
        if tenant:
            activate_now = now_iso()
            update_set: Dict[str, Any] = {"status": "active", "updated_at": activate_now}
            # Assign free trial plan
            try:
                free_trial = await db.plans.find_one({"is_default": True}, {"_id": 0})
                if free_trial:
                    limits = {k: v for k, v in free_trial.items() if k.startswith("max_")}
                    update_set["license"] = {
                        "plan_id": free_trial["id"],
                        "plan_name": free_trial["name"],
                        "assigned_at": activate_now,
                        **limits,
                    }
            except Exception:
                pass
            await db.tenants.update_one({"id": tenant["id"]}, {"$set": update_set})
            await create_audit_log(entity_type="tenant", entity_id=tenant["id"], action="partner_activated", actor=payload.email.lower(), details={})
        return {"message": "Verified", "partner_code": tenant.get("code") if tenant else None}

    return {"message": "Verified"}


class ForgotPasswordRequest(BaseModel):
    email: str
    partner_code: str = ""


class ResetPasswordRequest(BaseModel):
    email: str
    partner_code: str = ""
    code: str
    new_password: str


@router.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    """Request a password reset code. Always returns success to prevent email enumeration."""
    try:
        tenant_id = None
        if payload.partner_code:
            tenant = await resolve_tenant(payload.partner_code)
            tenant_id = tenant.get("id") if tenant else None
        query: Dict[str, Any] = {"email": payload.email.lower()}
        if tenant_id:
            query["tenant_id"] = tenant_id
        user = await db.users.find_one(query, {"_id": 0})
        if user:
            reset_code = f"{secrets.randbelow(999999):06d}"
            expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            await db.users.update_one(
                {"id": user["id"]},
                {"$set": {"password_reset_code": reset_code, "password_reset_expires": expiry}},
            )
            # Ensure password_reset template is enabled
            await db.email_templates.update_many(
                {"trigger": "password_reset"},
                {"$set": {"is_enabled": True}},
            )
            from services.email_service import EmailService
            await EmailService.send(
                trigger="password_reset",
                recipient=user["email"],
                variables={
                    "customer_name": user.get("full_name", ""),
                    "customer_email": user["email"],
                    "reset_code": reset_code,
                },
                db=db,
                tenant_id=user.get("tenant_id"),
            )
            await create_audit_log(
                entity_type="user", entity_id=user["id"],
                action="password_reset_requested", actor=user["email"], details={},
            )
    except Exception:
        pass  # Never reveal if the email exists
    return {"message": "If an account with that email exists, a reset code has been sent."}


@router.post("/auth/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    """Validate reset code and set new password."""
    tenant_id = None
    if payload.partner_code:
        tenant = await resolve_tenant(payload.partner_code)
        tenant_id = tenant.get("id") if tenant else None
    query: Dict[str, Any] = {"email": payload.email.lower()}
    if tenant_id:
        query["tenant_id"] = tenant_id
    user = await db.users.find_one(query, {"_id": 0})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

    stored_code = user.get("password_reset_code")
    expires_str = user.get("password_reset_expires")

    # Check per-user brute-force lockout
    reset_locked_until = user.get("password_reset_locked_until")
    if reset_locked_until:
        try:
            locked_dt = datetime.fromisoformat(reset_locked_until.replace("Z", "+00:00"))
            if locked_dt.tzinfo is None:
                locked_dt = locked_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < locked_dt:
                raise HTTPException(status_code=429, detail="Too many reset attempts. Please request a new code.")
        except (ValueError, TypeError):
            pass

    if not stored_code or stored_code != payload.code.strip():
        # Increment per-user attempt counter
        new_attempts = user.get("password_reset_attempts", 0) + 1
        attempt_update: Dict[str, Any] = {"password_reset_attempts": new_attempts}
        if new_attempts >= 5:
            lock_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            attempt_update["password_reset_locked_until"] = lock_until
            await db.users.update_one({"id": user["id"]}, {"$set": attempt_update})
            raise HTTPException(status_code=429, detail="Too many reset attempts. Please request a new code in 15 minutes.")
        await db.users.update_one({"id": user["id"]}, {"$set": attempt_update})
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

    if expires_str:
        try:
            expiry_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > expiry_dt:
                raise HTTPException(status_code=400, detail="Reset code has expired. Please request a new one.")
        except ValueError:
            pass

    err = _validate_password_complexity(payload.new_password)
    if err:
        raise HTTPException(status_code=400, detail=err)

    hashed = pwd_context.hash(payload.new_password)
    await db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {"password_hash": hashed, "updated_at": now_iso()},
            "$unset": {"password_reset_code": "", "password_reset_expires": "",
                       "password_reset_attempts": "", "password_reset_locked_until": ""},
            "$inc": {"token_version": 1},
        },
    )
    await create_audit_log(
        entity_type="user", entity_id=user["id"],
        action="password_reset_completed", actor=user["email"], details={},
    )
    return {"message": "Password reset successfully. You can now sign in with your new password."}


@router.get("/me")
async def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    address = None
    if customer:
        address = await db.addresses.find_one({"customer_id": customer["id"]}, {"_id": 0})
    # Resolve partner_code from tenant
    partner_code = None
    tenant_id = user.get("tenant_id")
    if tenant_id:
        tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0, "code": 1})
        if tenant:
            partner_code = tenant.get("code")
    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "company_name": user.get("company_name", ""),
            "phone": user.get("phone", ""),
            "job_title": user.get("job_title", ""),
            "is_verified": user.get("is_verified", False),
            "is_admin": user.get("is_admin", False),
            "role": user.get("role", "customer"),
            "tenant_id": tenant_id,
            "partner_code": partner_code,
            "must_change_password": user.get("must_change_password", False),
        },
        "customer": customer,
        "address": address,
    }


@router.put("/me")
async def update_me(
    payload: UpdateProfileRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    update_user: Dict[str, Any] = {}
    if payload.full_name is not None:
        update_user["full_name"] = payload.full_name
    if payload.company_name is not None:
        update_user["company_name"] = payload.company_name
    if payload.job_title is not None:
        update_user["job_title"] = payload.job_title
    if payload.phone is not None:
        update_user["phone"] = payload.phone

    if update_user:
        await db.users.update_one({"id": user["id"]}, {"$set": update_user})

    update_cust: Dict[str, Any] = {}
    if payload.company_name is not None:
        update_cust["company_name"] = payload.company_name
    if payload.phone is not None:
        update_cust["phone"] = payload.phone
    if update_cust:
        await db.customers.update_one({"id": customer["id"]}, {"$set": update_cust})

    if update_user or update_cust:
        await create_audit_log(
            entity_type="user", entity_id=user["id"],
            action="profile_updated", actor=user["email"],
            details={k: v for k, v in {**update_user, **update_cust}.items()},
        )

    # Update address if provided
    if payload.address is not None:
        addr_data = payload.address.model_dump()
        await db.addresses.update_one(
            {"customer_id": customer["id"]},
            {"$set": {**addr_data, "customer_id": customer["id"]}},
            upsert=True,
        )

    return {"message": "Profile updated"}


class ChangePasswordRequest(BaseModel):
    new_password: str


@router.post("/auth/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Force-change password for authenticated user. Clears the must_change_password flag.
    Used for first-time login password change flow.
    """
    err = _validate_password_complexity(payload.new_password)
    if err:
        raise HTTPException(status_code=422, detail=err)

    new_hash = pwd_context.hash(payload.new_password)
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": new_hash, "must_change_password": False}},
    )
    await create_audit_log(
        entity_type="user", entity_id=user["id"],
        action="password_changed", actor=user["email"],
        details={"method": "force_change"},
    )
    return {"message": "Password updated successfully"}
