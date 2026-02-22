from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, UploadFile, File, Body
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    CheckoutStatusResponse,
)
import stripe as stripe_sdk
import os
import uuid
import jwt
import secrets
import csv
import io
import base64
import asyncio
import re as _re
import resend
from gocardless_helper import create_gocardless_customer, create_redirect_flow, complete_redirect_flow, create_payment, get_payment_status

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ---------------------------------------------------------------------------
# Infrastructure imports from new modules
# ---------------------------------------------------------------------------
from db.session import db, client                          # MongoDB connection
from core.config import JWT_SECRET, STRIPE_API_KEY, ADMIN_EMAIL, ADMIN_PASSWORD  # env config
from core.helpers import (                                 # pure utils
    now_iso, make_id, round_cents, round_to_nearest_99,
    round_nearest_25, currency_for_country, _deep_merge, _slugify,
)
from core.security import (                               # auth + deps
    security, pwd_context,
    create_access_token, decode_token,
    get_current_user, require_admin, require_super_admin, optional_get_current_user,
)
from core.constants import (                             # hardcoded constants
    ALLOWED_ORDER_STATUSES, ALLOWED_SUBSCRIPTION_STATUSES,
    SERVICE_FEE_RATE, PREMIUM_MIGRATION_ITEMS, STANDARD_MIGRATION_SOURCES,
    PARTNER_TAG_RESPONSES, ARTICLE_CATEGORIES, SCOPE_FINAL_CATEGORIES,
)
from services.audit_service import AuditService, ensure_audit_indexes, create_audit_log
from services.settings_service import SettingsService
from middleware.request_id import RequestIDMiddleware

app = FastAPI()

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Include new route modules
# ---------------------------------------------------------------------------
from routes.auth import router as auth_router
from routes.store import router as store_router
from routes.checkout import router as checkout_router
from routes.gocardless import router as gocardless_router
from routes.webhooks import router as webhooks_router
from routes.admin.logs import router as audit_logs_router
from routes.admin.misc import router as admin_misc_router
from routes.admin.promo_codes import router as admin_promo_codes_router
from routes.admin.terms import router as admin_terms_router
from routes.admin.customers import router as admin_customers_router
from routes.admin.orders import router as admin_orders_router
from routes.admin.subscriptions import router as admin_subscriptions_router
from routes.admin.users import router as admin_users_router
from routes.admin.catalog import router as admin_catalog_router
from routes.admin.quote_requests import router as admin_quote_requests_router
from routes.admin.bank_transactions import router as admin_bank_transactions_router
from routes.admin.override_codes import router as admin_override_codes_router
from routes.admin.exports import router as admin_exports_router
from routes.admin.settings import router as admin_settings_router
from routes.articles import router as articles_router

app.include_router(auth_router)
app.include_router(store_router)
app.include_router(checkout_router)
app.include_router(gocardless_router)
app.include_router(webhooks_router)
app.include_router(audit_logs_router)
app.include_router(admin_misc_router)
app.include_router(admin_promo_codes_router)
app.include_router(admin_terms_router)
app.include_router(admin_customers_router)
app.include_router(admin_orders_router)
app.include_router(admin_subscriptions_router)
app.include_router(admin_users_router)
app.include_router(admin_catalog_router)
app.include_router(admin_quote_requests_router)
app.include_router(admin_bank_transactions_router)
app.include_router(admin_override_codes_router)
app.include_router(admin_exports_router)
app.include_router(admin_settings_router)
app.include_router(articles_router)


# ALLOWED_ORDER_STATUSES and ALLOWED_SUBSCRIPTION_STATUSES are imported from core.constants above.

def validate_order_status(status: str) -> bool:
    """Validate order status against allowed values"""
    return status in ALLOWED_ORDER_STATUSES


# --- Utility functions now live in core/helpers.py and core/security.py ---
# now_iso, make_id, round_cents, round_to_nearest_99, round_nearest_25,
# currency_for_country, _deep_merge, _slugify  → imported at top
# PREMIUM_MIGRATION_ITEMS, STANDARD_MIGRATION_SOURCES → imported at top
# create_access_token, decode_token, get_current_user, require_admin,
# require_super_admin, optional_get_current_user → imported at top


def calculate_books_migration_price(inputs: Dict[str, Any]) -> Dict[str, Any]:
    years_raw = str(inputs.get("years", "1")).replace("+YTD", "").replace("Y", "").strip()
    try:
        years = max(1, int(years_raw))
    except ValueError:
        years = 1
    data_types = inputs.get("data_types", [])
    if isinstance(data_types, str):
        data_types = [d.strip() for d in data_types.split(",") if d.strip()]
    has_premium = any(d in PREMIUM_MIGRATION_ITEMS for d in data_types)
    source_system = inputs.get("source_system", "quickbooks_online")

    base = 999.0
    if years > 1:
        extra = years - 1
        up_to_5 = min(extra, 4)   # years 2-5 → +350 each
        over_5 = max(0, extra - 4) # years 6+ → +300 each
        base += up_to_5 * 350.0 + over_5 * 300.0
    if has_premium:
        base *= 1.5
    if source_system not in STANDARD_MIGRATION_SOURCES:
        base *= 1.2

    price = round_to_nearest_99(base)
    line_items = [
        {"label": f"Migration ({years}Y + YTD)", "amount": 999.0},
    ]
    if years > 1:
        extra = years - 1
        up_to_5 = min(extra, 4)
        over_5 = max(0, extra - 4)
        if up_to_5:
            line_items.append({"label": f"+{up_to_5} additional year(s) × $350", "amount": up_to_5 * 350.0})
        if over_5:
            line_items.append({"label": f"+{over_5} additional year(s) × $300", "amount": over_5 * 300.0})
    if has_premium:
        line_items.append({"label": "Premium features (1.5× multiplier)", "amount": 0})
    if source_system not in STANDARD_MIGRATION_SOURCES:
        line_items.append({"label": "Source system complexity (1.2× multiplier)", "amount": 0})
    return {"subtotal": float(price), "line_items": line_items}


# round_nearest_25 is imported from core.helpers above.


def resolve_terms_tags(content: str, user: Dict[str, Any], address: Dict[str, Any], product_name: str) -> str:
    """Resolve dynamic tags in T&C content"""
    resolved = content
    resolved = resolved.replace("{product_name}", product_name)
    resolved = resolved.replace("{user_name}", user.get("full_name", ""))
    resolved = resolved.replace("{company_name}", user.get("company_name", ""))
    resolved = resolved.replace("{user_company_name}", user.get("company_name", ""))
    resolved = resolved.replace("{user_job_title}", user.get("job_title", ""))
    resolved = resolved.replace("{user_email}", user.get("email", ""))
    resolved = resolved.replace("{user_phone}", user.get("phone", ""))
    if address:
        resolved = resolved.replace("{user_address_line1}", address.get("line1", ""))
        resolved = resolved.replace("{user_city}", address.get("city", ""))
        resolved = resolved.replace("{user_state}", address.get("region", ""))
        resolved = resolved.replace("{user_postal}", address.get("postal", ""))
        resolved = resolved.replace("{user_country}", address.get("country", ""))
    return resolved


async def create_audit_log(entity_type: str, entity_id: str, action: str, actor: str, details: Dict[str, Any] = None):
    """Bridge: write to legacy audit_logs AND new comprehensive audit_trail collection."""
    await db.audit_logs.insert_one({
        "id": make_id(),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "actor": actor,
        "details": details or {},
        "created_at": now_iso(),
    })
    # Also write to the comprehensive audit trail
    actor_type = "admin" if "admin" in (actor or "").lower() else "system"
    await AuditService.log(
        action=f"{entity_type.upper()}_{action.upper().replace(' ', '_')}",
        description=f"{action} on {entity_type} {entity_id} by {actor}",
        entity_type=entity_type.capitalize(),
        entity_id=entity_id,
        actor_type=actor_type,
        actor_email=actor if "@" in (actor or "") else None,
        source="api",
        meta_json=details or {},
    )


# _deep_merge now lives in core/helpers.py (imported at top)
# kept here as alias for backward-compat with any existing references


def build_checkout_notes_json(
    order_items: list,
    payload,
    user_id: str,
    customer_id: str,
    payment_method: str = "unknown",
) -> dict:
    """Build JSON blob capturing all checkout inputs for order/subscription notes."""
    product_intake = {}
    scope_unlocks = {}
    for item in order_items:
        pid = item["product"]["id"]
        raw_inputs = dict(item.get("inputs") or {})
        # Extract scope unlock metadata if present
        if "_scope_unlock" in raw_inputs:
            scope_unlocks[pid] = raw_inputs.pop("_scope_unlock")
        product_intake[pid] = raw_inputs

    blob: dict = {
        "product_intake": product_intake,
        "checkout_intake": {
            "zoho_subscription_type": getattr(payload, "zoho_subscription_type", None),
            "current_zoho_product": getattr(payload, "current_zoho_product", None),
            "zoho_account_access": getattr(payload, "zoho_account_access", None),
            "partner_tag_response": getattr(payload, "partner_tag_response", None),
            "promo_code": getattr(payload, "promo_code", None),
            "terms_accepted": getattr(payload, "terms_accepted", False),
            "override_code_used": bool(getattr(payload, "override_code", None)),
        },
        "payment": {
            "method": payment_method,
        },
        "system_metadata": {
            "user_id": user_id,
            "customer_id": customer_id,
            "timestamp": now_iso(),
        },
    }
    if scope_unlocks:
        blob["scope_unlocks"] = scope_unlocks
    return blob


