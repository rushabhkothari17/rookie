"""
Centralised email service.

Usage:
    from services.email_service import EmailService
    await EmailService.send(trigger="verification", recipient="user@example.com",
                            variables={"verification_code": "123456"}, db=db)
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, Optional

from core.helpers import make_id, now_iso
from services.settings_service import SettingsService

# ---------------------------------------------------------------------------
# Default email templates
# ---------------------------------------------------------------------------

_TEMPLATES: list[Dict[str, Any]] = [
    {
        "trigger": "verification",
        "label": "Customer Verification",
        "description": "Sent when a customer registers and needs to verify their email address.",
        "subject": "Verify your {{store_name}} account",
        "html_body": """<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:32px;border:1px solid #e2e8f0">
  <p style="color:#94a3b8;font-size:13px;margin:0 0 8px">{{store_name}}</p>
  <h2 style="color:#1e293b;margin:0 0 16px">Verify your email</h2>
  <p style="color:#475569;">Hi {{customer_name}},</p>
  <p style="color:#475569;">Your verification code is:</p>
  <div style="background:#f1f5f9;border-radius:8px;padding:16px 24px;text-align:center;margin:24px 0">
    <span style="font-size:32px;font-weight:700;letter-spacing:8px;color:#1e293b">{{verification_code}}</span>
  </div>
  <p style="color:#64748b;font-size:14px;">This code expires in 24 hours.</p>
  <p style="color:#94a3b8;font-size:12px;margin-top:32px;border-top:1px solid #f1f5f9;padding-top:16px">© {{store_name}}</p>
</div></body></html>""",
        "is_enabled": True,
        "available_variables": ["{{store_name}}", "{{customer_name}}", "{{customer_email}}", "{{verification_code}}"],
        "is_system": True,
    },
    {
        "trigger": "article_email",
        "label": "Article Shared with Customer",
        "description": "Sent when an admin manually shares an article/document with customers.",
        "subject": "{{article_title}} — from {{store_name}}",
        "html_body": """<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:32px;border:1px solid #e2e8f0">
  <p style="color:#94a3b8;font-size:13px;margin:0 0 8px">{{store_name}}</p>
  <h2 style="color:#1e293b;margin:0 0 8px">{{article_title}}</h2>
  <p style="color:#64748b;font-size:13px;margin:0 0 16px">{{article_category}}</p>
  <p style="color:#475569;">{{article_message}}</p>
  <a href="{{article_url}}" style="display:inline-block;background:#1e293b;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;margin:16px 0;font-weight:600">{{cta_text}}</a>
  <p style="color:#94a3b8;font-size:12px;margin-top:32px;border-top:1px solid #f1f5f9;padding-top:16px">{{footer_text}}<br>© {{store_name}}</p>
</div></body></html>""",
        "is_enabled": True,
        "available_variables": ["{{store_name}}", "{{article_title}}", "{{article_category}}", "{{article_url}}", "{{article_message}}", "{{article_price}}", "{{cta_text}}", "{{footer_text}}"],
        "is_system": True,
    },
    {
        "trigger": "quote_request_admin",
        "label": "New Quote Request (Admin Notification)",
        "description": "Sent to the admin when a customer submits a quote request.",
        "subject": "New Quote Request: {{product_name}} from {{customer_name}}",
        "html_body": """<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:32px;border:1px solid #e2e8f0">
  <p style="color:#94a3b8;font-size:13px;margin:0 0 8px">{{store_name}} — Admin Notification</p>
  <h2 style="color:#1e293b;margin:0 0 16px">New Quote Request</h2>
  <table style="width:100%;border-collapse:collapse">
    <tr><td style="padding:8px 0;color:#64748b;font-size:13px;width:140px">Product</td><td style="padding:8px 0;color:#1e293b;font-weight:600">{{product_name}}</td></tr>
    <tr><td style="padding:8px 0;color:#64748b;font-size:13px">Name</td><td style="padding:8px 0;color:#1e293b">{{customer_name}}</td></tr>
    <tr><td style="padding:8px 0;color:#64748b;font-size:13px">Email</td><td style="padding:8px 0;color:#1e293b">{{customer_email}}</td></tr>
    <tr><td style="padding:8px 0;color:#64748b;font-size:13px">Company</td><td style="padding:8px 0;color:#1e293b">{{company}}</td></tr>
    <tr><td style="padding:8px 0;color:#64748b;font-size:13px">Phone</td><td style="padding:8px 0;color:#1e293b">{{phone}}</td></tr>
    <tr><td style="padding:8px 0;color:#64748b;font-size:13px;vertical-align:top">Message</td><td style="padding:8px 0;color:#1e293b">{{message}}</td></tr>
  </table>
  <p style="color:#94a3b8;font-size:12px;margin-top:32px;border-top:1px solid #f1f5f9;padding-top:16px">© {{store_name}}</p>
