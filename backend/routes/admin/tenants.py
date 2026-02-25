"""Admin: Tenant (Partner Organization) management — platform super admin only."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.security import pwd_context
from core.tenant import require_platform_admin, DEFAULT_TENANT_ID, get_tenant_admin, get_tenant_filter, tenant_id_of
from db.session import db
from models import TenantCreate, TenantUpdate, CreatePartnerAdminRequest
from services.audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["admin-tenants"])


@router.get("/admin/tenants")
async def list_tenants(admin: Dict[str, Any] = Depends(require_platform_admin)):
    tenants = await db.tenants.find({}, {"_id": 0}).to_list(500)
    return {"tenants": tenants}


@router.post("/admin/tenants")
async def create_tenant(payload: TenantCreate, admin: Dict[str, Any] = Depends(require_platform_admin)):
    code = payload.code.lower().strip().replace(" ", "-")
    # Explicitly block the reserved platform admin code
    if code == DEFAULT_TENANT_ID:
        raise HTTPException(status_code=400, detail="This code is reserved for platform administration and cannot be used for a partner tenant.")
    existing = await db.tenants.find_one({"code": code})
    if existing:
        raise HTTPException(status_code=400, detail="Partner code already in use")

    tenant_id = make_id()
    doc = {
        "id": tenant_id,
        "name": payload.name,
        "code": code,
        "status": payload.status,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    # Insert a copy so MongoDB _id mutation doesn't pollute our response dict
    await db.tenants.insert_one({**doc})

    # Seed generic defaults (never copy from another tenant)
    from routes.auth import _seed_new_tenant
    await _seed_new_tenant(tenant_id, payload.name, now_iso())

    await create_audit_log(entity_type="tenant", entity_id=tenant_id, action="created", actor=admin.get("email", "admin"), details={"name": payload.name, "code": code})
    return {"tenant": doc}


@router.put("/admin/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, payload: TenantUpdate, admin: Dict[str, Any] = Depends(require_platform_admin)):
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    updates: Dict[str, Any] = {"updated_at": now_iso()}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.status is not None:
        if payload.status not in ("active", "inactive"):
            raise HTTPException(status_code=400, detail="status must be 'active' or 'inactive'")
        updates["status"] = payload.status

    await db.tenants.update_one({"id": tenant_id}, {"$set": updates})
    updated = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    await create_audit_log(entity_type="tenant", entity_id=tenant_id, action="updated", actor=admin.get("email", "admin"), details={"fields": list(updates.keys())})
    return {"tenant": updated}


@router.post("/admin/tenants/{tenant_id}/activate")
async def activate_tenant(tenant_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    result = await db.tenants.update_one(
        {"id": tenant_id},
        {"$set": {"status": "active", "updated_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await create_audit_log(entity_type="tenant", entity_id=tenant_id, action="activated", actor=admin.get("email", "admin"), details={})
    return {"message": "Tenant activated"}


@router.post("/admin/tenants/{tenant_id}/deactivate")
async def deactivate_tenant(tenant_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    if tenant_id == DEFAULT_TENANT_ID:
        raise HTTPException(status_code=400, detail="Cannot deactivate the default tenant")
    result = await db.tenants.update_one(
        {"id": tenant_id},
        {"$set": {"status": "inactive", "updated_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await create_audit_log(entity_type="tenant", entity_id=tenant_id, action="deactivated", actor=admin.get("email", "admin"), details={})
    return {"message": "Tenant deactivated"}


@router.post("/admin/tenants/{tenant_id}/create-admin")
async def create_partner_admin(
    tenant_id: str,
    payload: CreatePartnerAdminRequest,
    admin: Dict[str, Any] = Depends(require_platform_admin),
):
    """Create a partner_super_admin (or partner_admin) user for a tenant."""
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    existing = await db.users.find_one({"email": payload.email.lower(), "tenant_id": tenant_id})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered for this tenant")

    valid_roles = ("partner_super_admin", "partner_admin", "partner_staff")
    if payload.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {valid_roles}")

    user_id = make_id()
    hashed = pwd_context.hash(payload.password)
    user_doc = {
        "id": user_id,
        "email": payload.email.lower(),
        "password_hash": hashed,
        "full_name": payload.full_name,
        "company_name": "",
        "job_title": "",
        "phone": "",
        "is_verified": True,  # Platform admin creates verified users
        "is_admin": True,
        "role": payload.role,
        "tenant_id": tenant_id,
        "is_active": True,
        "created_at": now_iso(),
    }
    await db.users.insert_one(user_doc)
    await create_audit_log(entity_type="tenant_admin", entity_id=user_id, action="created", actor=admin.get("email", "admin"), details={"email": payload.email, "role": payload.role, "tenant_id": tenant_id})
    return {
        "message": f"{payload.role} created for tenant {tenant['name']}",
        "user_id": user_id,
    }


@router.get("/admin/tenants/{tenant_id}/users")
async def list_tenant_users(tenant_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    users = await db.users.find(
        {"tenant_id": tenant_id},
        {"_id": 0, "password_hash": 0, "verification_code": 0},
    ).to_list(500)
    return {"users": users}


@router.get("/admin/tenants/{tenant_id}/customers")
async def list_tenant_customers(tenant_id: str, admin: Dict[str, Any] = Depends(require_platform_admin)):
    """List customers for a specific tenant — used by the Customer Switcher."""
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    customers = await db.customers.find({"tenant_id": tenant_id}, {"_id": 0}).to_list(500)
    user_ids = [c["user_id"] for c in customers if c.get("user_id")]
    users = await db.users.find(
        {"id": {"$in": user_ids}},
        {"_id": 0, "id": 1, "email": 1, "full_name": 1},
    ).to_list(500)
    user_map = {u["id"]: u for u in users}
    result = []
    for c in customers:
        uid = c.get("user_id")
        u = user_map.get(uid, {})
        result.append({
            "id": c["id"],
            "user_id": uid,
            "company_name": c.get("company_name", ""),
            "email": u.get("email", ""),
            "full_name": u.get("full_name", ""),
        })
    return {"customers": result}


# ---------------------------------------------------------------------------
# Custom Domain Management with Verification
# ---------------------------------------------------------------------------

from pydantic import BaseModel
from typing import List, Optional
import socket
import asyncio

class CustomDomainAdd(BaseModel):
    domain: str

class CustomDomainRequest(BaseModel):
    domains: List[str]


async def check_dns_cname(domain: str, expected_target: str) -> dict:
    """
    Check if a domain has a CNAME record pointing to the expected target.
    
    Returns:
        {
            "verified": bool,
            "status": "verified" | "pending" | "failed" | "incorrect",
            "message": str,
            "cname_found": str | None
        }
    """
    import dns.resolver
    
    try:
        answers = await asyncio.to_thread(lambda: dns.resolver.resolve(domain, 'CNAME'))
        for rdata in answers:
            cname = str(rdata.target).rstrip('.')
            if expected_target.lower() in cname.lower() or cname.lower().endswith(expected_target.lower()):
                return {
                    "verified": True,
                    "status": "verified",
                    "message": f"CNAME correctly points to {cname}",
                    "cname_found": cname
                }
            else:
                return {
                    "verified": False,
                    "status": "incorrect",
                    "message": f"CNAME points to {cname}, expected {expected_target}",
                    "cname_found": cname
                }
    except dns.resolver.NXDOMAIN:
        return {
            "verified": False,
            "status": "failed",
            "message": "Domain not found (NXDOMAIN). Check if the domain exists.",
            "cname_found": None
        }
    except dns.resolver.NoAnswer:
        # Try A record as fallback
        try:
            a_answers = await asyncio.to_thread(lambda: dns.resolver.resolve(domain, 'A'))
            return {
                "verified": False,
                "status": "pending",
                "message": "No CNAME record found. Please add a CNAME record pointing to the platform.",
                "cname_found": None
            }
        except Exception:
            pass
        return {
            "verified": False,
            "status": "pending",
            "message": "No DNS records found for this domain yet.",
            "cname_found": None
        }
    except dns.resolver.Timeout:
        return {
            "verified": False,
            "status": "pending",
            "message": "DNS lookup timed out. DNS may still be propagating.",
            "cname_found": None
        }
    except Exception as e:
        return {
            "verified": False,
            "status": "pending",
            "message": f"Could not verify DNS: {str(e)}",
            "cname_found": None
        }


@router.get("/admin/custom-domains")
async def get_custom_domains(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Get custom domains configured for the current tenant with verification status."""
    tid = tenant_id_of(admin)
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "custom_domains_data": 1, "custom_domains": 1, "custom_domain": 1})
    if not tenant:
        return {"domains": []}
    
    # Return the full domain data with verification status
    domains_data = tenant.get("custom_domains_data", [])
    
    # Migrate legacy format if needed
    if not domains_data:
        legacy_domains = tenant.get("custom_domains", [])
        if not legacy_domains and tenant.get("custom_domain"):
            legacy_domains = [tenant["custom_domain"]]
        # Convert legacy to new format with pending status
        domains_data = [
            {"domain": d, "status": "pending", "verified_at": None, "added_at": now_iso()}
            for d in legacy_domains
        ]
    
    return {"domains": domains_data}