async def validate_and_consume_partner_tag(
    customer_id: str,
    partner_tag_response: Optional[str],
    override_code: Optional[str],
    order_id: Optional[str] = None,
) -> Optional[str]:
    """
    Validates partner tag response and override code (if needed).
    Updates customer partner_map and marks override code as used.
    Returns override_code_id if a code was consumed, else None.
    Raises HTTPException on validation failure.
    """
    if not partner_tag_response or partner_tag_response not in VALID_PARTNER_TAG_RESPONSES:
        raise HTTPException(
            status_code=400,
            detail="Please select whether you have tagged us as your Zoho Partner before proceeding."
        )

    override_code_id = None

    if partner_tag_response == "Not yet":
        if not override_code or not override_code.strip():
            await create_audit_log(
                entity_type="checkout", entity_id=customer_id,
                action="checkout_blocked_no_override_code", actor="system",
                details={"reason": "No override code provided", "partner_tag": partner_tag_response}
            )
            raise HTTPException(
                status_code=400,
                detail="An override code is required to proceed without tagging us as your Zoho Partner."
            )

        oc = await db.override_codes.find_one({"code": override_code.strip()}, {"_id": 0})
        if not oc:
            await create_audit_log(
                entity_type="checkout", entity_id=customer_id,
                action="checkout_blocked_invalid_override_code", actor="system",
                details={"reason": "Override code not found", "code": override_code}
            )
            raise HTTPException(status_code=400, detail="Invalid override code.")

        if oc.get("customer_id") != customer_id:
            await create_audit_log(
                entity_type="checkout", entity_id=customer_id,
                action="checkout_blocked_override_code_mismatch", actor="system",
                details={"reason": "Code not assigned to customer", "code": override_code}
            )
            raise HTTPException(status_code=400, detail="This override code is not valid for your account.")

        # Auto-expire check
        expires_at = oc.get("expires_at")
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > exp_dt:
                    await create_audit_log(
                        entity_type="override_code", entity_id=oc["id"],
                        action="override_code_expired_at_checkout", actor="system",
                        details={"customer_id": customer_id, "expires_at": expires_at}
                    )
                    raise HTTPException(status_code=400, detail="This override code has expired. Please contact admin for a new one.")
            except HTTPException:
                raise
            except Exception:
                pass

        if oc.get("status") != "active":
            raise HTTPException(status_code=400, detail="This override code is no longer active.")

        override_code_id = oc["id"]

    # Update customer partner_map to pending
    pending_value = f"{partner_tag_response} - Pending Verification"
    await db.customers.update_one(
        {"id": customer_id},
        {"$set": {"partner_map": pending_value}}
    )
    await create_audit_log(
        entity_type="customer", entity_id=customer_id,
        action="partner_map_updated", actor="system",
        details={"partner_map": pending_value, "order_id": order_id, "trigger": "checkout"}
    )

    # Append note and mark code used if override code was used
    if override_code_id and override_code:
        note_text = f"Override code used: {override_code.strip()} at {now_iso()}"
        if order_id:
            note_text += f" for Order {order_id}"
        await db.customers.update_one(
            {"id": customer_id},
            {"$push": {"notes": {"text": note_text, "timestamp": now_iso(), "actor": "system"}}}
        )
        await create_audit_log(
            entity_type="customer", entity_id=customer_id,
            action="customer_note_appended", actor="system",
            details={"note": note_text, "override_code_id": override_code_id}
        )
        await db.override_codes.update_one(
            {"id": override_code_id},
            {"$set": {"status": "inactive", "used_at": now_iso(), "used_for_order_id": order_id}}
        )
        await create_audit_log(
            entity_type="override_code", entity_id=override_code_id,
            action="override_code_used", actor="system",
            details={"customer_id": customer_id, "order_id": order_id, "code": override_code.strip()}
        )

    return override_code_id


class AddressInput(BaseModel):
    line1: str
    line2: Optional[str] = ""
    city: str
    region: str
    postal: str
    country: str


class RegisterRequest(BaseModel):
    full_name: str
    job_title: str
    company_name: str
    email: str
    phone: str
    password: str
    address: AddressInput


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


class UpdateProfileRequest(BaseModel):
    full_name: str
    company_name: str
    phone: str
    address: AddressInput


class PricingCalcRequest(BaseModel):
    product_id: str
    inputs: Dict[str, Any] = Field(default_factory=dict)


class CartItemInput(BaseModel):
    product_id: str
    quantity: int = 1
    inputs: Dict[str, Any] = Field(default_factory=dict)
    price_override: Optional[float] = None


class OrderPreviewRequest(BaseModel):
    items: List[CartItemInput]


VALID_PARTNER_TAG_RESPONSES = ["Yes", "Pre-existing Customer", "Not yet"]


class CheckoutSessionRequestBody(BaseModel):
    items: List[CartItemInput]
    checkout_type: str
    origin_url: str
    promo_code: Optional[str] = None
    terms_accepted: bool = False
    terms_id: Optional[str] = None
    start_date: Optional[str] = None  # YYYY-MM-DD for subscription start
    partner_tag_response: Optional[str] = None  # "Yes", "Pre-existing Customer", "Not yet"
    override_code: Optional[str] = None
    zoho_subscription_type: Optional[str] = None
    current_zoho_product: Optional[str] = None
    zoho_account_access: Optional[str] = None


class BankTransferCheckoutRequest(BaseModel):
    items: List[CartItemInput]
    checkout_type: str
    promo_code: Optional[str] = None
    terms_accepted: bool = False
    terms_id: Optional[str] = None
    start_date: Optional[str] = None  # YYYY-MM-DD for subscription start
    partner_tag_response: Optional[str] = None  # "Yes", "Pre-existing Customer", "Not yet"
    override_code: Optional[str] = None
    zoho_subscription_type: Optional[str] = None
    current_zoho_product: Optional[str] = None
    zoho_account_access: Optional[str] = None



class ScopeRequestBody(BaseModel):
    items: List[CartItemInput]


class CancelSubscriptionBody(BaseModel):
    reason: Optional[str] = ""


class AdminProductUpdate(BaseModel):
    name: str
    short_description: Optional[str] = ""
    tagline: Optional[str] = ""
    description_long: str = ""
    bullets: Optional[List[str]] = None
    bullets_included: Optional[List[str]] = None
    bullets_excluded: Optional[List[str]] = None
    bullets_needed: Optional[List[str]] = None
    tag: Optional[str] = None
    category: Optional[str] = None
    outcome: Optional[str] = None
    automation_details: Optional[str] = None
    support_details: Optional[str] = None
    inclusions: Optional[List[str]] = None
    exclusions: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    next_steps: Optional[List[str]] = None
    faqs: Optional[List[Any]] = None
    terms_id: Optional[str] = None
    base_price: Optional[float] = None
    is_subscription: Optional[bool] = None
    stripe_price_id: Optional[str] = None
    pricing_complexity: Optional[str] = None
    pricing_rules: Optional[Dict[str, Any]] = None
    is_active: bool = True
    visible_to_customers: Optional[List[str]] = None

class AdminCustomerPaymentUpdate(BaseModel):
    allow_bank_transfer: bool
    allow_card_payment: bool




class AdminOrderUpdate(BaseModel):
    manual_status: Optional[str] = None
    internal_note: Optional[str] = None


class CurrencyOverrideRequest(BaseModel):
    customer_email: str
    currency: str


class PromoCodeCreate(BaseModel):
    code: str
    discount_type: str  # "percent" or "fixed"
    discount_value: float
    applies_to: str  # "one-time", "subscription", "both"
    applies_to_products: str = "all"  # "all" or "selected"
    product_ids: List[str] = Field(default_factory=list)
    expiry_date: Optional[str] = None
    max_uses: Optional[int] = None
    one_time_code: bool = False
    enabled: bool = True


class PromoCodeUpdate(BaseModel):
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    applies_to: Optional[str] = None
    applies_to_products: Optional[str] = None
    product_ids: Optional[List[str]] = None
    expiry_date: Optional[str] = None
    max_uses: Optional[int] = None
    one_time_code: Optional[bool] = None
    enabled: Optional[bool] = None


class OverrideCodeCreate(BaseModel):
    code: str
    customer_id: str
    expires_at: Optional[str] = None  # ISO string; defaults to created_at + 48h


class OverrideCodeUpdate(BaseModel):
    code: Optional[str] = None
    customer_id: Optional[str] = None
    status: Optional[str] = None  # "active" or "inactive"
    expires_at: Optional[str] = None


class CustomerPartnerMapUpdate(BaseModel):
    partner_map: str  # final values: Yes / Pre-existing Customer / Not yet


class TermsCreate(BaseModel):
    title: str
    content: str
    is_default: bool = False
    status: str = "active"


class TermsUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None


class ManualOrderCreate(BaseModel):
    customer_email: str
    product_id: str
    quantity: int = 1
    inputs: Dict[str, Any] = Field(default_factory=dict)
    subtotal: float
    discount: float = 0.0
    fee: float = 0.0
    status: str = "paid"
    internal_note: Optional[str] = ""


class ManualSubscriptionCreate(BaseModel):
    customer_email: str
    product_id: str
    quantity: int = 1
    inputs: Dict[str, Any] = Field(default_factory=dict)
    amount: float
    renewal_date: str
    start_date: Optional[str] = None
    status: str = "active"
    internal_note: Optional[str] = ""


class AdminCreateUserRequest(BaseModel):
    email: str
    full_name: str
    company_name: Optional[str] = ""
    job_title: Optional[str] = ""
    phone: Optional[str] = ""
    password: str
    role: str = "admin"


class AdminCreateCustomerRequest(BaseModel):
    full_name: str
    company_name: Optional[str] = ""
    job_title: Optional[str] = ""
    email: str
    phone: Optional[str] = ""
    password: str
    line1: str
    line2: Optional[str] = ""
    city: str
    region: str
    postal: str
    country: str
    mark_verified: bool = True


class SubscriptionUpdate(BaseModel):
    renewal_date: Optional[str] = None
    start_date: Optional[str] = None
    contract_end_date: Optional[str] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    plan_name: Optional[str] = None
    product_id: Optional[str] = None
    customer_id: Optional[str] = None
    payment_method: Optional[str] = None
    new_note: Optional[str] = None


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None


