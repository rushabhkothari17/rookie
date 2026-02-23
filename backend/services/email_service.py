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
        "label": "New Scope Request (Admin Notification)",
        "description": "Sent to the admin when a customer submits a scope request.",
        "subject": "New Scope Request: {{order_number}} from {{customer_name}}",
        "html_body": """<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:20px">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:32px;border:1px solid #e2e8f0">
  <p style="color:#94a3b8;font-size:13px;margin:0 0 8px">{{store_name}} — Admin Notification</p>
  <h2 style="color:#1e293b;margin:0 0 16px">New Scope Request: {{order_number}}</h2>
  <p><strong>Customer:</strong> {{customer_name}} ({{customer_email}})</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0">
  <p><strong>Project Summary:</strong><br>{{project_summary}}</p>
  <p><strong>Desired Outcomes:</strong><br>{{desired_outcomes}}</p>
  <p><strong>Apps Involved:</strong> {{apps_involved}}</p>
  <p><strong>Timeline:</strong> {{timeline_urgency}}</p>
  <p><strong>Budget:</strong> {{budget_range}}</p>
  <p><strong>Notes:</strong> {{additional_notes}}</p>
  <p style="color:#94a3b8;font-size:12px;margin-top:32px;border-top:1px solid #f1f5f9;padding-top:16px">© {{store_name}}</p>
</div></body></html>""",
        "is_enabled": True,
        "available_variables": ["{{store_name}}", "{{order_number}}", "{{customer_name}}", "{{customer_email}}", "{{project_summary}}", "{{desired_outcomes}}", "{{apps_involved}}", "{{timeline_urgency}}", "{{budget_range}}", "{{additional_notes}}"],
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
        "is_enabled": False,
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


async def _resolve_refs(text: str, db) -> str:
    """Replace {{ref:key}} with values from website_references collection."""
    refs = await db.website_references.find({}, {"_id": 0}).to_list(500)
    ref_map = {r["key"]: r["value"] for r in refs}

    def replacer(m: re.Match) -> str:  # type: ignore[type-arg]
        key = m.group(1).strip()
        return ref_map.get(key, m.group(0))
    return re.sub(r"\{\{ref:([^}]+)\}\}", replacer, text)


class EmailService:
    @staticmethod
    async def ensure_seeded(db, tenant_id: str = "automate-accounts") -> None:
        """Seed default email templates for a tenant if none exist."""
        count = await db.email_templates.count_documents({"tenant_id": tenant_id})
        if count == 0:
            now = now_iso()
            docs = [{"id": make_id(), "tenant_id": tenant_id, "created_at": now, "updated_at": now, **t} for t in _TEMPLATES]
            await db.email_templates.insert_many(docs)

    @staticmethod
    async def send(trigger: str, recipient: str, variables: Dict[str, Any], db, admin_notify: bool = False) -> Dict[str, Any]:
        """
        Send an email using the configured provider.
        Falls back to email_outbox (mocked) when provider is disabled.
        Logs all attempts to email_logs.
        """
        await EmailService.ensure_seeded(db)

        template = await db.email_templates.find_one({"trigger": trigger}, {"_id": 0})
        if not template:
            return {"status": "skipped", "reason": f"no template for trigger: {trigger}"}
        if not template.get("is_enabled", True):
            return {"status": "skipped", "reason": "template disabled"}

        # Resolve store_name
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
            "created_at": now_iso(),
        }

        provider_enabled = await SettingsService.get("email_provider_enabled", False)
        resend_key = await SettingsService.get("resend_api_key", "")

        if provider_enabled and resend_key:
            from_name = await SettingsService.get("email_from_name", "") or store_name
            from_email = await SettingsService.get("resend_sender_email", "noreply@example.com")
            reply_to = await SettingsService.get("email_reply_to", "") or None
            cc_str = await SettingsService.get("email_cc", "") or ""
            bcc_str = await SettingsService.get("email_bcc", "") or ""

            log_entry["provider"] = "resend"
            try:
                import resend as resend_sdk
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
                await asyncio.to_thread(resend_sdk.Emails.send, params)
                log_entry["status"] = "sent"
            except Exception as exc:
                log_entry["status"] = "failed"
                log_entry["error_message"] = str(exc)
                await db.email_logs.insert_one(log_entry)
                return {"status": "failed", "error": str(exc)}
        else:
            # Mocked — write to outbox
            log_entry["status"] = "mocked"
            await db.email_outbox.insert_one({
                "id": make_id(),
                "to": recipient,
                "subject": subject,
                "body": body,
                "type": trigger,
                "status": "MOCKED",
                "created_at": now_iso(),
            })

        await db.email_logs.insert_one(log_entry)
        return {"status": log_entry["status"]}
