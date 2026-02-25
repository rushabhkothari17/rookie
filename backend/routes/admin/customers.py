"""Admin: Customer management routes."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso, currency_for_country
from core.security import require_admin, require_super_admin, pwd_context
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, get_tenant_admin, get_tenant_super_admin, is_platform_admin, enrich_partner_codes
from db.session import db
from models import (
    AdminCustomerPaymentUpdate,
    AdminCreateCustomerRequest,
    CustomerUpdate,
    AddressUpdate,
)
from services.audit_service import create_audit_log
from services.zoho_service import auto_sync_to_zoho_crm, auto_sync_to_zoho_books

router = APIRouter(prefix="/api", tags=["admin-customers"])


@router.get("/admin/customers")
async def admin_customers(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    country: Optional[str] = None,
    status: Optional[str] = None,
    payment_mode: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    
    # Build base customer query
    query: Dict[str, Any] = {**tf}
    if payment_mode == "gocardless":
        query["allow_bank_transfer"] = True
    elif payment_mode == "stripe":
        query["allow_card_payment"] = True
    elif payment_mode == "both":
        query["allow_bank_transfer"] = True
        query["allow_card_payment"] = True
    elif payment_mode == "none":
        query["allow_bank_transfer"] = False
        query["allow_card_payment"] = False
    
    # Use aggregation pipeline for efficient querying
    pipeline: list = [
        {"$match": query},
        # Join with users
        {
            "$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "id",
                "as": "user_data"
            }
        },
        {"$unwind": {"path": "$user_data", "preserveNullAndEmptyArrays": True}},
        # Join with addresses
        {
            "$lookup": {
                "from": "addresses",
                "localField": "id",
                "foreignField": "customer_id",
                "as": "address_data"
            }
        },
        {"$unwind": {"path": "$address_data", "preserveNullAndEmptyArrays": True}},
    ]
    
    # Add filters based on joined data
    match_filters = []
    if country:
        match_filters.append({"address_data.country": {"$regex": f"^{country}$", "$options": "i"}})
    if status:
        if status == "active":
            match_filters.append({"$or": [{"user_data.is_active": True}, {"user_data.is_active": {"$exists": False}}]})
        elif status == "inactive":
            match_filters.append({"user_data.is_active": False})
    if search:
        search_regex = {"$regex": search, "$options": "i"}
        match_filters.append({
            "$or": [
                {"user_data.email": search_regex},
                {"user_data.full_name": search_regex},
                {"company_name": search_regex}
            ]
        })
    
    if match_filters:
        pipeline.append({"$match": {"$and": match_filters}})
    
    # Count total for pagination (before skip/limit)
    count_pipeline = pipeline + [{"$count": "total"}]
    count_result = await db.customers.aggregate(count_pipeline).to_list(1)
    total = count_result[0]["total"] if count_result else 0
    
    # Add pagination
    skip = (page - 1) * per_page
    pipeline.extend([
        {"$sort": {"created_at": -1}},
        {"$skip": skip},
        {"$limit": per_page},
        # Project to clean output
        {
            "$project": {
                "_id": 0,
                "customer": {
                    "id": "$id",
                    "user_id": "$user_id",
                    "company_name": "$company_name",
                    "partner_map_id": "$partner_map_id",
                    "allow_card_payment": "$allow_card_payment",
                    "allow_bank_transfer": "$allow_bank_transfer",
                    "stripe_customer_id": "$stripe_customer_id",
                    "gocardless_customer_id": "$gocardless_customer_id",
                    "currency": "$currency",
                    "created_at": "$created_at",
                    "tenant_id": "$tenant_id"
                },
                "user": {
                    "id": "$user_data.id",
                    "email": "$user_data.email",
                    "full_name": "$user_data.full_name",
                    "is_active": "$user_data.is_active"
                },
                "address": {
                    "id": "$address_data.id",
                    "customer_id": "$address_data.customer_id",
                    "line1": "$address_data.line1",
                    "line2": "$address_data.line2",
                    "city": "$address_data.city",
                    "region": "$address_data.region",
                    "postal": "$address_data.postal",
                    "country": "$address_data.country"
                }
            }
        }
    ])
    
    results = await db.customers.aggregate(pipeline).to_list(per_page)
    
    # Flatten results for backward compatibility
    customers = []
    users = []
    addresses = []
    seen_users = set()
    seen_addresses = set()
    
    for r in results:
        customers.append(r["customer"])
        if r.get("user", {}).get("id") and r["user"]["id"] not in seen_users:
            users.append(r["user"])
            seen_users.add(r["user"]["id"])
        if r.get("address", {}).get("id") and r["address"]["id"] not in seen_addresses:
            addresses.append(r["address"])
            seen_addresses.add(r["address"]["id"])
    
    return {
        "customers": customers,
        "users": users,
        "addresses": addresses,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


@router.put("/admin/customers/{customer_id}/payment-methods")
async def admin_update_customer_payment_methods(
    customer_id: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    existing = await db.customers.find_one({**tf, "id": customer_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Customer not found")

    allowed_modes = payload.get("allowed_payment_modes")
    update_doc: Dict[str, Any] = {}

    if allowed_modes is not None:
        # Normalize old mode names (bank_transfer→gocardless, card→stripe)
        normalized = []
        for m in allowed_modes:
            if m == "bank_transfer":
                normalized.append("gocardless")
            elif m == "card":
                normalized.append("stripe")
            else:
                normalized.append(m)
        update_doc["allowed_payment_modes"] = normalized
        update_doc["allow_bank_transfer"] = "gocardless" in normalized
        update_doc["allow_card_payment"] = "stripe" in normalized
    else:
        # Legacy individual field updates
        if "allow_bank_transfer" in payload:
            update_doc["allow_bank_transfer"] = payload["allow_bank_transfer"]
        if "allow_card_payment" in payload:
            update_doc["allow_card_payment"] = payload["allow_card_payment"]

    if not update_doc:
        return {"message": "Nothing to update"}

    await db.customers.update_one({"id": customer_id}, {"$set": update_doc})
    await create_audit_log(entity_type="customer", entity_id=customer_id, action="payment_methods_updated", actor=admin["email"], details=update_doc)
    return {"message": "Payment methods updated"}


@router.post("/admin/customers/create")
async def admin_create_customer(
    payload: AdminCreateCustomerRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    existing = await db.users.find_one({"email": payload.email.lower(), "tenant_id": tid}, {"_id": 0})
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
        "tenant_id": tid,
        "must_change_password": True,
        "verification_code": None,
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
    }
    await db.users.insert_one(user_doc)

    customer_doc = {
        "id": customer_id,
        "user_id": user_id,
        "tenant_id": tid,
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
        "tenant_id": tid,
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

    # Auto-sync to Zoho CRM (fire and forget - don't block response)
    asyncio.create_task(auto_sync_to_zoho_crm(tid, "customers", customer_doc, "create"))
    asyncio.create_task(auto_sync_to_zoho_books(tid, "customers", customer_doc, "create"))

    return {"message": "Customer created", "customer_id": customer_id, "user_id": user_id}


@router.put("/admin/customers/{customer_id}")
async def update_customer(
    customer_id: str,
    customer_data: CustomerUpdate,
    address_data: AddressUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    customer = await db.customers.find_one({**tf, "id": customer_id}, {"_id": 0})
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

    # Auto-sync to Zoho CRM on update (fire and forget)
    updated_customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if updated_customer:
        asyncio.create_task(auto_sync_to_zoho_crm(tf.get("tenant_id", ""), "customers", updated_customer, "update"))
        asyncio.create_task(auto_sync_to_zoho_books(tf.get("tenant_id", ""), "customers", updated_customer, "update"))

    return {"message": "Customer updated successfully"}


@router.patch("/admin/customers/{customer_id}/active")
async def admin_set_customer_active(
    customer_id: str,
    active: bool,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    customer = await db.customers.find_one({**tf, "id": customer_id}, {"_id": 0})
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


@router.get("/admin/customers/{customer_id}/logs")
async def get_customer_logs(customer_id: str, page: int = 1, limit: int = 20, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    # Verify customer belongs to this admin's tenant before returning logs
    customer = await db.customers.find_one({**tf, "id": customer_id}, {"_id": 0, "id": 1})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    flt = {"entity_type": "customer", "entity_id": customer_id}
    total = await db.audit_logs.count_documents(flt)
    skip = (page - 1) * limit
    logs = await db.audit_logs.find(flt, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"logs": logs, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}