class AddressUpdate(BaseModel):
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    postal: Optional[str] = None
    country: Optional[str] = None


class OrderUpdate(BaseModel):
    customer_id: Optional[str] = None
    status: Optional[str] = None
    payment_method: Optional[str] = None
    order_date: Optional[str] = None
    payment_date: Optional[str] = None
    subtotal: Optional[float] = None
    fee: Optional[float] = None
    total: Optional[float] = None
    internal_note: Optional[str] = None
    new_note: Optional[str] = None
    subscription_id: Optional[str] = None
    product_id: Optional[str] = None


class OrderDelete(BaseModel):
    reason: Optional[str] = ""


class CompleteGoCardlessRedirect(BaseModel):
    redirect_flow_id: str
    session_token: Optional[str] = None
    order_id: Optional[str] = None
    subscription_id: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    subtotal: Optional[float] = None  # looked up from order/subscription if not provided
    discount: float = 0.0
    fee: float = 0.0
    status: str = "paid"
    internal_note: Optional[str] = ""


class ApplyPromoRequest(BaseModel):
    code: str
    checkout_type: str  # "one_time" or "subscription"


class ScopeRequestFormData(BaseModel):
    project_summary: str
    desired_outcomes: str
    apps_involved: str
    timeline_urgency: str
    budget_range: Optional[str] = ""
    additional_notes: Optional[str] = ""


class ScopeRequestWithForm(BaseModel):
    items: List[CartItemInput]
    form_data: ScopeRequestFormData


class CategoryCreate(BaseModel):
    name: str
    description: str = ""
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class AdminProductCreate(BaseModel):
    name: str
    short_description: str = ""
    description_long: str = ""
    bullets: List[str] = Field(default_factory=list)
    tag: Optional[str] = None
    category: str = ""
    outcome: Optional[str] = None
    automation_details: Optional[str] = None
    support_details: Optional[str] = None
    inclusions: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    faqs: List[Dict[str, str]] = Field(default_factory=list)
    terms_id: Optional[str] = None
    base_price: float = 0.0
    is_subscription: bool = False
    stripe_price_id: Optional[str] = None
    pricing_complexity: str = "SIMPLE"
    is_active: bool = True
    visible_to_customers: List[str] = Field(default_factory=list)

    @property
    def validated_complexity(self) -> str:
        allowed = {"SIMPLE", "COMPLEX", "REQUEST_FOR_QUOTE"}
        if self.pricing_complexity.upper() in allowed:
            return self.pricing_complexity.upper()
        return "SIMPLE"


class AppSettingsUpdate(BaseModel):
    stripe_public_key: Optional[str] = None
    stripe_secret_key: Optional[str] = None
    gocardless_token: Optional[str] = None
    resend_api_key: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    logo_url: Optional[str] = None
    store_name: Optional[str] = None


class QuoteRequest(BaseModel):
    product_id: str
    product_name: str
    name: str
    email: str
    company: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None


class BankTransactionCreate(BaseModel):
    date: str  # YYYY-MM-DD
    source: str  # "stripe", "gocardless", "manual"
    transaction_id: Optional[str] = None
    type: str  # "payment", "refund", "chargeback", "credit", "debit", "fee"
    amount: float
    fees: Optional[float] = 0.0
    net_amount: Optional[float] = None
    currency: Optional[str] = "USD"
    status: str  # "pending", "completed", "failed", "refunded"
    description: Optional[str] = None
    linked_order_id: Optional[str] = None
    internal_notes: Optional[str] = None


class BankTransactionUpdate(BaseModel):
    date: Optional[str] = None
    source: Optional[str] = None
    transaction_id: Optional[str] = None
    type: Optional[str] = None
    amount: Optional[float] = None
    fees: Optional[float] = None
    net_amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    linked_order_id: Optional[str] = None
    internal_notes: Optional[str] = None