</div></body></html>""",
        "is_enabled": True,
        "available_variables": ["{{store_name}}", "{{product_name}}", "{{customer_name}}", "{{customer_email}}", "{{company}}", "{{phone}}", "{{message}}"],
        "is_system": True,
    },
    {
        "trigger": "quote_request_customer",
        "label": "Quote Request Confirmation (Customer)",
        "description": "Sent to the customer confirming their quote request was received.",
        "subject": "We've received your quote request — {{product_name}}",
        "html_body": """<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:32px;border:1px solid #e2e8f0">
  <p style="color:#94a3b8;font-size:13px;margin:0 0 8px">{{store_name}}</p>
  <h2 style="color:#1e293b;margin:0 0 16px">Quote Request Received</h2>
  <p style="color:#475569;">Hi {{customer_name}},</p>
  <p style="color:#475569;">Thank you for your interest in <strong>{{product_name}}</strong>. We've received your request and will get back to you shortly.</p>
  <p style="color:#94a3b8;font-size:12px;margin-top:32px;border-top:1px solid #f1f5f9;padding-top:16px">© {{store_name}}</p>
</div></body></html>""",
        "is_enabled": False,
        "available_variables": ["{{store_name}}", "{{product_name}}", "{{customer_name}}", "{{customer_email}}"],
        "is_system": True,
    },
    {
        "trigger": "scope_request_admin",
        "label": "New Enquiry (Admin Notification)",
        "description": "Sent to the admin when a customer submits an enquiry (scope request or quote request).",
        "subject": "New Enquiry: {{order_number}} from {{customer_name}}",
        "html_body": """<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:32px;border:1px solid #e2e8f0">
  <p style="color:#94a3b8;font-size:13px;margin:0 0 8px">{{store_name}} — Admin Notification</p>
  <h2 style="color:#1e293b;margin:0 0 4px">New Enquiry</h2>
  <p style="color:#64748b;font-size:13px;margin:0 0 20px">Reference: <strong>{{order_number}}</strong></p>
  <div style="background:#f8fafc;border-radius:6px;padding:16px;margin-bottom:20px">
    <p style="color:#1e293b;font-weight:600;margin:0 0 10px;font-size:14px">Customer</p>
    <table style="width:100%;border-collapse:collapse">
      <tr><td style="padding:4px 0;color:#64748b;font-size:13px;width:140px">Name</td><td style="padding:4px 0;color:#1e293b">{{customer_name}}</td></tr>
      <tr><td style="padding:4px 0;color:#64748b;font-size:13px">Email</td><td style="padding:4px 0;color:#1e293b">{{customer_email}}</td></tr>
      <tr><td style="padding:4px 0;color:#64748b;font-size:13px">Company</td><td style="padding:4px 0;color:#1e293b">{{company}}</td></tr>
      <tr><td style="padding:4px 0;color:#64748b;font-size:13px">Phone</td><td style="padding:4px 0;color:#1e293b">{{phone}}</td></tr>
      <tr><td style="padding:4px 0;color:#64748b;font-size:13px">Products</td><td style="padding:4px 0;color:#1e293b;font-weight:600">{{products}}</td></tr>
    </table>
  </div>
  <div style="border-top:1px solid #e2e8f0;padding-top:16px">
    <p style="color:#1e293b;font-weight:600;margin:0 0 10px;font-size:14px">Submission Details</p>
    <table style="width:100%;border-collapse:collapse">
      <tr><td style="padding:6px 0;color:#64748b;font-size:13px;width:160px;vertical-align:top">Message</td><td style="padding:6px 0;color:#1e293b">{{message}}</td></tr>
      <tr><td style="padding:6px 0;color:#64748b;font-size:13px;vertical-align:top">Project Summary</td><td style="padding:6px 0;color:#1e293b">{{project_summary}}</td></tr>
      <tr><td style="padding:6px 0;color:#64748b;font-size:13px;vertical-align:top">Desired Outcomes</td><td style="padding:6px 0;color:#1e293b">{{desired_outcomes}}</td></tr>
      <tr><td style="padding:6px 0;color:#64748b;font-size:13px">Apps Involved</td><td style="padding:6px 0;color:#1e293b">{{apps_involved}}</td></tr>
      <tr><td style="padding:6px 0;color:#64748b;font-size:13px">Timeline / Urgency</td><td style="padding:6px 0;color:#1e293b">{{timeline_urgency}}</td></tr>
      <tr><td style="padding:6px 0;color:#64748b;font-size:13px">Budget Range</td><td style="padding:6px 0;color:#1e293b">{{budget_range}}</td></tr>
      <tr><td style="padding:6px 0;color:#64748b;font-size:13px;vertical-align:top">Additional Notes</td><td style="padding:6px 0;color:#1e293b">{{additional_notes}}</td></tr>
    </table>
  </div>
  <p style="color:#94a3b8;font-size:12px;margin-top:32px;border-top:1px solid #f1f5f9;padding-top:16px">© {{store_name}}</p>