@router.post("/admin/custom-domains")
async def add_custom_domain(
    payload: CustomDomainAdd,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """
    Add a new custom domain with pending verification status.
    
    Domain will need to be verified before it becomes active.
    """
    import re
    
    tid = tenant_id_of(admin)
    domain = payload.domain.lower().strip()
    
    # Validate domain format
    domain_pattern = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$')
    if not domain_pattern.match(domain):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain format: {domain}. Use format like 'billing.company.com'"
        )
    
    # Check if domain is already used by another tenant
    existing = await db.tenants.find_one({
        "custom_domains_data.domain": domain,
        "id": {"$ne": tid}
    })
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Domain '{domain}' is already configured for another organization"
        )
    
    # Check if already added for this tenant
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "custom_domains_data": 1})
    existing_domains = [d["domain"] for d in (tenant.get("custom_domains_data") or [])]
    if domain in existing_domains:
        raise HTTPException(status_code=400, detail=f"Domain '{domain}' is already added")
    
    # Add domain with pending status
    domain_data = {
        "domain": domain,
        "status": "pending",
        "verified_at": None,
        "added_at": now_iso(),
        "last_check_at": None,
        "last_check_message": None
    }
    
    await db.tenants.update_one(
        {"id": tid},
        {"$push": {"custom_domains_data": domain_data}}
    )
    
    await create_audit_log(entity_type="custom_domain", entity_id=domain, action="added", actor=admin.get("email", "admin"), details={"domain": domain}, tenant_id=tid)
    return {
        "message": f"Domain '{domain}' added. Please verify DNS configuration.",
        "domain": domain_data,
        "setup_instructions": {
            "cname_target": "preview.emergentagent.com",
            "step1": f"Add a CNAME record: {domain} → preview.emergentagent.com",
            "step2": "Wait for DNS propagation (usually 5-30 minutes)",
            "step3": "Click 'Verify Now' to check the configuration"
        }
    }


