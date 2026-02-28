"""Admin audit trail / logs routes."""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from core.security import require_admin
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, get_tenant_admin, is_platform_admin, enrich_partner_codes
from db.session import db
from services.audit_service import AuditService

router = APIRouter(prefix="/api/admin/audit-logs", tags=["admin-logs"])


@router.get("/stats")
async def get_audit_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    """Summary statistics for the Audit Trail Dashboard."""
    tf = get_tenant_filter(admin)
    tid = tf.get("tenant_id")

    # Default to last 30 days
    effective_date_from = date_from or (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    base_flt: Dict[str, Any] = {}
    if tid:
        base_flt["tenant_id"] = tid

    period_flt: Dict[str, Any] = {**base_flt, "occurred_at": {"$gte": effective_date_from}}
    if date_to:
        period_flt["occurred_at"]["$lte"] = date_to + "T23:59:59"

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_flt: Dict[str, Any] = {**base_flt, "occurred_at": {"$gte": today_str}}

    async def _count_period() -> int:
        return await db.audit_trail.count_documents(period_flt)

    async def _count_errors() -> int:
        return await db.audit_trail.count_documents({**period_flt, "success": False})

    async def _count_today() -> int:
        return await db.audit_trail.count_documents(today_flt)

    async def _by_actor_type() -> Dict[str, int]:
        pipeline = [
            {"$match": period_flt},
            {"$group": {"_id": "$actor_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        results = await db.audit_trail.aggregate(pipeline).to_list(10)
        return {(r["_id"] or "unknown"): r["count"] for r in results}

    async def _top_actions() -> list:
        pipeline = [
            {"$match": period_flt},
            {"$group": {"_id": "$action", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 8},
        ]
        results = await db.audit_trail.aggregate(pipeline).to_list(8)
        return [{"action": r["_id"], "count": r["count"]} for r in results]

    async def _top_entity_types() -> list:
        pipeline = [
            {"$match": period_flt},
            {"$group": {"_id": "$entity_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 8},
        ]
        results = await db.audit_trail.aggregate(pipeline).to_list(8)
        return [{"entity_type": r["_id"], "count": r["count"]} for r in results]

    total, errors, today, by_actor, top_actions, top_entity = await asyncio.gather(
        _count_period(), _count_errors(), _count_today(),
        _by_actor_type(), _top_actions(), _top_entity_types(),
    )

    return {
        "total": total,
        "errors": errors,
        "today": today,
        "by_actor_type": by_actor,
        "top_actions": top_actions,
        "top_entity_types": top_entity,
        "date_from": effective_date_from,
        "date_to": date_to,
    }


@router.get("")
async def list_audit_logs(
    actor: Optional[str] = None,
    actor_type: Optional[str] = None,      # admin | system | user | webhook
    source: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    action: Optional[str] = None,
    success: Optional[str] = None,         # "true" | "false" | None
    severity: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    cursor: Optional[str] = None,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    success_bool: Optional[bool] = None
    if success == "true":
        success_bool = True
    elif success == "false":
        success_bool = False

    per_page = min(limit, 100)
    common = dict(
        actor=actor or None,
        actor_type=actor_type or None,
        source=source or None,
        entity_type=entity_type or None,
        entity_id=entity_id or None,
        action=action or None,
        success=success_bool,
        severity=severity or None,
        date_from=date_from or None,
        date_to=date_to or None,
        q=q or None,
    )

    total, (records, next_cursor) = await _parallel_query(common, page, per_page, cursor, get_tenant_filter(admin))
    records = await enrich_partner_codes(records, is_platform_admin(admin))

    return {
        "logs": records,
        "next_cursor": next_cursor,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


async def _parallel_query(common: dict, page: int, per_page: int, cursor: Optional[str], tenant_filter: dict = {}):
    """Run count and query in parallel, respecting tenant isolation."""
    import asyncio
    # Extract tenant_id from filter and pass directly to AuditService
    tenant_id = tenant_filter.get("tenant_id") if tenant_filter else None
    params = {**common, "tenant_id": tenant_id} if tenant_id else common
    total_task = AuditService.count(**params)
    query_task = AuditService.query(**params, page=page, limit=per_page, before_cursor=cursor)
    return await asyncio.gather(total_task, query_task)


@router.get("/{log_id}")
async def get_audit_log(
    log_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    from db.session import db
    log = await db.audit_trail.find_one({"id": log_id}, {"_id": 0})
    if not log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Log entry not found")
    return {"log": log}
