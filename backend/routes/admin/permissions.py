"""
Admin User Permissions System

Supports:
- Per-module read/write access (module_permissions: {module_key: "read"|"write"})
- Platform modules (visible to platform_admin / platform_super_admin only)
- Partner modules (visible to all admin roles)
- Super admin roles bypass all checks
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import pwd_context
from core.tenant import get_tenant_admin, tenant_id_of, get_tenant_filter
from db.session import db
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-permissions"])

# ── Module Definitions ────────────────────────────────────────────────────────

PLATFORM_MODULES: Dict[str, Dict] = {
    "partner_orgs":            {"name": "Partner Orgs",            "description": "Manage partner organisations"},
    "plans":                   {"name": "Plans",                   "description": "Manage partner plans and billing tiers"},
    "partner_subscriptions":   {"name": "Partner Subscriptions",   "description": "View and manage partner subscriptions"},
    "partner_orders":          {"name": "Partner Orders",          "description": "View and manage partner orders"},
    "partner_submissions":     {"name": "Partner Submissions",     "description": "View partner form submissions"},
    "billing_settings":        {"name": "Billing Settings",        "description": "Configure billing settings and rates"},
    "currencies":              {"name": "Supported Currencies",    "description": "Manage the platform currency list"},
}

PARTNER_MODULES: Dict[str, Dict] = {
    "customers":    {"name": "Customers",          "description": "View and manage customer accounts"},
    "orders":       {"name": "Orders",             "description": "View and manage orders, process refunds"},
    "subscriptions":{"name": "Subscriptions",      "description": "View and manage subscriptions"},
    "products":     {"name": "Products & Catalog", "description": "Manage products, categories, pricing"},
    "promo_codes":  {"name": "Promo Codes",        "description": "Create and manage promotional codes"},
    "content":      {"name": "Content",            "description": "Manage articles, terms, website content"},
    "integrations": {"name": "Integrations",       "description": "Configure CRM, payment, email integrations"},
    "webhooks":     {"name": "Webhooks",            "description": "Configure and manage webhooks"},
    "settings":     {"name": "Settings",           "description": "Configure store settings and branding"},
    "users":        {"name": "User Management",    "description": "Manage admin users and permissions"},
    "reports":      {"name": "Reports & Analytics","description": "View reports and analytics"},
    "logs":         {"name": "Audit Logs",         "description": "View system audit logs"},
}

ADMIN_MODULES: Dict[str, Dict] = {**PLATFORM_MODULES, **PARTNER_MODULES}

# ── Preset roles (updated to use module_permissions format) ───────────────────

PRESET_ROLES = {
    "manager": {
        "name": "Manager",
        "description": "Manage customers, orders, and subscriptions",
        "module_permissions": {
            "customers": "write", "orders": "write", "subscriptions": "write",
            "products": "write", "promo_codes": "write",
        },
    },
    "support": {
        "name": "Support Agent",
        "description": "Handle customer inquiries and view orders",
        "module_permissions": {
            "customers": "write", "orders": "read", "subscriptions": "read",
        },
    },
    "viewer": {
        "name": "Viewer",
        "description": "Read-only access to all partner modules",
        "module_permissions": {k: "read" for k in PARTNER_MODULES},
    },
    "accountant": {
        "name": "Accountant",
        "description": "Access to financial data and reports",
        "module_permissions": {
            "orders": "read", "subscriptions": "read", "reports": "read",
        },
    },
    "content_editor": {
        "name": "Content Editor",
        "description": "Manage website content and articles",
        "module_permissions": {"content": "write", "products": "read"},
    },
}

# ── Pydantic models ───────────────────────────────────────────────────────────

class RoleCreate(BaseModel):
    name: str
    description: str = ""
    module_permissions: Dict[str, str] = {}  # {module_key: "read"|"write"}


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    module_permissions: Optional[Dict[str, str]] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/admin/permissions/modules")
async def get_available_modules(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Return available modules scoped to the calling admin's role context."""
    role = admin.get("role", "")
    if role in ("platform_super_admin", "platform_admin"):
        modules_dict = ADMIN_MODULES
    else:
        modules_dict = PARTNER_MODULES
    return {
        "modules": [{"key": k, **v} for k, v in modules_dict.items()],
        "platform_module_keys": list(PLATFORM_MODULES.keys()),
        "partner_module_keys": list(PARTNER_MODULES.keys()),
        "preset_roles": [{"key": k, **v} for k, v in PRESET_ROLES.items()],
    }


