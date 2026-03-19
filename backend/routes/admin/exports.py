"""Admin: CSV export routes."""
from __future__ import annotations

import csv
import io
import json
import re as _re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core.tenant import get_tenant_filter, tenant_id_of, get_tenant_admin, is_platform_admin
from db.session import db
from services.audit_service import create_audit_log
from routes.admin.permissions import has_permission as _has_perm

router = APIRouter(prefix="/api", tags=["admin-exports"])


def _serialize_val(v: Any) -> str:
    """Serialize a value for CSV. Lists/dicts become JSON strings.
    Cells starting with formula characters are prefixed with a single quote
    to prevent formula injection when opened in spreadsheet apps."""
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        result = json.dumps(v, ensure_ascii=False)
    else:
        result = str(v)
    # CSV formula injection prevention (Excel / LibreOffice)
    if result and result[0] in ("=", "+", "-", "@", "\t", "\r"):
        result = "'" + result
    return result


def _make_csv_response(rows: List[Dict[str, Any]], filename: str) -> StreamingResponse:
    if not rows:
        output = io.StringIO()
        output.write("No data\n")
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    all_keys: List[str] = []
    seen: set = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                all_keys.append(k)
                seen.add(k)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=all_keys, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _serialize_val(row.get(k)) for k in all_keys})

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _split(val: Optional[str]) -> List[str]:
    """Split a comma-separated filter string into a list of non-empty values."""
    if not val:
        return []
    return [v.strip() for v in val.split(",") if v.strip()]


