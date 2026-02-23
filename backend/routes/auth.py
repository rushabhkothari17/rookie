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

from fastapi import APIRouter, Body, Depends, HTTPException, Response, Request
from fastapi.responses import JSONResponse

from core.helpers import make_id, now_iso, currency_for_country
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
from services.settings_service import SettingsService
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
    return {"token": token, "refresh_token": refresh_token, "role": role, "tenant_id": user.get("tenant_id")}


# ---------------------------------------------------------------------------
# Partner Login (admin/staff users for a tenant)
# ---------------------------------------------------------------------------

@router.post("/auth/partner-login")
async def partner_login(payload: PartnerLoginRequest, response: Response):
    """Login for partner organization users (super_admin, admin, staff).
    Requires partner_code to identify the tenant.
    Sets HttpOnly cookies with JWT access and refresh tokens.
    """
    tenant = await resolve_tenant(payload.partner_code)
    partner_roles = ["partner_super_admin", "partner_admin", "partner_staff",
                     "platform_admin", "super_admin", "admin"]
    result = await _authenticate(payload.email, payload.password, tenant["id"], partner_roles)
    _set_auth_cookie(response, result["token"], result.get("refresh_token"))
    # Don't expose refresh token in response body
    return {"token": result["token"], "role": result["role"], "tenant_id": result["tenant_id"]}


# ---------------------------------------------------------------------------
# Customer Login (customers scoped to a tenant)
# ---------------------------------------------------------------------------

@router.post("/auth/customer-login")
async def customer_login(payload: CustomerLoginRequest, response: Response):
    """Login for customers belonging to a specific partner organization.
    Requires partner_code to identify the tenant.
    Sets HttpOnly cookies with JWT access and refresh tokens.
    """
    tenant = await resolve_tenant(payload.partner_code)
    # Any non-admin user is a customer
    query: Dict[str, Any] = {"email": payload.email.lower(), "tenant_id": tenant["id"]}
    user = await db.users.find_one(query, {"_id": 0})
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

    # Customers must not be admin users
    if user.get("is_admin") or user.get("role") in ("partner_super_admin", "partner_admin", "partner_staff"):
        raise HTTPException(status_code=403, detail="Please use Partner Login for admin accounts")

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
        # Route to tenant-scoped login
        tenant = await resolve_tenant(payload.partner_code)
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
async def get_tenant_info(code: str):
    """Public endpoint to verify a partner code and get tenant display name."""
    tenant = await db.tenants.find_one({"code": code.lower()}, {"_id": 0, "id": 1, "name": 1, "code": 1, "status": 1})
    if not tenant:
        raise HTTPException(status_code=404, detail="Partner code not found")
    if tenant.get("status") != "active":
        raise HTTPException(status_code=403, detail="Organization is inactive")
    return {"tenant": {"name": tenant["name"], "code": tenant["code"]}}


async def _seed_new_tenant(tenant_id: str, tenant_name: str, now: str) -> None:
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
        "register_subtitle": "",
        "signup_label": "Get Started",
        "signup_form_title": "Create your account",
        "signup_form_subtitle": "",
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
        "email_from_name": "",
        "email_article_subject_template": "Article: {{article_title}}",
        "email_article_cta_text": "View Article",
        "email_article_footer_text": "Your consultant has shared this document with you.",
        "email_verification_subject": "Verify your email address",
        "email_verification_body": "Your verification code is: {{code}}. This code expires in 24 hours.",
        "articles_hero_label": "Resources",
        "articles_hero_title": "Articles & Guides",
        "articles_hero_subtitle": "Tips, guides, and updates from our team.",
        "checkout_zoho_enabled": False,
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
        "description": "This is a sample service. Edit or replace it from the Admin > Catalog panel.",
        "category": "General Services",
        "is_active": True,
        "currency": "GBP",
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

    # 7. Default email template (order confirmation)
    tpl_id = make_id()
    await db.email_templates.insert_one({
        "id": tpl_id,
        "tenant_id": tenant_id,
        "trigger": "order_confirmed",
        "name": "Order Confirmed",
        "subject": "Your order has been confirmed — {{order_number}}",
        "body": "<p>Hi {{customer_name}},</p><p>Thank you for your order. Your order <strong>{{order_number}}</strong> has been confirmed.</p><p>We'll be in touch soon.</p><p>Thanks,<br>{{store_name}}</p>",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    })