</div></body></html>""",
        "is_enabled": True,
        "available_variables": ["{{store_name}}", "{{order_number}}", "{{customer_name}}", "{{customer_email}}", "{{company}}", "{{phone}}", "{{products}}", "{{message}}", "{{project_summary}}", "{{desired_outcomes}}", "{{apps_involved}}", "{{timeline_urgency}}", "{{budget_range}}", "{{additional_notes}}"],
        "is_system": True,
    },
    {
        "trigger": "enquiry_customer",
        "label": "Enquiry Confirmation (Customer)",
        "description": "Sent to the customer confirming their enquiry was received, with a full summary of what they submitted.",
        "subject": "We've received your enquiry — {{order_number}}",
        "html_body": """<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:32px;border:1px solid #e2e8f0">
  <p style="color:#94a3b8;font-size:13px;margin:0 0 8px">{{store_name}}</p>
  <h2 style="color:#1e293b;margin:0 0 8px">Enquiry Received</h2>
  <p style="color:#64748b;font-size:13px;margin:0 0 20px">Reference: <strong>{{order_number}}</strong></p>
  <p style="color:#475569;">Hi {{customer_name}},</p>
  <p style="color:#475569;">Thank you for getting in touch. We've received your enquiry about <strong>{{products}}</strong> and will be in touch with you shortly.</p>
  <div style="background:#f8fafc;border-radius:6px;padding:16px;margin:20px 0">
    <p style="color:#1e293b;font-weight:600;margin:0 0 10px;font-size:13px">Your Submission Summary</p>
    <table style="width:100%;border-collapse:collapse">
      <tr><td style="padding:4px 0;color:#64748b;font-size:13px;width:140px">Reference</td><td style="padding:4px 0;color:#1e293b;font-weight:600">{{order_number}}</td></tr>
      <tr><td style="padding:4px 0;color:#64748b;font-size:13px">Products</td><td style="padding:4px 0;color:#1e293b">{{products}}</td></tr>
      <tr><td style="padding:4px 0;color:#64748b;font-size:13px;vertical-align:top">Message / Summary</td><td style="padding:4px 0;color:#1e293b">{{summary}}</td></tr>
    </table>
  </div>
  <p style="color:#475569;font-size:13px">We aim to respond within 1-2 business days. If you have any urgent questions, please contact us directly.</p>
  <p style="color:#94a3b8;font-size:12px;margin-top:32px;border-top:1px solid #f1f5f9;padding-top:16px">© {{store_name}}</p>
</div></body></html>""",
        "is_enabled": True,
        "available_variables": ["{{store_name}}", "{{order_number}}", "{{customer_name}}", "{{customer_email}}", "{{products}}", "{{summary}}"],
        "is_system": True,
    },
    {
        "trigger": "order_placed",
        "label": "Order Confirmation (Customer)",
        "description": "Sent to the customer when an order is placed.",
        "subject": "Order Confirmed — {{order_number}}",
        "html_body": """<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:32px;border:1px solid #e2e8f0">
  <p style="color:#94a3b8;font-size:13px;margin:0 0 8px">{{store_name}}</p>
  <h2 style="color:#1e293b;margin:0 0 16px">Order Confirmed</h2>
  <p style="color:#475569;">Hi {{customer_name}},</p>
  <p style="color:#475569;">Your order <strong>{{order_number}}</strong> has been confirmed. Our team will be in touch shortly.</p>
  <p style="color:#94a3b8;font-size:12px;margin-top:32px;border-top:1px solid #f1f5f9;padding-top:16px">© {{store_name}}</p>