def build_seed_products(external_books_url: str) -> List[Dict[str, Any]]:
    return [
        {
            "id": "prod_zoho_one_express",
            "category": "Zoho Express Setup",
            "sku": "START-ZOHO-ONE-EXP",
            "name": "Zoho One Express Setup",
            "tagline": "Launch Zoho One with a clean, automation-ready foundation.",
            "description_long": "A rapid implementation sprint to centralize your stack, align teams, and start automating in days—not weeks.",
            "bullets_included": [
                "Up to 10 users configured",
                "Core app setup and access controls",
                "50 automation credits",
                "1 month Unlimited Zoho Support (up to 10 users)",
            ],
            "bullets_excluded": [
                "Custom app development",
                "Complex integrations",
                "Historical data cleanups",
            ],
            "bullets_needed": [
                "Admin access to existing Zoho account",
                "Primary business processes list",
                "Key user list with roles",
            ],
            "next_steps": [
                "Discovery call within 2 business days",
                "Automation roadmap approval",
                "Implementation + QA handoff",
            ],
            "faqs": ["Automation credits are consumed after workflow approval."],
            "pricing_type": "fixed",
            "base_price": 4999.0,
            "is_subscription": False,
            "pricing_rules": {"bundle_free_items": ["1 month Unlimited Zoho Support (up to 10 users)"]},
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_zoho_crm_express",
            "category": "Zoho Express Setup",
            "sku": "START-ZOHO-CRM-EXP",
            "name": "Zoho CRM Express Setup",
            "tagline": "Go live fast with a CRM that fits your pipeline.",
            "description_long": "We configure your CRM, map your sales stages, and align automation for consistent follow-through.",
            "bullets_included": [
                "Pipeline + stages setup",
                "Lead & deal views",
                "25 automation credits",
                "CRM data migration calculator included",
                "1 month Unlimited Zoho Support (up to 10 users)",
            ],
            "bullets_excluded": ["Advanced integrations", "Complex custom functions"],
            "bullets_needed": ["Sales process outline", "Existing CRM export"],
            "next_steps": ["Kickoff call", "Data import run", "Go-live review"],
            "faqs": ["CRM data migration service is bundled and cannot be purchased separately."],
            "pricing_type": "fixed",
            "base_price": 2499.0,
            "is_subscription": False,
            "pricing_rules": {"includes_sku": ["MIG-CRM"], "bundle_free_items": ["1 month Unlimited Zoho Support (up to 10 users)"]},
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_zoho_books_express",
            "category": "Zoho Express Setup",
            "sku": "START-ZOHO-BOOKS-EXP",
            "name": "Zoho Books Express Setup",
            "tagline": "Stand up clean accounting without the spreadsheet chaos.",
            "description_long": "We configure Zoho Books for your workflow and reporting needs with clarity on inventory and multi-currency options.",
            "bullets_included": ["Chart of accounts", "Bank feeds setup", "Invoice templates"],
            "bullets_excluded": ["Historical transaction cleanup", "Complex tax automation"],
            "bullets_needed": ["Last 3 months statements", "Tax configuration preferences"],
            "next_steps": ["Setup session", "Review & adjustments", "Launch"],
            "faqs": ["Inventory and multi-currency add complexity and pricing."],
            "pricing_type": "tiered",
            "base_price": None,
            "is_subscription": False,
            "pricing_rules": {
                "variants": [
                    {"id": "basic", "label": "No inventory / No multi-currency", "price": 999.0},
                    {"id": "advanced", "label": "Inventory and/or multi-currency", "price": 1499.0},
                ]
            },
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_zoho_expense_setup",
            "category": "Zoho Express Setup",
            "sku": "START-ZOHO-EXPENSE",
            "name": "Zoho Expense Setup",
            "tagline": "Put expense control on autopilot.",
            "description_long": "We align policies, approval flows, and reporting to keep spend transparent and compliant.",
            "bullets_included": ["Policy setup", "Approval chains", "Receipt capture tuning"],
            "bullets_excluded": ["Corporate card integrations"],
            "bullets_needed": ["Expense policy document", "Approver list"],
            "next_steps": ["Policy mapping", "Configuration", "Training"],
            "faqs": ["Integrations can be scoped post-launch."],
            "pricing_type": "fixed",
            "base_price": 999.0,
            "is_subscription": False,
            "pricing_rules": {"bundle_free_items": ["1 month Unlimited Zoho Support (up to 10 users)"]},
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_zoho_people_setup",
            "category": "Zoho Express Setup",
            "sku": "START-ZOHO-PEOPLE",
            "name": "Zoho People Setup",
            "tagline": "Launch HR operations with structured policies.",
            "description_long": "We configure leave, attendance, and employee profiles for clean HR operations.",
            "bullets_included": ["Leave policies", "Attendance setup", "Employee profiles"],
            "bullets_excluded": ["Advanced payroll automation"],
            "bullets_needed": ["HR policy docs", "Employee list"],
            "next_steps": ["Policy review", "System setup", "HR onboarding"],
            "faqs": ["Payroll can be scoped in a later phase."],
            "pricing_type": "fixed",
            "base_price": 1499.0,
            "is_subscription": False,
            "pricing_rules": {"bundle_free_items": ["1 month Unlimited Zoho Support (up to 10 users)"]},
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_health_check_starter",
            "category": "Audit & Optimize",
            "sku": "AUDIT-HEALTH-START",
            "name": "Zoho Health Check Starter",
            "tagline": "Pinpoint friction across your top Zoho apps.",
            "description_long": "A focused audit that surfaces gaps, quick wins, and a prioritized optimization roadmap.",
            "bullets_included": ["3 Zoho apps review", "Up to 10 functions", "1 x 1.5hr discovery"],
            "bullets_excluded": ["Implementation work"],
            "bullets_needed": ["Access to apps", "Stakeholder availability"],
            "next_steps": ["Discovery", "Audit report", "Action plan"],
            "faqs": ["Add Creator/Catalyst extensions if needed."],
            "pricing_type": "calculator",
            "base_price": 999.0,
            "is_subscription": False,
            "pricing_rules": {
                "calc_type": "health_check",
                "base_price": 999.0,
                "add_ons": [
                    {"id": "none", "label": "No extension", "price": 0.0},
                    {"id": "100", "label": "Up to 100 functions", "price": 999.0},
                    {"id": "250", "label": "Up to 250 functions", "price": 1999.0},
                    {"id": "500", "label": "Up to 500 functions", "price": 3499.0},
                ],
            },
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_health_check_plus",
            "category": "Audit & Optimize",
            "sku": "AUDIT-HEALTH-PLUS",
            "name": "Zoho Health Check Plus",
            "tagline": "Deep audit for multi-app Zoho ecosystems.",
            "description_long": "Expanded audit coverage with multiple discovery sessions and a prioritized roadmap.",
            "bullets_included": ["10 Zoho apps review", "Up to 10 functions", "3 x 1.5hr discovery"],
            "bullets_excluded": ["Implementation work"],
            "bullets_needed": ["Access to apps", "Key process owners"],
            "next_steps": ["Discovery", "Audit report", "Optimization roadmap"],
            "faqs": ["Creator/Catalyst extensions optional."],
            "pricing_type": "calculator",
            "base_price": 1999.0,
            "is_subscription": False,
            "pricing_rules": {
                "calc_type": "health_check",
                "base_price": 1999.0,
                "add_ons": [
                    {"id": "none", "label": "No extension", "price": 0.0},
                    {"id": "100", "label": "Up to 100 functions", "price": 999.0},
                    {"id": "250", "label": "Up to 250 functions", "price": 1999.0},
                    {"id": "500", "label": "Up to 500 functions", "price": 3499.0},
                ],
            },
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_hours_pack",
            "category": "Build & Automate",
            "sku": "BUILD-HOURS-PACK",
            "name": "Build What You Need — Hours Pack",
            "tagline": "Scale automation with a flexible monthly hours pack.",
            "description_long": "Choose the hours you need. Pay now for immediate execution or scope first and pay later.",
            "bullets_included": ["Custom automation delivery", "Monthly cadence", "Dedicated automation lead"],
            "bullets_excluded": ["24/7 on-call support"],
            "bullets_needed": ["Project brief", "Priority list"],
            "next_steps": ["Scoping", "Monthly execution", "Review"],
            "faqs": ["Scope & Pay Later creates a CRM deal and timeline."],
            "pricing_type": "calculator",
            "base_price": None,
            "is_subscription": True,
            "pricing_rules": {
                "calc_type": "hours_pack",
                "min_hours": 10,
                "max_hours": 200,
                "step": 10,
                "pay_now_rate": 75.0,
                "scope_later_rate": 90.0,
            },
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_bookkeeping",
            "category": "Accounting on Zoho",
            "sku": "ACC-BOOKKEEPING",
            "name": "Accounting on Zoho — Bookkeeping",
            "tagline": "Monthly bookkeeping tailored to your transaction volume.",
            "description_long": "A dynamic subscription that scales with your business volume and complexity.",
            "bullets_included": ["Monthly reconciliation", "Management reports", "Dedicated finance contact"],
            "bullets_excluded": ["Tax filing"],
            "bullets_needed": ["Monthly transaction count", "System access"],
            "next_steps": ["Intake", "Setup", "Monthly cadence"],
            "faqs": ["Pricing scales with transaction volume."],
            "pricing_type": "calculator",
            "base_price": None,
            "is_subscription": True,
            "pricing_rules": {
                "calc_type": "bookkeeping",
                "min_transactions": 1,
            },
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_support_plan",
            "category": "Ongoing Plans",
            "sku": "ONGOING-SUPPORT",
            "name": "Unlimited Zoho Support",
            "tagline": "Support-only plans for continuous coverage.",
            "description_long": "Pick the user tier that matches your team size and receive unlimited support requests.",
            "bullets_included": [
                "Unlimited support requests",
                "Dedicated Zoho expert",
                "24-hour SLA target",
                "Small workflow implementations",
            ],
            "bullets_excluded": ["Project development"],
            "bullets_needed": ["User count", "Support point-of-contact"],
            "next_steps": ["Onboarding", "Support kickoff", "Monthly review"],
            "faqs": ["Development work is not included."],
            "pricing_type": "tiered",
            "base_price": None,
            "is_subscription": True,
            "pricing_rules": {
                "variants": [
                    {"id": "10", "label": "Up to 10 users", "price": 250.0},
                    {"id": "25", "label": "Up to 25 users", "price": 500.0},
                    {"id": "50", "label": "Up to 50 users", "price": 1500.0},
                    {"id": "75", "label": "Up to 75 users", "price": 2500.0},
                ]
            },
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_dev_retainer",
            "category": "Ongoing Plans",
            "sku": "ONGOING-DEV",
            "name": "Ongoing Zoho Development",
            "tagline": "Retainers that keep delivery moving.",
            "description_long": "Choose a task start time that matches your urgency. One task at a time with clear priority control.",
            "bullets_included": ["1 task at a time", "Clear task start time", "Monthly cadence"],
            "bullets_excluded": ["Multiple simultaneous tracks"],
            "bullets_needed": ["Backlog list", "Primary stakeholders"],
            "next_steps": ["Retainer kickoff", "Task intake", "Delivery"],
            "faqs": ["Tasks typically run ~15 hours."],
            "pricing_type": "tiered",
            "base_price": None,
            "is_subscription": True,
            "pricing_rules": {
                "variants": [
                    {"id": "48", "label": "48 hour task start time", "price": 2500.0},
                    {"id": "24", "label": "24 hour task start time", "price": 5000.0},
                    {"id": "0", "label": "0 hour task start time", "price": 7500.0},
                ]
            },
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_dev_enterprise",
            "category": "Ongoing Plans",
            "sku": "ONGOING-DEV-ENTERPRISE",
            "name": "Ongoing Zoho Development — Enterprise",
            "tagline": "Parallel delivery tracks for enterprise teams.",
            "description_long": "Enterprise engagement with simultaneous development streams. Inquiry only.",
            "bullets_included": ["Simultaneous tracks", "Dedicated pod", "Executive reporting"],
            "bullets_excluded": ["Self-serve checkout"],
            "bullets_needed": ["Executive sponsor", "Delivery scope"],
            "next_steps": ["Strategy call", "Proposal", "Engagement"],
            "faqs": ["Enterprise plans are scoped on demand."],
            "pricing_type": "inquiry",
            "base_price": 0.0,
            "is_subscription": False,
            "pricing_rules": {},
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_migrate_books",
            "category": "Migrations",
            "sku": "MIG-BOOKS",
            "name": "Migrate to Zoho Books",
            "tagline": "Continue to the dedicated migration checkout.",
            "description_long": "This migration is handled through a dedicated secure flow.",
            "bullets_included": ["Dedicated migration workflow"],
            "bullets_excluded": ["In-app checkout"],
            "bullets_needed": ["Migration intake"],
            "next_steps": ["Continue to migration checkout"],
            "faqs": ["This flow opens in a new tab."],
            "pricing_type": "external",
            "base_price": 0.0,
            "is_subscription": False,
            "pricing_rules": {"external_url": external_books_url},
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_migrate_mail",
            "category": "Migrations",
            "sku": "MIG-MAIL",
            "name": "Migrate to Zoho Mail",
            "tagline": "Move mailboxes without service disruption.",
            "description_long": "Per-mailbox migration pricing with clear scope and timelines.",
            "bullets_included": ["Mailbox migration", "DNS cutover support"],
            "bullets_excluded": ["Legacy mail cleanup"],
            "bullets_needed": ["Mailbox count", "Domain access"],
            "next_steps": ["Intake", "Migration", "Validation"],
            "faqs": ["Pricing is per mailbox."],
            "pricing_type": "calculator",
            "base_price": None,
            "is_subscription": False,
            "pricing_rules": {"calc_type": "mailboxes", "rate": 350.0},
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_migrate_workdrive",
            "category": "Migrations",
            "sku": "MIG-WORKDRIVE",
            "name": "Migrate to Zoho WorkDrive",
            "tagline": "Move shared drives into a structured Zoho workspace.",
            "description_long": "Priced per 50GB blocks to keep scope transparent.",
            "bullets_included": ["Data migration", "Permissions mapping"],
            "bullets_excluded": ["Data cleansing"],
            "bullets_needed": ["Storage total", "Access to source"],
            "next_steps": ["Intake", "Migration", "Validation"],
            "faqs": ["Select storage blocks in 50GB increments."],
            "pricing_type": "calculator",
            "base_price": None,
            "is_subscription": False,
            "pricing_rules": {"calc_type": "storage_blocks", "rate": 100.0},
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_migrate_crm",
            "category": "Migrations",
            "sku": "MIG-CRM",
            "name": "Data Migration to Zoho CRM",
            "tagline": "Bring your CRM data into Zoho with precision.",
            "description_long": "Calculator-based pricing for modules, records, and setup.",
            "bullets_included": ["Module mapping", "Record import", "Base setup"],
            "bullets_excluded": ["Workflow automation", "Permissions design"],
            "bullets_needed": ["Module list", "Record counts"],
            "next_steps": ["Mapping", "Migration", "Validation"],
            "faqs": ["Included in CRM Express Setup."],
            "pricing_type": "calculator",
            "base_price": None,
            "is_subscription": False,
            "pricing_rules": {"calc_type": "crm_migration", "base_fee": 499.0},
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_migrate_forms",
            "category": "Migrations",
            "sku": "MIG-FORMS",
            "name": "Migrate to Zoho Forms",
            "tagline": "Rebuild forms with clean validation logic.",
            "description_long": "Calculator-based pricing for validations, fields, and notifications.",
            "bullets_included": ["Form rebuild", "Validation logic"],
            "bullets_excluded": ["Custom integrations"],
            "bullets_needed": ["Form list", "Validation rules"],
            "next_steps": ["Intake", "Rebuild", "QA"],
            "faqs": ["Email notifications are priced per workflow."],
            "pricing_type": "calculator",
            "base_price": None,
            "is_subscription": False,
            "pricing_rules": {"calc_type": "forms_migration"},
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_migrate_desk",
            "category": "Migrations",
            "sku": "MIG-DESK",
            "name": "Migrate to Zoho Desk",
            "tagline": "Move support operations into Zoho Desk.",
            "description_long": "Calculator pricing for departments, tickets, and knowledge base.",
            "bullets_included": ["Department setup", "Ticket migration"],
            "bullets_excluded": ["Workflow automation"],
            "bullets_needed": ["Ticket volumes", "KB article count"],
            "next_steps": ["Intake", "Migration", "Go-live"],
            "faqs": ["Ticket pricing is per record."],
            "pricing_type": "calculator",
            "base_price": None,
            "is_subscription": False,
            "pricing_rules": {"calc_type": "desk_migration"},
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_migrate_sign",
            "category": "Migrations",
            "sku": "MIG-SIGN",
            "name": "Migrate to Zoho Sign",
            "tagline": "Digitize signature workflows without disruption.",
            "description_long": "Pricing based on templates and WorkDrive document storage.",
            "bullets_included": ["Template rebuild", "WorkDrive linkage"],
            "bullets_excluded": ["Custom API work"],
            "bullets_needed": ["Template list", "Document storage count"],
            "next_steps": ["Template import", "Validation", "Launch"],
            "faqs": ["WorkDrive storage billed per document."],
            "pricing_type": "calculator",
            "base_price": None,
            "is_subscription": False,
            "pricing_rules": {"calc_type": "sign_migration"},
            "stripe_price_id": None,
            "is_active": True,
        },
        {
            "id": "prod_migrate_people",
            "category": "Migrations",
            "sku": "MIG-PEOPLE",
            "name": "Migrate to Zoho People",
            "tagline": "Move HR systems with structured pricing.",
            "description_long": "Calculator pricing for policies, requests, and employee assets.",
            "bullets_included": ["Base setup", "Policy migration"],
            "bullets_excluded": ["Payroll automation"],
            "bullets_needed": ["Policy list", "Employee data"],
            "next_steps": ["Intake", "Migration", "Go-live"],
            "faqs": ["Base setup is included."],
            "pricing_type": "calculator",
            "base_price": None,
            "is_subscription": False,
            "pricing_rules": {"calc_type": "people_migration", "base_fee": 999.0},
            "stripe_price_id": None,
            "is_active": True,
        },
    ]


