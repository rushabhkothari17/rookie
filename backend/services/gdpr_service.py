"""GDPR compliance service for data export and right-to-erasure."""
import json
import csv
import io
import zipfile
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from db.session import db
import logging

logger = logging.getLogger(__name__)


async def export_customer_data(customer_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Export all customer data for GDPR compliance.
    Returns a structured export of all customer-related data.
    """
    export_data = {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "customer_id": customer_id,
        "tenant_id": tenant_id,
        "data": {}
    }
    
    # 1. Customer profile
    customer = await db.customers.find_one(
        {"id": customer_id, "tenant_id": tenant_id},
        {"_id": 0}
    )
    if customer:
        export_data["data"]["profile"] = customer
    
    # 2. User account (without password)
    user = await db.users.find_one(
        {"id": customer.get("user_id") if customer else None},
        {"_id": 0, "password_hash": 0}
    )
    if user:
        export_data["data"]["account"] = user
    
    # 3. Address
    address = await db.addresses.find_one(
        {"customer_id": customer_id},
        {"_id": 0}
    )
    if address:
        export_data["data"]["address"] = address
    
    # 4. Orders
    orders = await db.orders.find(
        {"customer_id": customer_id, "tenant_id": tenant_id},
        {"_id": 0}
    ).to_list(1000)
    export_data["data"]["orders"] = orders
    
    # 5. Subscriptions
    subscriptions = await db.subscriptions.find(
        {"customer_id": customer_id, "tenant_id": tenant_id},
        {"_id": 0}
    ).to_list(100)
    export_data["data"]["subscriptions"] = subscriptions
    
    # 7. Customer notes (redact internal-only notes)
    notes = await db.customer_notes.find(
        {"customer_id": customer_id, "tenant_id": tenant_id},
        {"_id": 0}
    ).to_list(500)
    export_data["data"]["notes"] = [
        {**n, "content": n.get("content") if not n.get("internal_only") else "[INTERNAL]"}
        for n in notes
    ]
    
    # 8. Audit log entries (customer's actions only)
    audit_logs = await db.audit_logs.find(
        {"tenant_id": tenant_id, "actor": {"$regex": f"customer:{customer_id}"}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    export_data["data"]["activity_log"] = audit_logs
    
    return export_data


def generate_export_zip(export_data: Dict[str, Any]) -> bytes:
    """Generate a ZIP file containing all exported data in multiple formats."""
    buffer = io.BytesIO()
    
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Full JSON export
        zf.writestr(
            "full_export.json",
            json.dumps(export_data, indent=2, default=str)
        )
        
        # 2. Profile as readable text
        profile_text = []
        profile_text.append("=== CUSTOMER DATA EXPORT ===\n")
        profile_text.append(f"Export Date: {export_data['export_date']}\n\n")
        
        if "profile" in export_data.get("data", {}):
            profile = export_data["data"]["profile"]
            profile_text.append("--- PROFILE ---\n")
            profile_text.append(f"Name: {profile.get('full_name', 'N/A')}\n")
            profile_text.append(f"Email: {profile.get('email', 'N/A')}\n")
            profile_text.append(f"Company: {profile.get('company_name', 'N/A')}\n")
            profile_text.append(f"Phone: {profile.get('phone', 'N/A')}\n")
            profile_text.append(f"Currency: {profile.get('currency', 'N/A')}\n")
        
        if "address" in export_data.get("data", {}):
            addr = export_data["data"]["address"]
            profile_text.append("\n--- ADDRESS ---\n")
            profile_text.append(f"Line 1: {addr.get('line1', 'N/A')}\n")
            profile_text.append(f"Line 2: {addr.get('line2', 'N/A')}\n")
            profile_text.append(f"City: {addr.get('city', 'N/A')}\n")
            profile_text.append(f"State: {addr.get('state', 'N/A')}\n")
            profile_text.append(f"Postal Code: {addr.get('postal_code', 'N/A')}\n")
            profile_text.append(f"Country: {addr.get('country', 'N/A')}\n")
        
        zf.writestr("profile_summary.txt", "".join(profile_text))
        
        # 3. Orders as CSV
        orders = export_data.get("data", {}).get("orders", [])
        if orders:
            csv_buffer = io.StringIO()
            writer = csv.DictWriter(csv_buffer, fieldnames=[
                "order_number", "status", "type", "total", "currency", 
                "payment_method", "created_at"
            ])
            writer.writeheader()
            for order in orders:
                writer.writerow({
                    "order_number": order.get("order_number"),
                    "status": order.get("status"),
                    "type": order.get("type"),
                    "total": order.get("total"),
                    "currency": order.get("currency"),
                    "payment_method": order.get("payment_method"),
                    "created_at": order.get("created_at")
                })
            zf.writestr("orders.csv", csv_buffer.getvalue())
        
        # 4. Subscriptions as CSV
        subs = export_data.get("data", {}).get("subscriptions", [])
        if subs:
            csv_buffer = io.StringIO()
            writer = csv.DictWriter(csv_buffer, fieldnames=[
                "subscription_number", "plan_name", "status", "amount", 
                "currency", "billing_cycle", "created_at"
            ])
            writer.writeheader()
            for sub in subs:
                writer.writerow({
                    "subscription_number": sub.get("subscription_number"),
                    "plan_name": sub.get("plan_name"),
                    "status": sub.get("status"),
                    "amount": sub.get("amount"),
                    "currency": sub.get("currency"),
                    "billing_cycle": sub.get("billing_cycle"),
                    "created_at": sub.get("created_at")
                })
            zf.writestr("subscriptions.csv", csv_buffer.getvalue())
    
    buffer.seek(0)
    return buffer.getvalue()


async def request_data_deletion(
    customer_id: str, 
    tenant_id: str, 
    reason: str = ""
) -> Dict[str, Any]:
    """
    Process a GDPR right-to-erasure request.
    This anonymizes customer data instead of hard deletion to maintain data integrity.
    """
    now = datetime.now(timezone.utc).isoformat()
    anonymized_email = f"deleted_{customer_id[:8]}@anonymized.local"
    
    # 1. Get customer info for audit
    customer = await db.customers.find_one(
        {"id": customer_id, "tenant_id": tenant_id},
        {"_id": 0}
    )
    
    if not customer:
        return {"success": False, "error": "Customer not found"}
    
    user_id = customer.get("user_id")
    original_email = customer.get("email")
    
    # 2. Anonymize customer record
    await db.customers.update_one(
        {"id": customer_id, "tenant_id": tenant_id},
        {"$set": {
            "email": anonymized_email,
            "full_name": "Deleted User",
            "company_name": "Deleted",
            "phone": "",
            "is_active": False,
            "gdpr_deleted": True,
            "gdpr_deleted_at": now,
            "gdpr_deletion_reason": reason
        }}
    )
    
    # 3. Anonymize user account
    if user_id:
        await db.users.update_one(
            {"id": user_id},
            {"$set": {
                "email": anonymized_email,
                "full_name": "Deleted User",
                "company_name": "Deleted",
                "phone": "",
                "is_active": False,
                "is_verified": False,
                "gdpr_deleted": True,
                "gdpr_deleted_at": now
            }}
        )
    
    # 4. Delete address
    await db.addresses.delete_one({"customer_id": customer_id})
    
    # 5. Delete customer notes
    await db.customer_notes.delete_many(
        {"customer_id": customer_id, "tenant_id": tenant_id}
    )
    
    # 6. Anonymize quote requests (keep for business records, anonymize PII)
    await db.quote_requests.update_many(
        {"customer_id": customer_id, "tenant_id": tenant_id},
        {"$set": {
            "email": anonymized_email,
            "contact_name": "Deleted User",
            "company_name": "Deleted",
            "phone": "",
            "gdpr_anonymized": True
        }}
    )
    
    # 7. Create audit log
    await db.audit_logs.insert_one({
        "tenant_id": tenant_id,
        "entity_type": "gdpr_deletion",
        "entity_id": customer_id,
        "action": "data_deletion_request",
        "actor": f"customer:{customer_id}",
        "details": {
            "original_email": original_email,
            "reason": reason,
            "anonymized_at": now
        },
        "created_at": now
    })
    
    # 8. Create deletion request record for compliance tracking
    await db.gdpr_requests.insert_one({
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "request_type": "erasure",
        "original_email": original_email,
        "status": "completed",
        "requested_at": now,
        "completed_at": now,
        "reason": reason
    })
    
    return {
        "success": True,
        "message": "Data deletion completed successfully",
        "customer_id": customer_id,
        "completed_at": now
    }


async def get_gdpr_requests(tenant_id: str) -> List[Dict[str, Any]]:
    """Get all GDPR requests for a tenant (admin view)."""
    requests = await db.gdpr_requests.find(
        {"tenant_id": tenant_id},
        {"_id": 0}
    ).sort("requested_at", -1).to_list(500)
    return requests