@router.post("/auth/register-partner")
async def register_partner(payload: Dict[str, Any] = Body(...)):
    """Self-service partner organization registration.
    Creates a new tenant + partner_super_admin user.
    """
    name = payload.get("name", "").strip()
    code = payload.get("code", "").strip().lower().replace(" ", "-")
    admin_name = payload.get("admin_name", "").strip()
    admin_email = payload.get("admin_email", "").strip().lower()
    admin_password = payload.get("admin_password", "")

    if not all([name, code, admin_name, admin_email, admin_password]):
        raise HTTPException(status_code=400, detail="All fields are required")

    # Password complexity check
    pw_error = _validate_password_complexity(admin_password)
    if pw_error:
        raise HTTPException(status_code=400, detail=pw_error)

    # Validate code uniqueness
    if await db.tenants.find_one({"code": code}):
        raise HTTPException(status_code=400, detail="Partner code already in use. Choose a different code.")

    # Check email uniqueness across all tenants
    if await db.users.find_one({"email": admin_email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create the tenant
    tenant_id = make_id()
    now = now_iso()
    await db.tenants.insert_one({
        "id": tenant_id,
        "name": name,
        "code": code,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })

    # Seed with generic defaults — never copy from another tenant
    await _seed_new_tenant(tenant_id, name, now)

    # Create partner_super_admin user
    user_id = make_id()
    hashed = pwd_context.hash(admin_password)
    await db.users.insert_one({
        "id": user_id,
        "email": admin_email,
        "password_hash": hashed,
        "full_name": admin_name,
        "company_name": name,
        "job_title": "",
        "phone": "",
        "is_admin": True,
        "is_verified": True,
        "role": "partner_super_admin",
        "tenant_id": tenant_id,
        "is_active": True,
        "created_at": now,
    })

    return {
        "message": "Partner organization created successfully. You can now log in.",
        "tenant_name": name,
        "partner_code": code,
    }


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@router.post("/auth/register")
async def register(payload: RegisterRequest, partner_code: Optional[str] = None):
    # Password complexity check
    pw_error = _validate_password_complexity(payload.password)
    if pw_error:
        raise HTTPException(status_code=400, detail=pw_error)

    # Resolve tenant
    if partner_code:
        tenant = await resolve_tenant(partner_code)
        tenant_id = tenant["id"]
    else:
        tenant_id = DEFAULT_TENANT_ID

    existing = await db.users.find_one(
        {"email": payload.email.lower(), "tenant_id": tenant_id},
        {"_id": 0},
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = make_id()
    verification_code = f"{secrets.randbelow(999999):06d}"
    hashed = pwd_context.hash(payload.password)

    user_doc = {
        "id": user_id,
        "email": payload.email.lower(),
        "password_hash": hashed,
        "full_name": payload.full_name,
        "job_title": payload.job_title,
        "company_name": payload.company_name,
        "phone": payload.phone,
        "is_verified": False,
        "is_admin": False,
        "role": "customer",
        "tenant_id": tenant_id,
        "verification_code": verification_code,
        "created_at": now_iso(),
    }
    if payload.profile_meta:
        user_doc["profile_meta"] = payload.profile_meta
    await db.users.insert_one(user_doc)

    customer_id = make_id()
    currency = currency_for_country(payload.address.country)
    await db.customers.insert_one({
        "id": customer_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "company_name": payload.company_name,
        "phone": payload.phone,
        "currency": currency,
        "currency_locked": False,
        "allow_bank_transfer": True,
        "allow_card_payment": False,
        "stripe_customer_id": None,
        "zoho_crm_contact_id": None,
        "zoho_books_contact_id": None,
        "created_at": now_iso(),
    })
    await db.addresses.insert_one({
        "id": make_id(),
        "customer_id": customer_id,
        "tenant_id": tenant_id,
        "line1": payload.address.line1,
        "line2": payload.address.line2 or "",
        "city": payload.address.city,
        "region": payload.address.region,
        "postal": payload.address.postal,
        "country": payload.address.country,
    })
    from services.email_service import EmailService
    await EmailService.send(
        trigger="verification",
        recipient=payload.email.lower(),
        variables={
            "customer_name": payload.full_name,
            "customer_email": payload.email.lower(),
            "verification_code": verification_code,
        },
        db=db,
    )
    await AuditService.log(
        action="USER_REGISTERED",
        description=f"New user registered: {payload.email}",
        entity_type="User",
        entity_id=user_id,
        actor_type="user",
        actor_email=payload.email.lower(),
        source="customer_ui",
        meta_json={"company_name": payload.company_name, "tenant_id": tenant_id},
    )
    # Webhook: customer.registered
    from services.webhook_service import dispatch_event as _wh_dispatch
    await _wh_dispatch("customer.registered", {
        "id": customer_id,
        "email": payload.email.lower(),
        "full_name": payload.full_name,
        "company": payload.company_name or "",
        "phone": payload.phone or "",
        "country": getattr(payload.address, "country", ""),
        "created_at": now_iso(),
    }, tenant_id)
    return {
        "message": "Verification required",
        "verification_code": verification_code,
        "email_delivery": "MOCKED",
    }


@router.post("/auth/resend-verification-email")
async def resend_verification_email(payload: ResendVerificationRequest):
    user = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
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
    await EmailService.send(
        trigger="verification",
        recipient=user["email"],
        variables={
            "customer_name": user.get("full_name", ""),
            "customer_email": user["email"],
            "verification_code": verification_code,
        },
        db=db,
    )
    await create_audit_log(
        entity_type="user", entity_id=user["id"],
        action="verification_resent", actor=user["email"], details={},
    )
    return {"message": "Verification email resent", "verification_code": verification_code}


@router.post("/auth/verify-email")
async def verify_email(payload: VerifyEmailRequest):
    user = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
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
    
    if user.get("verification_code") != payload.code:
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
    
    # Valid code - clear verification state
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"is_verified": True, "verification_code": None, "verification_attempts": 0, "verification_locked_until": None}},
    )
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
    return {"message": "Verified"}


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
    return {"message": "Profile updated"}
