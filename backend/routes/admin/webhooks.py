"""Admin: Webhook endpoint management and delivery logs."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, get_tenant_filter, tenant_id_of
from db.session import db
from services.audit_service import create_audit_log
from services.webhook_service import EVENT_CATALOG, _validate_webhook_url

router = APIRouter(prefix="/api", tags=["admin-webhooks"])


def _gen_secret() -> str:
    return f"whsec_{secrets.token_hex(24)}"


def _validate_url(url: str) -> None:
    """Validate webhook URL — rejects private/internal IPs (SSRF protection)."""
    try:
        _validate_webhook_url(url.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _validate_subscriptions(subs: List[Dict[str, Any]]) -> None:
    for s in subs:
        event = s.get("event", "")
        if event not in EVENT_CATALOG:
            raise HTTPException(status_code=400, detail=f"Unknown event: '{event}'")
        fields = s.get("fields") or []
        allowed = set(EVENT_CATALOG[event]["fields"].keys())
        bad = [f for f in fields if f not in allowed]
        if bad:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown fields for event '{event}': {bad}. Allowed: {sorted(allowed)}",
            )


# ── Event catalog ────────────────────────────────────────────────────────────

@router.get("/admin/webhooks/events")
async def get_event_catalog(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Return the full event catalog with available fields per event."""
    return {"events": EVENT_CATALOG}


# ── Delivery Stats (must be before {webhook_id} to avoid route conflict) ─────

