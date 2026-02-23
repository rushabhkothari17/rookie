"""Admin: CSV export routes."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from core.security import require_admin
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, get_tenant_admin
from db.session import db

router = APIRouter(prefix="/api", tags=["admin-exports"])


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
        writer.writerow({k: str(row.get(k, "")) for k in all_keys})

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/export/orders")
async def export_orders_csv(
    sort_by: str = "created_at",
    sort_order: str = "desc",
    include_deleted: bool = False,
    product_filter: Optional[str] = None,
    order_number_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    email_filter: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    query: Dict[str, Any] = {**tf}
    if not include_deleted:
        query["deleted_at"] = {"$exists": False}
    if order_number_filter:
        query["order_number"] = {"$regex": order_number_filter, "$options": "i"}
    if status_filter:
        query["status"] = status_filter

    sort_dir = -1 if sort_order == "desc" else 1
    orders = await db.orders.find(query, {"_id": 0}).sort(sort_by, sort_dir).to_list(10000)

    customer_ids = list({o.get("customer_id") for o in orders if o.get("customer_id")})
    customers = await db.customers.find({"id": {"$in": customer_ids}}, {"_id": 0}).to_list(1000)
    user_ids = [c.get("user_id") for c in customers]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "password_hash": 0}).to_list(1000)
    customer_map = {c["id"]: c for c in customers}
    user_map = {u["id"]: u for u in users}

    enriched = []
    for o in orders:
        cust = customer_map.get(o.get("customer_id"), {})
        user = user_map.get(cust.get("user_id"), {})
        if email_filter and email_filter.lower() not in (user.get("email", "")).lower():
            continue
        o["_customer_email"] = user.get("email", "")
        o["_customer_name"] = user.get("full_name", "")
        enriched.append(o)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _make_csv_response(enriched, f"orders_{today}.csv")


@router.get("/admin/export/customers")
async def export_customers_csv(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    customers = await db.customers.find(tf, {"_id": 0}).to_list(10000)
    user_ids_all = [c.get("user_id") for c in customers if c.get("user_id")]
    users = await db.users.find({"id": {"$in": user_ids_all}}, {"_id": 0, "password_hash": 0}).to_list(10000)
    cust_ids_all = [c["id"] for c in customers]
    addresses = await db.addresses.find({"customer_id": {"$in": cust_ids_all}}, {"_id": 0}).to_list(10000)

    user_map = {u["id"]: u for u in users}
    addr_map = {a["customer_id"]: a for a in addresses}

    rows = []
    for c in customers:
        u = user_map.get(c.get("user_id"), {})
        a = addr_map.get(c["id"], {})
        row = {**c}
        row["email"] = u.get("email", "")
        row["full_name"] = u.get("full_name", "")
        row["job_title"] = u.get("job_title", "")
        row["phone"] = u.get("phone", "")
        row["is_verified"] = u.get("is_verified", False)
        row["is_active"] = u.get("is_active", True)
        row["role"] = u.get("role", "customer")
        row["line1"] = a.get("line1", "")
        row["line2"] = a.get("line2", "")
        row["city"] = a.get("city", "")
        row["region"] = a.get("region", "")
        row["postal"] = a.get("postal", "")
        row["country"] = a.get("country", "")
        rows.append(row)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _make_csv_response(rows, f"customers_{today}.csv")


@router.get("/admin/export/subscriptions")
async def export_subscriptions_csv(
    sort_by: str = "created_at",
    sort_order: str = "desc",
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    query: Dict[str, Any] = {}
    if created_from:
        query.setdefault("created_at", {})["$gte"] = created_from
    if created_to:
        query.setdefault("created_at", {})["$lte"] = created_to + "T23:59:59"

    sort_dir = -1 if sort_order == "desc" else 1
    subs = await db.subscriptions.find(query, {"_id": 0}).sort(sort_by, sort_dir).to_list(10000)

    customer_ids = list({s.get("customer_id") for s in subs if s.get("customer_id")})
    customers = await db.customers.find({"id": {"$in": customer_ids}}, {"_id": 0}).to_list(1000)
    user_ids = [c.get("user_id") for c in customers]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "password_hash": 0}).to_list(1000)
    customer_map = {c["id"]: c for c in customers}
    user_map = {u["id"]: u for u in users}

    for s in subs:
        cust = customer_map.get(s.get("customer_id"), {})
        user = user_map.get(cust.get("user_id"), {})
        s["_customer_email"] = user.get("email", "")
        s["_customer_name"] = user.get("full_name", "")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _make_csv_response(subs, f"subscriptions_{today}.csv")


@router.get("/admin/export/catalog")
async def export_catalog_csv(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    products = await db.products.find({}, {"_id": 0}).to_list(10000)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _make_csv_response(products, f"catalog_{today}.csv")


@router.get("/admin/export/quote-requests")
async def export_quote_requests_csv(
    status: Optional[str] = None,
    email: Optional[str] = None,
    product: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if email:
        query["email"] = {"$regex": email, "$options": "i"}
    if product:
        query["product_name"] = {"$regex": product, "$options": "i"}
    if date_from:
        query.setdefault("created_at", {})["$gte"] = date_from
    if date_to:
        query.setdefault("created_at", {})["$lte"] = date_to + "T23:59:59"
    quotes = await db.quote_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(quotes, f"quote-requests-{ts}.csv")


@router.get("/admin/export/articles")
async def export_articles_csv(
    category: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    query: Dict[str, Any] = {}
    if category:
        query["category"] = category
    articles = await db.articles.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(articles, f"articles-{ts}.csv")


@router.get("/admin/export/categories")
async def export_categories_csv(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    cats = await db.categories.find({}, {"_id": 0}).sort("name", 1).to_list(1000)
    for cat in cats:
        cat["product_count"] = await db.products.count_documents({"category": cat["name"]})
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(cats, f"categories-{ts}.csv")


@router.get("/admin/export/terms")
async def export_terms_csv(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    terms = await db.terms_and_conditions.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(terms, f"terms-{ts}.csv")


@router.get("/admin/export/override-codes")
async def export_override_codes_csv(
    status: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    codes = await db.override_codes.find({}, {"_id": 0}).sort("created_at", -1).to_list(10000)
    if status:
        codes = [c for c in codes if c.get("status") == status]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(codes, f"override-codes-{ts}.csv")


@router.get("/admin/export/promo-codes")
async def export_promo_codes_csv(
    applies_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    query: Dict[str, Any] = {}
    if applies_to:
        query["applies_to"] = applies_to
    codes = await db.promo_codes.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return _make_csv_response(codes, f"promo-codes-{ts}.csv")
