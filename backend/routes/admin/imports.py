"""Admin: CSV import routes with upsert (create + update by id)."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, get_tenant_filter, tenant_id_of
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-imports"])

# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_val(v: str) -> Any:
    """Try to parse JSON for nested fields; otherwise return as-is."""
    if not v or not isinstance(v, str):
        return v
    stripped = v.strip()
    if stripped.startswith(("{", "[")):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    return stripped


def _parse_csv(content: bytes) -> List[Dict[str, str]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _clean(row: Dict[str, str], required_fields: List[str]) -> Optional[str]:
    """Return error string if required fields are missing, else None."""
    for f in required_fields:
        if not (row.get(f) or "").strip():
            return f"Missing required field: {f}"
    return None


ENTITY_COLLECTIONS: Dict[str, str] = {
    "customers": "customers",
    "subscriptions": "subscriptions",
    "orders": "orders",
    "promo-codes": "promo_codes",
    "quote-requests": "quote_requests",
    "bank-transactions": "bank_transactions",
    "articles": "articles",
    "article-templates": "article_templates",
    "article-categories": "article_categories",
    "override-codes": "override_codes",
    "categories": "categories",
    "catalog": "products",
    "terms": "terms_and_conditions",
}

# Fields that contain JSON-serialized nested data
JSON_FIELDS: Dict[str, List[str]] = {
    "catalog": [
        "price_inputs", "intake_schema_json", "faqs", "bullets_included",
        "bullets_excluded", "bullets_needed", "card_bullets", "pricing_rules",
        "custom_sections", "requirements", "inclusions", "exclusions",
        "next_steps", "automation_details", "support_details",
    ],
    "articles": ["restricted_to", "tags", "sections"],
    "article-templates": ["sections", "variables"],
    "customers": ["payment_modes_available"],
    "subscriptions": ["metadata"],
    "orders": ["items", "metadata"],
    "quote-requests": ["fields", "answers"],
}

REQUIRED_FIELDS: Dict[str, List[str]] = {
    "customers": ["email"],
    "subscriptions": ["customer_id"],
    "orders": ["customer_id"],
    "promo-codes": ["code"],
    "quote-requests": ["email"],
    "bank-transactions": ["date", "description"],
    "articles": ["title"],
    "article-templates": ["name"],
    "article-categories": ["name"],
    "override-codes": ["code"],
    "categories": ["name"],
    "catalog": ["name"],
    "terms": ["title"],
}


def _build_doc(row: Dict[str, str], entity: str, tid: str, existing_id: Optional[str]) -> Dict[str, Any]:
    """Convert a CSV row dict into a MongoDB document."""
    json_fields = JSON_FIELDS.get(entity, [])
    doc: Dict[str, Any] = {}
    for key, val in row.items():
        key = key.strip()
        if not key:
            continue
        if key in json_fields:
            doc[key] = _parse_val(val)
        else:
            doc[key] = _parse_val(val)
    # Ensure tenant isolation
    doc["tenant_id"] = tid
    # Remove empty strings for non-required fields
    doc = {k: v for k, v in doc.items() if v != "" and v is not None}
    if existing_id:
        # UPDATE: add updated_at, keep id
        doc["updated_at"] = now_iso()
        doc.pop("id", None)  # don't overwrite id from CSV row
        doc.pop("tenant_id", None)  # don't allow changing tenant
    else:
        # CREATE: generate id if not present
        if not doc.get("id"):
            doc["id"] = make_id()
        doc["created_at"] = doc.get("created_at") or now_iso()
        doc["updated_at"] = now_iso()
    return doc


@router.post("/admin/import/{entity}")
async def import_entity(
    entity: str,
    file: UploadFile = File(...),
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Upsert records from a CSV file. Rows with an existing 'id' are updated; others are created."""
    collection_name = ENTITY_COLLECTIONS.get(entity)
    if not collection_name:
        raise HTTPException(status_code=400, detail=f"Unknown entity: {entity}. Valid: {list(ENTITY_COLLECTIONS)}")

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()

    # File size limit: 10 MB
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum allowed size is 10 MB.")

    # Content-type sanity check (must look like text, not binary)
    try:
        content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File does not appear to be a valid UTF-8 CSV.")
    try:
        rows = _parse_csv(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {e}")

    if not rows:
        return {"created": 0, "updated": 0, "errors": [], "total": 0}

    # Row count safety limit
    MAX_ROWS = 5000
    if len(rows) > MAX_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"CSV has too many rows ({len(rows)}). Maximum allowed is {MAX_ROWS} rows per import."
        )

    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    collection = getattr(db, collection_name)
    required = REQUIRED_FIELDS.get(entity, [])

    created = 0
    updated = 0
    errors: List[Dict[str, Any]] = []

    for i, row in enumerate(rows, start=2):  # row 1 is header
        # Skip blank rows
        if not any((v or "").strip() for v in row.values()):
            continue

        err = _clean(row, required)
        if err:
            errors.append({"row": i, "error": err, "data": row})
            continue

        row_id = (row.get("id") or "").strip()
        try:
            if row_id:
                # Check if record exists for this tenant
                existing = await collection.find_one({**tf, "id": row_id}, {"_id": 0, "id": 1})
                if existing:
                    doc = _build_doc(row, entity, tid, existing_id=row_id)
                    await collection.update_one({"id": row_id, "tenant_id": tid}, {"$set": doc})
                    updated += 1
                    continue
            # CREATE
            doc = _build_doc(row, entity, tid, existing_id=None)
            await collection.insert_one(doc)
            created += 1
        except Exception as e:
            errors.append({"row": i, "error": str(e), "data": row})

    return {
        "created": created,
        "updated": updated,
        "errors": errors[:50],  # cap error list
        "total": len(rows),
        "skipped": len(rows) - created - updated - len(errors),
    }


