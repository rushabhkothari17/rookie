"""
Admin User Permissions System

Supports:
1. Access levels: read_only, full_access
2. Module-based permissions: customers, orders, subscriptions, products, settings, users, etc.
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

# Available modules and their descriptions
ADMIN_MODULES = {
    "customers": {"name": "Customers", "description": "View and manage customer accounts"},
    "orders": {"name": "Orders", "description": "View and manage orders, process refunds"},
    "subscriptions": {"name": "Subscriptions", "description": "View and manage subscriptions"},
    "products": {"name": "Products & Catalog", "description": "Manage products, categories, pricing"},
    "promo_codes": {"name": "Promo Codes", "description": "Create and manage promotional codes"},
    "content": {"name": "Content", "description": "Manage articles, terms, website content"},
    "integrations": {"name": "Integrations", "description": "Configure CRM, payment, email integrations"},
    "webhooks": {"name": "Webhooks", "description": "Configure and manage webhooks"},
    "settings": {"name": "Settings", "description": "Configure store settings and branding"},
    "users": {"name": "User Management", "description": "Manage admin users and permissions"},
    "reports": {"name": "Reports & Analytics", "description": "View reports and analytics"},
    "logs": {"name": "Audit Logs", "description": "View system audit logs"},
}

# Access levels
ACCESS_LEVELS = {
    "full_access": {"name": "Full Access", "description": "Can view, create, edit, and delete"},
    "read_only": {"name": "Read Only", "description": "Can only view data, no modifications"},
}

# Preset roles
PRESET_ROLES = {
    "super_admin": {
        "name": "Super Admin",
        "description": "Full access to all modules",
        "access_level": "full_access",
        "modules": list(ADMIN_MODULES.keys())
    },
    "manager": {
        "name": "Manager",
        "description": "Manage customers, orders, and subscriptions",
        "access_level": "full_access",
        "modules": ["customers", "orders", "subscriptions", "products", "promo_codes"]
    },
    "support": {
        "name": "Support Agent",
        "description": "Handle customer inquiries and view orders",
        "access_level": "full_access",
        "modules": ["customers", "orders", "subscriptions"]
    },
    "viewer": {
        "name": "Viewer",
        "description": "Read-only access to all data",
        "access_level": "read_only",
        "modules": list(ADMIN_MODULES.keys())
    },
    "accountant": {
        "name": "Accountant",
        "description": "Access to financial data and reports",
        "access_level": "read_only",
        "modules": ["orders", "subscriptions", "reports"]
    },
    "content_editor": {
        "name": "Content Editor",
        "description": "Manage website content and articles",
        "access_level": "full_access",
        "modules": ["content", "products"]
    },
}


class AdminUserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    access_level: str = "read_only"  # full_access or read_only
    modules: List[str] = []  # List of module keys
    preset_role: Optional[str] = None  # If set, overrides access_level and modules


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = None
    access_level: Optional[str] = None
    modules: Optional[List[str]] = None
    is_active: Optional[bool] = None


class PermissionCheck(BaseModel):
    module: str
    action: str  # view, create, edit, delete


@router.get("/admin/permissions/modules")
async def get_available_modules(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Get list of available modules and access levels."""
    return {
        "modules": [
            {"key": k, **v} for k, v in ADMIN_MODULES.items()
        ],
        "access_levels": [
            {"key": k, **v} for k, v in ACCESS_LEVELS.items()
        ],
        "preset_roles": [
            {"key": k, **v} for k, v in PRESET_ROLES.items()
        ]
    }


# NOTE: GET /admin/users, POST /admin/users, and PUT /admin/users/{user_id} routes are
# intentionally defined in admin/users.py (registered first). The permission-checking
# logic for create/edit is enforced in those routes via has_permission(). See admin/users.py.

@router.delete("/admin/users/{user_id}")
async def delete_admin_user(
    user_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Deactivate an admin user (soft delete)."""
    tf = get_tenant_filter(admin)
    
    if not await has_permission(admin, "users", "delete"):
        raise HTTPException(status_code=403, detail="You don't have permission to delete users")
    
    if user_id == admin.get("id"):
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    
    user = await db.users.find_one({**tf, "id": user_id, "is_admin": True})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_active": False, "deactivated_at": now_iso(), "deactivated_by": admin.get("id")}}
    )
    
    await create_audit_log(entity_type="admin_user", entity_id=user_id, action="deactivated", actor=admin.get("email", "admin"), details={"email": user.get("email")})
    return {"message": "User deactivated successfully"}


@router.post("/admin/users/{user_id}/reactivate")
async def reactivate_admin_user(
    user_id: str,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """Reactivate a deactivated admin user."""
    tf = get_tenant_filter(admin)
    
    if not await has_permission(admin, "users", "edit"):
        raise HTTPException(status_code=403, detail="You don't have permission to reactivate users")
    
    user = await db.users.find_one({**tf, "id": user_id, "is_admin": True})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_active": True}, "$unset": {"deactivated_at": "", "deactivated_by": ""}}
    )
    
    await create_audit_log(entity_type="admin_user", entity_id=user_id, action="reactivated", actor=admin.get("email", "admin"), details={"email": user.get("email")})
    return {"message": "User reactivated successfully"}


@router.get("/admin/my-permissions")
async def get_my_permissions(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Get current user's permissions."""
    permissions = admin.get("permissions", {})
    access_level = admin.get("access_level", "full_access")
    role = admin.get("role", "partner_super_admin")
    
    # Super admins have all permissions
    if role in ("platform_admin", "platform_super_admin", "partner_super_admin", "super_admin"):
        return {
            "access_level": "full_access",
            "role": role,
            "modules": list(ADMIN_MODULES.keys()),
            "is_super_admin": True
        }
    
    return {
        "access_level": access_level,
        "role": role,
        "modules": permissions.get("modules", []),
        "is_super_admin": False
    }


async def has_permission(admin: Dict[str, Any], module: str, action: str) -> bool:
    """
    Check if an admin has permission for a specific action on a module.
    
    Args:
        admin: The admin user dict
        module: The module key (e.g., 'customers', 'orders')
        action: The action (view, create, edit, delete)
    
    Returns:
        True if permitted, False otherwise
    """
    role = admin.get("role", "")
    
    # Super admins (and platform admin) have all permissions
    if role in ("platform_admin", "platform_super_admin", "partner_super_admin", "super_admin"):
        return True
    
    # Check module access
    permissions = admin.get("permissions", {})
    allowed_modules = permissions.get("modules", [])
    
    if module not in allowed_modules:
        return False
    
    # Check access level for write actions
    access_level = admin.get("access_level", "read_only")
    
    if action == "view":
        return True  # If module is in list, view is always allowed
    
    # Write actions require full_access
    if action in ("create", "edit", "delete"):
        return access_level == "full_access"
    
    return False


def check_permission(module: str, action: str = "view"):
    """
    Dependency factory for checking permissions.
    
    Usage:
        @router.get("/some-route")
        async def some_route(
            admin: Dict[str, Any] = Depends(get_tenant_admin),
            _: None = Depends(check_permission("customers", "edit"))
        ):
            ...
    """
    async def _check(admin: Dict[str, Any] = Depends(get_tenant_admin)):
        if not await has_permission(admin, module, action):
            raise HTTPException(
                status_code=403,
                detail=f"You don't have permission to {action} {module}"
            )
        return None
    return _check