</div></body></html>""",
        "is_enabled": False,
        "available_variables": ["{{store_name}}", "{{order_number}}", "{{customer_name}}", "{{customer_email}}", "{{order_total}}", "{{order_currency}}"],
        "is_system": True,
    },
    {
        "trigger": "refund_processed",
        "label": "Refund Processed (Customer)",
        "description": "Sent to the customer when a refund is processed for their order.",
        "subject": "Refund Processed — {{order_number}}",
        "html_body": """<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:32px;border:1px solid #e2e8f0">
  <p style="color:#94a3b8;font-size:13px;margin:0 0 8px">{{store_name}}</p>
  <h2 style="color:#1e293b;margin:0 0 16px">Refund Processed</h2>
  <p style="color:#475569;">Hi {{customer_name}},</p>
  <p style="color:#475569;">We've processed a refund for your order <strong>{{order_number}}</strong>.</p>
  <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin:16px 0">
    <table style="width:100%;border-collapse:collapse">
      <tr><td style="padding:4px 0;color:#64748b;font-size:13px;width:140px">Refund Amount</td><td style="padding:4px 0;color:#15803d;font-weight:700;font-size:18px">{{refund_currency}}{{refund_amount}}</td></tr>
      <tr><td style="padding:4px 0;color:#64748b;font-size:13px">Reason</td><td style="padding:4px 0;color:#1e293b">{{refund_reason}}</td></tr>
      <tr><td style="padding:4px 0;color:#64748b;font-size:13px">Processing Time</td><td style="padding:4px 0;color:#1e293b">{{processing_time}}</td></tr>
    </table>
  </div>
  <p style="color:#475569;font-size:13px">The refund will be credited back to your original payment method. If you have any questions, please don't hesitate to contact us.</p>
  <p style="color:#94a3b8;font-size:12px;margin-top:32px;border-top:1px solid #f1f5f9;padding-top:16px">© {{store_name}}</p>
</div></body></html>""",
        "is_enabled": True,
        "available_variables": ["{{store_name}}", "{{order_number}}", "{{customer_name}}", "{{customer_email}}", "{{refund_amount}}", "{{refund_currency}}", "{{refund_reason}}", "{{processing_time}}", "{{payment_method}}"],
        "is_system": True,
    },
    {
        "trigger": "subscription_created",
        "label": "Subscription Started (Customer)",
        "description": "Sent to the customer when a new subscription is created.",
        "subject": "Subscription Active — {{store_name}}",
        "html_body": """<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:32px;border:1px solid #e2e8f0">
  <p style="color:#94a3b8;font-size:13px;margin:0 0 8px">{{store_name}}</p>
  <h2 style="color:#1e293b;margin:0 0 16px">Subscription Active</h2>
  <p style="color:#475569;">Hi {{customer_name}},</p>
  <p style="color:#475569;">Your subscription is now active. You can manage it any time from your portal.</p>
  <p style="color:#94a3b8;font-size:12px;margin-top:32px;border-top:1px solid #f1f5f9;padding-top:16px">© {{store_name}}</p>
</div></body></html>""",
        "is_enabled": False,
        "available_variables": ["{{store_name}}", "{{customer_name}}", "{{customer_email}}"],
        "is_system": True,
    },
    {
        "trigger": "subscription_cancellation",
        "label": "Subscription Cancellation (Customer)",
        "description": "Sent to the customer when a subscription cancellation is requested.",
        "subject": "Subscription Cancellation Confirmed — {{store_name}}",
        "html_body": """<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:32px;border:1px solid #e2e8f0">
  <p style="color:#94a3b8;font-size:13px;margin:0 0 8px">{{store_name}}</p>
  <h2 style="color:#1e293b;margin:0 0 16px">Cancellation Scheduled</h2>
  <p style="color:#475569;">Hi {{customer_name}},</p>
  <p style="color:#475569;">Your subscription will be cancelled at the end of the current billing period.</p>
  <p style="color:#94a3b8;font-size:12px;margin-top:32px;border-top:1px solid #f1f5f9;padding-top:16px">© {{store_name}}</p>