def build_price_inputs(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    pricing_type = product.get("pricing_type")
    rules = product.get("pricing_rules", {})
    if pricing_type == "tiered":
        return [
            {
                "id": "variant",
                "label": "Select option",
                "type": "select",
                "options": rules.get("variants", []),
            }
        ]
    if pricing_type == "calculator":
        calc_type = rules.get("calc_type")
        if calc_type == "health_check":
            return [
                {
                    "id": "creator_extension",
                    "label": "Creator/Catalyst extension",
                    "type": "select",
                    "options": rules.get("add_ons", []),
                }
            ]
        if calc_type == "hours_pack":
            return [
                {
                    "id": "hours",
                    "label": "Hours per month",
                    "type": "number",
                    "min": rules.get("min_hours"),
                    "max": rules.get("max_hours"),
                    "step": rules.get("step"),
                },
                {
                    "id": "payment_option",
                    "label": "Payment option",
                    "type": "select",
                    "options": [
                        {"id": "pay_now", "label": "Pay Now"},
                        {"id": "scope_later", "label": "Scope & Pay Later"},
                    ],
                },
            ]
        if calc_type == "bookkeeping":
            return [
                {"id": "transactions", "label": "Monthly transactions", "type": "number", "min": 1},
                {"id": "inventory", "label": "Inventory tracking", "type": "checkbox"},
                {"id": "multi_currency", "label": "Multi-currency", "type": "checkbox"},
                {"id": "offshore", "label": "Offshore finance department", "type": "checkbox"},
            ]
        if calc_type == "mailboxes":
            return [{"id": "mailboxes", "label": "Mailbox count", "type": "number", "min": 1}]
        if calc_type == "storage_blocks":
            return [{"id": "blocks", "label": "50GB blocks", "type": "number", "min": 1}]
        if calc_type == "crm_migration":
            return [
                {"id": "tables", "label": "Tables/Modules", "type": "number", "min": 1},
                {"id": "records", "label": "Records", "type": "number", "min": 1},
            ]
        if calc_type == "forms_migration":
            return [
                {"id": "forms_with_validation", "label": "Forms with validation", "type": "number", "min": 0},
                {"id": "forms_without_validation", "label": "Forms without validation", "type": "number", "min": 0},
                {"id": "total_fields", "label": "Total fields", "type": "number", "min": 0},
                {"id": "email_notifications", "label": "Email notifications", "type": "number", "min": 0},
            ]
        if calc_type == "desk_migration":
            return [
                {"id": "departments", "label": "Departments", "type": "number", "min": 1},
                {"id": "tickets", "label": "Tickets", "type": "number", "min": 0},
                {"id": "kb_articles", "label": "KB articles", "type": "number", "min": 0},
            ]
        if calc_type == "sign_migration":
            return [
                {"id": "templates", "label": "Templates", "type": "number", "min": 1},
                {"id": "workdrive_docs", "label": "WorkDrive documents", "type": "number", "min": 0},
            ]
        if calc_type == "people_migration":
            return [
                {"id": "leave_policies", "label": "Leave policies", "type": "number", "min": 0},
                {"id": "leave_requests", "label": "Leave requests", "type": "number", "min": 0},
                {"id": "timesheets", "label": "Timesheets", "type": "number", "min": 0},
                {"id": "attendance", "label": "Attendance", "type": "number", "min": 0},
                {"id": "employee_docs", "label": "Employee file docs", "type": "number", "min": 0},
                {"id": "employee_profiles", "label": "Employee profiles", "type": "number", "min": 0},
                {"id": "templates", "label": "Templates", "type": "number", "min": 0},
            ]
    if pricing_type == "scope_request":
        return []
    return []


def calculate_price(product: Dict[str, Any], inputs: Dict[str, Any], fee_rate: float = SERVICE_FEE_RATE) -> Dict[str, Any]:
    pricing_type = product.get("pricing_type")
    rules = product.get("pricing_rules", {})
    subtotal = 0.0
    line_items = []
    is_scope_request = False
    is_subscription = bool(product.get("is_subscription"))
    requires_checkout = pricing_type not in ["external", "inquiry"]
    external_url = rules.get("external_url") if pricing_type == "external" else None

    if pricing_type == "fixed":
        subtotal = float(product.get("base_price") or 0.0)
        line_items.append({"label": product["name"], "amount": subtotal})
    elif pricing_type == "tiered":
        variants = rules.get("variants", [])
        variant_id = inputs.get("variant") or (variants[0]["id"] if variants else None)
        variant = next((v for v in variants if v["id"] == variant_id), variants[0] if variants else None)
        if not variant:
            raise HTTPException(status_code=400, detail="Invalid option")
        subtotal = float(variant["price"])
        line_items.append({"label": f"{product['name']} — {variant['label']}", "amount": subtotal})
    elif pricing_type == "scope_request":
        # Check if scope has been unlocked via Scope ID
        scope_unlock = inputs.get("_scope_unlock")
        if scope_unlock and scope_unlock.get("price"):
            subtotal = float(scope_unlock["price"])
            is_scope_request = False
            requires_checkout = True
            line_items.append({"label": product["name"], "amount": subtotal})
        else:
            is_scope_request = True
            requires_checkout = False
            subtotal = 0.0
            line_items.append({"label": product["name"], "amount": subtotal})

    elif pricing_type == "calculator":
        calc_type = rules.get("calc_type")
        if calc_type == "health_check":
            base = float(rules.get("base_price", 0.0))
            add_on_id = inputs.get("creator_extension", "none")
            add_on = next((a for a in rules.get("add_ons", []) if a["id"] == add_on_id), rules.get("add_ons", [])[0])
            add_price = float(add_on.get("price", 0.0)) if add_on else 0.0
            subtotal = base + add_price
            line_items.append({"label": product["name"], "amount": base})
            if add_price > 0:
                line_items.append({"label": f"Creator/Catalyst extension ({add_on['label']})", "amount": add_price})
        elif calc_type == "hours_pack":
            hours = int(inputs.get("hours", rules.get("min_hours", 10)))
            hours = max(rules.get("min_hours", 10), min(hours, rules.get("max_hours", 200)))
            option = inputs.get("payment_option", "pay_now")
            if option == "scope_later":
                rate = float(rules.get("scope_later_rate", 90.0))
                is_scope_request = True
                requires_checkout = False
                is_subscription = False
            else:
                rate = float(rules.get("pay_now_rate", 75.0))
            subtotal = hours * rate
            line_items.append({"label": f"{hours} hours/month", "amount": subtotal})
        elif calc_type == "bookkeeping":
            transactions = max(1, int(inputs.get("transactions", 1)))
            base = max(249.0, transactions * 3.0)
            multiplier = 1.0
            if inputs.get("inventory"):
                multiplier *= 1.2
            if inputs.get("multi_currency"):
                multiplier *= 1.1
            if inputs.get("offshore"):
                multiplier *= 1.2
            subtotal = round_nearest_25(base * multiplier)
            line_items.append({"label": f"{transactions} monthly transactions", "amount": subtotal})
        elif calc_type == "mailboxes":
            count = max(1, int(inputs.get("mailboxes", 1)))
            subtotal = count * float(rules.get("rate", 350.0))
            line_items.append({"label": f"{count} mailboxes", "amount": subtotal})
        elif calc_type == "storage_blocks":
            blocks = max(1, int(inputs.get("blocks", 1)))
            subtotal = blocks * float(rules.get("rate", 100.0))
            line_items.append({"label": f"{blocks} × 50GB", "amount": subtotal})
        elif calc_type == "crm_migration":
            tables = max(1, int(inputs.get("tables", 1)))
            records = max(1, int(inputs.get("records", 1)))
            subtotal = float(rules.get("base_fee", 499.0)) + tables * 250.0 + records * 0.10
            subtotal = round_nearest_25(subtotal)
            line_items.append({"label": f"{tables} modules", "amount": tables * 250.0})
            line_items.append({"label": f"{records} records", "amount": round_cents(records * 0.10)})
            line_items.append({"label": "Base setup", "amount": float(rules.get("base_fee", 499.0))})
        elif calc_type == "forms_migration":
            forms_with_validation = max(0, int(inputs.get("forms_with_validation", 0)))
            forms_without = max(0, int(inputs.get("forms_without_validation", 0)))
            fields = max(0, int(inputs.get("total_fields", 0)))
            notifications = max(0, int(inputs.get("email_notifications", 0)))
            subtotal = forms_with_validation * 200.0 + forms_without * 100.0 + fields * 1.0 + notifications * 25.0
            line_items.append({"label": "Forms with validation", "amount": forms_with_validation * 200.0})
            line_items.append({"label": "Forms without validation", "amount": forms_without * 100.0})
            line_items.append({"label": "Total fields", "amount": fields * 1.0})
            line_items.append({"label": "Email notifications", "amount": notifications * 25.0})
        elif calc_type == "desk_migration":
            departments = max(1, int(inputs.get("departments", 1)))
            tickets = max(0, int(inputs.get("tickets", 0)))
            kb_articles = max(0, int(inputs.get("kb_articles", 0)))
            subtotal = departments * 499.0 + tickets * 0.10 + kb_articles * 25.0
            line_items.append({"label": "Departments", "amount": departments * 499.0})
            line_items.append({"label": "Tickets", "amount": round_cents(tickets * 0.10)})
            line_items.append({"label": "KB articles", "amount": kb_articles * 25.0})
        elif calc_type == "sign_migration":
            templates = max(1, int(inputs.get("templates", 1)))
            workdrive_docs = max(0, int(inputs.get("workdrive_docs", 0)))
            subtotal = templates * 99.0 + workdrive_docs * 5.0
            line_items.append({"label": "Templates", "amount": templates * 99.0})
            line_items.append({"label": "WorkDrive docs", "amount": workdrive_docs * 5.0})
        elif calc_type == "people_migration":
            base_fee = float(rules.get("base_fee", 999.0))
            leave_policies = max(0, int(inputs.get("leave_policies", 0)))
            leave_requests = max(0, int(inputs.get("leave_requests", 0)))
            timesheets = max(0, int(inputs.get("timesheets", 0)))
            attendance = max(0, int(inputs.get("attendance", 0)))
            employee_docs = max(0, int(inputs.get("employee_docs", 0)))
            employee_profiles = max(0, int(inputs.get("employee_profiles", 0)))
            templates = max(0, int(inputs.get("templates", 0)))
            subtotal = (
                base_fee
                + leave_policies * 99.0
                + leave_requests * 1.0
                + timesheets * 0.10
                + attendance * 0.10
                + employee_docs * 5.0
                + employee_profiles * 50.0
                + templates * 50.0
            )
            line_items.append({"label": "Base setup", "amount": base_fee})
            line_items.append({"label": "Leave policies", "amount": leave_policies * 99.0})
            line_items.append({"label": "Leave requests", "amount": leave_requests * 1.0})
            line_items.append({"label": "Timesheets", "amount": round_cents(timesheets * 0.10)})
            line_items.append({"label": "Attendance", "amount": round_cents(attendance * 0.10)})
            line_items.append({"label": "Employee docs", "amount": employee_docs * 5.0})
            line_items.append({"label": "Employee profiles", "amount": employee_profiles * 50.0})
            line_items.append({"label": "Templates", "amount": templates * 50.0})
        elif calc_type == "books_migration":
            bm = calculate_books_migration_price(inputs)
            subtotal = bm["subtotal"]
            line_items = bm["line_items"]
        else:
            subtotal = 0.0
    else:
        subtotal = 0.0

    fee = round_cents(subtotal * fee_rate) if requires_checkout and not is_scope_request else 0.0
    total = round_cents(subtotal + fee)

    return {
        "subtotal": round_cents(subtotal),
        "fee": fee,
        "total": total,
        "line_items": line_items,
        "requires_checkout": requires_checkout,
        "is_subscription": is_subscription,
        "is_scope_request": is_scope_request,
        "external_url": external_url,
    }


async def seed_admin_user():
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        return
    existing = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
    if existing:
        return
    user_id = make_id()
    hashed = pwd_context.hash(ADMIN_PASSWORD)
    user_doc = {
        "id": user_id,
        "email": ADMIN_EMAIL,
        "password_hash": hashed,
        "full_name": "Automate Accounts Admin",
        "company_name": "Automate Accounts",
        "phone": "",
        "is_verified": True,
        "is_admin": True,
        "verification_code": None,
        "created_at": now_iso(),
    }
    await db.users.insert_one(user_doc)
    customer_id = make_id()
    await db.customers.insert_one(
        {
            "id": customer_id,
            "user_id": user_id,
            "company_name": "Automate Accounts",
            "phone": "",
            "currency": "USD",
            "currency_locked": True,
            "allow_bank_transfer": True,
            "allow_card_payment": True,
            "stripe_customer_id": None,
            "zoho_crm_contact_id": None,
            "zoho_books_contact_id": None,
            "created_at": now_iso(),
        }
    )
    await db.addresses.insert_one(
        {
            "id": make_id(),
            "customer_id": customer_id,
            "line1": "",
            "line2": "",
            "city": "",
            "region": "",
            "postal": "",
            "country": "USA",
        }
    )


async def seed_products():
    if await db.products.count_documents({}) > 0:
        return
    settings = await db.settings.find_one({"id": "app_settings"}, {"_id": 0})
    if not settings:
        settings = {
            "id": "app_settings",
            "zoho_books_migration_url": "https://paymentprocess-873927405.development.catalystserverless.com/app/index.html",
        }
        await db.settings.insert_one(settings)
    products = build_seed_products(settings["zoho_books_migration_url"])
    for product in products:
        product["price_inputs"] = build_price_inputs(product)
        await db.products.insert_one(product)
        await db.pricing_rules.insert_one(
            {
                "id": make_id(),
                "product_id": product["id"],
                "rule_json": product.get("pricing_rules", {}),
            }
        )




async def apply_catalog_overrides():
    updates = [
        {
            "sku": "START-ZOHO-ONE-EXP",
            "updates": {
                "category": "Zoho Express Setup",
                "card_tag": "Project based",
                "card_title": "Zoho One",
                "card_description": "Unified Zoho rollout across core apps with a clean operating baseline.",
                "card_bullets": [
                    "Configure upto 10 zoho apps",
                    "Core setup + permissions baseline",
                    "50 automation credits and more",
                ],
                "bullets_included": [
                    "Configure upto 10 zoho apps",
                    "Core setup + permissions baseline",
                    "50 automation credits and more",
                ],
            },
        },
        {
            "sku": "START-ZOHO-CRM-EXP",
            "updates": {
                "category": "Zoho Express Setup",
                "card_tag": "Project based",
                "card_title": "Zoho CRM",
                "card_description": "Sales pipeline foundations with clean automation and reporting.",
                "card_bullets": [
                    "Configure CRM + 2 other Zoho Apps",
                    "Leads, Deals & Pipelines",
                    "25 automation credits and more",
                ],
                "bullets_included": [
                    "Configure CRM + 2 other Zoho Apps",
                    "Leads, Deals & Pipelines",
                    "25 automation credits and more",
                ],
            },
        },
        {
            "sku": "START-ZOHO-BOOKS-EXP",
            "updates": {
                "category": "Zoho Express Setup",
                "card_tag": "Project based",
                "card_title": "Zoho Books",
                "card_description": "Get a clean accounting system with customizable reports and automation capabilities.",
                "description_long": "Get a clean accounting system with customizable reports and automation capabilities.",
                "card_bullets": [
                    "Organization & permission setup",
                    "PDF Templates, emails & modules",
                    "Inventory, Multi-currency & Projects and more",
                ],
                "bullets_included": [
                    "Organization & permission setup",
                    "PDF Templates, emails & modules",
                    "Inventory, Multi-currency & Projects and more",
                ],
            },
        },
        {
            "sku": "START-ZOHO-EXPENSE",
            "updates": {
                "category": "Zoho Express Setup",
                "card_tag": "Project based",
                "card_title": "Zoho Expense",
                "card_description": "Policy-led expense workflows with fast reimbursements.",
                "card_bullets": [
                    "Organization & permission setup",
                    "Policy setup & reimbursements",
                    "Receipt capture and more",
                ],
                "bullets_included": [
                    "Organization & permission setup",
                    "Policy setup & reimbursements",
                    "Receipt capture and more",
                ],
            },
        },
        {
            "sku": "START-ZOHO-PEOPLE",
            "updates": {
                "category": "Zoho Express Setup",
                "card_tag": "Project based",
                "card_title": "Zoho People",
                "card_description": "Structured HR operations with configurable policies.",
                "card_bullets": [
                    "Organization & Employees setup",
                    "Leave & attendance policy",
                    "Templates and more",
                ],
                "bullets_included": [
                    "Organization & Employees setup",
                    "Leave & attendance policy",
                    "Templates and more",
                ],
            },
        },
        {
            "sku": "AUDIT-HEALTH-START",
            "updates": {
                "category": "Audit & Optimize",
                "card_tag": "Project based",
                "card_bullets": [
                    "Up to 3 Zoho apps",
                    "Upto 10 creator/catalyst functions",
                    "1 x 1.5hr discovery calls and more",
                ],
                "bullets_included": [
                    "Up to 3 Zoho apps",
                    "Upto 10 creator/catalyst functions",
                    "1 x 1.5hr discovery calls and more",
                ],
            },
        },
        {
            "sku": "AUDIT-HEALTH-PLUS",
            "updates": {
                "category": "Audit & Optimize",
                "card_tag": "Project based",
                "card_bullets": [
                    "Up to 10 Zoho apps",
                    "Upto 10 creator/catalyst functions",
                    "3 x 1.5hr discovery calls and more",
                ],
                "bullets_included": [
                    "Up to 10 Zoho apps",
                    "Upto 10 creator/catalyst functions",
                    "3 x 1.5hr discovery calls and more",
                ],
            },
        },
        {
            "sku": "BUILD-HOURS-PACK",
            "updates": {
                "category": "Build & Automate",
                "name": "On-Demand Build Hours Pack",
                "tagline": "Prepaid bank of hours for custom software builds or Zoho developments.",
                "description_long": "Prepaid bank of hours for custom software builds or Zoho developments.",
                "card_tag": "One time",
                "card_title": "On-Demand Build Hours Pack",
                "card_description": "Prepaid bank of hours for custom software builds or Zoho developments.",
                "card_bullets": [
                    "Custom applications and tailored workflows",
                    "Integrate with existing business tools",
                    "Flexible, fast & cost effective and more",
                ],
                "bullets_included": [
                    "Custom applications and tailored workflows",
                    "Integrate with existing business tools",
                    "Flexible, fast & cost effective and more",
                ],
            },
        },
        {
            "sku": "ACC-BOOKKEEPING",
            "updates": {
                "category": "Accounting on Zoho",
                "name": "Ongoing Bookkeeping",
                "tagline": "Consistent, accurate bookkeeping inside Zoho Books",
                "description_long": "Consistent, accurate bookkeeping inside Zoho Books",
                "card_tag": "Subscription",
                "card_title": "Ongoing Bookkeeping",
                "card_description": "Consistent, accurate bookkeeping inside Zoho Books",
                "card_bullets": [
                    "Transaction categorization & Reconciliations",
                    "Taxes, Inventory, Projects, Multi-currency",
                    "Reports and more",
                ],
                "bullets_included": [
                    "Transaction categorization & Reconciliations",
                    "Taxes, Inventory, Projects, Multi-currency",
                    "Reports and more",
                ],
            },
        },
        {
            "sku": "ONGOING-SUPPORT",
            "updates": {
                "category": "Manages Services",
                "card_tag": "Subscription",
                "card_bullets": [
                    "Unlimited support requests",
                    "Dedicated Zoho expert",
                    "24-hour SLA target and more",
                ],
                "bullets_included": [
                    "Unlimited support requests",
                    "Dedicated Zoho expert",
                    "24-hour SLA target and more",
                ],
            },
        },
        {
            "sku": "ONGOING-DEV",
            "updates": {
                "category": "Manages Services",
                "tagline": "Continuous Zoho developments and improvements",
                "description_long": "Continuous Zoho developments and improvements",
                "card_tag": "Subscription",
                "card_bullets": [
                    "Unlimited development requests",
                    "1 task at a time with clear start times",
                    "Strategy, development, support and more",
                ],
                "bullets_included": [
                    "Unlimited development requests",
                    "1 task at a time with clear start times",
                    "Strategy, development, support and more",
                ],
            },
        },
        {
            "sku": "ONGOING-DEV-ENTERPRISE",
            "updates": {
                "category": "Manages Services",
                "card_tag": "Subscription",
                "card_bullets": [
                    "Unlimited development requests",
                    "Multiple tasks at a time with clear start times",
                    "Strategy, development, support and more",
                ],
                "bullets_included": [
                    "Unlimited development requests",
                    "Multiple tasks at a time with clear start times",
                    "Strategy, development, support and more",
                ],
                "pricing_type": "tiered",
                "pricing_rules": {
                    "variants": [
                        {"id": "2", "label": "2 simultaneous tasks", "price": 13999.0},
                        {"id": "3", "label": "3 simultaneous tasks", "price": 19999.0},
                        {"id": "4", "label": "4 simultaneous tasks", "price": 24999.0},
                        {"id": "5", "label": "5 simultaneous tasks", "price": 29999.0},
                    ]
                },
                "is_subscription": True,
            },
        },
        {
            "sku": "MIG-BOOKS",
            "updates": {
                "category": "Migrate to Zoho",
                "card_tag": "Project based",
                "tagline": "Clean & accurate transition to Zoho Books with minimum downtime",
                "description_long": "Clean & accurate transition to Zoho Books with minimum downtime",
                "pricing_type": "calculator",
                "pricing_rules": {"calc_type": "books_migration"},
                "card_bullets": [
                    "Multi-year historical data transfer",
                    "Inventory, Projects, Multi-currency",
                    "Post-migration checks and support and more",
                ],
                "bullets_included": [
                    "Multi-year historical data transfer",
                    "Inventory, Projects, Multi-currency",
                    "Post-migration checks and support and more",
                ],
            },
        },
        {
            "sku": "MIG-MAIL",
            "updates": {
                "category": "Migrate to Zoho",
                "card_tag": "Project based",
                "card_bullets": [
                    "Mailbox and folder migration",
                    "Calendar and contact transfer",
                    "Minimal email disruption and more",
                ],
                "bullets_included": [
                    "Mailbox and folder migration",
                    "Calendar and contact transfer",
                    "Minimal email disruption and more",
                ],
            },
        },
        {
            "sku": "MIG-WORKDRIVE",
            "updates": {
                "category": "Migrate to Zoho",
                "card_tag": "Project based",
                "tagline": "Move data into a structured Zoho workspace.",
                "description_long": "Move data into a structured Zoho workspace.",
                "card_bullets": [
                    "Bulk document transfer",
                    "Permissions mapping",
                    "Folder hierarchy restructuring and more",
                ],
                "bullets_included": [
                    "Bulk document transfer",
                    "Permissions mapping",
                    "Folder hierarchy restructuring and more",
                ],
            },
        },
        {
            "sku": "MIG-CRM",
            "updates": {
                "category": "Migrate to Zoho",
                "card_tag": "Project based",
                "tagline": "Clean, structured CRM data transition.",
                "description_long": "Clean, structured CRM data transition.",
                "card_bullets": [
                    "Leads, contacts, accounts, deals",
                    "Custom modules & unlimited records",
                    "Notes and activity transfer and more",
                ],
                "bullets_included": [
                    "Leads, contacts, accounts, deals",
                    "Custom modules & unlimited records",
                    "Notes and activity transfer and more",
                ],
            },
        },
        {
            "sku": "MIG-FORMS",
            "updates": {
                "category": "Migrate to Zoho",
                "card_tag": "Project based",
                "card_bullets": [
                    "Form rebuild and optimization",
                    "Field logic",
                    "Data import and validation and more",
                ],
                "bullets_included": [
                    "Form rebuild and optimization",
                    "Field logic",
                    "Data import and validation and more",
                ],
            },
        },
        {
            "sku": "MIG-DESK",
            "updates": {
                "category": "Migrate to Zoho",
                "card_tag": "Project based",
                "card_bullets": [
                    "Ticket, contacts",
                    "Knowledge base transfer",
                    "Setup and more",
                ],
                "bullets_included": [
                    "Ticket, contacts",
                    "Knowledge base transfer",
                    "Setup and more",
                ],
            },
        },
        {
            "sku": "MIG-SIGN",
            "updates": {
                "category": "Migrate to Zoho",
                "card_tag": "Project based",
                "card_bullets": [
                    "Template recreation and setup",
                    "Branding and email customization",
                    "Data store in workdrive and more",
                ],
                "bullets_included": [
                    "Template recreation and setup",
                    "Branding and email customization",
                    "Data store in workdrive and more",
                ],
            },
        },
        {
            "sku": "MIG-PEOPLE",
            "updates": {
                "category": "Migrate to Zoho",
                "card_tag": "Project based",
                "card_bullets": [
                    "People Setup",
                    "Employee records",
                    "Leave and attendance records and more",
                ],
                "bullets_included": [
                    "People Setup",
                    "Employee records",
                    "Leave and attendance records and more",
                ],
            },
        },
    ]

    for entry in updates:
        existing = await db.products.find_one({"sku": entry["sku"]}, {"_id": 0})
        if not existing:
            continue
        updated = {**existing, **entry["updates"]}
        updated["price_inputs"] = build_price_inputs(updated)
        await db.products.update_one({"sku": entry["sku"]}, {"$set": updated})
        if "pricing_rules" in entry["updates"]:
            await db.pricing_rules.update_one(
                {"product_id": existing["id"]},
                {"$set": {"rule_json": updated.get("pricing_rules", {})}},
                upsert=True,
            )

    new_products = [
        {
            "id": "prod_fixed_scope_dev",
            "category": "Build & Automate",
            "sku": "BUILD-FIXED-SCOPE",
            "name": "Fixed-Scope Development",
            "tagline": "Fixed-scope custom builds with defined deliverables and timelines.",
            "description_long": "Fixed-scope custom builds with a scope workshop, milestones, timeline, and approval gates before delivery.",
            "bullets_included": [
                "Custom applications and tailored workflows",
                "Integrate with existing business tools",
                "Clear scope, milestones, timeline and budget and more",
            ],
            "bullets_excluded": ["Ongoing retainer work", "Open-ended scope changes"],
            "bullets_needed": ["Business goals", "Access to existing systems", "Stakeholder availability"],
            "next_steps": ["Scope workshop", "Milestone plan approval", "Delivery kickoff"],
            "faqs": ["Request scope to start the fixed-scope planning process."],
            "pricing_type": "scope_request",
            "base_price": 0.0,
            "is_subscription": False,
            "pricing_rules": {},
            "stripe_price_id": None,
            "is_active": True,
            "card_tag": "Project based",
            "card_title": "Fixed-Scope Development",
            "card_description": "Fixed-scope custom builds with defined deliverables and timelines.",
            "card_bullets": [
                "Custom applications and tailored workflows",
                "Integrate with existing business tools",
                "Clear scope, milestones, timeline and budget and more",
            ],
        },
        {
            "id": "prod_historical_accounting",
            "category": "Accounting on Zoho",
            "sku": "ACC-HISTORICAL",
            "name": "Historical Accounting & Data Cleanup",
            "tagline": "Fix past periods, clean up messy books, and get reporting back on track.",
            "description_long": "Fix past periods, clean up messy books, and get reporting back on track.",
            "bullets_included": [
                "Cleanup of miscategorized transactions",
                "Catch-up bookkeeping for past periods",
                "Transaction categorization & Reconciliations",
            ],
            "bullets_excluded": ["Ongoing monthly bookkeeping"],
            "bullets_needed": ["Bank statements", "Existing accounting data access"],
            "next_steps": ["Assessment", "Cleanup execution", "Final review"],
            "faqs": ["One-time purchase for a bank of hours."],
            "pricing_type": "calculator",
            "base_price": None,
            "is_subscription": False,
            "pricing_rules": {
                "calc_type": "hours_pack",
                "min_hours": 10,
                "max_hours": 100,
                "step": 10,
                "pay_now_rate": 75.0,
                "scope_later_rate": 90.0,
            },
            "stripe_price_id": None,
            "is_active": True,
            "card_tag": "Project based",
            "card_title": "Historical Accounting & Data Cleanup",
            "card_description": "Fix past periods, clean up messy books, and get reporting back on track.",
            "card_bullets": [
                "Cleanup of miscategorized transactions",
                "Catch-up bookkeeping for past periods",
                "Transaction categorization & Reconciliations",
            ],
        },
    ]

    for product in new_products:
        existing = await db.products.find_one({"id": product["id"]}, {"_id": 0})
        if existing:
            continue
        product["price_inputs"] = build_price_inputs(product)
        await db.products.insert_one(product)


@app.on_event("startup")
async def startup_tasks():
    await ensure_audit_indexes()
    await SettingsService.cleanup_obsolete()
    await SettingsService.seed()
    await seed_admin_user()
    await seed_products()
    await apply_catalog_overrides()
    await db.products.update_many(
        {"category": "Start Here"},
        {"$set": {"category": "Zoho Express Setup"}},
    )
    await db.products.update_many(
        {"category": "Migrations"},
        {"$set": {"category": "Migrate to Zoho"}},
    )
    await db.products.update_many(
        {"category": "Ongoing Plans"},
        {"$set": {"category": "Managed Services"}},
    )
    # Fix "Manages Services" typo to "Managed Services"
    await db.products.update_many(
        {"category": "Manages Services"},
        {"$set": {"category": "Managed Services"}},
    )
    await db.customers.update_many(
        {"allow_bank_transfer": {"$exists": False}},
        {"$set": {"allow_bank_transfer": True}},
    )
    await db.customers.update_many(
        {"allow_card_payment": {"$exists": False}},
        {"$set": {"allow_card_payment": False}},
    )
    # Remove duplicate Historical Accounting product
    await db.products.delete_one({"id": "prod_accounting_cleanup"})
    await db.order_items.delete_many({"product_id": "prod_accounting_cleanup"})
    
    # Ensure default T&C exists
    default_terms = await db.terms_and_conditions.find_one({"is_default": True}, {"_id": 0})
    if not default_terms:
        await db.terms_and_conditions.insert_one({
            "id": make_id(),
            "title": "Default Terms & Conditions",
            "content": "{company_name} {product_name} - TEST",
            "is_default": True,
            "status": "active",
            "created_at": now_iso(),
        })
    
    # Migrate payment_method="manual" → "offline" for subscriptions (canonical value)
    await db.subscriptions.update_many(
        {"payment_method": "manual"},
        {"$set": {"payment_method": "offline"}}
    )
    
    # Migrate any subscription with status not in ALLOWED_SUBSCRIPTION_STATUSES
    invalid_status_subs = await db.subscriptions.find(
        {"status": {"$nin": ALLOWED_SUBSCRIPTION_STATUSES}}, {"_id": 0, "id": 1, "status": 1}
    ).to_list(500)
    for sub in invalid_status_subs:
        old_status = sub.get("status", "unknown")
        await db.subscriptions.update_one(
            {"id": sub["id"]},
            {"$set": {"status": "active", "_migrated_status": old_status}}
        )
        await create_audit_log(
            entity_type="subscription",
            entity_id=sub["id"],
            action="status_migrated",
            actor="system",
            details={"old_status": old_status, "new_status": "active", "reason": "canonical status migration"}
        )
    
    # Backfill subscription_number for any subscriptions missing it
    subs_missing_number = await db.subscriptions.find(
        {"subscription_number": {"$exists": False}}, {"_id": 0, "id": 1}
    ).to_list(500)
    for sub in subs_missing_number:
        sub_num = f"SUB-{sub['id'].split('-')[0].upper()}"
        await db.subscriptions.update_one({"id": sub["id"]}, {"$set": {"subscription_number": sub_num}})
    
    # Backfill start_date for subscriptions missing it
    await db.subscriptions.update_many(
        {"start_date": {"$exists": False}, "current_period_start": {"$exists": True}},
        [{"$set": {"start_date": "$current_period_start"}}]
    )
    await db.subscriptions.update_many(
        {"start_date": {"$exists": False}},
        [{"$set": {"start_date": "$created_at"}}]
    )
    
    # Backfill role field for admin users (set existing admins to super_admin)
    await db.users.update_many(
        {"is_admin": True, "role": {"$exists": False}},
        {"$set": {"role": "super_admin"}}
    )
    await db.users.update_many(
        {"is_admin": False, "role": {"$exists": False}},
        {"$set": {"role": "customer"}}
    )
    
    # Backfill is_active=True for all existing users (so nobody is inadvertently locked out)
    await db.users.update_many(
        {"is_active": {"$exists": False}},
        {"$set": {"is_active": True}}
    )

    # Backfill partner_map and notes fields for existing customers
    await db.customers.update_many(
        {"partner_map": {"$exists": False}},
        {"$set": {"partner_map": None}}
    )
    await db.customers.update_many(
        {"notes": {"$exists": False}},
        {"$set": {"notes": []}}
    )

    # === NEW MIGRATIONS ===

    # 1. Seed categories collection from existing product category strings (with blurbs)
    CATEGORY_BLURBS_SEED = {
        "Zoho Express Setup": "Fast-track your Zoho setup with expert-led implementation.",
        "Migrate to Zoho": "Move critical systems with minimal downtime and clear milestones.",
        "Managed Services": "Your long-term Zoho partner - managing enhancements, resolving issues, and scaling workflows as you evolve.",
        "Build & Automate": "On-demand development hours to design, build, automate, and refine your Technology stack (Zoho & Non-Zoho).",
        "Accounting on Zoho": "Monthly finance operations tailored to your transaction volume.",
        "Audit & Optimize": "Diagnose what's slowing you down - Refine, Streamline & Maximize",
    }
    all_prods = await db.products.find({}, {"_id": 0, "category": 1}).to_list(2000)
    existing_prod_cats = {p["category"] for p in all_prods if p.get("category")}
    for cat_name in existing_prod_cats:
        existing_cat = await db.categories.find_one({"name": cat_name})
        if not existing_cat:
            await db.categories.insert_one({
                "id": make_id(),
                "name": cat_name,
                "description": CATEGORY_BLURBS_SEED.get(cat_name, ""),
                "is_active": True,
                "created_at": now_iso(),
            })
        elif "description" not in existing_cat and cat_name in CATEGORY_BLURBS_SEED:
            await db.categories.update_one(
                {"name": cat_name},
                {"$set": {"description": CATEGORY_BLURBS_SEED[cat_name]}}
            )

    # Backfill contract_end_date for existing subscriptions (default 12 months from start)
    async for sub in db.subscriptions.find({"contract_end_date": {"$exists": False}}):
        start_raw = sub.get("start_date") or sub.get("current_period_start") or sub.get("created_at")
        if start_raw:
            try:
                start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                contract_end = start_dt + timedelta(days=365)
                await db.subscriptions.update_one(
                    {"id": sub["id"]},
                    {"$set": {"contract_end_date": contract_end.isoformat()}}
                )
            except Exception:
                pass

    # Seed default app settings (brand colors) if not already customized
    existing_settings = await db.app_settings.find_one({})
    if not existing_settings:
        await db.app_settings.insert_one({
            "primary_color": "#0f172a",
            "secondary_color": "#f8fafc",
            "accent_color": "#dc2626",
            "store_name": "Automate Accounts",
            "logo_url": "",
        })
    else:
        # Update test color placeholders to proper brand defaults
        updates = {}
        if existing_settings.get("primary_color") == "#123456":
            updates["primary_color"] = "#0f172a"
        if not existing_settings.get("accent_color"):
            updates["accent_color"] = "#dc2626"
        if updates:
            await db.app_settings.update_one({}, {"$set": updates})

    # 2. Backfill pricing_complexity based on pricing_type for products missing it
    PRICING_TYPE_TO_COMPLEXITY = {
        "fixed": "SIMPLE",
        "simple": "SIMPLE",
        "calculator": "COMPLEX",
        "tiered": "COMPLEX",
        "hours": "COMPLEX",
        "external": "REQUEST_FOR_QUOTE",
        "scope_request": "REQUEST_FOR_QUOTE",
        "inquiry": "REQUEST_FOR_QUOTE",
    }
    products_missing_complexity = await db.products.find(
        {"pricing_complexity": {"$exists": False}}, {"_id": 0, "id": 1, "pricing_type": 1}
    ).to_list(2000)
    for prod in products_missing_complexity:
        p_type = prod.get("pricing_type", "fixed")
        complexity = PRICING_TYPE_TO_COMPLEXITY.get(p_type, "SIMPLE")
        await db.products.update_one(
            {"id": prod["id"]},
            {"$set": {"pricing_complexity": complexity}}
        )




@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