# ── Sample template download ─────────────────────────────────────────────────

TEMPLATES: Dict[str, List[str]] = {
    "customers": [
        "id", "email", "full_name", "company_name", "country", "state_province",
        "currency", "status", "payment_mode", "partner_map_id", "notes",
    ],
    "subscriptions": [
        "id", "customer_id", "product_id", "product_name", "billing_cycle",
        "amount", "currency", "status", "start_date", "end_date", "next_billing_date",
        "stripe_subscription_id", "notes",
    ],
    "orders": [
        "id", "customer_id", "order_number", "status", "total_amount", "currency",
        "items", "payment_method", "created_at", "notes",
    ],
    "promo-codes": [
        "id", "code", "discount_type", "discount_value", "max_uses",
        "used_count", "expires_at", "is_active", "applicable_products", "description",
    ],
    "quote-requests": [
        "id", "email", "full_name", "product_name", "status", "notes",
        "fields", "created_at",
    ],
    "bank-transactions": [
        "id", "date", "description", "amount", "currency", "type",
        "reference", "reconciled", "notes",
    ],
    "articles": [
        "id", "title", "slug", "category", "status", "content",
        "visible_to_customers", "restricted_to", "tags", "created_at",
    ],
    "article-templates": [
        "id", "name", "category", "description", "content", "sections",
        "variables", "created_at",
    ],
    "article-categories": [
        "id", "name", "slug", "description", "display_order", "is_active",
    ],
    "override-codes": [
        "id", "code", "type", "value", "description", "is_active",
        "expires_at", "max_uses", "used_count",
    ],
    "categories": [
        "id", "name", "description", "is_active", "display_order",
    ],
    "catalog": [
        "id", "name", "sku", "category", "tagline", "short_description",
        "description", "base_price", "currency", "billing_period",
        "pricing_type", "is_active", "is_subscription", "visible_to_customers",
        "tag", "stripe_price_id", "terms_id",
        "price_inputs", "intake_schema_json", "faqs",
        "bullets_included", "bullets_excluded", "bullets_needed",
        "custom_sections", "requirements", "inclusions", "exclusions",
        "next_steps", "automation_details", "support_details",
    ],
    "terms": [
        "id", "title", "content", "version", "is_active", "created_at",
    ],
}

SAMPLE_DATA: Dict[str, List[Dict[str, Any]]] = {
    "customers": [{"email": "customer@example.com", "full_name": "Jane Smith", "company_name": "Acme Ltd", "country": "GB", "currency": "GBP", "status": "active"}],
    "subscriptions": [{"customer_id": "cust_xxx", "product_id": "prod_xxx", "product_name": "Monthly Plan", "billing_cycle": "monthly", "amount": "99.00", "currency": "GBP", "status": "active", "start_date": "2025-01-01"}],
    "orders": [{"customer_id": "cust_xxx", "status": "complete", "total_amount": "199.00", "currency": "GBP", "items": '[{"product_name":"Setup","quantity":1,"price":199.0}]'}],
    "promo-codes": [{"code": "SAVE20", "discount_type": "percentage", "discount_value": "20", "max_uses": "100", "is_active": "true", "expires_at": "2026-12-31"}],
    "quote-requests": [{"email": "lead@example.com", "full_name": "John Doe", "product_name": "Enterprise Plan", "status": "pending", "notes": "Interested in annual pricing"}],
    "bank-transactions": [{"date": "2025-01-15", "description": "Client payment", "amount": "500.00", "currency": "GBP", "type": "credit", "reference": "INV-001", "reconciled": "false"}],
    "articles": [{"title": "Getting Started Guide", "slug": "getting-started", "category": "Setup Guides", "status": "published", "content": "<h1>Welcome</h1><p>This guide helps you get started.</p>", "visible_to_customers": "true"}],
    "article-templates": [{"name": "Monthly Report Template", "category": "Reports", "content": "<h1>Monthly Report</h1><p>{{company_name}}</p>"}],
    "article-categories": [{"name": "Setup Guides", "slug": "setup-guides", "description": "Step-by-step guides for setting up your account", "is_active": "true", "display_order": "1"}],
    "override-codes": [{"code": "OVERRIDE123", "type": "discount", "value": "50", "description": "Partner override code", "is_active": "true"}],
    "categories": [{"name": "Accounting Services", "description": "Bookkeeping and accounting services", "is_active": "true", "display_order": "1"}],
    "catalog": [{"name": "Starter Package", "sku": "START-001", "category": "Accounting Services", "tagline": "Perfect for small businesses", "base_price": "499.00", "currency": "GBP", "billing_period": "monthly", "pricing_type": "fixed", "is_active": "true", "is_subscription": "true", "visible_to_customers": "true", "price_inputs": "[]", "intake_schema_json": "[]", "faqs": "[]", "bullets_included": '["Bookkeeping","VAT returns"]'}],
    "terms": [{"title": "Standard Service Agreement", "content": "<h1>Terms</h1><p>This agreement...</p>", "version": "1.0", "is_active": "true"}],
}


@router.get("/admin/import/template/{entity}")
async def download_import_template(
    entity: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Download a sample CSV import template for the given entity."""
    columns = TEMPLATES.get(entity)
    if not columns:
        raise HTTPException(status_code=400, detail=f"Unknown entity: {entity}")

    samples = SAMPLE_DATA.get(entity, [{}])
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for sample in samples:
        # Serialize any list/dict values as JSON
        row = {}
        for col in columns:
            v = sample.get(col, "")
            row[col] = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else (v or "")
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="import_template_{entity}.csv"'},
    )
