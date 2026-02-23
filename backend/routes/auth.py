"""Authentication routes: register, verify-email, login, /me."""
from __future__ import annotations

import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso, currency_for_country
from core.security import pwd_context, create_access_token, get_current_user
from db.session import db
from models import RegisterRequest, LoginRequest, VerifyEmailRequest, UpdateProfileRequest
from services.audit_service import AuditService, create_audit_log
from services.settings_service import SettingsService

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/")
async def root():
    return {"message": "Automate Accounts API"}


@router.post("/auth/register")
async def register(payload: RegisterRequest):
    existing = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
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
        meta_json={"company_name": payload.company_name, "country": payload.address.country},
    )
    await db.audit_logs.insert_one({"id": make_id(), "entity_type": "user", "entity_id": user_id, "action": "registered", "actor": payload.email.lower(), "details": {"company_name": payload.company_name, "country": payload.address.country}, "created_at": now_iso()})
    return {
        "message": "Verification required",
        "verification_code": verification_code,
        "email_delivery": "MOCKED",
    }


@router.post("/auth/resend-verification-email")
async def resend_verification_email(payload: VerifyEmailRequest):
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
        "subject": "Welcome to Automate Accounts",
        "body": "Your email has been verified.",
        "type": "welcome",
        "status": "MOCKED",
        "created_at": now_iso(),
    })
    await create_audit_log(entity_type="user", entity_id=user["id"], action="email_verified", actor=payload.email.lower(), details={})
    return {"message": "Verified"}


@router.post("/auth/login")
async def login(payload: LoginRequest):
    user = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not pwd_context.verify(payload.password, user.get("password_hash")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_verified"):
        raise HTTPException(status_code=403, detail="Email verification required")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact your administrator.")
    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
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
        meta_json={"role": user.get("role", "customer")},
    )
    await db.audit_logs.insert_one({"id": make_id(), "entity_type": "user", "entity_id": user["id"], "action": "login", "actor": user["email"], "details": {"role": user.get("role", "customer")}, "created_at": now_iso()})
    return {"token": token}


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
            "company_name": user["company_name"],
            "phone": user["phone"],
            "is_verified": user.get("is_verified", False),
            "is_admin": user.get("is_admin", False),
            "role": user.get("role", "customer"),
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
        await create_audit_log(entity_type="user", entity_id=user["id"], action="profile_updated", actor=user["email"], details={k: v for k, v in {**update_user, **update_cust}.items()})

    return {"message": "Profile updated"}
