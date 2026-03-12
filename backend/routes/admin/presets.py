"""Admin: Custom User Preset CRUD — tenant-specific permission presets."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, validator

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_admin, get_tenant_filter, tenant_id_of
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-presets"])


class PresetCreate(BaseModel):
    name: str
    description: str = ""
    module_permissions: Dict[str, str]  # {module_key: "read"|"write"}

    @validator("name")
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Preset name is required")
        if len(v) > 80:
            raise ValueError("Preset name must be 80 characters or less")
        return v


class PresetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    module_permissions: Optional[Dict[str, str]] = None


@router.get("/admin/presets")
async def list_presets(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    presets = (
        await db.user_presets.find(tf, {"_id": 0}).sort("created_at", 1).to_list(200)
    )
    return {"presets": presets}


@router.post("/admin/presets")
async def create_preset(
    payload: PresetCreate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tid = tenant_id_of(admin)
    existing = await db.user_presets.find_one(
        {"tenant_id": tid, "name": payload.name}, {"_id": 0, "id": 1}
    )
    if existing:
        raise HTTPException(
            status_code=409, detail=f"A preset named '{payload.name}' already exists"
        )

    preset_id = make_id()
    # Generate a safe key from name
    import re
    key = re.sub(r"[^a-z0-9]+", "_", payload.name.lower()).strip("_")

    doc = {
        "id": preset_id,
        "tenant_id": tid,
        "key": key,
        "name": payload.name,
        "description": payload.description.strip(),
        "module_permissions": payload.module_permissions,
        "is_custom": True,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "created_by": admin.get("email", "admin"),
    }
    await db.user_presets.insert_one({**doc})
    await create_audit_log(
        entity_type="user_preset",
        entity_id=preset_id,
        action="created",
        actor=admin.get("email", "admin"),
        details={"name": doc["name"]},
    )
    return {"preset": doc}


@router.put("/admin/presets/{preset_id}")
async def update_preset(
    preset_id: str,
    payload: PresetUpdate,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    existing = await db.user_presets.find_one({**tf, "id": preset_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Preset not found")

    updates: Dict[str, Any] = {"updated_at": now_iso()}
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Preset name is required")
        # Check for name collision
        tid = tenant_id_of(admin)
        other = await db.user_presets.find_one(
            {"tenant_id": tid, "name": name, "id": {"$ne": preset_id}},
            {"_id": 0, "id": 1},
        )
        if other:
            raise HTTPException(
                status_code=409, detail=f"A preset named '{name}' already exists"
            )
        updates["name"] = name
    if payload.description is not None:
        updates["description"] = payload.description.strip()
    if payload.module_permissions is not None:
        updates["module_permissions"] = payload.module_permissions

    await db.user_presets.update_one({"id": preset_id}, {"$set": updates})
    updated = await db.user_presets.find_one({"id": preset_id}, {"_id": 0})
    await create_audit_log(
        entity_type="user_preset",
        entity_id=preset_id,
        action="updated",
        actor=admin.get("email", "admin"),
        details=updates,
    )
    return {"preset": updated}


@router.delete("/admin/presets/{preset_id}")
async def delete_preset(
    preset_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin),
):
    tf = get_tenant_filter(admin)
    existing = await db.user_presets.find_one({**tf, "id": preset_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Preset not found")
    await db.user_presets.delete_one({"id": preset_id})
    await create_audit_log(
        entity_type="user_preset",
        entity_id=preset_id,
        action="deleted",
        actor=admin.get("email", "admin"),
        details={"name": existing.get("name")},
    )
    return {"message": "Preset deleted"}