@router.get("/admin/export/orders")
async def export_orders_csv(
    sort_by: str = "created_at",
    sort_order: str = "desc",
    include_deleted: bool = False,
    product_filter: Optional[str] = None,
    order_number_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    email_filter: Optional[str] = None,
    customer_name_filter: Optional[str] = None,
    sub_number_filter: Optional[str] = None,
    processor_id_filter: Optional[str] = None,
    payment_method_filter: Optional[str] = None,
    partner_filter: Optional[str] = None,
    pay_date_from: Optional[str] = None,
    pay_date_to: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    if not await _has_perm(admin, "reports", "view"):
        raise HTTPException(403, "No access to reports module")

    query: Dict[str, Any] = {**tf}
    if not include_deleted:
        query["deleted_at"] = {"$exists": False}

    # Fix: order_number supports multi-value via $in
    order_nums = _split(order_number_filter)
    if order_nums:
        query["order_number"] = {"$in": order_nums} if len(order_nums) > 1 else {"$regex": _re.escape(order_nums[0]), "$options": "i"}

    # Fix: status supports multi-value via $in
    statuses = _split(status_filter)
    if statuses:
        query["status"] = {"$in": statuses} if len(statuses) > 1 else statuses[0]

    # Subscription number filter
    sub_nums = _split(sub_number_filter)
    if sub_nums:
        query["subscription_number"] = {"$in": sub_nums} if len(sub_nums) > 1 else {"$regex": _re.escape(sub_nums[0]), "$options": "i"}

    # Processor ID filter
    proc_ids = _split(processor_id_filter)
    if proc_ids:
        query["processor_id"] = {"$in": proc_ids} if len(proc_ids) > 1 else {"$regex": _re.escape(proc_ids[0]), "$options": "i"}

    # Payment method filter
    methods = _split(payment_method_filter)
    if methods:
        query["payment_method"] = {"$in": methods} if len(methods) > 1 else methods[0]

    # Payment date range
    if pay_date_from:
        query.setdefault("payment_date", {})["$gte"] = pay_date_from
    if pay_date_to:
        query.setdefault("payment_date", {})["$lte"] = pay_date_to + "T23:59:59"

    # Created date range
    if created_from:
        query.setdefault("created_at", {})["$gte"] = created_from
    if created_to:
        query.setdefault("created_at", {})["$lte"] = created_to + "T23:59:59"

    # Fix: product_filter — look up matching product IDs then filter order_items
    product_names = _split(product_filter)
    if product_names:
        prod_ids_matching = [
            p["id"] async for p in db.products.find(
                {**tf, "name": {"$in": product_names}}, {"_id": 0, "id": 1}
            )
        ]
        if prod_ids_matching:
            matching_order_ids = [
                oi["order_id"] async for oi in db.order_items.find(
                    {"product_id": {"$in": prod_ids_matching}}, {"_id": 0, "order_id": 1}
                )
            ]
            query["id"] = {"$in": matching_order_ids}
        else:
            # No matching products → empty export
            return _make_csv_response([], f"orders_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.csv")

    sort_dir = -1 if sort_order == "desc" else 1
    orders = await db.orders.find(query, {"_id": 0}).sort(sort_by, sort_dir).to_list(10000)

    customer_ids = list({o.get("customer_id") for o in orders if o.get("customer_id")})
    customers = await db.customers.find({"id": {"$in": customer_ids}}, {"_id": 0}).to_list(10000)
    user_ids = [c.get("user_id") for c in customers if c.get("user_id")]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "password_hash": 0}).to_list(10000)
    customer_map = {c["id"]: c for c in customers}
    user_map = {u["id"]: u for u in users}

    # Fix: partner_filter applies to customer's partner_code
    partner_codes = _split(partner_filter)

    enriched = []
    for o in orders:
        cust = customer_map.get(o.get("customer_id"), {})
        user = user_map.get(cust.get("user_id"), {})
        email = user.get("email", "")
        full_name = user.get("full_name", "")

        # Fix: email_filter supports multi-value — check each email individually
        if email_filter:
            email_vals = _split(email_filter)
            if email_vals and not any(v.lower() in email.lower() for v in email_vals):
                continue

        # Customer name filter
        if customer_name_filter:
            name_vals = _split(customer_name_filter)
            if name_vals and not any(v.lower() in full_name.lower() for v in name_vals):
                continue

        # Partner filter
        if partner_codes:
            cust_partner = cust.get("partner_code") or cust.get("tenant_id", "")
            if cust_partner not in partner_codes:
                continue

        o["_customer_email"] = email
        o["_customer_name"] = full_name
        # Ensure these columns always appear
        o.setdefault("base_currency_amount", 0.0)
        o.setdefault("tax_amount", 0.0)
        o.setdefault("tax_name", "")
        enriched.append(o)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await create_audit_log(
        entity_type="export", entity_id="orders",
        action="data_exported", actor=admin.get("email", "admin"),
        details={"records": len(enriched), "tenant_id": tenant_id_of(admin)},
    )
    return _make_csv_response(enriched, f"orders_{today}.csv")