@router.put("/admin/custom-domains")
async def update_custom_domains(
    payload: CustomDomainRequest,
    admin: Dict[str, Any] = Depends(get_tenant_admin)
):
    """
    Update custom domains for the current tenant (legacy endpoint).
    
    Domains should be fully qualified (e.g., billing.company.com).
    Partners must configure DNS (CNAME) to point to the platform.
    """
    import re
    
    tid = tenant_id_of(admin)
    
    # Validate domains
    domain_pattern = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$')
    validated_domains = []
    
    for domain in payload.domains:
        domain = domain.lower().strip()
        if not domain:
            continue
        if not domain_pattern.match(domain):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid domain format: {domain}. Use format like 'billing.company.com'"
            )
        
        # Check if domain is already used by another tenant
        existing = await db.tenants.find_one({
            "custom_domains": domain,
            "id": {"$ne": tid}
        })
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Domain '{domain}' is already configured for another organization"
            )
        
        validated_domains.append(domain)
    
    # Update tenant
    await db.tenants.update_one(
        {"id": tid},
        {"$set": {"custom_domains": validated_domains, "updated_at": now_iso()}}
    )
    
    await create_audit_log(entity_type="custom_domain", entity_id=tid, action="updated", actor=admin.get("email", "admin"), details={"domains": validated_domains}, tenant_id=tid)
    return {
        "message": "Custom domains updated successfully",
        "domains": validated_domains,
        "setup_instructions": {
            "step1": "Add a CNAME record for each domain pointing to your platform URL",
            "step2": "Wait for DNS propagation (usually 5-30 minutes)",
            "step3": "SSL certificates will be provisioned automatically",
            "step4": "Users can now access your portal at the custom domain without partner code"
        }
    }


