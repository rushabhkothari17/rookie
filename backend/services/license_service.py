"""Partner Licensing Service.

Manages resource limits and monthly usage tracking for each tenant.

Design:
- Total-count resources (users, storage, roles, etc.) are counted live from DB
- Monthly-rolling resources (orders, customers, subscriptions) use a counter
  in the `license_usage` collection with lazy-reset at EST month boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from core.helpers import make_id, now_iso
from db.session import db

EST = ZoneInfo("America/New_York")

# Resources tracked as monthly rolling counters (reset on 1st EST)
MONTHLY_RESOURCES = {"orders", "customers", "subscriptions"}

# Resources counted live from DB  →  (collection, filter_builder)
# filter_builder receives tenant_id and returns a MongoDB filter dict
TOTAL_RESOURCE_COUNTERS: Dict[str, Tuple[str, Any]] = {
    "users": ("users", lambda tid: {
        "tenant_id": tid,
        "role": {"$in": ["partner_super_admin", "partner_admin", "partner_staff", "custom"]},
    }),
    "user_roles": ("admin_roles", lambda tid: {"tenant_id": tid}),
    "product_categories": ("categories", lambda tid: {"tenant_id": tid}),
    "product_terms": ("terms", lambda tid: {"tenant_id": tid}),
    "resources": ("articles", lambda tid: {"tenant_id": tid, "deleted_at": {"$exists": False}}),
    "templates": ("article_templates", lambda tid: {"tenant_id": tid}),
    "email_templates": ("resource_email_templates", lambda tid: {"tenant_id": tid}),
    "categories": ("resource_categories", lambda tid: {"tenant_id": tid}),
    "forms": ("tenant_forms", lambda tid: {"tenant_id": tid}),
    "references": ("website_references", lambda tid: {"tenant_id": tid}),
    "enquiries": ("enquiries", lambda tid: {"tenant_id": tid, "deleted_at": {"$exists": False}}),
}

# Default license (no limits)
DEFAULT_LICENSE: Dict[str, Any] = {
    "plan": "unlimited",
    "warning_threshold_pct": 80,
    "effective_from": None,
    "max_users": None,
    "max_storage_mb": None,
    "max_user_roles": None,
    "max_product_categories": None,
    "max_product_terms": None,
    "max_enquiries": None,
    "max_resources": None,
    "max_templates": None,
    "max_email_templates": None,
    "max_categories": None,
    "max_forms": None,
    "max_references": None,
    "max_orders_per_month": None,
    "max_customers_per_month": None,
    "max_subscriptions_per_month": None,
}


def _current_est_period() -> str:
    """Return 'YYYY-MM' string for the current month in EST."""
    return datetime.now(EST).strftime("%Y-%m")


async def get_tenant_license(tenant_id: str) -> Dict[str, Any]:
    """Return the tenant's license config, falling back to defaults."""
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0, "license": 1})
    stored = (tenant or {}).get("license") or {}
    return {**DEFAULT_LICENSE, **stored}