@router.get("/admin/webhooks/delivery-stats")
async def get_delivery_stats(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Get aggregated delivery statistics for all webhooks."""
    tf = get_tenant_filter(admin)
    
    # Get all webhook IDs for this tenant
    webhooks = await db.webhooks.find(tf, {"_id": 0, "id": 1, "name": 1}).to_list(100)
    webhook_ids = [w["id"] for w in webhooks]
    
    if not webhook_ids:
        return {
            "total_deliveries": 0,
            "success_count": 0,
            "failed_count": 0,
            "pending_count": 0,
            "success_rate": 0,
            "recent_failures": []
        }
    
    # Count by status
    pipeline = [
        {"$match": {"webhook_id": {"$in": webhook_ids}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    status_counts = await db.webhook_deliveries.aggregate(pipeline).to_list(10)
    counts = {s["_id"]: s["count"] for s in status_counts}
    
    total = sum(counts.values())
    success = counts.get("success", 0)
    failed = counts.get("failed", 0)
    pending = counts.get("pending", 0)
    
    # Get recent failures
    recent_failures = await db.webhook_deliveries.find(
        {"webhook_id": {"$in": webhook_ids}, "status": "failed"},
        {"_id": 0, "id": 1, "webhook_id": 1, "event": 1, "error": 1, "response_status": 1, "created_at": 1}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    # Add webhook names
    webhook_map = {w["id"]: w["name"] for w in webhooks}
    for f in recent_failures:
        f["webhook_name"] = webhook_map.get(f["webhook_id"], "Unknown")
    
    return {
        "total_deliveries": total,
        "success_count": success,
        "failed_count": failed,
        "pending_count": pending,
        "success_rate": round((success / total * 100) if total > 0 else 0, 1),
        "recent_failures": recent_failures
    }


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.get("/admin/webhooks")
async def list_webhooks(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    webhooks = await db.webhooks.find(tf, {"_id": 0, "secret": 0}).sort("created_at", -1).to_list(100)
    # Mask the secret in list view
    return {"webhooks": webhooks}


@router.post("/admin/webhooks")
async def create_webhook(
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    url = (payload.get("url") or "").strip()
    _validate_url(url)

    name = (payload.get("name") or "My Webhook").strip()[:120]
    secret = (payload.get("secret") or _gen_secret()).strip()
    # Accept both full subscriptions format and shorthand events list
    subscriptions = payload.get("subscriptions") or []
    if not subscriptions and payload.get("events"):
        from services.webhook_service import _DEFAULT_FIELDS
        subscriptions = [
            {"event": e, "fields": _DEFAULT_FIELDS.get(e, [])}
            for e in payload["events"]
            if isinstance(e, str)
        ]
    _validate_subscriptions(subscriptions)

    tid = tenant_id_of(admin)
    wh_id = make_id()
    doc = {
        "id": wh_id,
        "tenant_id": tid,
        "name": name,
        "url": url,
        "secret": secret,
        "is_active": True,
        "subscriptions": subscriptions,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.webhooks.insert_one(doc)
    await create_audit_log(
        entity_type="webhook", entity_id=wh_id,
        action="webhook_created",
        actor=admin.get("email", "admin"),
        details={"name": name, "url": url, "events": [s["event"] for s in subscriptions]},
    )
    doc.pop("_id", None)
    # Return secret once on creation (then never shown again)
    return {**{k: v for k, v in doc.items() if k != "secret"}, "secret": secret}


@router.get("/admin/webhooks/{webhook_id}")
async def get_webhook(webhook_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    wh = await db.webhooks.find_one({**tf, "id": webhook_id}, {"_id": 0, "secret": 0})
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return wh


@router.put("/admin/webhooks/{webhook_id}")
async def update_webhook(
    webhook_id: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    existing = await db.webhooks.find_one({**tf, "id": webhook_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Webhook not found")

    updates: Dict[str, Any] = {"updated_at": now_iso()}

    if "name" in payload:
        updates["name"] = (payload["name"] or "").strip()[:120]
    if "url" in payload:
        _validate_url(payload["url"])
        updates["url"] = payload["url"].strip()
    if "is_active" in payload:
        updates["is_active"] = bool(payload["is_active"])
    if "secret" in payload and payload["secret"]:
        updates["secret"] = payload["secret"].strip()
    if "subscriptions" in payload:
        subs = payload["subscriptions"] or []
        # Accept shorthand events list too
        if not subs and payload.get("events"):
            from services.webhook_service import _DEFAULT_FIELDS
            subs = [
                {"event": e, "fields": _DEFAULT_FIELDS.get(e, [])}
                for e in payload["events"]
                if isinstance(e, str)
            ]
        _validate_subscriptions(subs)
        updates["subscriptions"] = subs
    elif "events" in payload:
        from services.webhook_service import _DEFAULT_FIELDS
        subs = [
            {"event": e, "fields": _DEFAULT_FIELDS.get(e, [])}
            for e in (payload["events"] or [])
            if isinstance(e, str)
        ]
        _validate_subscriptions(subs)
        updates["subscriptions"] = subs

    await db.webhooks.update_one({"id": webhook_id}, {"$set": updates})
    await create_audit_log(
        entity_type="webhook", entity_id=webhook_id,
        action="webhook_updated",
        actor=admin.get("email", "admin"),
        details={"changes": list(updates.keys())},
    )
    updated = await db.webhooks.find_one({"id": webhook_id}, {"_id": 0, "secret": 0})
    return updated


@router.delete("/admin/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    result = await db.webhooks.delete_one({**tf, "id": webhook_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await create_audit_log(
        entity_type="webhook", entity_id=webhook_id,
        action="webhook_deleted",
        actor=admin.get("email", "admin"),
        details={},
    )
    return {"success": True}


@router.post("/admin/webhooks/{webhook_id}/rotate-secret")
async def rotate_secret(webhook_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    new_secret = _gen_secret()
    result = await db.webhooks.update_one(
        {**tf, "id": webhook_id},
        {"$set": {"secret": new_secret, "updated_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await create_audit_log(
        entity_type="webhook", entity_id=webhook_id,
        action="webhook_secret_rotated",
        actor=admin.get("email", "admin"),
        details={},
    )
    return {"secret": new_secret, "message": "Copy this new secret now — it will not be shown again."}


# ── Test delivery ─────────────────────────────────────────────────────────────

@router.post("/admin/webhooks/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Send a test payload to the webhook URL immediately (no retry). Returns delivery result."""
    tf = get_tenant_filter(admin)
    wh = await db.webhooks.find_one({**tf, "id": webhook_id}, {"_id": 0})
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")

    event = payload.get("event", "order.created")
    test_payload = {
        "event": event,
        "webhook_id": webhook_id,
        "tenant_id": tenant_id_of(admin),
        "timestamp": now_iso(),
        "test": True,
        "data": {"message": f"This is a test delivery for event '{event}'", "id": "test_001"},
    }
    body = json.dumps(test_payload, default=str).encode()
    sig = hmac.new(wh["secret"].encode(), body, hashlib.sha256).hexdigest()
    delivery_id = make_id()

    # Pre-create delivery record so it always appears in logs
    await db.webhook_deliveries.insert_one({
        "id": delivery_id,
        "webhook_id": webhook_id,
        "tenant_id": tenant_id_of(admin),
        "event": event,
        "payload": test_payload,
        "attempts": 1,
        "status": "pending",
        "response_status": None,
        "response_body": None,
        "error": None,
        "is_test": True,
        "created_at": now_iso(),
        "last_attempt_at": now_iso(),
        "delivered_at": None,
    })

    # SSRF guard — re-validate URL at delivery time to catch DNS rebinding
    try:
        _validate_webhook_url(wh["url"])
    except ValueError as exc:
        await db.webhook_deliveries.update_one(
            {"id": delivery_id},
            {"$set": {"status": "failed", "error": f"SSRF_BLOCKED: {exc}"[:300]}}
        )
        raise HTTPException(status_code=400, detail=f"Webhook URL blocked: {exc}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                wh["url"],
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Event": event,
                    "X-Webhook-Signature": f"sha256={sig}",
                    "X-Webhook-Delivery": delivery_id,
                    "User-Agent": "AutomateAccounts-Webhook/1.0",
                },
            )
        success = 200 <= resp.status_code < 300
        await db.webhook_deliveries.update_one(
            {"id": delivery_id},
            {"$set": {
                "status": "success" if success else "failed",
                "response_status": resp.status_code,
                "response_body": resp.text[:500],
                **({"delivered_at": now_iso()} if success else {}),
            }}
        )
        return {"success": success, "status_code": resp.status_code, "body": resp.text[:500], "delivery_id": delivery_id}
    except Exception as exc:
        await db.webhook_deliveries.update_one(
            {"id": delivery_id},
            {"$set": {"status": "failed", "error": str(exc)[:300]}}
        )
        return {"success": False, "status_code": 0, "body": str(exc)[:300], "delivery_id": delivery_id}


