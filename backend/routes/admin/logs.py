"""Admin audit trail / logs routes."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from core.security import require_admin
from services.audit_service import AuditService

router = APIRouter(prefix="/api/admin/audit-logs", tags=["admin-logs"])


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
    admin: Dict[str, Any] = Depends(require_admin),
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

    total, (records, next_cursor) = await _parallel_query(common, page, per_page, cursor)

    return {
        "logs": records,
        "next_cursor": next_cursor,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    }


async def _parallel_query(common: dict, page: int, per_page: int, cursor: Optional[str]):
    """Run count and query in parallel."""
    import asyncio
    total_task = AuditService.count(**common)
    query_task = AuditService.query(**common, page=page, limit=per_page, before_cursor=cursor)
    return await asyncio.gather(total_task, query_task)


@router.get("/{log_id}")
async def get_audit_log(
    log_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    from db.session import db
    log = await db.audit_trail.find_one({"id": log_id}, {"_id": 0})
    if not log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Log entry not found")
    return {"log": log}