@router.get("/admin/export/customers")
async def export_customers_csv(
    name_filter: Optional[str] = None,
    email_filter: Optional[str] = None,
    country_filter: Optional[str] = None,
    state_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    payment_mode_filter: Optional[str] = None,
    partner_filter: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    if not await _has_perm(admin, "customers", "view"):
        raise HTTPException(403, "No access to customers module")
    tf = get_tenant_filter(admin)
    customers = await db.customers.find(tf, {"_id": 0}).to_list(10000)
    cust_ids_all = [c["id"] for c in customers]
    user_ids_all = [c.get("user_id") for c in customers if c.get("user_id")]
    users = await db.users.find({"id": {"$in": user_ids_all}}, {"_id": 0, "password_hash": 0}).to_list(10000)
    addresses = await db.addresses.find({"customer_id": {"$in": cust_ids_all}}, {"_id": 0}).to_list(10000)

    user_map = {u["id"]: u for u in users}
    addr_map = {a["customer_id"]: a for a in addresses}

    # Pre-parse filter values
    name_vals = _split(name_filter)
    email_vals = _split(email_filter)
    country_vals = _split(country_filter)
    state_vals = _split(state_filter)
    status_vals = _split(status_filter)
    payment_mode_vals = _split(payment_mode_filter)
    partner_vals = _split(partner_filter)

    rows = []
    for c in customers:
        u = user_map.get(c.get("user_id"), {})
        a = addr_map.get(c["id"], {})

        email = u.get("email", "")
        full_name = u.get("full_name", "")
        is_active = u.get("is_active", True)

        # Fix: apply all active filters
        if email_vals and not any(v.lower() in email.lower() for v in email_vals):
            continue
        if name_vals and not any(v.lower() in full_name.lower() for v in name_vals):
            continue
        if country_vals and a.get("country", "") not in country_vals:
            continue
        if state_vals and a.get("region", "") not in state_vals:
            continue
        if status_vals:
            status_label = "Active" if is_active else "Inactive"
            if status_label not in status_vals:
                continue
        if payment_mode_vals:
            modes = c.get("allowed_payment_modes") or []
            if not any(m in modes for m in payment_mode_vals):
                continue
        if partner_vals:
            cust_partner = c.get("partner_code") or c.get("tenant_id", "")
            if cust_partner not in partner_vals:
                continue

        row = {**c}
        row["email"] = email
        row["full_name"] = full_name
        row["job_title"] = u.get("job_title", "")
        row["phone"] = u.get("phone", "") or c.get("phone", "")
        row["is_verified"] = u.get("is_verified", False)
        row["is_active"] = is_active
        row["role"] = u.get("role", "customer")
        row["line1"] = a.get("line1", "")
        row["line2"] = a.get("line2", "")
        row["city"] = a.get("city", "")
        row["region"] = a.get("region", "")
        row["postal"] = a.get("postal", "")
        row["country"] = a.get("country", "")
        rows.append(row)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await create_audit_log(
        entity_type="export", entity_id="customers",
        action="data_exported", actor=admin.get("email", "admin"),
        details={"records": len(rows), "tenant_id": tenant_id_of(admin)},
    )
    return _make_csv_response(rows, f"customers_{today}.csv")


@router.get("/admin/export/subscriptions")
async def export_subscriptions_csv(
    sort_by: str = "created_at",
    sort_order: str = "desc",
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    status: Optional[str] = None,
    payment_method: Optional[str] = None,
    currency_filter: Optional[str] = None,
    renewal_from: Optional[str] = None,
    renewal_to: Optional[str] = None,
    start_from: Optional[str] = None,
    start_to: Optional[str] = None,
    contract_end_from: Optional[str] = None,
    contract_end_to: Optional[str] = None,
    sub_number_filter: Optional[str] = None,
    email_filter: Optional[str] = None,
    plan_filter: Optional[str] = None,
    processor_id_filter: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    if not await _has_perm(admin, "subscriptions", "view"):
        raise HTTPException(403, "No access to subscriptions module")
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    if created_from:
        query.setdefault("created_at", {})["$gte"] = created_from
    if created_to:
        query.setdefault("created_at", {})["$lte"] = created_to + "T23:59:59"
    if status:
        statuses = _split(status)
        query["status"] = {"$in": statuses} if len(statuses) > 1 else statuses[0]
    if payment_method:
        methods = _split(payment_method)
        query["payment_method"] = {"$in": methods} if len(methods) > 1 else methods[0]
    if currency_filter:
        currencies = _split(currency_filter)
        query["currency"] = {"$in": currencies} if len(currencies) > 1 else currencies[0]
    if renewal_from:
        query.setdefault("renewal_date", {})["$gte"] = renewal_from
    if renewal_to:
        query.setdefault("renewal_date", {})["$lte"] = renewal_to + "T23:59:59"
    if start_from:
        query.setdefault("start_date", {})["$gte"] = start_from
    if start_to:
        query.setdefault("start_date", {})["$lte"] = start_to + "T23:59:59"
    if contract_end_from:
        query.setdefault("contract_end_date", {})["$gte"] = contract_end_from
    if contract_end_to:
        query.setdefault("contract_end_date", {})["$lte"] = contract_end_to + "T23:59:59"
    if sub_number_filter:
        sub_nums = _split(sub_number_filter)
        query["subscription_number"] = {"$in": sub_nums} if len(sub_nums) > 1 else {"$regex": _re.escape(sub_nums[0]), "$options": "i"}

    # Fix: plan_filter support
    if plan_filter:
        plans = _split(plan_filter)
        query["plan_name"] = {"$in": plans} if len(plans) > 1 else {"$regex": _re.escape(plans[0]), "$options": "i"}

    # Fix: processor_id_filter support
    if processor_id_filter:
        pids = _split(processor_id_filter)
        query["processor_id"] = {"$in": pids} if len(pids) > 1 else {"$regex": _re.escape(pids[0]), "$options": "i"}

    sort_dir = -1 if sort_order == "desc" else 1
    subs = await db.subscriptions.find(query, {"_id": 0}).sort(sort_by, sort_dir).to_list(10000)

    customer_ids = list({s.get("customer_id") for s in subs if s.get("customer_id")})
    customers = await db.customers.find({"id": {"$in": customer_ids}}, {"_id": 0}).to_list(10000)
    user_ids = [c.get("user_id") for c in customers if c.get("user_id")]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "password_hash": 0}).to_list(10000)
    customer_map = {c["id"]: c for c in customers}
    user_map = {u["id"]: u for u in users}

    # Fix: apply email filter after enrichment
    email_vals = _split(email_filter)

    enriched = []
    for s in subs:
        cust = customer_map.get(s.get("customer_id"), {})
        user = user_map.get(cust.get("user_id"), {})
        email = user.get("email", "")

        if email_vals and not any(v.lower() in email.lower() for v in email_vals):
            continue

        s["_customer_email"] = email
        s["_customer_name"] = user.get("full_name", "")
        # Ensure these columns always appear
        s.setdefault("base_currency_amount", 0.0)
        s.setdefault("tax_amount", 0.0)
        s.setdefault("tax_name", "")
        enriched.append(s)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Fix: add missing audit log
    await create_audit_log(
        entity_type="export", entity_id="subscriptions",
        action="data_exported", actor=admin.get("email", "admin"),
        details={"records": len(enriched), "tenant_id": tenant_id_of(admin)},
    )
    return _make_csv_response(enriched, f"subscriptions_{today}.csv")