# ── Delivery logs ─────────────────────────────────────────────────────────────

@router.get("/admin/webhooks/{webhook_id}/logs")
async def get_webhook_audit_logs(webhook_id: str, page: int = 1, limit: int = 20,
                                  admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Audit trail for webhook config changes (create/update/delete/rotate-secret)."""
    tf = get_tenant_filter(admin)
    wh = await db.webhooks.find_one({**tf, "id": webhook_id}, {"_id": 0, "id": 1})
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    flt = {"entity_type": "webhook", "entity_id": webhook_id}
    total = await db.audit_logs.count_documents(flt)
    logs = await db.audit_logs.find(flt, {"_id": 0}).sort("timestamp", -1).skip((page - 1) * limit).limit(limit).to_list(limit)
    return {"logs": logs, "total": total}

@router.get("/admin/webhooks/{webhook_id}/deliveries")
async def get_deliveries(
    webhook_id: str,
    page: int = 1,
    per_page: int = 25,
    status: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    # Verify ownership
    wh = await db.webhooks.find_one({**tf, "id": webhook_id}, {"_id": 0, "id": 1})
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")

    query: Dict[str, Any] = {"webhook_id": webhook_id}
    if status:
        query["status"] = status

    total = await db.webhook_deliveries.count_documents(query)
    skip = (page - 1) * per_page
    deliveries = (
        await db.webhook_deliveries.find(query, {"_id": 0, "payload": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(per_page)
        .to_list(per_page)
    )
    return {
        "deliveries": deliveries,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


@router.get("/admin/webhooks/{webhook_id}/deliveries/{delivery_id}")
async def get_delivery_detail(
    webhook_id: str,
    delivery_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    wh = await db.webhooks.find_one({**tf, "id": webhook_id}, {"_id": 0, "id": 1})
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    delivery = await db.webhook_deliveries.find_one(
        {"id": delivery_id, "webhook_id": webhook_id}, {"_id": 0}
    )
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery


@router.post("/admin/webhooks/{webhook_id}/deliveries/{delivery_id}/replay")
async def replay_delivery(
    webhook_id: str,
    delivery_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Replay a failed webhook delivery with the original payload."""
    tf = get_tenant_filter(admin)
    wh = await db.webhooks.find_one({**tf, "id": webhook_id}, {"_id": 0})
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    delivery = await db.webhook_deliveries.find_one(
        {"id": delivery_id, "webhook_id": webhook_id}, {"_id": 0}
    )
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    # Get the original payload
    payload = delivery.get("payload")
    if not payload:
        raise HTTPException(status_code=400, detail="No payload found for this delivery")
    
    # Mark as replaying
    await db.webhook_deliveries.update_one(
        {"id": delivery_id},
        {"$set": {"status": "pending", "last_attempt_at": now_iso()}}
    )

    # SSRF guard — re-validate URL at delivery time to catch DNS rebinding
    try:
        _validate_webhook_url(wh["url"])
    except ValueError as exc:
        await db.webhook_deliveries.update_one(
            {"id": delivery_id},
            {"$set": {"status": "failed", "error": f"SSRF_BLOCKED: {exc}"[:300]}}
        )
        return {"success": False, "status_code": 0, "body": str(exc)[:300], "message": "Webhook URL blocked (SSRF protection)"}

    # Re-send the webhook
    body = json.dumps(payload, default=str).encode()
    sig = hmac.new(wh["secret"].encode(), body, hashlib.sha256).hexdigest()
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                wh["url"],
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Event": delivery.get("event", "unknown"),
                    "X-Webhook-Signature": f"sha256={sig}",
                    "X-Webhook-Delivery": delivery_id,
                    "X-Webhook-Replay": "true",
                    "User-Agent": "AutomateAccounts-Webhook/1.0",
                },
            )
        
        success = 200 <= resp.status_code < 300
        await db.webhook_deliveries.update_one(
            {"id": delivery_id},
            {"$set": {
                "status": "success" if success else "failed",
                "response_status": resp.status_code,
                "response_body": resp.text[:1000],
                "delivered_at": now_iso() if success else None,
                "attempts": (delivery.get("attempts", 0) or 0) + 1,
                "last_attempt_at": now_iso(),
            }}
        )
        
        await create_audit_log(
            entity_type="webhook",
            entity_id=webhook_id,
            action="delivery_replayed",
            actor=admin.get("email", "admin"),
            details={"delivery_id": delivery_id, "success": success, "status_code": resp.status_code},
        )
        
        return {
            "success": success,
            "status_code": resp.status_code,
            "body": resp.text[:500],
            "message": "Replay successful" if success else f"Replay failed with status {resp.status_code}"
        }
    except Exception as exc:
        await db.webhook_deliveries.update_one(
            {"id": delivery_id},
            {"$set": {
                "status": "failed",
                "error": str(exc)[:500],
                "attempts": (delivery.get("attempts", 0) or 0) + 1,
                "last_attempt_at": now_iso(),
            }}
        )
        return {"success": False, "status_code": 0, "body": str(exc)[:300], "message": "Replay failed"}