async def get_or_create_monthly_usage(tenant_id: str) -> Dict[str, Any]:
    """
    Get the current monthly usage record for a tenant.
    Lazy-reset: if the stored period != current EST period, reset monthly counters.
    """
    period = _current_est_period()
    usage = await db.license_usage.find_one({"tenant_id": tenant_id}, {"_id": 0})

    if not usage:
        doc: Dict[str, Any] = {
            "id": make_id(),
            "tenant_id": tenant_id,
            "period": period,
            "orders_count": 0,
            "customers_count": 0,
            "subscriptions_count": 0,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        await db.license_usage.insert_one({**doc})
        doc.pop("_id", None)
        return doc

    if usage.get("period") != period:
        # New month — reset rolling counters
        reset_doc = {
            "period": period,
            "orders_count": 0,
            "customers_count": 0,
            "subscriptions_count": 0,
            "updated_at": now_iso(),
        }
        await db.license_usage.update_one({"tenant_id": tenant_id}, {"$set": reset_doc})
        return {**usage, **reset_doc}

    return usage


async def get_live_count(tenant_id: str, resource: str) -> int:
    """Count a total-count resource live from MongoDB."""
    if resource not in TOTAL_RESOURCE_COUNTERS:
        return 0
    collection_name, filter_fn = TOTAL_RESOURCE_COUNTERS[resource]
    coll = getattr(db, collection_name)
    return await coll.count_documents(filter_fn(tenant_id))


async def get_storage_used_mb(tenant_id: str) -> float:
    """Sum all file sizes for a tenant in MB."""
    pipeline = [
        {"$match": {"tenant_id": tenant_id}},
        {"$group": {"_id": None, "total_bytes": {"$sum": "$file_size"}}},
    ]
    result = await db.uploads.aggregate(pipeline).to_list(1)
    if not result:
        return 0.0
    return round((result[0].get("total_bytes") or 0) / (1024 * 1024), 2)


async def check_limit(tenant_id: str, resource: str) -> Dict[str, Any]:
    """
    Check if a tenant is allowed to create one more of `resource`.

    Returns:
        {
            "allowed": bool,
            "current": int | float,
            "limit": int | float | None,
            "pct": int,          # 0-100+
            "warning": bool,     # True when pct >= warning_threshold
        }
    """
    license_data = await get_tenant_license(tenant_id)

    # Determine the limit key (e.g. orders → max_orders_per_month)
    if resource in MONTHLY_RESOURCES:
        limit_key = f"max_{resource}_per_month"
    elif resource == "storage":
        limit_key = "max_storage_mb"
    else:
        limit_key = f"max_{resource}"

    max_val = license_data.get(limit_key)
    warning_threshold = int(license_data.get("warning_threshold_pct") or 80)

    # If no limit set → unlimited
    if max_val is None:
        return {"allowed": True, "current": 0, "limit": None, "pct": 0, "warning": False}

    # Get current count
    if resource in MONTHLY_RESOURCES:
        usage = await get_or_create_monthly_usage(tenant_id)
        current = usage.get(f"{resource}_count", 0)
    elif resource == "storage":
        current = await get_storage_used_mb(tenant_id)
    else:
        current = await get_live_count(tenant_id, resource)

    allowed = current < max_val
    pct = int((current / max_val) * 100) if max_val > 0 else 0
    warning = pct >= warning_threshold

    return {
        "allowed": allowed,
        "current": current,
        "limit": max_val,
        "pct": pct,
        "warning": warning,
    }


async def increment_monthly(tenant_id: str, resource: str, by: int = 1) -> None:
    """Increment a monthly rolling counter (orders/customers/subscriptions)."""
    if resource not in MONTHLY_RESOURCES:
        return
    period = _current_est_period()
    field = f"{resource}_count"
    # Upsert the usage record and increment
    await db.license_usage.update_one(
        {"tenant_id": tenant_id},
        {
            "$inc": {field: by},
            "$setOnInsert": {
                "id": make_id(),
                "tenant_id": tenant_id,
                "period": period,
                "orders_count": 0 if resource != "orders" else by,
                "customers_count": 0 if resource != "customers" else by,
                "subscriptions_count": 0 if resource != "subscriptions" else by,
                "created_at": now_iso(),
            },
            "$set": {"updated_at": now_iso()},
        },
        upsert=True,
    )


async def get_full_usage_snapshot(tenant_id: str) -> Dict[str, Any]:
    """
    Return a complete usage snapshot for a tenant: all resource counts + license.
    Used by the partner dashboard and the platform admin license view.
    """
    license_data = await get_tenant_license(tenant_id)
    monthly_usage = await get_or_create_monthly_usage(tenant_id)
    warning_threshold = int(license_data.get("warning_threshold_pct") or 80)

    def _build(resource: str, current, limit_key: str):
        max_val = license_data.get(limit_key)
        if max_val is None:
            return {"current": current, "limit": None, "pct": 0, "warning": False, "blocked": False}
        pct = int((current / max_val) * 100) if max_val > 0 else 0
        return {
            "current": current,
            "limit": max_val,
            "pct": pct,
            "warning": pct >= warning_threshold,
            "blocked": current >= max_val,
        }

    # Count all total resources in parallel
    import asyncio
    counts = await asyncio.gather(
        get_live_count(tenant_id, "users"),
        get_live_count(tenant_id, "user_roles"),
        get_live_count(tenant_id, "product_categories"),
        get_live_count(tenant_id, "product_terms"),
        get_live_count(tenant_id, "enquiries"),
        get_live_count(tenant_id, "resources"),
        get_live_count(tenant_id, "templates"),
        get_live_count(tenant_id, "email_templates"),
        get_live_count(tenant_id, "categories"),
        get_live_count(tenant_id, "forms"),
        get_live_count(tenant_id, "references"),
        get_storage_used_mb(tenant_id),
    )
    (
        users_c, roles_c, prod_cats_c, prod_terms_c, enquiries_c,
        resources_c, templates_c, email_tmpl_c, categories_c, forms_c,
        references_c, storage_c
    ) = counts

    orders_c = monthly_usage.get("orders_count", 0)
    customers_c = monthly_usage.get("customers_count", 0)
    subs_c = monthly_usage.get("subscriptions_count", 0)

    return {
        "period": monthly_usage.get("period"),
        "license": license_data,
        "usage": {
            "users": _build("users", users_c, "max_users"),
            "storage_mb": _build("storage", storage_c, "max_storage_mb"),
            "user_roles": _build("user_roles", roles_c, "max_user_roles"),
            "product_categories": _build("product_categories", prod_cats_c, "max_product_categories"),
            "product_terms": _build("product_terms", prod_terms_c, "max_product_terms"),
            "enquiries": _build("enquiries", enquiries_c, "max_enquiries"),
            "resources": _build("resources", resources_c, "max_resources"),
            "templates": _build("templates", templates_c, "max_templates"),
            "email_templates": _build("email_templates", email_tmpl_c, "max_email_templates"),
            "categories": _build("categories", categories_c, "max_categories"),
            "forms": _build("forms", forms_c, "max_forms"),
            "references": _build("references", references_c, "max_references"),
            "orders_this_month": _build("orders", orders_c, "max_orders_per_month"),
            "customers_this_month": _build("customers", customers_c, "max_customers_per_month"),
            "subscriptions_this_month": _build("subscriptions", subs_c, "max_subscriptions_per_month"),
        },
    }