@router.get("/admin/export/catalog")
async def export_catalog_csv(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    if not await _has_perm(admin, "products", "view"):
        raise HTTPException(403, "No access to products module")
    tf = get_tenant_filter(admin)
    products = await db.products.find(tf, {"_id": 0}).to_list(10000)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _make_csv_response(products, f"catalog_{today}.csv")


@router.get("/admin/export/articles")
async def export_articles_csv(
    category: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    if not await _has_perm(admin, "content", "view"):
        raise HTTPException(403, "No access to content module")
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    if category:
        query["category"] = category
    articles = await db.articles.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(articles, f"articles-{ts}.csv")


@router.get("/admin/export/categories")
async def export_categories_csv(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    if not await _has_perm(admin, "products", "view"):
        raise HTTPException(403, "No access to products module")
    tf = get_tenant_filter(admin)
    cats = await db.categories.find(tf, {"_id": 0}).sort("name", 1).to_list(1000)
    for cat in cats:
        cat["product_count"] = await db.products.count_documents({**tf, "category": cat["name"]})
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(cats, f"categories-{ts}.csv")


@router.get("/admin/export/terms")
async def export_terms_csv(
    search: Optional[str] = None,
    status: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    if not await _has_perm(admin, "content", "view"):
        raise HTTPException(403, "No access to content module")
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    # Fix: apply search filter on title
    if search:
        search_vals = _split(search)
        query["title"] = {"$regex": "|".join(_re.escape(v) for v in search_vals), "$options": "i"}
    # Fix: apply status filter (active = is_active true, inactive = false)
    if status:
        status_vals = _split(status)
        lower_vals = [v.lower() for v in status_vals]
        if "active" in lower_vals and "inactive" not in lower_vals:
            query["is_active"] = True
        elif "inactive" in lower_vals and "active" not in lower_vals:
            query["is_active"] = False
    terms = await db.terms_and_conditions.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(terms, f"terms-{ts}.csv")


@router.get("/admin/export/promo-codes")
async def export_promo_codes_csv(
    applies_to: Optional[str] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    if not await _has_perm(admin, "promo_codes", "view"):
        raise HTTPException(403, "No access to promo codes module")
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}

    # Fix: applies_to supports multi-value
    if applies_to:
        at_vals = _split(applies_to)
        query["applies_to"] = {"$in": at_vals} if len(at_vals) > 1 else at_vals[0]

    # Fix: search filter on code
    if search:
        search_vals = _split(search)
        query["code"] = {"$regex": "|".join(_re.escape(v) for v in search_vals), "$options": "i"}

    codes = await db.promo_codes.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)

    # Fix: status filter (computed from enabled, expiry_date, max_uses, usage_count)
    if status:
        status_vals = _split(status)
        now_iso = datetime.now(timezone.utc).isoformat()

        def _promo_status(p: Dict[str, Any]) -> str:
            if p.get("expiry_date") and p["expiry_date"] < now_iso:
                return "Expired"
            if p.get("max_uses") and (p.get("usage_count") or 0) >= p["max_uses"]:
                return "Inactive"
            if not p.get("enabled", True):
                return "Inactive"
            return "Active"

        codes = [c for c in codes if _promo_status(c) in status_vals]

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(codes, f"promo-codes-{ts}.csv")


@router.get("/admin/export/article-categories")
async def export_article_categories_csv(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    if not await _has_perm(admin, "content", "view"):
        raise HTTPException(403, "No access to content module")
    tf = get_tenant_filter(admin)
    cats = await db.article_categories.find(tf, {"_id": 0}).sort("name", 1).to_list(1000)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(cats, f"article-categories-{ts}.csv")


@router.get("/admin/export/article-templates")
async def export_article_templates_csv(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    if not await _has_perm(admin, "content", "view"):
        raise HTTPException(403, "No access to content module")
    tf = get_tenant_filter(admin)
    templates = await db.article_templates.find(tf, {"_id": 0}).sort("name", 1).to_list(1000)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(templates, f"article-templates-{ts}.csv")


# ── New: Resources export endpoints ─────────────────────────────────────────

@router.get("/admin/export/resources")
async def export_resources_csv(
    category: Optional[str] = None,
    search: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    if not await _has_perm(admin, "content", "view"):
        raise HTTPException(403, "No access to content module")
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    if category:
        cat_vals = _split(category)
        query["category"] = {"$in": cat_vals} if len(cat_vals) > 1 else cat_vals[0]
    if search:
        search_vals = _split(search)
        query["title"] = {"$regex": "|".join(_re.escape(v) for v in search_vals), "$options": "i"}
    resources = await db.resources.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(resources, f"resources-{ts}.csv")


@router.get("/admin/export/resource-categories")
async def export_resource_categories_csv(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    if not await _has_perm(admin, "content", "view"):
        raise HTTPException(403, "No access to content module")
    tf = get_tenant_filter(admin)
    cats = await db.resource_categories.find(tf, {"_id": 0}).sort("name", 1).to_list(1000)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(cats, f"resource-categories-{ts}.csv")


@router.get("/admin/export/resource-templates")
async def export_resource_templates_csv(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    if not await _has_perm(admin, "content", "view"):
        raise HTTPException(403, "No access to content module")
    tf = get_tenant_filter(admin)
    templates = await db.resource_templates.find(tf, {"_id": 0}).sort("name", 1).to_list(1000)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(templates, f"resource-templates-{ts}.csv")
