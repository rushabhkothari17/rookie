"""Admin audit trail / logs routes."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from core.security import require_admin
from services.audit_service import AuditService

router = APIRouter(prefix="/api/admin/audit-logs", tags=["admin-logs"])


@router.get("")
async def list_audit_logs(
    actor: Optional[str] = None,
    source: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    action: Optional[str] = None,
    success: Optional[str] = None,   # "true" | "false" | None
    severity: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    q: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = 50,
    admin: Dict[str, Any] = Depends(require_admin),
):
    success_bool: Optional[bool] = None
    if success == "true":
        success_bool = True
    elif success == "false":
        success_bool = False

    records, next_cursor = await AuditService.query(
        actor=actor or None,
        source=source or None,
        entity_type=entity_type or None,
        entity_id=entity_id or None,
        action=action or None,
        success=success_bool,
        severity=severity or None,
        date_from=date_from or None,
        date_to=date_to or None,
        q=q or None,
        before_cursor=cursor or None,
        limit=min(limit, 200),
    )
    return {"logs": records, "next_cursor": next_cursor}


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
