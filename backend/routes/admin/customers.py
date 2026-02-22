"""Admin: Customer management routes."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso, currency_for_country
from core.security import require_admin, require_super_admin, pwd_context
from db.session import db
from models import (
    AdminCustomerPaymentUpdate,
    AdminCreateCustomerRequest,
    CustomerUpdate,
    AddressUpdate,
)
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-customers"])


@router.get("/admin/customers")
async def admin_customers(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    country: Optional[str] = None,
    status: Optional[str] = None,
    bank_transfer: Optional[str] = None,
    card_payment: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    users_all = await db.users.find({}, {"_id": 0, "id": 1, "email": 1, "full_name": 1, "is_active": 1}).to_list(10000)
    user_map = {u["id"]: u for u in users_all}
    addresses_all = await db.addresses.find({}, {"_id": 0}).to_list(10000)
    addr_map = {a["customer_id"]: a for a in addresses_all}

    query: Dict[str, Any] = {}
    if bank_transfer is not None:
        query["allow_bank_transfer"] = (bank_transfer == "true")
    if card_payment is not None:
        query["allow_card_payment"] = (card_payment == "true")

    customers_all = await db.customers.find(query, {"_id": 0}).to_list(10000)
    filtered = []
    for c in customers_all:
        user = user_map.get(c.get("user_id", ""), {})
        addr = addr_map.get(c["id"], {})
        if country and addr.get("country", "").upper() != country.upper():
            continue
        if status:
            is_active = user.get("is_active", True)
            if status == "active" and not is_active:
                continue
            if status == "inactive" and is_active:
                continue
        if search:
            s = search.lower()
            haystack = " ".join(filter(None, [
                user.get("email", ""), user.get("full_name", ""), c.get("company_name", "")
            ])).lower()
            if s not in haystack:
                continue
        filtered.append(c)

    total = len(filtered)
    skip = (page - 1) * per_page
    page_custs = filtered[skip: skip + per_page]
    page_uid_set = {c.get("user_id") for c in page_custs}
    page_cid_set = {c["id"] for c in page_custs}
    page_users = [u for u in users_all if u["id"] in page_uid_set]
    page_addrs = [a for a in addresses_all if a.get("customer_id") in page_cid_set]

    return {
        "customers": page_custs,
        "users": page_users,
        "addresses": page_addrs,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


@router.put("/admin/customers/{customer_id}/payment-methods")
async def admin_update_customer_payment_methods(
    customer_id: str,
    payload: AdminCustomerPaymentUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    existing = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.customers.update_one(
        {"id": customer_id},
        {"$set": {
            "allow_bank_transfer": payload.allow_bank_transfer,
            "allow_card_payment": payload.allow_card_payment,
        }}
    )
    await create_audit_log(entity_type="customer", entity_id=customer_id, action="payment_methods_updated", actor=admin["email"], details={"allow_bank_transfer": payload.allow_bank_transfer, "allow_card_payment": payload.allow_card_payment})
    return {"message": "Payment methods updated"}


@router.post("/admin/customers/create")
async def admin_create_customer(
    payload: AdminCreateCustomerRequest,
    admin: Dict[str, Any] = Depends(require_admin),
):
    existing = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = make_id()
    customer_id = make_id()
    hashed = pwd_context.hash(payload.password)
    currency = currency_for_country(payload.country)

    user_doc = {
        "id": user_id,
        "email": payload.email.lower(),
        "password_hash": hashed,
        "full_name": payload.full_name,
        "company_name": payload.company_name or "",
        "job_title": payload.job_title or "",
        "phone": payload.phone or "",
        "is_admin": False,
        "is_verified": payload.mark_verified,
        "role": "customer",
        "must_change_password": True,
        "verification_code": None,
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
    }
    await db.users.insert_one(user_doc)

    customer_doc = {
        "id": customer_id,
        "user_id": user_id,
        "company_name": payload.company_name or "",
        "phone": payload.phone or "",
        "currency": currency,
        "currency_locked": False,
        "allow_bank_transfer": True,
        "allow_card_payment": False,
        "stripe_customer_id": None,
        "zoho_crm_contact_id": None,
        "zoho_books_contact_id": None,
        "created_at": now_iso(),
    }
    await db.customers.insert_one(customer_doc)

    await db.addresses.insert_one({
        "id": make_id(),
        "customer_id": customer_id,
        "line1": payload.line1,
        "line2": payload.line2 or "",
        "city": payload.city,
        "region": payload.region,
        "postal": payload.postal,
        "country": payload.country,
    })

    await create_audit_log(
        entity_type="customer",
        entity_id=customer_id,
        action="customer_created_by_admin",
        actor=f"admin:{admin['id']}",
        details={"email": payload.email, "full_name": payload.full_name, "verified": payload.mark_verified},
    )

    return {"message": "Customer created", "customer_id": customer_id, "user_id": user_id}


@router.put("/admin/customers/{customer_id}")
async def update_customer(
    customer_id: str,
    customer_data: CustomerUpdate,
    address_data: AddressUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    user = await db.users.find_one({"id": customer["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    changes: Dict[str, Any] = {}

    user_updates: Dict[str, Any] = {}
    if customer_data.full_name is not None:
        user_updates["full_name"] = customer_data.full_name
        changes["full_name"] = {"old": user.get("full_name"), "new": customer_data.full_name}
    if customer_data.company_name is not None:
        user_updates["company_name"] = customer_data.company_name
        changes["company_name"] = {"old": user.get("company_name"), "new": customer_data.company_name}
    if customer_data.job_title is not None:
        user_updates["job_title"] = customer_data.job_title
        changes["job_title"] = {"old": user.get("job_title"), "new": customer_data.job_title}
    if customer_data.phone is not None:
        user_updates["phone"] = customer_data.phone
        changes["phone"] = {"old": user.get("phone"), "new": customer_data.phone}

    if user_updates:
        await db.users.update_one({"id": user["id"]}, {"$set": user_updates})

    address = await db.addresses.find_one({"customer_id": customer_id}, {"_id": 0})
    if address:
        address_updates: Dict[str, Any] = {}
        if address_data.line1 is not None:
            address_updates["line1"] = address_data.line1
            changes["address_line1"] = {"old": address.get("line1"), "new": address_data.line1}
        if address_data.line2 is not None:
            address_updates["line2"] = address_data.line2
        if address_data.city is not None:
            address_updates["city"] = address_data.city
            changes["city"] = {"old": address.get("city"), "new": address_data.city}
        if address_data.region is not None:
            address_updates["region"] = address_data.region
            changes["region"] = {"old": address.get("region"), "new": address_data.region}
        if address_data.postal is not None:
            address_updates["postal"] = address_data.postal
        if address_data.country is not None:
            address_updates["country"] = address_data.country
            changes["country"] = {"old": address.get("country"), "new": address_data.country}
        if address_updates:
            await db.addresses.update_one({"customer_id": customer_id}, {"$set": address_updates})

    await create_audit_log(
        entity_type="customer",
        entity_id=customer_id,
        action="updated",
        actor=f"admin:{admin['id']}",
        details={"changes": changes},
    )

    return {"message": "Customer updated successfully"}


@router.patch("/admin/customers/{customer_id}/active")
async def admin_set_customer_active(
    customer_id: str,
    active: bool,
    admin: Dict[str, Any] = Depends(require_admin),
):
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    linked_user = await db.users.find_one({"id": customer.get("user_id")}, {"_id": 0})
    if linked_user and linked_user["id"] == admin["id"] and not active:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")

    user = linked_user
    old_state = user.get("is_active", True) if user else True

    await db.customers.update_one({"id": customer_id}, {"$set": {"is_active": active, "updated_at": now_iso()}})
    if user:
        await db.users.update_one({"id": user["id"]}, {"$set": {"is_active": active, "updated_at": now_iso()}})

    await create_audit_log(
        entity_type="customer",
        entity_id=customer_id,
        action="set_active" if active else "set_inactive",
        actor=f"admin:{admin['id']}",
        details={"is_active": {"old": old_state, "new": active}, "also_updated_user": bool(user)},
    )
    return {"message": f"Customer {'activated' if active else 'deactivated'}", "is_active": active}
