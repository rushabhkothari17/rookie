"""
Comprehensive AuditService — write-optimised append-only audit trail.

Schema
------
Each record captures who did what to which entity, from which surface,
with full before/after state and correlation IDs so you can trace any
operation across logs.

Indexes (created on startup):
  - (occurred_at DESC)
  - (entity_type, entity_id)
  - (actor_id)
  - (action)
  - (source)
  - (success)
"""
from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional, Tuple

from typing import Any, Dict, List, Optional, Tuple  # noqa: F811

from core.helpers import make_id, now_iso
from db.session import db

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ACTOR_TYPES = {"admin", "user", "system", "webhook"}
SOURCES = {"admin_ui", "customer_ui", "api", "webhook", "cron"}
SEVERITIES = {"info", "warn", "error"}


# ---------------------------------------------------------------------------
# Index bootstrap — call once at startup
# ---------------------------------------------------------------------------

async def ensure_audit_indexes() -> None:
    col = db.audit_trail
    await col.create_index([("occurred_at", -1)])
    await col.create_index([("entity_type", 1), ("entity_id", 1)])
    await col.create_index([("actor_id", 1)])
    await col.create_index([("action", 1)])
    await col.create_index([("source", 1)])
    await col.create_index([("success", 1)])
    await col.create_index([("severity", 1)])


# ---------------------------------------------------------------------------
# AuditService
# ---------------------------------------------------------------------------

class AuditService:
    """Static helper — call AuditService.log(...) anywhere."""

    @staticmethod
    async def log(
        *,
        action: str,
        description: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        actor_type: str = "system",
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
        source: str = "api",
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        severity: str = "info",
        success: bool = True,
        error_message: Optional[str] = None,
        before_json: Optional[Dict[str, Any]] = None,
        after_json: Optional[Dict[str, Any]] = None,
        meta_json: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Fire-and-forget audit record insert."""
        doc = {
            "id": make_id(),
            "occurred_at": now_iso(),
            "actor_type": actor_type,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "actor_role": actor_role,
            "source": source,
            "request_id": request_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "action": action,
            "description": description,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "severity": severity,
            "success": success,
            "error_message": error_message,
            "before_json": before_json,
            "after_json": after_json,
            "meta_json": meta_json,
        }
        try:
            await db.audit_trail.insert_one(doc)
        except Exception:
            pass  # audit failures must never crash the main request

    @staticmethod
    def _encode_cursor(occurred_at: str, doc_id: str) -> str:
        raw = json.dumps({"t": occurred_at, "id": doc_id})
        return base64.urlsafe_b64encode(raw.encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> Tuple[str, str]:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        d = json.loads(raw)
        return d["t"], d["id"]

    @staticmethod
    async def query(
        *,
        actor: Optional[str] = None,
        source: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
        success: Optional[bool] = None,
        severity: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        q: Optional[str] = None,
        before_cursor: Optional[str] = None,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Keyset-paginated query. Returns (records, next_cursor | None)."""
        flt: Dict[str, Any] = {}

        if actor:
            flt["$or"] = [
                {"actor_email": {"$regex": actor, "$options": "i"}},
                {"actor_id": {"$regex": actor, "$options": "i"}},
            ]
        if source:
            flt["source"] = source
        if entity_type:
            flt["entity_type"] = {"$regex": entity_type, "$options": "i"}
        if entity_id:
            flt["entity_id"] = entity_id
        if action:
            flt["action"] = {"$regex": action, "$options": "i"}
        if success is not None:
            flt["success"] = success
        if severity:
            flt["severity"] = severity
        if date_from:
            flt.setdefault("occurred_at", {})["$gte"] = date_from
        if date_to:
            flt.setdefault("occurred_at", {})["$lte"] = date_to
        if q:
            flt["description"] = {"$regex": q, "$options": "i"}

        # Keyset pagination: records *older* than the cursor
        if before_cursor:
            try:
                cur_t, cur_id = AuditService._decode_cursor(before_cursor)
                flt["$and"] = flt.get("$and", []) + [
                    {"$or": [
                        {"occurred_at": {"$lt": cur_t}},
                        {"occurred_at": cur_t, "id": {"$gt": cur_id}},
                    ]}
                ]
            except Exception:
                pass

        records = (
            await db.audit_trail.find(flt, {"_id": 0})
            .sort([("occurred_at", -1), ("id", 1)])
            .limit(limit + 1)
            .to_list(limit + 1)
        )

        has_more = len(records) > limit
        records = records[:limit]

        next_cursor: Optional[str] = None
        if has_more and records:
            last = records[-1]
            next_cursor = AuditService._encode_cursor(last["occurred_at"], last["id"])

        return records, next_cursor
