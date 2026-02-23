"""Authentication routes: register, verify-email, login, /me.
Supports multi-tenant login via partner_code.
"""
from __future__ import annotations

import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso, currency_for_country
from core.security import pwd_context, create_access_token, get_current_user
from core.tenant import resolve_tenant, DEFAULT_TENANT_ID, PLATFORM_ROLE
from db.session import db
from models import (
    RegisterRequest, LoginRequest, PartnerLoginRequest, CustomerLoginRequest,
    VerifyEmailRequest, UpdateProfileRequest, ResendVerificationRequest,
)
from services.audit_service import AuditService, create_audit_log
from services.settings_service import SettingsService

router = APIRouter(prefix="/api", tags=["auth"])


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
    # For platform_super_admin, also try null tenant_id
    if not user and tenant_id:
        user = await db.users.find_one({"email": email.lower(), "tenant_id": None}, {"_id": 0})
        # Only accept if they are platform super admin
        if user and user.get("role") != PLATFORM_ROLE:
            user = None
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not pwd_context.verify(password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_verified"):
        raise HTTPException(status_code=403, detail="Email verification required")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact your administrator.")

    role = user.get("role", "customer")
    if expected_roles and role not in expected_roles:
        raise HTTPException(status_code=403, detail="Access denied for this login type")

    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "tenant_id": user.get("tenant_id"),
        "is_admin": user.get("is_admin", False),
    })
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
    return {"token": token, "role": role, "tenant_id": user.get("tenant_id")}


# ---------------------------------------------------------------------------
# Partner Login (admin/staff users for a tenant)
# ---------------------------------------------------------------------------

@router.post("/auth/partner-login")
async def partner_login(payload: PartnerLoginRequest):
    """Login for partner organization users (super_admin, admin, staff).
    Requires partner_code to identify the tenant.
    """
    tenant = await resolve_tenant(payload.partner_code)
    partner_roles = ["partner_super_admin", "partner_admin", "partner_staff",
                     "platform_super_admin", "super_admin", "admin"]
    return await _authenticate(payload.email, payload.password, tenant["id"], partner_roles)


# ---------------------------------------------------------------------------
# Customer Login (customers scoped to a tenant)
# ---------------------------------------------------------------------------

@router.post("/auth/customer-login")
async def customer_login(payload: CustomerLoginRequest):
    """Login for customers belonging to a specific partner organization.
    Requires partner_code to identify the tenant.
    """
    tenant = await resolve_tenant(payload.partner_code)
    customer_roles = ["customer", ""]
    # Any non-admin user is a customer
    query: Dict[str, Any] = {"email": payload.email.lower(), "tenant_id": tenant["id"]}
    user = await db.users.find_one(query, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not pwd_context.verify(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_verified"):
        raise HTTPException(status_code=403, detail="Email verification required")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact your administrator.")

    # Customers must not be admin users
    if user.get("is_admin") or user.get("role") in ("partner_super_admin", "partner_admin", "partner_staff"):
        raise HTTPException(status_code=403, detail="Please use Partner Login for admin accounts")

    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "role": user.get("role", "customer"),
        "tenant_id": tenant["id"],
        "is_admin": False,
    })
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
    return {"token": token, "role": "customer", "tenant_id": tenant["id"]}


# ---------------------------------------------------------------------------
# Legacy login (backward compat — platform super admin and existing sessions)
# ---------------------------------------------------------------------------

@router.post("/auth/login")
async def login(payload: LoginRequest):
    """Legacy login endpoint. If partner_code provided, routes to tenant-scoped auth.
    Without partner_code, only platform_super_admin can log in.
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
            return await customer_login(cust_payload)
        else:
            partner_payload = PartnerLoginRequest(
                partner_code=payload.partner_code,
                email=payload.email,
                password=payload.password,
            )
            return await partner_login(partner_payload)

    # No partner_code: platform super admin only
    user = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not pwd_context.verify(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_verified"):
        raise HTTPException(status_code=403, detail="Email verification required")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact your administrator.")
    if user.get("role") != PLATFORM_ROLE and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Partner code required. Please use the Partner Login tab.")

    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "role": user.get("role", "admin"),
        "tenant_id": user.get("tenant_id"),
        "is_admin": user.get("is_admin", False),
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

    # Seed website/app settings from default tenant
    existing_ws = await db.website_settings.find_one({"tenant_id": DEFAULT_TENANT_ID}, {"_id": 0})
    if existing_ws:
        seed = {k: v for k, v in existing_ws.items() if k != "_id"}
        seed["tenant_id"] = tenant_id
        await db.website_settings.insert_one(seed)

    existing_app = await db.app_settings.find_one(
        {"key": {"$exists": False}, "tenant_id": DEFAULT_TENANT_ID}, {"_id": 0}
    )
    if existing_app:
        seed_app = {k: v for k, v in existing_app.items() if k != "_id"}
        seed_app["tenant_id"] = tenant_id
        await db.app_settings.insert_one(seed_app)

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
    if user.get("verification_code") != payload.code:
        raise HTTPException(status_code=400, detail="Invalid code")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"is_verified": True, "verification_code": None}},
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
            "tenant_id": user.get("tenant_id"),
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