</div></body></html>""",
        "is_enabled": True,
        "available_variables": ["{{store_name}}", "{{customer_name}}", "{{customer_email}}"],
        "is_system": True,
    },
    {
        "trigger": "password_reset",
        "label": "Password Reset",
        "description": "Sent when a customer requests a password reset.",
        "subject": "Reset your {{store_name}} password",
        "html_body": """<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:32px;border:1px solid #e2e8f0">
  <p style="color:#94a3b8;font-size:13px;margin:0 0 8px">{{store_name}}</p>
  <h2 style="color:#1e293b;margin:0 0 16px">Reset your password</h2>
  <p style="color:#475569;">Hi {{customer_name}},</p>
  <p style="color:#475569;">Your password reset code is:</p>
  <div style="background:#f1f5f9;border-radius:8px;padding:16px 24px;text-align:center;margin:24px 0">
    <span style="font-size:28px;font-weight:700;letter-spacing:6px;color:#1e293b">{{reset_code}}</span>
  </div>
  <p style="color:#94a3b8;font-size:12px;margin-top:32px;border-top:1px solid #f1f5f9;padding-top:16px">© {{store_name}}</p>
</div></body></html>""",
        "is_enabled": True,
        "available_variables": ["{{store_name}}", "{{customer_name}}", "{{customer_email}}", "{{reset_code}}"],
        "is_system": True,
    },
]


def _resolve_vars(template: str, variables: Dict[str, Any]) -> str:
    """Replace {{var}} placeholders. Leaves {{ref:...}} untouched."""
    def replacer(m: re.Match) -> str:  # type: ignore[type-arg]
        key = m.group(1).strip()
        if key.startswith("ref:"):
            return m.group(0)
        val = variables.get(key)
        return str(val) if val is not None else ""
    return re.sub(r"\{\{([^}]+)\}\}", replacer, template)


async def _resolve_refs(text: str, db, tenant_id: str = "") -> str:
    """Replace {{ref:key}} with values from website_references collection.
    Looks up tenant-scoped refs first, then falls back to global (no tenant_id)."""
    query: dict = {}
    if tenant_id:
        query = {"$or": [{"tenant_id": tenant_id}, {"tenant_id": {"$exists": False}}]}
    refs = await db.website_references.find(query, {"_id": 0}).to_list(500)
    ref_map = {r["key"]: r["value"] for r in refs}

    def replacer(m: re.Match) -> str:  # type: ignore[type-arg]
        key = m.group(1).strip()
        return ref_map.get(key, m.group(0))
    return re.sub(r"\{\{ref:([^}]+)\}\}", replacer, text)


class EmailService:
    @staticmethod
    async def ensure_seeded(db, tenant_id: str = "automate-accounts") -> None:
        """
        Seed default email templates for a tenant.
        
        - Seeds all templates if none exist for the tenant
        - Seeds any missing templates if some exist (for new templates added later)
        - Updates existing system templates when their definition changes
        """
        existing_count = await db.email_templates.count_documents({"tenant_id": tenant_id})
        now = now_iso()
        
        if existing_count == 0:
            # First time seeding - add all templates
            docs = [{"id": make_id(), "tenant_id": tenant_id, "created_at": now, "updated_at": now, **t} for t in _TEMPLATES]
            await db.email_templates.insert_many(docs)
        else:
            # Check for missing templates and add them
            existing_triggers = set()
            cursor = db.email_templates.find(
                {"tenant_id": tenant_id},
                {"_id": 0, "trigger": 1}
            )
            async for doc in cursor:
                existing_triggers.add(doc["trigger"])
            
            # Find templates that don't exist yet
            missing = [t for t in _TEMPLATES if t["trigger"] not in existing_triggers]
            if missing:
                docs = [{"id": make_id(), "tenant_id": tenant_id, "created_at": now, "updated_at": now, **t} for t in missing]
                await db.email_templates.insert_many(docs)
            
            # Update system templates that have new available_variables (non-destructive: only if admin hasn't edited them)
            for t in _TEMPLATES:
                if t.get("is_system") and t["trigger"] in existing_triggers:
                    await db.email_templates.update_one(
                        {"tenant_id": tenant_id, "trigger": t["trigger"]},
                        {"$set": {"available_variables": t["available_variables"], "label": t["label"], "description": t["description"], "updated_at": now}},
                    )

    @staticmethod
    async def send(
        trigger: str,
        recipient: str,
        variables: Dict[str, Any],
        db,
        admin_notify: bool = False,
        attachments: Optional[list[Dict[str, Any]]] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an email using the configured provider.
        Falls back to email_outbox (mocked) when provider is disabled.
        Logs all attempts to email_logs.
        
        Args:
            trigger: Email template trigger name
            recipient: Email address to send to
            variables: Template variables to substitute
            db: Database instance
            admin_notify: Whether this is an admin notification
            attachments: Optional list of attachments. Each dict should have:
                - filename: str - Name of the file
                - content: bytes - File content
                - content_type: str - MIME type (e.g., "application/pdf")
            tenant_id: Optional tenant ID for tenant-scoped settings
        """
        await EmailService.ensure_seeded(db, tenant_id or "automate-accounts")

        # Look for template in tenant scope first, then fall back to global
        template = None
        if tenant_id:
            template = await db.email_templates.find_one(
                {"trigger": trigger, "tenant_id": tenant_id},
                {"_id": 0}
            )
        if not template:
            template = await db.email_templates.find_one({"trigger": trigger}, {"_id": 0})
        
        if not template:
            return {"status": "skipped", "reason": f"no template for trigger: {trigger}"}
        if not template.get("is_enabled", True):
            return {"status": "skipped", "reason": "template disabled"}

        # Resolve store_name (global setting)
        store_name = await SettingsService.get("store_name", "") or ""
        all_vars = {"store_name": store_name, **variables}

        subject = _resolve_vars(template["subject"], all_vars)
        body = _resolve_vars(template["html_body"], all_vars)

        # Resolve {{ref:key}} references
        subject = await _resolve_refs(subject, db)
        body = await _resolve_refs(body, db)

        log_entry: Dict[str, Any] = {
            "id": make_id(),
            "trigger": trigger,
            "recipient": recipient,
            "subject": subject,
            "status": "pending",
            "provider": "mocked",
            "has_attachments": bool(attachments),
            "attachment_count": len(attachments) if attachments else 0,
            "created_at": now_iso(),
        }
        if tenant_id:
            log_entry["tenant_id"] = tenant_id

        # Check for email provider in oauth_connections (Connected Services)
        resend_conn = None
        zoho_mail_conn = None
        
        if tenant_id:
            resend_conn = await db.oauth_connections.find_one(
                {"tenant_id": tenant_id, "provider": "resend", "is_validated": True},
                {"_id": 0}
            )
            zoho_mail_conn = await db.oauth_connections.find_one(
                {"tenant_id": tenant_id, "provider": "zoho_mail", "is_validated": True},
                {"_id": 0}
            )
        
        # Also check global/tenant-less connections
        if not resend_conn:
            resend_conn = await db.oauth_connections.find_one(
                {"provider": "resend", "is_validated": True, "$or": [{"tenant_id": {"$exists": False}}, {"tenant_id": None}]},
                {"_id": 0}
            )
        if not zoho_mail_conn:
            zoho_mail_conn = await db.oauth_connections.find_one(
                {"provider": "zoho_mail", "is_validated": True, "$or": [{"tenant_id": {"$exists": False}}, {"tenant_id": None}]},
                {"_id": 0}
            )
        
        # Try Resend first if connected
        if resend_conn:
            creds = resend_conn.get("credentials", {})
            resend_settings = resend_conn.get("settings", {})
            resend_key = creds.get("api_key", "")
            # from_email is stored in settings for Resend
            from_email = resend_settings.get("from_email", "") or creds.get("sender_email", "") or creds.get("from_email", "noreply@example.com")
            
            if resend_key:
                from_name = await SettingsService.get("email_from_name", "") or store_name
                reply_to = await SettingsService.get("email_reply_to", "") or None
                cc_str = await SettingsService.get("email_cc", "") or ""
                bcc_str = await SettingsService.get("email_bcc", "") or ""

                log_entry["provider"] = "resend"
                try:
                    import resend as resend_sdk
                    import base64
                    resend_sdk.api_key = resend_key
                    params: Dict[str, Any] = {
                        "from": f"{from_name} <{from_email}>" if from_name else from_email,
                        "to": [recipient],
                        "subject": subject,
                        "html": body,
                    }
                    if reply_to:
                        params["reply_to"] = reply_to
                    if cc_str:
                        params["cc"] = [e.strip() for e in cc_str.split(",") if e.strip()]
                    if bcc_str:
                        params["bcc"] = [e.strip() for e in bcc_str.split(",") if e.strip()]
                    
                    # Add attachments if provided
                    if attachments:
                        params["attachments"] = [
                            {
                                "filename": att["filename"],
                                "content": base64.b64encode(att["content"]).decode("utf-8"),
                                "content_type": att.get("content_type", "application/octet-stream")
                            }
                            for att in attachments
                        ]
                    
                    await asyncio.to_thread(resend_sdk.Emails.send, params)
                    log_entry["status"] = "sent"
                except Exception as exc:
                    log_entry["status"] = "failed"
                    log_entry["error_message"] = str(exc)
                    await db.email_logs.insert_one(log_entry)
                    return {"status": "failed", "error": str(exc)}
        # Try Zoho Mail if connected and Resend not available
        elif zoho_mail_conn:
            from services.zoho_service import ZohoMailService, ZohoOAuthService
            creds = zoho_mail_conn.get("credentials", {})
            # from_email is stored in settings, not credentials
            settings = zoho_mail_conn.get("settings", {})
            from_email = settings.get("from_email", "") or settings.get("sender_email", "")
            from_name = settings.get("from_name", "")
            account_id = creds.get("account_id", "")
            datacenter = (zoho_mail_conn.get("data_center") or "US").upper()

            if from_email and account_id:
                # Refresh the access token using stored credentials
                oauth_svc = ZohoOAuthService(tenant_id or "", datacenter)
                try:
                    token_result = await oauth_svc.refresh_access_token(
                        creds.get("refresh_token", ""),
                        creds.get("client_id", ""),
                        creds.get("client_secret", ""),
                    )
                    access_token = token_result.get("access_token", "")
                except Exception as exc:
                    log_entry["status"] = "failed"
                    log_entry["error_message"] = f"Zoho token refresh failed: {exc}"
                    await db.email_logs.insert_one(log_entry)
                    return {"status": "failed", "error": str(exc)}

                if not access_token:
                    log_entry["status"] = "failed"
                    log_entry["error_message"] = "Zoho token refresh returned no access_token"
                    await db.email_logs.insert_one(log_entry)
                    return {"status": "failed", "error": "Failed to refresh Zoho access token"}

                from_address = f"{from_name} <{from_email}>" if from_name else from_email
                zoho_mail_svc = ZohoMailService(tenant_id or "", datacenter)
                result = await zoho_mail_svc.send_email(
                    access_token=access_token,
                    account_id=account_id,
                    from_address=from_address,
                    to_addresses=[recipient],
                    subject=subject,
                    content=body,
                    content_type="html",
                )
                log_entry["provider"] = "zoho_mail"
                if result.get("success"):
                    log_entry["status"] = "sent"
                else:
                    log_entry["status"] = "failed"
                    log_entry["error_message"] = result.get("error", "Unknown Zoho Mail error")
                    await db.email_logs.insert_one(log_entry)
                    return {"status": "failed", "error": result.get("error")}
            else:
                # Missing from_email or account_id — fall through to mocked
                log_entry["status"] = "mocked"
                log_entry["error_message"] = "Zoho Mail configured but from_email or account_id missing"
                outbox_entry = {
                    "id": make_id(), "to": recipient, "subject": subject, "body": body,
                    "type": trigger, "status": "MOCKED", "created_at": now_iso(),
                }
                if tenant_id:
                    outbox_entry["tenant_id"] = tenant_id
                await db.email_outbox.insert_one(outbox_entry)
        else:
            # Mocked — write to outbox
            log_entry["status"] = "mocked"
            outbox_entry = {
                "id": make_id(),
                "to": recipient,
                "subject": subject,
                "body": body,
                "type": trigger,
                "status": "MOCKED",
                "has_attachments": bool(attachments),
                "attachment_names": [att["filename"] for att in attachments] if attachments else [],
                "created_at": now_iso(),
            }
            if tenant_id:
                outbox_entry["tenant_id"] = tenant_id
            await db.email_outbox.insert_one(outbox_entry)

        await db.email_logs.insert_one(log_entry)
        return {"status": log_entry["status"]}