@router.post("/admin/custom-domains/{domain}/verify")
async def verify_custom_domain(domain: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Verify DNS configuration for a custom domain."""
    tid = tenant_id_of(admin)
    domain = domain.lower().strip()
    
    # Check domain exists for this tenant
    tenant = await db.tenants.find_one(
        {"id": tid, "custom_domains_data.domain": domain},
        {"_id": 0}
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    # Perform DNS verification
    expected_target = "preview.emergentagent.com"  # Or get from settings
    result = await check_dns_cname(domain, expected_target)
    
    # Update domain status
    update_data = {
        "custom_domains_data.$.status": result["status"],
        "custom_domains_data.$.last_check_at": now_iso(),
        "custom_domains_data.$.last_check_message": result["message"]
    }
    
    if result["verified"]:
        update_data["custom_domains_data.$.verified_at"] = now_iso()
    
    await db.tenants.update_one(
        {"id": tid, "custom_domains_data.domain": domain},
        {"$set": update_data}
    )
    
    await create_audit_log(entity_type="custom_domain", entity_id=domain, action="verified", actor=admin.get("email", "admin"), details={"domain": domain, "status": result["status"]}, tenant_id=tid)
    return {
        "domain": domain,
        "verification": result,
        "expected_cname": expected_target
    }


@router.delete("/admin/custom-domains/{domain}")
async def remove_custom_domain(domain: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Remove a specific custom domain."""
    tid = tenant_id_of(admin)
    
    result = await db.tenants.update_one(
        {"id": tid},
        {"$pull": {"custom_domains": domain.lower()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    await create_audit_log(entity_type="custom_domain", entity_id=domain, action="removed", actor=admin.get("email", "admin"), details={"domain": domain}, tenant_id=tid)
    return {"message": f"Domain '{domain}' removed successfully"}


@router.get("/admin/setup-checklist")
async def get_setup_checklist(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    """Return setup checklist completion status for the current tenant."""
    tf = get_tenant_filter(admin)

    website_settings = await db.website_settings.find_one(tf, {"_id": 0})
    has_brand = bool(
        website_settings and (
            website_settings.get("logo_url") or
            (website_settings.get("store_name") and website_settings.get("store_name") not in ("My Store", "Automate Accounts", ""))
        )
    )

    product_count = await db.products.count_documents({**tf, "is_active": True})
    has_product = product_count > 0

    app_settings = await db.app_settings.find_one(tf, {"_id": 0})
    has_payment = bool(app_settings and (app_settings.get("stripe_enabled") or app_settings.get("gocardless_enabled")))

    customer_count = await db.customers.count_documents(tf)
    has_customer = customer_count > 0

    article_count = await db.articles.count_documents({**tf, "deleted_at": {"$exists": False}})
    has_article = article_count > 0

    checklist = {
        "brand_customized": has_brand,
        "first_product": has_product,
        "payment_configured": has_payment,
        "first_customer": has_customer,
        "first_article": has_article,
    }
    completed = sum(checklist.values())
    return {"checklist": checklist, "completed": completed, "total": len(checklist)}