@router.get("/admin/my-permissions")
async def get_my_permissions(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Get current user's permissions in the new module_permissions format."""
    role = admin.get("role", "")

    if role == "platform_super_admin":
        mp = {k: "write" for k in ADMIN_MODULES}
        return {"module_permissions": mp, "modules": list(mp.keys()), "is_super_admin": True, "role": role}

    if role == "partner_super_admin":
        mp = {k: "write" for k in PARTNER_MODULES}
        return {"module_permissions": mp, "modules": list(mp.keys()), "is_super_admin": True, "role": role}

    # Non-super admins: read from module_permissions field (new format) or fall back to old format
    mp: Dict[str, str] = admin.get("module_permissions") or {}
    if not mp:
        # Backwards compatibility: convert old access_level + permissions.modules
        old_modules = admin.get("permissions", {}).get("modules") or []
        access_level = admin.get("access_level", "read_only")
        mp = {m: "write" if access_level == "full_access" else "read" for m in old_modules}

    return {
        "module_permissions": mp,
        "modules": list(mp.keys()),
        "is_super_admin": False,
        "role": role,
    }


@router.get("/admin/roles")
async def get_roles(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    preset = [
        {"id": k, "key": k, "name": v["name"], "description": v["description"],
         "module_permissions": v["module_permissions"], "is_preset": True}
        for k, v in PRESET_ROLES.items()
    ]
    custom = await db.admin_roles.find({**tf}, {"_id": 0}).to_list(None)
    return {
        "roles": preset + custom,
        "modules": [{"key": k, **v} for k, v in ADMIN_MODULES.items()],
    }


@router.post("/admin/roles")
async def create_role(body: RoleCreate, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    if not await has_permission(admin, "users", "create"):
        raise HTTPException(403, "Insufficient permissions to manage roles")
    tid = tenant_id_of(admin)
    invalid = [m for m in body.module_permissions if m not in ADMIN_MODULES]
    if invalid:
        raise HTTPException(400, f"Unknown modules: {invalid}")
    for v in body.module_permissions.values():
        if v not in ("read", "write"):
            raise HTTPException(400, "Module permission must be 'read' or 'write'")
    role = {
        "id": make_id(), "key": None, "name": body.name, "description": body.description,
        "module_permissions": body.module_permissions, "is_preset": False,
        "tenant_id": tid, "created_at": now_iso(), "created_by": admin.get("email"),
    }
    await db.admin_roles.insert_one(role)
    role.pop("_id", None)
    return role


@router.put("/admin/roles/{role_id}")
async def update_role(role_id: str, body: RoleUpdate, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    if not await has_permission(admin, "users", "edit"):
        raise HTTPException(403, "Insufficient permissions to manage roles")
    tf = get_tenant_filter(admin)
    role = await db.admin_roles.find_one({**tf, "id": role_id})
    if not role:
        raise HTTPException(404, "Custom role not found")
    update = {k: v for k, v in body.dict(exclude_none=True).items()}
    if "module_permissions" in update:
        invalid = [m for m in update["module_permissions"] if m not in ADMIN_MODULES]
        if invalid:
            raise HTTPException(400, f"Unknown modules: {invalid}")
    update["updated_at"] = now_iso()
    await db.admin_roles.update_one({"id": role_id}, {"$set": update})
    role.update(update)
    role.pop("_id", None)
    return role


@router.delete("/admin/roles/{role_id}")
async def delete_role(role_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    if not await has_permission(admin, "users", "delete"):
        raise HTTPException(403, "Insufficient permissions to manage roles")
    tf = get_tenant_filter(admin)
    role = await db.admin_roles.find_one({**tf, "id": role_id})
    if not role:
        raise HTTPException(404, "Custom role not found (built-in roles cannot be deleted)")
    await db.admin_roles.delete_one({"id": role_id})
    return {"message": "Role deleted"}


@router.delete("/admin/users/{user_id}")
async def delete_admin_user(user_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Deactivate an admin user (soft delete)."""
    tf = get_tenant_filter(admin)
    if not _is_super_admin(admin):
        raise HTTPException(403, "Only super admins can deactivate users")
    if user_id == admin.get("id"):
        raise HTTPException(400, "You cannot deactivate your own account")
    user = await db.users.find_one({**tf, "id": user_id, "is_admin": True})
    if not user:
        raise HTTPException(404, "User not found")
    if user.get("role") == "platform_super_admin":
        raise HTTPException(403, "Platform super admin cannot be deactivated")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_active": False, "deactivated_at": now_iso(), "deactivated_by": admin.get("id")}}
    )
    await create_audit_log(entity_type="admin_user", entity_id=user_id, action="deactivated",
                           actor=admin.get("email", "admin"), details={"email": user.get("email")})
    return {"message": "User deactivated successfully"}


@router.post("/admin/users/{user_id}/reactivate")
async def reactivate_admin_user(user_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Reactivate a deactivated admin user."""
    tf = get_tenant_filter(admin)
    if not _is_super_admin(admin):
        raise HTTPException(403, "Only super admins can reactivate users")
    user = await db.users.find_one({**tf, "id": user_id, "is_admin": True})
    if not user:
        raise HTTPException(404, "User not found")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_active": True}, "$unset": {"deactivated_at": "", "deactivated_by": ""}}
    )
    await create_audit_log(entity_type="admin_user", entity_id=user_id, action="reactivated",
                           actor=admin.get("email", "admin"), details={"email": user.get("email")})
    return {"message": "User reactivated successfully"}


# ── Permission helpers ────────────────────────────────────────────────────────

def _is_super_admin(admin: Dict[str, Any]) -> bool:
    return admin.get("role") in ("platform_super_admin", "partner_super_admin")


async def has_permission(admin: Dict[str, Any], module: str, action: str) -> bool:
    """
    Check if an admin has permission for a specific action on a module.
    action: "view" | "create" | "edit" | "delete"
    """
    role = admin.get("role", "")

    # Super admins bypass all checks
    if role in ("platform_super_admin", "partner_super_admin"):
        return True

    # New format: module_permissions
    mp: Dict[str, str] = admin.get("module_permissions") or {}
    if mp:
        perm = mp.get(module)
        if not perm:
            return False
        if action == "view":
            return True
        return perm == "write"

    # Backwards compatibility: old access_level + permissions.modules
    permissions = admin.get("permissions", {})
    allowed_modules = permissions.get("modules", [])
    if module not in allowed_modules:
        return False
    access_level = admin.get("access_level", "read_only")
    if action == "view":
        return True
    return access_level == "full_access"


def check_permission(module: str, action: str = "view"):
    """Dependency factory for checking permissions inline."""
    async def _check(admin: Dict[str, Any] = Depends(get_tenant_admin)):
        if not await has_permission(admin, module, action):
            raise HTTPException(403, f"You don't have permission to {action} {module}")
        return None
    return _check
