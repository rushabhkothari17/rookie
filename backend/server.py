from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, UploadFile, File
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
from services.audit_service import AuditService, ensure_audit_indexes
from middleware.request_id import RequestIDMiddleware

app = FastAPI()
api_router = APIRouter(prefix="/api")

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
from routes.admin.logs import router as audit_logs_router
app.include_router(audit_logs_router)


# Order status enum — imported from core.constants (ALLOWED_ORDER_STATUSES, ALLOWED_SUBSCRIPTION_STATUSES)
ALLOWED_ORDER_STATUSES = [
    "pending",
    "pending_direct_debit_setup",
    "pending_payment",
    "awaiting_bank_transfer",
    "paid",
    "unpaid",
    "completed",
    "cancelled",
    "refunded",
    "disputed",
    "scope_pending",
    "canceled_pending",
]

ALLOWED_SUBSCRIPTION_STATUSES = [
    "active",
    "unpaid",
    "paused",
    "canceled_pending",
    "cancelled",
    "offline_manual",
]


def validate_order_status(status: str) -> bool:
    """Validate order status against allowed values"""
    return status in ALLOWED_ORDER_STATUSES


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def make_id():
    return str(uuid.uuid4())


def round_cents(value: float) -> float:
    return float(f"{value:.2f}")


PREMIUM_MIGRATION_ITEMS = {"price_list", "multi_currency", "projects", "timesheet"}
STANDARD_MIGRATION_SOURCES = {"quickbooks_online", "sage_50_online", "spreadsheet"}


def round_to_nearest_99(amount: float) -> int:
    """Round amount to nearest 'X99' value. Tie goes to high."""
    low = int(amount / 100) * 100 - 1
    high = low + 100
    return high if abs(amount - high) <= abs(amount - low) else low


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


def round_nearest_25(value: float) -> float:
    return float(round(value / 25) * 25)


def currency_for_country(country: str) -> str:
    c = (country or "").strip().lower()
    if c in ["canada", "ca"]:
        return "CAD"
    if c in ["usa", "us", "united states", "united states of america"]:
        return "USD"
    return "UNSUPPORTED"


def create_access_token(payload: Dict[str, Any]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    payload.update({"exp": expire})
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    payload = decode_token(credentials.credentials)
    user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact your administrator.")
    return user


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)):
    if not (user.get("is_admin") or user.get("role") in ("admin", "super_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_super_admin(user: Dict[str, Any] = Depends(get_current_user)):
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


async def optional_get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        token = auth_header.split(" ", 1)[1]
        payload = decode_token(token)
        user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
        if user and user.get("is_active", True):
            return user
    except Exception:
        pass
    return None


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
    """Create an audit log entry"""
    await db.audit_logs.insert_one({
        "id": make_id(),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "actor": actor,
        "details": details or {},
        "created_at": now_iso(),
    })


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge override into base. Override values win on conflict."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


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


def calculate_price(product: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
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

    fee = round_cents(subtotal * 0.05) if requires_checkout and not is_scope_request else 0.0
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


@api_router.post("/checkout/bank-transfer")
async def checkout_bank_transfer(
    payload: BankTransferCheckoutRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    # Validate T&C acceptance
    if not payload.terms_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Terms & Conditions to proceed")
    
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not customer.get("allow_bank_transfer", True):
        raise HTTPException(status_code=403, detail="Bank transfer not enabled")

    # Validate Zoho Partner Tag (before building order items to fail fast)
    await validate_and_consume_partner_tag(
        customer_id=customer["id"],
        partner_tag_response=payload.partner_tag_response,
        override_code=payload.override_code,
        order_id=None,  # order_id not yet known; updated below after creation
    )

    order_items = await build_order_items(payload.items)

    if any(i["product"].get("sku") == "MIG-CRM" for i in order_items) and any(
        i["product"].get("sku") == "START-ZOHO-CRM-EXP" for i in order_items
    ):
        raise HTTPException(status_code=400, detail="CRM data migration is included in CRM Express Setup")

    checkout_type = payload.checkout_type
    if checkout_type not in ["one_time", "subscription"]:
        raise HTTPException(status_code=400, detail="Invalid checkout type")

    if checkout_type == "subscription":
        subscription_items = [i for i in order_items if i["pricing"].get("is_subscription")]
        if len(subscription_items) != len(order_items):
            raise HTTPException(status_code=400, detail="Subscription checkout must include only subscription items")
        if len(subscription_items) != 1:
            raise HTTPException(status_code=400, detail="Subscription checkout supports one plan at a time")

        product = subscription_items[0]["product"]
        subtotal = subscription_items[0]["pricing"]["subtotal"]
        
        # Get T&C and resolve
        terms_id = payload.terms_id if payload.terms_id else product.get("terms_id")
        if not terms_id:
            default_terms = await db.terms_and_conditions.find_one({"is_default": True, "status": "active"}, {"_id": 0})
            terms_id = default_terms["id"] if default_terms else None
        
        rendered_terms_text = ""
        if terms_id:
            terms = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
            if terms:
                address = await db.addresses.find_one({"user_id": user["id"]}, {"_id": 0})
                rendered_terms_text = resolve_terms_tags(terms["content"], user, address, product["name"])
        
        period_start = datetime.now(timezone.utc)
        # If start_date provided and in the future, use it as period start
        requested_start = None
        if payload.start_date:
            try:
                sd = datetime.fromisoformat(payload.start_date)
                if sd.tzinfo is None:
                    sd = sd.replace(tzinfo=timezone.utc)
                if sd > datetime.now(timezone.utc):
                    period_start = sd
                    requested_start = payload.start_date
            except Exception:
                pass
        period_end = period_start + timedelta(days=30)
        contract_end = period_start + timedelta(days=365)
        sub_id = make_id()
        
        # Create GoCardless customer and redirect flow
        gocardless_redirect_url = None
        gc_customer_id = customer.get("gocardless_customer_id")
        redirect_flow_id = None
        
        if not gc_customer_id:
            # Create GoCardless customer
            name_parts = user.get("full_name", "Customer User").split()
            gc_customer = create_gocardless_customer(
                email=user["email"],
                given_name=name_parts[0],
                family_name=name_parts[-1] if len(name_parts) > 1 else "User",
                company_name=user.get("company_name", "")
            )
            if gc_customer:
                gc_customer_id = gc_customer["id"]
                await db.customers.update_one(
                    {"id": customer["id"]},
                    {"$set": {"gocardless_customer_id": gc_customer_id}}
                )
        
        # Create redirect flow for mandate setup
        if gc_customer_id:
            session_token = make_id()
            success_url = f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/gocardless/callback?session_token={session_token}&subscription_id={sub_id}"
            
            redirect_flow = create_redirect_flow(
                session_token=session_token,
                success_redirect_url=success_url,
                description=f"Direct Debit for {product['name']}"
            )
            
            if redirect_flow:
                redirect_flow_id = redirect_flow["id"]
                gocardless_redirect_url = redirect_flow["redirect_url"]
        
        await db.subscriptions.insert_one(
            {
                "id": sub_id,
                "order_id": None,
                "customer_id": customer["id"],
                "plan_name": product["name"],
                "status": "pending_direct_debit_setup",
                "stripe_subscription_id": None,
                "gocardless_customer_id": gc_customer_id,
                "gocardless_redirect_flow_id": redirect_flow_id,
                "current_period_start": period_start.isoformat(),
                "current_period_end": period_end.isoformat(),
                "cancel_at_period_end": False,
                "canceled_at": None,
                "amount": subtotal,
                "payment_method": "bank_transfer",
                "terms_id_used": terms_id,
                "rendered_terms_text": rendered_terms_text,
                "terms_accepted_at": now_iso(),
                "start_date": requested_start or period_start.isoformat(),
                "contract_end_date": contract_end.isoformat(),
                "partner_tag_response": payload.partner_tag_response,
                "override_code_id": None,  # updated below after override code lookup
                "partner_tag_timestamp": now_iso(),
                "notes_json": build_checkout_notes_json(order_items, payload, user["id"], customer["id"], payment_method="bank_transfer"),
            }
        )
        
        await create_audit_log(
            entity_type="subscription",
            entity_id=sub_id,
            action="created",
            actor="customer",
            details={"status": "pending_direct_debit_setup", "payment_method": "bank_transfer"}
        )
        
        await db.zoho_sync_logs.insert_one(
            {
                "id": make_id(),
                "entity_type": "subscription_request",
                "entity_id": sub_id,
                "status": "Not Sent",
                "last_error": None,
                "attempts": 0,
                "created_at": now_iso(),
                "mocked": True,
            }
        )
        
        if not gocardless_redirect_url:
            raise HTTPException(
                status_code=500,
                detail="Failed to create GoCardless redirect flow. Please contact support or try card payment."
            )
        
        return {
            "message": "Subscription request created. Please complete Direct Debit setup.",
            "subscription_id": sub_id,
            "status": "pending_direct_debit_setup",
            "gocardless_customer_id": gc_customer_id,
            "gocardless_redirect_url": gocardless_redirect_url,
            "redirect_flow_id": redirect_flow_id,
        }

    subtotal = sum(i["pricing"]["subtotal"] for i in order_items)
    
    # Apply promo code discount with product-level eligibility (no fee for bank transfer)
    promo_code_data = None
    discount_amount = 0.0
    if payload.promo_code:
        promo = await db.promo_codes.find_one({"code": payload.promo_code.upper()}, {"_id": 0})
        if promo and promo.get("enabled"):
            now = datetime.now(timezone.utc).isoformat()
            is_expired = promo.get("expiry_date") and promo["expiry_date"] < now
            max_reached = promo.get("max_uses") and promo.get("usage_count", 0) >= promo["max_uses"]
            applies_to = promo.get("applies_to", "both")
            type_matches = applies_to == "both" or applies_to == "one-time"
            
            # Check product-level eligibility
            product_eligible = True
            applies_to_products = promo.get("applies_to_products", "all")
            if applies_to_products == "selected":
                eligible_product_ids = promo.get("product_ids", [])
                cart_product_ids = [i["product"]["id"] for i in order_items]
                if not all(pid in eligible_product_ids for pid in cart_product_ids):
                    product_eligible = False
            
            if not is_expired and not max_reached and type_matches and product_eligible:
                if promo["discount_type"] == "percent":
                    discount_amount = round_cents(subtotal * promo["discount_value"] / 100)
                else:
                    discount_amount = min(round_cents(promo["discount_value"]), subtotal)
                promo_code_data = promo
    
    total = round_cents(subtotal - discount_amount)
    
    # Get T&C for the product and resolve tags
    primary_product = order_items[0]["product"]
    terms_id = payload.terms_id if payload.terms_id else primary_product.get("terms_id")
    if not terms_id:
        default_terms = await db.terms_and_conditions.find_one({"is_default": True, "status": "active"}, {"_id": 0})
        terms_id = default_terms["id"] if default_terms else None
    
    rendered_terms_text = ""
    if terms_id:
        terms = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
        if terms:
            address = await db.addresses.find_one({"user_id": user["id"]}, {"_id": 0})
            rendered_terms_text = resolve_terms_tags(terms["content"], user, address, primary_product["name"])
    
    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"
    
    # Create GoCardless redirect flow for one-time payment
    gocardless_redirect_url = None
    gc_customer_id = customer.get("gocardless_customer_id")
    redirect_flow_id = None
    
    if not gc_customer_id:
        name_parts = user.get("full_name", "Customer User").split()
        gc_customer = create_gocardless_customer(
            email=user["email"],
            given_name=name_parts[0],
            family_name=name_parts[-1] if len(name_parts) > 1 else "User",
            company_name=user.get("company_name", "")
        )
        if gc_customer:
            gc_customer_id = gc_customer["id"]
            await db.customers.update_one(
                {"id": customer["id"]},
                {"$set": {"gocardless_customer_id": gc_customer_id}}
            )
    
    # Create redirect flow
    if gc_customer_id:
        session_token = make_id()
        success_url = f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/gocardless/callback?session_token={session_token}&order_id={order_id}"
        
        redirect_flow = create_redirect_flow(
            session_token=session_token,
            success_redirect_url=success_url,
            description=f"Payment for Order {order_number}"
        )
        
        if redirect_flow:
            redirect_flow_id = redirect_flow["id"]
            gocardless_redirect_url = redirect_flow["redirect_url"]
    
    order_doc = {
        "id": order_id,
        "order_number": order_number,
        "customer_id": customer["id"],
        "type": "one_time",
        "status": "pending_direct_debit_setup",
        "subtotal": round_cents(subtotal),
        "discount_amount": discount_amount,
        "promo_code": promo_code_data["code"] if promo_code_data else None,
        "fee": 0.0,
        "total": total,
        "currency": customer.get("currency"),
        "payment_method": "bank_transfer",
        "gocardless_redirect_flow_id": redirect_flow_id,
        "terms_id_used": terms_id,
        "rendered_terms_text": rendered_terms_text,
        "terms_accepted_at": now_iso(),
        "partner_tag_response": payload.partner_tag_response,
        "override_code_id": None,  # set after override code validation
        "partner_tag_timestamp": now_iso(),
        "notes_json": build_checkout_notes_json(order_items, payload, user["id"], customer["id"], payment_method="bank_transfer"),
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order_doc)
    
    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="created",
        actor="customer",
        details={"status": "pending_direct_debit_setup", "payment_method": "bank_transfer", "total": total}
    )
    
    # Increment promo code usage
    if promo_code_data:
        await db.promo_codes.update_one(
            {"id": promo_code_data["id"]},
            {"$inc": {"usage_count": 1}}
        )

    for item in order_items:
        product = item["product"]
        await db.order_items.insert_one(
            {
                "id": make_id(),
                "order_id": order_id,
                "product_id": product["id"],
                "quantity": item["quantity"],
                "metadata_json": item["inputs"],
                "unit_price": item["pricing"]["subtotal"],
                "line_total": item["pricing"]["subtotal"],
            }
        )

    await db.invoices.insert_one(
        {
            "id": make_id(),
            "order_id": order_id,
            "subscription_id": None,
            "stripe_invoice_id": None,
            "zoho_books_invoice_id": None,
            "amount_paid": 0.0,
            "status": "unpaid",
        }
    )
    await db.zoho_sync_logs.insert_one(
        {
            "id": make_id(),
            "entity_type": "deal",
            "entity_id": order_id,
            "status": "Not Sent",
            "last_error": None,
            "attempts": 0,
            "created_at": now_iso(),
            "mocked": True,
        }
    )
    
    # Email T&C to customer (mocked)
    if rendered_terms_text:
        await db.email_outbox.insert_one({
            "id": make_id(),
            "to": user["email"],
            "subject": f"Terms & Conditions for Order {order_number}",
            "body": rendered_terms_text,
            "type": "terms_and_conditions",
            "status": "MOCKED",
            "created_at": now_iso(),
        })
    
    if not gocardless_redirect_url:
        raise HTTPException(
            status_code=500,
            detail="Failed to create GoCardless redirect flow. Please contact support or try card payment."
        )

    return {
        "message": "Order created. Please complete Direct Debit setup.",
        "order_id": order_id,
        "order_number": order_number,
        "gocardless_redirect_url": gocardless_redirect_url,
        "redirect_flow_id": redirect_flow_id,
        "status": "pending_direct_debit_setup",
    }
    
    # Apply promo code discount (no fee for bank transfer)
    promo_code_data = None
    discount_amount = 0.0
    if payload.promo_code:
        promo = await db.promo_codes.find_one({"code": payload.promo_code.upper()}, {"_id": 0})
        if promo and promo.get("enabled"):
            now = datetime.now(timezone.utc).isoformat()
            is_expired = promo.get("expiry_date") and promo["expiry_date"] < now
            max_reached = promo.get("max_uses") and promo.get("usage_count", 0) >= promo["max_uses"]
            applies_to = promo.get("applies_to", "both")
            type_matches = applies_to == "both" or applies_to == "one-time"
            
            if not is_expired and not max_reached and type_matches:
                if promo["discount_type"] == "percent":
                    discount_amount = round_cents(subtotal * promo["discount_value"] / 100)
                else:
                    discount_amount = min(round_cents(promo["discount_value"]), subtotal)
                promo_code_data = promo
    
    total = round_cents(subtotal - discount_amount)
    
    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"
    order_doc = {
        "id": order_id,
        "order_number": order_number,
        "customer_id": customer["id"],
        "type": "one_time",
        "status": "awaiting_bank_transfer",
        "subtotal": round_cents(subtotal),
        "discount_amount": discount_amount,
        "promo_code": promo_code_data["code"] if promo_code_data else None,
        "fee": 0.0,
        "total": total,
        "currency": customer.get("currency"),
        "payment_method": "bank_transfer",
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order_doc)
    
    # Increment promo code usage
    if promo_code_data:
        await db.promo_codes.update_one(
            {"id": promo_code_data["id"]},
            {"$inc": {"usage_count": 1}}
        )

    for item in order_items:
        product = item["product"]
        await db.order_items.insert_one(
            {
                "id": make_id(),
                "order_id": order_id,
                "product_id": product["id"],
                "quantity": item["quantity"],
                "metadata_json": item["inputs"],
                "unit_price": item["pricing"]["subtotal"],
                "line_total": item["pricing"]["subtotal"],
            }
        )

    await db.invoices.insert_one(
        {
            "id": make_id(),
            "order_id": order_id,
            "subscription_id": None,
            "stripe_invoice_id": None,
            "zoho_books_invoice_id": None,
            "amount_paid": 0.0,
            "status": "unpaid",
        }
    )
    await db.zoho_sync_logs.insert_one(
        {
            "id": make_id(),
            "entity_type": "deal",
            "entity_id": order_id,
            "status": "Not Sent",
            "last_error": None,
            "attempts": 0,
            "created_at": now_iso(),
            "mocked": True,
        }
    )

    return {
        "message": "Bank transfer order created",
        "order_id": order_id,
        "order_number": order_number,
    }


@app.on_event("startup")
async def startup_tasks():
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



@api_router.get("/")
async def root():
    return {"message": "Automate Accounts API"}


@api_router.post("/auth/register")
async def register(payload: RegisterRequest):
    existing = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = make_id()
    verification_code = f"{secrets.randbelow(999999):06d}"
    hashed = pwd_context.hash(payload.password)

    user_doc = {
        "id": user_id,
        "email": payload.email.lower(),
        "password_hash": hashed,
        "full_name": payload.full_name,
        "job_title": payload.job_title,
        "company_name": payload.company_name,
        "phone": payload.phone,
        "is_verified": False,
        "is_admin": False,
        "verification_code": verification_code,
        "created_at": now_iso(),
    }
    await db.users.insert_one(user_doc)

    customer_id = make_id()
    currency = currency_for_country(payload.address.country)
    await db.customers.insert_one(
        {
            "id": customer_id,
            "user_id": user_id,
            "company_name": payload.company_name,
            "phone": payload.phone,
            "currency": currency,
            "currency_locked": False,
            "allow_bank_transfer": True,
            "allow_card_payment": False,
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
            "line1": payload.address.line1,
            "line2": payload.address.line2 or "",
            "city": payload.address.city,
            "region": payload.address.region,
            "postal": payload.address.postal,
            "country": payload.address.country,
        }
    )

    await db.email_outbox.insert_one(
        {
            "id": make_id(),
            "to": payload.email.lower(),
            "subject": "Verify your Automate Accounts account",
            "body": f"Your verification code is {verification_code}",
            "type": "verification",
            "status": "MOCKED",
            "created_at": now_iso(),
        }
    )

    return {
        "message": "Verification required",
        "verification_code": verification_code,
        "email_delivery": "MOCKED",
    }


@api_router.post("/auth/verify-email")
async def verify_email(payload: VerifyEmailRequest):
    user = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("is_verified"):
        return {"message": "Already verified"}
    if user.get("verification_code") != payload.code:
        raise HTTPException(status_code=400, detail="Invalid code")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"is_verified": True, "verification_code": None}},
    )
    await db.email_outbox.insert_one(
        {
            "id": make_id(),
            "to": payload.email.lower(),
            "subject": "Welcome to Automate Accounts",
            "body": "Your email has been verified.",
            "type": "welcome",
            "status": "MOCKED",
            "created_at": now_iso(),
        }
    )
    return {"message": "Verified"}


@api_router.post("/auth/login")
async def login(payload: LoginRequest):
    user = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not pwd_context.verify(payload.password, user.get("password_hash")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_verified"):
        raise HTTPException(status_code=403, detail="Email verification required")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact your administrator.")

    token = create_access_token(
        {
            "sub": user["id"],
            "email": user["email"],
            "is_admin": user.get("is_admin", False),
        }
    )
    return {"token": token}


@api_router.get("/me")
async def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    address = None
    if customer:
        address = await db.addresses.find_one({"customer_id": customer["id"]}, {"_id": 0})
    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "company_name": user["company_name"],
            "phone": user["phone"],
            "is_verified": user.get("is_verified", False),
            "is_admin": user.get("is_admin", False),
            "role": user.get("role", "customer"),
            "must_change_password": user.get("must_change_password", False),
        },
        "customer": customer,
        "address": address,
    }


@api_router.put("/me")
async def update_me(
    payload: UpdateProfileRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    # Get current address to check country
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    current_address = await db.addresses.find_one({"customer_id": customer["id"]}, {"_id": 0})
    
    # Block country changes for non-admins
    if current_address and payload.address.country != current_address.get("country"):
        raise HTTPException(status_code=403, detail="Country cannot be changed. Contact admin for assistance.")
    
    await db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {
                "full_name": payload.full_name,
                "company_name": payload.company_name,
                "phone": payload.phone,
            }
        },
    )

    update_fields = {
        "company_name": payload.company_name,
        "phone": payload.phone,
    }
    await db.customers.update_one({"id": customer["id"]}, {"$set": update_fields})

    await db.addresses.update_one(
        {"customer_id": customer["id"]},
        {
            "$set": {
                "line1": payload.address.line1,
                "line2": payload.address.line2 or "",
                "city": payload.address.city,
                "region": payload.address.region,
                "postal": payload.address.postal,
            }
        },
    )
    return {"message": "Profile updated"}


@api_router.get("/categories")
async def get_categories():
    inactive_cats = await db.categories.find({"is_active": False}, {"_id": 0, "name": 1}).to_list(500)
    inactive_names = {c["name"] for c in inactive_cats}
    all_cats = await db.categories.find({"is_active": True}, {"_id": 0, "name": 1, "description": 1}).to_list(500)
    cat_map = {c["name"]: c.get("description", "") for c in all_cats}
    products = await db.products.find({"is_active": True}, {"_id": 0, "category": 1}).to_list(1000)
    categories = sorted({
        p["category"] for p in products
        if p.get("category") and p["category"] not in inactive_names
    })
    blurbs = {name: cat_map.get(name, "") for name in categories}
    return {"categories": categories, "category_blurbs": blurbs}


@api_router.get("/products")
async def get_products(user: Optional[Dict[str, Any]] = Depends(optional_get_current_user)):
    # Get inactive categories
    inactive_cats = await db.categories.find({"is_active": False}, {"_id": 0, "name": 1}).to_list(500)
    inactive_cat_names = {c["name"] for c in inactive_cats}

    query: Dict[str, Any] = {"is_active": True}
    if inactive_cat_names:
        query["category"] = {"$nin": list(inactive_cat_names)}

    all_products = await db.products.find(query, {"_id": 0}).to_list(1000)

    # Filter by customer visibility
    if user:
        customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
        customer_id = customer["id"] if customer else None
    else:
        customer_id = None

    def is_visible(p: Dict) -> bool:
        vis = p.get("visible_to_customers", [])
        if not vis:
            return True
        return customer_id in vis if customer_id else False

    products = [p for p in all_products if is_visible(p)]
    return {"products": products}


@api_router.get("/products/{product_id}")
async def get_product(product_id: str):
    product = await db.products.find_one({"id": product_id, "is_active": True}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"product": product}


@api_router.post("/pricing/calc")
async def pricing_calc(
    payload: PricingCalcRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    product = await db.products.find_one({"id": payload.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    result = calculate_price(product, payload.inputs)
    return {"product_id": product["id"], **result}


async def build_order_items(items: List[CartItemInput]):
    order_items = []
    for item in items:
        product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        pricing = calculate_price(product, item.inputs)
        order_items.append(
            {
                "id": make_id(),
                "product": product,
                "quantity": item.quantity,
                "pricing": pricing,
                "inputs": item.inputs,
            }
        )
    return order_items


@api_router.post("/orders/preview")
async def orders_preview(
    payload: OrderPreviewRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    order_items = await build_order_items(payload.items)
    groups = {"one_time": [], "subscription": [], "scope_request": [], "external": [], "inquiry": []}
    for item in order_items:
        product = item["product"]
        pricing = item["pricing"]
        if product.get("pricing_type") == "external":
            groups["external"].append(item)
        elif product.get("pricing_type") == "inquiry" or pricing.get("requires_checkout") is False and pricing.get("is_scope_request") is False:
            groups["inquiry"].append(item)
        elif pricing.get("is_scope_request"):
            groups["scope_request"].append(item)
        elif pricing.get("is_subscription"):
            groups["subscription"].append(item)
        else:
            groups["one_time"].append(item)

    def summarize(group_items):
        subtotal = sum(i["pricing"]["subtotal"] for i in group_items)
        fee = sum(i["pricing"]["fee"] for i in group_items)
        total = sum(i["pricing"]["total"] for i in group_items)
        return {
            "count": len(group_items),
            "subtotal": round_cents(subtotal),
            "fee": round_cents(fee),
            "total": round_cents(total),
        }

    return {
        "currency": customer.get("currency"),
        "items": order_items,
        "summary": {
            "one_time": summarize(groups["one_time"]),
            "subscription": summarize(groups["subscription"]),
            "scope_request": summarize(groups["scope_request"]),
        },
    }


@api_router.post("/orders/scope-request")
async def scope_request(
    payload: ScopeRequestBody,
    user: Dict[str, Any] = Depends(get_current_user),
):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    order_items = await build_order_items(payload.items)
    scope_items = [i for i in order_items if i["pricing"].get("is_scope_request")]
    if not scope_items:
        raise HTTPException(status_code=400, detail="No scope request items found")

    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"
    subtotal = sum(i["pricing"]["subtotal"] for i in scope_items)

    order_doc = {
        "id": order_id,
        "order_number": order_number,
        "customer_id": customer["id"],
        "type": "scope_request",
        "status": "scope_requested",
        "subtotal": round_cents(subtotal),
        "fee": 0.0,
        "total": round_cents(subtotal),
        "currency": customer.get("currency"),
        "payment_method": "scope_request",
        "notes_json": {
            "product_intake": {
                item["product"]["id"]: item.get("inputs", {})
                for item in scope_items
            },
            "payment": {"method": "scope_request"},
            "system_metadata": {
                "user_id": user["id"],
                "customer_id": customer["id"],
                "timestamp": now_iso(),
            },
        },
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order_doc)

    for item in scope_items:
        product = item["product"]
        await db.order_items.insert_one(
            {
                "id": make_id(),
                "order_id": order_id,
                "product_id": product["id"],
                "quantity": item["quantity"],
                "metadata_json": item["inputs"],
                "unit_price": item["pricing"]["subtotal"],
                "line_total": item["pricing"]["subtotal"],
            }
        )

    await db.zoho_sync_logs.insert_one(
        {
            "id": make_id(),
            "entity_type": "deal",
            "entity_id": order_id,
            "status": "Not Sent",
            "last_error": None,
            "attempts": 0,
            "created_at": now_iso(),
            "mocked": True,
        }
    )

    return {"message": "Scope request created", "order_id": order_id, "order_number": order_number}


@api_router.post("/checkout/session")
async def create_checkout_session(
    payload: CheckoutSessionRequestBody,
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
):
    # Validate T&C acceptance
    if not payload.terms_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Terms & Conditions to proceed")
    
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.get("currency") not in ["USD", "CAD"]:
        raise HTTPException(status_code=400, detail="Purchases not supported in your region yet")

    # Validate Zoho account context questions
    if not payload.zoho_subscription_type:
        raise HTTPException(status_code=400, detail="Please select your current Zoho subscription type.")
    if not payload.current_zoho_product:
        raise HTTPException(status_code=400, detail="Please select your current Zoho product.")
    if not payload.zoho_account_access:
        raise HTTPException(status_code=400, detail="Please indicate whether you have provided Zoho account access.")

    # Validate Zoho Partner Tag (fail fast before building order)
    await validate_and_consume_partner_tag(
        customer_id=customer["id"],
        partner_tag_response=payload.partner_tag_response,
        override_code=payload.override_code,
        order_id=None,
    )

    order_items = await build_order_items(payload.items)

    if any(i["product"].get("sku") == "MIG-CRM" for i in order_items) and any(
        i["product"].get("sku") == "START-ZOHO-CRM-EXP" for i in order_items
    ):
        raise HTTPException(status_code=400, detail="CRM data migration is included in CRM Express Setup")

    checkout_type = payload.checkout_type
    if checkout_type not in ["one_time", "subscription"]:
        raise HTTPException(status_code=400, detail="Invalid checkout type")

    if checkout_type == "subscription":
        subscription_items = [i for i in order_items if i["pricing"].get("is_subscription")]
        if len(subscription_items) != len(order_items):
            raise HTTPException(status_code=400, detail="Subscription checkout must include only subscription items")
        if len(subscription_items) != 1:
            raise HTTPException(status_code=400, detail="Subscription checkout supports one plan at a time")
        
        product = subscription_items[0]["product"]
        subtotal = subscription_items[0]["pricing"]["subtotal"]
        
        # Validate subscription has pricing
        if not subtotal or subtotal <= 0:
            raise HTTPException(status_code=400, detail="Subscription pricing not configured. Please contact support.")
        
        # Validate customer is eligible for card payment
        if not customer.get("allow_card_payment", False):
            raise HTTPException(status_code=403, detail="Card payment is not enabled for your account. Please contact support or use Bank Transfer.")
        
        # Check if stripe_price_id exists for subscription products
        stripe_price_id = product.get("stripe_price_id")
        if not stripe_price_id:
            raise HTTPException(
                status_code=400, 
                detail=f"Subscription product '{product.get('name')}' is not configured for card payment. Missing Stripe Price ID. Please contact support or use Bank Transfer."
            )

    if checkout_type == "one_time":
        for item in order_items:
            if item["pricing"].get("is_subscription"):
                raise HTTPException(status_code=400, detail="One-time checkout cannot include subscriptions")
            if item["pricing"].get("is_scope_request") or item["product"].get("pricing_type") in ["external", "inquiry"]:
                raise HTTPException(status_code=400, detail="Checkout not supported for this item")

    # Calculate base subtotal
    subtotal = sum(i["pricing"]["subtotal"] for i in order_items)
    
    # Apply promo code discount with product-level eligibility check
    promo_code_data = None
    discount_amount = 0.0
    if payload.promo_code:
        promo = await db.promo_codes.find_one({"code": payload.promo_code.upper()}, {"_id": 0})
        if promo and promo.get("enabled"):
            now = datetime.now(timezone.utc).isoformat()
            is_expired = promo.get("expiry_date") and promo["expiry_date"] < now
            max_reached = promo.get("max_uses") and promo.get("usage_count", 0) >= promo["max_uses"]
            applies_to = promo.get("applies_to", "both")
            type_matches = applies_to == "both" or \
                (applies_to == "one-time" and checkout_type == "one_time") or \
                (applies_to == "subscription" and checkout_type == "subscription")
            
            # Check product-level eligibility
            product_eligible = True
            applies_to_products = promo.get("applies_to_products", "all")
            if applies_to_products == "selected":
                eligible_product_ids = promo.get("product_ids", [])
                cart_product_ids = [i["product"]["id"] for i in order_items]
                if not all(pid in eligible_product_ids for pid in cart_product_ids):
                    product_eligible = False
            
            if not is_expired and not max_reached and type_matches and product_eligible:
                if promo["discount_type"] == "percent":
                    discount_amount = round_cents(subtotal * promo["discount_value"] / 100)
                else:  # fixed
                    discount_amount = min(round_cents(promo["discount_value"]), subtotal)
                promo_code_data = promo
    
    # Calculate fee on discounted subtotal: fee = 5% * (subtotal - discount)
    discounted_subtotal = subtotal - discount_amount
    fee = round_cents(discounted_subtotal * 0.05)
    total = round_cents(discounted_subtotal + fee)
    
    # Get T&C for the product and resolve tags
    primary_product = order_items[0]["product"]
    terms_id = payload.terms_id if payload.terms_id else primary_product.get("terms_id")
    if not terms_id:
        # Get default
        default_terms = await db.terms_and_conditions.find_one({"is_default": True, "status": "active"}, {"_id": 0})
        terms_id = default_terms["id"] if default_terms else None
    
    rendered_terms_text = ""
    if terms_id:
        terms = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
        if terms:
            address = await db.addresses.find_one({"user_id": user["id"]}, {"_id": 0})
            rendered_terms_text = resolve_terms_tags(terms["content"], user, address, primary_product["name"])

    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"
    order_doc = {
        "id": order_id,
        "order_number": order_number,
        "customer_id": customer["id"],
        "type": "subscription_start" if checkout_type == "subscription" else "one_time",
        "status": "pending",
        "subtotal": round_cents(subtotal),
        "discount_amount": discount_amount,
        "promo_code": promo_code_data["code"] if promo_code_data else None,
        "fee": fee,
        "total": total,
        "currency": customer.get("currency"),
        "payment_method": "card",
        "terms_id_used": terms_id,
        "rendered_terms_text": rendered_terms_text,
        "terms_accepted_at": now_iso(),
        "partner_tag_response": payload.partner_tag_response,
        "override_code_id": None,
        "partner_tag_timestamp": now_iso(),
        "notes_json": build_checkout_notes_json(order_items, payload, user["id"], customer["id"], payment_method="card"),
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order_doc)
    
    # Create audit log
    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="created",
        actor="system",
        details={"checkout_type": checkout_type, "payment_method": "card", "total": total}
    )

    for item in order_items:
        product = item["product"]
        await db.order_items.insert_one(
            {
                "id": make_id(),
                "order_id": order_id,
                "product_id": product["id"],
                "quantity": item["quantity"],
                "metadata_json": item["inputs"],
                "unit_price": item["pricing"]["subtotal"],
                "line_total": item["pricing"]["subtotal"],
            }
        )

    host_url = payload.origin_url.rstrip("/")
    success_url = f"{host_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{host_url}/cart"

    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=f"{host_url}/api/webhook/stripe")

    metadata = {
        "order_id": order_id,
        "order_number": order_number,
        "customer_id": customer["id"],
        "checkout_type": checkout_type,
        "promo_code": promo_code_data["code"] if promo_code_data else "",
        "discount_amount": str(discount_amount),
    }

    if checkout_type == "subscription":
        product = order_items[0]["product"]
        stripe_price_id = product.get("stripe_price_id")
        # For subscriptions, use Stripe SDK directly to set mode="subscription"
        try:
            stripe_sdk.api_key = STRIPE_API_KEY
            # Build subscription_data with optional start date
            subscription_data: Dict[str, Any] = {"metadata": metadata}
            requested_start_date = payload.start_date
            if requested_start_date:
                try:
                    sd = datetime.fromisoformat(requested_start_date)
                    if sd.tzinfo is None:
                        sd = sd.replace(tzinfo=timezone.utc)
                    min_future = datetime.now(timezone.utc) + timedelta(days=3)
                    if sd > min_future:
                        subscription_data["trial_end"] = int(sd.timestamp())
                        subscription_data["trial_settings"] = {
                            "end_behavior": {"missing_payment_method": "pause"}
                        }
                        metadata["start_date"] = requested_start_date
                    elif sd > datetime.now(timezone.utc):
                        raise HTTPException(status_code=400, detail="Subscription start date must be at least 3 days in the future")
                except HTTPException:
                    raise
                except Exception:
                    pass
            session = stripe_sdk.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': stripe_price_id,
                    'quantity': order_items[0]["quantity"],
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
                customer_email=user["email"],
                subscription_data=subscription_data,
            )
            session_response = CheckoutSessionResponse(
                session_id=session.id,
                url=session.url
            )
        except stripe_sdk.error.StripeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Stripe subscription checkout error: {str(e)}"
            )
    else:
        checkout_request = CheckoutSessionRequest(
            amount=float(total),
            currency=customer.get("currency", "USD").lower(),
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )
        
        try:
            session_response: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)
        except Exception as e:
            error_msg = str(e)
            if "price" in error_msg.lower():
                raise HTTPException(status_code=400, detail=f"Stripe Price configuration error: {error_msg}")
            elif "currency" in error_msg.lower():
                raise HTTPException(status_code=400, detail=f"Currency mismatch: {error_msg}")
            else:
                raise HTTPException(status_code=500, detail=f"Checkout session creation failed: {error_msg}")

    await db.payment_transactions.insert_one(
        {
            "id": make_id(),
            "session_id": session_response.session_id,
            "payment_status": "initiated",
            "amount": float(total),
            "currency": customer.get("currency"),
            "metadata": metadata,
            "user_id": user["id"],
            "order_id": order_id,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
    )

    return {"url": session_response.url, "session_id": session_response.session_id, "order_id": order_id}


@api_router.get("/checkout/status/{session_id}")
async def checkout_status(
    session_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url="")
    status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)

    transaction = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if transaction:
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "payment_status": status.payment_status,
                    "status": status.status,
                    "updated_at": now_iso(),
                }
            },
        )

    if status.payment_status == "paid" and transaction:
        order = await db.orders.find_one({"id": transaction.get("order_id")}, {"_id": 0})
        if order and order.get("status") != "paid":
            await db.orders.update_one({"id": order["id"]}, {"$set": {"status": "paid"}})
            await db.invoices.insert_one(
                {
                    "id": make_id(),
                    "order_id": order["id"],
                    "subscription_id": None,
                    "stripe_invoice_id": None,
                    "zoho_books_invoice_id": None,
                    "amount_paid": order.get("total"),
                    "status": "paid",
                }
            )
            if order.get("type") == "subscription_start":
                existing_sub = await db.subscriptions.find_one({"order_id": order["id"]}, {"_id": 0})
                if not existing_sub:
                    items = await db.order_items.find({"order_id": order["id"]}, {"_id": 0}).to_list(5)
                    product_name = "Subscription"
                    if items:
                        product = await db.products.find_one({"id": items[0]["product_id"]}, {"_id": 0})
                        if product:
                            product_name = product["name"]
                    period_start = datetime.now(timezone.utc)
                    period_end = period_start + timedelta(days=30)
                    sub_id = make_id()
                    await db.subscriptions.insert_one(
                        {
                            "id": sub_id,
                            "order_id": order["id"],
                            "customer_id": order["customer_id"],
                            "plan_name": product_name,
                            "status": "active",
                            "stripe_subscription_id": None,
                            "current_period_start": period_start.isoformat(),
                            "current_period_end": period_end.isoformat(),
                            "cancel_at_period_end": False,
                            "canceled_at": None,
                            "amount": order.get("total"),
                            "payment_method": "card",
                            "partner_tag_response": order.get("partner_tag_response"),
                            "override_code_id": order.get("override_code_id"),
                            "partner_tag_timestamp": order.get("partner_tag_timestamp"),
                        }
                    )
                    await db.email_outbox.insert_one(
                        {
                            "id": make_id(),
                            "to": user["email"],
                            "subject": "Subscription started",
                            "body": f"Your subscription {product_name} is active.",
                            "type": "subscription_started",
                            "status": "MOCKED",
                            "created_at": now_iso(),
                        }
                    )
            customer = await db.customers.find_one({"id": order["customer_id"]}, {"_id": 0})
            if customer and not customer.get("currency_locked"):
                await db.customers.update_one(
                    {"id": customer["id"]}, {"$set": {"currency_locked": True}}
                )
            await db.email_outbox.insert_one(
                {
                    "id": make_id(),
                    "to": user["email"],
                    "subject": "Order confirmation",
                    "body": f"Your order {order['order_number']} is confirmed.",
                    "type": "order_confirmation",
                    "status": "MOCKED",
                    "created_at": now_iso(),
                }
            )

    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency,
        "metadata": status.metadata,
    }


@api_router.get("/orders")
async def get_orders(user: Dict[str, Any] = Depends(get_current_user)):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    orders = await db.orders.find({"customer_id": customer["id"]}, {"_id": 0}).to_list(500)
    order_ids = [o["id"] for o in orders]
    items = await db.order_items.find({"order_id": {"$in": order_ids}}, {"_id": 0}).to_list(1000)
    return {"orders": orders, "items": items}


@api_router.get("/orders/{order_id}")
async def get_order(order_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    items = await db.order_items.find({"order_id": order_id}, {"_id": 0}).to_list(200)
    return {"order": order, "items": items}


@api_router.get("/subscriptions")
async def get_subscriptions(user: Dict[str, Any] = Depends(get_current_user)):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    subs = await db.subscriptions.find({"customer_id": customer["id"]}, {"_id": 0}).to_list(200)
    return {"subscriptions": subs}


@api_router.post("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: str,
    payload: CancelSubscriptionBody,
    user: Dict[str, Any] = Depends(get_current_user),
):
    subscription = await db.subscriptions.find_one({"id": subscription_id}, {"_id": 0})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await db.subscriptions.update_one(
        {"id": subscription_id},
        {"$set": {"cancel_at_period_end": True, "status": "canceled_pending", "canceled_at": now_iso()}},
    )
    await db.email_outbox.insert_one(
        {
            "id": make_id(),
            "to": user["email"],
            "subject": "Cancellation requested",
            "body": "Your subscription will cancel at the end of the billing period.",
            "type": "cancellation",
            "status": "MOCKED",
            "created_at": now_iso(),
        }
    )
    return {"message": "Cancellation scheduled"}


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url="")
    body = await request.body()
    webhook_response = await stripe_checkout.handle_webhook(body, request.headers.get("Stripe-Signature"))

    existing = await db.audit_logs.find_one({"action": "stripe_event", "payload.event_id": webhook_response.event_id}, {"_id": 0})
    if existing:
        return {"status": "ignored"}

    await db.audit_logs.insert_one(
        {
            "id": make_id(),
            "actor": "stripe",
            "action": "stripe_event",
            "payload": {
                "event_id": webhook_response.event_id,
                "event_type": webhook_response.event_type,
                "session_id": webhook_response.session_id,
                "payment_status": webhook_response.payment_status,
                "metadata": webhook_response.metadata,
            },
            "created_at": now_iso(),
        }
    )

    metadata = webhook_response.metadata or {}
    order_id = metadata.get("order_id")
    email_target = None
    if order_id:
        order = await db.orders.find_one({"id": order_id}, {"_id": 0})
        if order:
            customer = await db.customers.find_one({"id": order.get("customer_id")}, {"_id": 0})
            if customer:
                user = await db.users.find_one({"id": customer["user_id"]}, {"_id": 0})
                if user:
                    email_target = user["email"]

    if webhook_response.event_type == "invoice.paid":
        # Check if this is a renewal (not first payment)
        stripe_invoice_id = webhook_response.metadata.get("stripe_invoice_id") or f"inv_{webhook_response.event_id}"
        existing_renewal = await db.orders.find_one({"stripe_invoice_id": stripe_invoice_id}, {"_id": 0})
        
        if not existing_renewal and order_id:
            # Find subscription from original order
            original_order = await db.orders.find_one({"id": order_id}, {"_id": 0})
            if original_order and original_order.get("type") == "subscription_start":
                subscription = await db.subscriptions.find_one(
                    {"order_id": order_id, "status": "active"},
                    {"_id": 0}
                )
                if subscription:
                    # Create renewal order
                    renewal_order_id = make_id()
                    renewal_order_number = f"AA-{renewal_order_id.split('-')[0].upper()}"
                    renewal_amount = subscription.get("amount", 0)
                    renewal_fee = round_cents(renewal_amount * 0.05)
                    renewal_total = round_cents(renewal_amount + renewal_fee)
                    
                    renewal_doc = {
                        "id": renewal_order_id,
                        "order_number": renewal_order_number,
                        "customer_id": original_order["customer_id"],
                        "type": "subscription_renewal",
                        "status": "paid",
                        "subtotal": renewal_amount,
                        "discount_amount": 0.0,
                        "fee": renewal_fee,
                        "total": renewal_total,
                        "currency": original_order.get("currency"),
                        "payment_method": "card",
                        "stripe_invoice_id": stripe_invoice_id,
                        "subscription_id": subscription["id"],
                        "subscription_number": subscription.get("subscription_number", ""),
                        "created_at": now_iso(),
                    }
                    await db.orders.insert_one(renewal_doc)
                    
                    await create_audit_log(
                        entity_type="order",
                        entity_id=renewal_order_id,
                        action="created_renewal",
                        actor="stripe_webhook",
                        details={"subscription_id": subscription["id"], "stripe_invoice_id": stripe_invoice_id, "amount": renewal_total}
                    )
                    
                    # Copy order items from original
                    original_items = await db.order_items.find({"order_id": order_id}, {"_id": 0}).to_list(100)
                    for item in original_items:
                        await db.order_items.insert_one({
                            "id": make_id(),
                            "order_id": renewal_order_id,
                            "product_id": item["product_id"],
                            "quantity": item["quantity"],
                            "metadata_json": item["metadata_json"],
                            "unit_price": item["unit_price"],
                            "line_total": item["line_total"],
                        })
                    
                    # Sync to Zoho (mocked)
                    await db.zoho_sync_logs.insert_one({
                        "id": make_id(),
                        "entity_type": "subscription_renewal",
                        "entity_id": renewal_order_id,
                        "status": "Sent",
                        "last_error": None,
                        "attempts": 1,
                        "created_at": now_iso(),
                        "mocked": True,
                    })
        
        if email_target:
            await db.email_outbox.insert_one(
                {
                    "id": make_id(),
                    "to": email_target,
                    "subject": "Subscription renewal paid",
                    "body": "Your subscription renewal has been paid successfully.",
                    "type": "subscription_renewal",
                    "status": "MOCKED",
                    "created_at": now_iso(),
                }
            )
    if webhook_response.event_type == "payment_intent.payment_failed" and email_target:
        await db.email_outbox.insert_one(
            {
                "id": make_id(),
                "to": email_target,
                "subject": "Payment failed",
                "body": "Your payment failed. Please update your payment method.",
                "type": "payment_failed",
                "status": "MOCKED",
                "created_at": now_iso(),
            }
        )

    
    return {"status": "ok"}


@api_router.get("/admin/customers")
async def admin_customers(admin: Dict[str, Any] = Depends(require_admin)):
    customers = await db.customers.find({}, {"_id": 0}).to_list(500)
    users = await db.users.find({}, {"_id": 0, "id": 1, "email": 1, "full_name": 1}).to_list(500)
    addresses = await db.addresses.find({}, {"_id": 0}).to_list(500)
    return {"customers": customers, "users": users, "addresses": addresses}


@api_router.put("/admin/customers/{customer_id}/payment-methods")
async def admin_update_customer_payment_methods(
    customer_id: str,
    payload: AdminCustomerPaymentUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    existing = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.customers.update_one(
        {"id": customer_id},
        {"$set": {
            "allow_bank_transfer": payload.allow_bank_transfer,
            "allow_card_payment": payload.allow_card_payment,
        }}
    )
    return {"message": "Payment methods updated"}


@api_router.get("/admin/orders")
async def admin_orders(
    page: int = 1,
    per_page: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    include_deleted: bool = False,
    product_filter: Optional[str] = None,
    order_number_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Get paginated orders list"""
    skip = (page - 1) * per_page
    
    # Build query
    query: Dict[str, Any] = {}
    if not include_deleted:
        query["deleted_at"] = {"$exists": False}
    if order_number_filter:
        query["order_number"] = {"$regex": order_number_filter, "$options": "i"}
    if status_filter:
        query["status"] = status_filter
    
    # Get orders
    sort_direction = -1 if sort_order == "desc" else 1
    orders = await db.orders.find(query, {"_id": 0}).sort(sort_by, sort_direction).skip(skip).limit(per_page).to_list(per_page)
    
    # Get order items for product filtering
    if product_filter:
        order_ids = [o["id"] for o in orders]
        items = await db.order_items.find({"order_id": {"$in": order_ids}}, {"_id": 0}).to_list(1000)
        products = await db.products.find({}, {"_id": 0}).to_list(1000)
        
        # Filter orders by product name
        product_ids_matching = [p["id"] for p in products if product_filter.lower() in p.get("name", "").lower()]
        matching_order_ids = [i["order_id"] for i in items if i["product_id"] in product_ids_matching]
        orders = [o for o in orders if o["id"] in matching_order_ids]
    
    # Get items for all orders
    all_order_ids = [o["id"] for o in orders]
    items = await db.order_items.find({"order_id": {"$in": all_order_ids}}, {"_id": 0}).to_list(1000)
    
    total_count = await db.orders.count_documents(query)
    
    return {
        "orders": orders,
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total_count,
        "total_pages": (total_count + per_page - 1) // per_page
    }


@api_router.get("/admin/subscriptions")
async def admin_subscriptions(
    sort_by: str = "created_at",
    sort_order: str = "desc",
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin)
):
    query: Dict[str, Any] = {}
    if created_from:
        query.setdefault("created_at", {})["$gte"] = created_from
    if created_to:
        query.setdefault("created_at", {})["$lte"] = created_to + "T23:59:59"
    
    sort_dir = -1 if sort_order == "desc" else 1
    subs = await db.subscriptions.find(query, {"_id": 0}).sort(sort_by, sort_dir).to_list(500)
    return {"subscriptions": subs}


@api_router.put("/admin/products/{product_id}")
async def admin_update_product(
    product_id: str,
    payload: AdminProductUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    existing = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")
    update_fields: Dict[str, Any] = {
        "name": payload.name,
        "is_active": payload.is_active,
    }
    # Optional new fields
    if payload.short_description is not None:
        update_fields["short_description"] = payload.short_description
        update_fields["tagline"] = payload.short_description
    if payload.tagline is not None and not payload.short_description:
        update_fields["tagline"] = payload.tagline
    if payload.description_long is not None:
        update_fields["description_long"] = payload.description_long
    if payload.bullets is not None:
        update_fields["bullets"] = payload.bullets
    if payload.bullets_included is not None:
        update_fields["bullets_included"] = payload.bullets_included
    if payload.bullets_excluded is not None:
        update_fields["bullets_excluded"] = payload.bullets_excluded
    if payload.bullets_needed is not None:
        update_fields["bullets_needed"] = payload.bullets_needed
    if payload.tag is not None:
        update_fields["tag"] = payload.tag
    if payload.category is not None:
        update_fields["category"] = payload.category
    if payload.outcome is not None:
        update_fields["outcome"] = payload.outcome
    if payload.automation_details is not None:
        update_fields["automation_details"] = payload.automation_details
    if payload.support_details is not None:
        update_fields["support_details"] = payload.support_details
    if payload.inclusions is not None:
        update_fields["inclusions"] = payload.inclusions
    if payload.exclusions is not None:
        update_fields["exclusions"] = payload.exclusions
    if payload.requirements is not None:
        update_fields["requirements"] = payload.requirements
    if payload.next_steps is not None:
        update_fields["next_steps"] = payload.next_steps
    if payload.faqs is not None:
        update_fields["faqs"] = payload.faqs
    if payload.terms_id is not None:
        update_fields["terms_id"] = payload.terms_id
    if payload.base_price is not None:
        update_fields["base_price"] = payload.base_price
    if payload.is_subscription is not None:
        update_fields["is_subscription"] = payload.is_subscription
    if payload.stripe_price_id is not None:
        update_fields["stripe_price_id"] = payload.stripe_price_id
    if payload.pricing_complexity is not None:
        update_fields["pricing_complexity"] = payload.pricing_complexity
    if payload.pricing_rules is not None:
        update_fields["pricing_rules"] = payload.pricing_rules
    if payload.visible_to_customers is not None:
        update_fields["visible_to_customers"] = payload.visible_to_customers
    merged = {**existing, **update_fields}
    merged["price_inputs"] = build_price_inputs(merged)
    await db.products.update_one({"id": product_id}, {"$set": merged})
    return {"message": "Product updated"}


@api_router.post("/admin/currency-override")
async def admin_currency_override(
    payload: CurrencyOverrideRequest,
    admin: Dict[str, Any] = Depends(require_admin),
):
    user = await db.users.find_one({"email": payload.customer_email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.customers.update_one(
        {"id": customer["id"]},
        {"$set": {"currency": payload.currency, "currency_locked": True}},
    )
    return {"message": "Currency overridden"}


@api_router.get("/admin/sync-logs")
async def admin_sync_logs(admin: Dict[str, Any] = Depends(require_admin)):
    logs = await db.zoho_sync_logs.find({}, {"_id": 0}).to_list(500)
    return {"logs": logs}


@api_router.post("/admin/sync-logs/{log_id}/retry")
async def admin_retry_sync(log_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    await db.zoho_sync_logs.update_one(
        {"id": log_id},
        {"$set": {"status": "Sent", "last_error": None}, "$inc": {"attempts": 1}},
    )
    return {"message": "Retry queued", "mocked": True}


# ============ PROMO CODE ENDPOINTS ============

@api_router.get("/admin/promo-codes")
async def admin_list_promo_codes(admin: Dict[str, Any] = Depends(require_admin)):
    codes = await db.promo_codes.find({}, {"_id": 0}).to_list(500)
    # Add computed status
    now = datetime.now(timezone.utc).isoformat()
    for code in codes:
        is_expired = code.get("expiry_date") and code["expiry_date"] < now
        max_reached = code.get("max_uses") and code.get("usage_count", 0) >= code["max_uses"]
        code["status"] = "Active" if code.get("enabled") and not is_expired and not max_reached else "Inactive"
    return {"promo_codes": codes}


@api_router.post("/admin/promo-codes")
async def admin_create_promo_code(payload: PromoCodeCreate, admin: Dict[str, Any] = Depends(require_admin)):
    existing = await db.promo_codes.find_one({"code": payload.code.upper()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Promo code already exists")
    
    promo = {
        "id": make_id(),
        "code": payload.code.upper(),
        "discount_type": payload.discount_type,
        "discount_value": payload.discount_value,
        "applies_to": payload.applies_to,
        "applies_to_products": payload.applies_to_products,
        "product_ids": payload.product_ids if payload.applies_to_products == "selected" else [],
        "expiry_date": payload.expiry_date,
        "max_uses": payload.max_uses,
        "one_time_code": payload.one_time_code,
        "usage_count": 0,
        "enabled": payload.enabled,
        "created_at": now_iso(),
    }
    await db.promo_codes.insert_one(promo)
    return {"message": "Promo code created", "promo_code": {k: v for k, v in promo.items() if k != "_id"}}


@api_router.put("/admin/promo-codes/{code_id}")
async def admin_update_promo_code(code_id: str, payload: PromoCodeUpdate, admin: Dict[str, Any] = Depends(require_admin)):
    existing = await db.promo_codes.find_one({"id": code_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Promo code not found")
    
    update_fields = {}
    if payload.discount_type is not None:
        update_fields["discount_type"] = payload.discount_type
    if payload.discount_value is not None:
        update_fields["discount_value"] = payload.discount_value
    if payload.applies_to is not None:
        update_fields["applies_to"] = payload.applies_to
    if payload.applies_to_products is not None:
        update_fields["applies_to_products"] = payload.applies_to_products
    if payload.product_ids is not None:
        update_fields["product_ids"] = payload.product_ids
    if payload.expiry_date is not None:
        update_fields["expiry_date"] = payload.expiry_date
    if payload.max_uses is not None:
        update_fields["max_uses"] = payload.max_uses
    if payload.one_time_code is not None:
        update_fields["one_time_code"] = payload.one_time_code
    if payload.enabled is not None:
        update_fields["enabled"] = payload.enabled
    
    if update_fields:
        await db.promo_codes.update_one({"id": code_id}, {"$set": update_fields})
    return {"message": "Promo code updated"}


@api_router.delete("/admin/promo-codes/{code_id}")
async def admin_delete_promo_code(code_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    result = await db.promo_codes.delete_one({"id": code_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Promo code not found")
    return {"message": "Promo code deleted"}


@api_router.post("/promo-codes/validate")
async def validate_promo_code(payload: ApplyPromoRequest, user: Dict[str, Any] = Depends(get_current_user)):
    code = await db.promo_codes.find_one({"code": payload.code.upper()}, {"_id": 0})
    if not code:
        raise HTTPException(status_code=404, detail="Invalid promo code")
    
    # Check if enabled
    if not code.get("enabled"):
        raise HTTPException(status_code=400, detail="Promo code is not active")
    
    # Check expiry
    now = datetime.now(timezone.utc).isoformat()
    if code.get("expiry_date") and code["expiry_date"] < now:
        raise HTTPException(status_code=400, detail="Promo code has expired")
    
    # Check max uses
    if code.get("max_uses") and code.get("usage_count", 0) >= code["max_uses"]:
        raise HTTPException(status_code=400, detail="Promo code usage limit reached")
    
    # Check applies_to
    checkout_type = payload.checkout_type
    applies_to = code.get("applies_to", "both")
    if applies_to == "one-time" and checkout_type == "subscription":
        raise HTTPException(status_code=400, detail="Promo code only valid for one-time purchases")
    if applies_to == "subscription" and checkout_type == "one_time":
        raise HTTPException(status_code=400, detail="Promo code only valid for subscriptions")
    
    # Check one-time code usage per customer
    if code.get("one_time_code"):
        customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
        if customer:
            used = await db.orders.find_one({
                "customer_id": customer["id"],
                "promo_code": code["code"]
            }, {"_id": 0})
            if used:
                raise HTTPException(status_code=400, detail="You have already used this promo code")
    
    return {
        "valid": True,
        "code": code["code"],
        "discount_type": code["discount_type"],
        "discount_value": code["discount_value"],
    }


# ============ SCOPE REQUEST WITH FORM ============

@api_router.post("/orders/scope-request-form")
async def create_scope_request_with_form(
    payload: ScopeRequestWithForm,
    user: Dict[str, Any] = Depends(get_current_user),
):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Create order/deal
    order_id = make_id()
    order_number = f"AA-{order_id[:8].upper()}"
    
    order_items = []
    for item in payload.items:
        product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if not product:
            continue
        order_items.append({
            "id": make_id(),
            "order_id": order_id,
            "product_id": item.product_id,
            "quantity": item.quantity,
            "inputs": item.inputs,
            "unit_price": 0,
            "subtotal": 0,
        })
    
    order = {
        "id": order_id,
        "order_number": order_number,
        "customer_id": customer["id"],
        "type": "scope_request",
        "status": "scope_pending",
        "subtotal": 0,
        "fee": 0,
        "total": 0,
        "currency": customer.get("currency", "USD"),
        "payment_method": None,
        "scope_form_data": {
            "project_summary": payload.form_data.project_summary,
            "desired_outcomes": payload.form_data.desired_outcomes,
            "apps_involved": payload.form_data.apps_involved,
            "timeline_urgency": payload.form_data.timeline_urgency,
            "budget_range": payload.form_data.budget_range or "",
            "additional_notes": payload.form_data.additional_notes or "",
        },
        "notes_json": _deep_merge(
            {
                "product_intake": {item.product_id: dict(item.inputs) for item in payload.items},
                "payment": {"method": "scope_request_form"},
                "system_metadata": {
                    "user_id": user["id"],
                    "customer_id": customer["id"],
                    "timestamp": now_iso(),
                },
            },
            {
                "scope_form": {
                    "project_summary": payload.form_data.project_summary,
                    "desired_outcomes": payload.form_data.desired_outcomes,
                    "apps_involved": payload.form_data.apps_involved,
                    "timeline_urgency": payload.form_data.timeline_urgency,
                    "budget_range": payload.form_data.budget_range or "",
                    "additional_notes": payload.form_data.additional_notes or "",
                }
            },
        ),
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order)
    
    for item in order_items:
        await db.order_items.insert_one(item)
    
    # Create Zoho sync log (mocked email)
    product_names = []
    for item in payload.items:
        product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if product:
            product_names.append(product.get("name", item.product_id))
    
    email_body = f"""
New Scope Request from {user.get('full_name', 'Unknown')}

Customer: {user.get('full_name', 'Unknown')}
Email: {user.get('email', 'Unknown')}
Company: {customer.get('company_name', 'Unknown')}

Products: {', '.join(product_names)}

PROJECT DETAILS:
----------------
Project Summary: {payload.form_data.project_summary}

Desired Outcomes: {payload.form_data.desired_outcomes}

Apps Involved: {payload.form_data.apps_involved}

Timeline/Urgency: {payload.form_data.timeline_urgency}

Budget Range: {payload.form_data.budget_range or 'Not specified'}

Additional Notes: {payload.form_data.additional_notes or 'None'}

Order/Deal ID: {order_number}
"""
    
    await db.email_outbox.insert_one({
        "id": make_id(),
        "to": "rushabh@automateaccounts.com",
        "subject": f"New Scope Request: {order_number} from {user.get('full_name', 'Customer')}",
        "body": email_body,
        "type": "scope_request",
        "status": "MOCKED",
        "created_at": now_iso(),
    })
    
    await db.zoho_sync_logs.insert_one({
        "id": make_id(),
        "entity_type": "scope_request",
        "entity_id": order_id,
        "action": "create_deal",
        "status": "Sent",
        "last_error": None,
        "attempts": 1,
        "created_at": now_iso(),
        "mocked": True,
    })
    
    return {
        "message": "Scope request submitted",
        "order_id": order_id,
        "order_number": order_number,
        "email_sent_to": "rushabh@automateaccounts.com",
        "email_delivery": "MOCKED",
    }


# ============ TERMS & CONDITIONS ENDPOINTS ============

@api_router.get("/terms")
async def get_all_terms():
    terms = await db.terms_and_conditions.find({}, {"_id": 0}).to_list(100)
    return {"terms": terms}


@api_router.get("/terms/default")
async def get_default_terms():
    default = await db.terms_and_conditions.find_one({"is_default": True, "status": "active"}, {"_id": 0})
    if not default:
        raise HTTPException(status_code=404, detail="No default terms found")
    return default


@api_router.get("/terms/for-product/{product_id}")
async def get_terms_for_product(product_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    # Check if product has specific T&C assigned
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    terms_id = product.get("terms_id")
    if terms_id:
        terms = await db.terms_and_conditions.find_one({"id": terms_id, "status": "active"}, {"_id": 0})
    else:
        # Use default T&C
        terms = await db.terms_and_conditions.find_one({"is_default": True, "status": "active"}, {"_id": 0})
    
    if not terms:
        raise HTTPException(status_code=404, detail="No terms found for this product")
    
    # Get user and address for tag resolution
    address = await db.addresses.find_one({"user_id": user["id"]}, {"_id": 0})
    resolved_content = resolve_terms_tags(terms["content"], user, address, product["name"])
    
    return {
        "id": terms["id"],
        "title": terms["title"],
        "content": resolved_content,
        "raw_content": terms["content"],
    }


@api_router.post("/admin/terms")
async def create_terms(payload: TermsCreate, admin: Dict[str, Any] = Depends(require_admin)):
    # If setting as default, unset other defaults
    if payload.is_default:
        await db.terms_and_conditions.update_many(
            {"is_default": True},
            {"$set": {"is_default": False}}
        )
    
    terms_id = make_id()
    terms_doc = {
        "id": terms_id,
        "title": payload.title,
        "content": payload.content,
        "is_default": payload.is_default,
        "status": payload.status,
        "created_at": now_iso(),
    }
    await db.terms_and_conditions.insert_one(terms_doc)
    return {"message": "Terms created", "id": terms_id}


@api_router.put("/admin/terms/{terms_id}")
async def update_terms(
    terms_id: str,
    payload: TermsUpdate,
    admin: Dict[str, Any] = Depends(require_admin)
):
    existing = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Terms not found")
    
    update_data = {}
    if payload.title is not None:
        update_data["title"] = payload.title
    if payload.content is not None:
        update_data["content"] = payload.content
    if payload.status is not None:
        update_data["status"] = payload.status
    
    if update_data:
        await db.terms_and_conditions.update_one({"id": terms_id}, {"$set": update_data})
    
    return {"message": "Terms updated"}


@api_router.delete("/admin/terms/{terms_id}")
async def delete_terms(terms_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    existing = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Terms not found")
    
    if existing.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot delete default terms")
    
    await db.terms_and_conditions.delete_one({"id": terms_id})
    # Remove from products
    await db.products.update_many({"terms_id": terms_id}, {"$unset": {"terms_id": ""}})
    return {"message": "Terms deleted"}


@api_router.put("/admin/products/{product_id}/terms")
async def assign_terms_to_product(
    product_id: str,
    terms_id: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin)
):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if terms_id:
        terms = await db.terms_and_conditions.find_one({"id": terms_id}, {"_id": 0})
        if not terms:
            raise HTTPException(status_code=404, detail="Terms not found")
        await db.products.update_one({"id": product_id}, {"$set": {"terms_id": terms_id}})
    else:
        # Remove assignment (will use default)
        await db.products.update_one({"id": product_id}, {"$unset": {"terms_id": ""}})
    
    return {"message": "Terms assignment updated"}


# ============ MANUAL/OFFLINE ORDER ENDPOINTS ============

@api_router.post("/gocardless/complete-redirect")
async def complete_gocardless_redirect(
    payload: CompleteGoCardlessRedirect,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Complete GoCardless redirect flow and update order/subscription status"""
    try:
        redirect_flow = complete_redirect_flow(payload.redirect_flow_id, session_token=payload.session_token or "")
        
        if not redirect_flow:
            # Log the failure
            await create_audit_log(
                entity_type="system",
                entity_id=payload.order_id or payload.subscription_id or "unknown",
                action="gocardless_redirect_failed",
                actor="system",
                details={"error": "Failed to complete redirect flow", "redirect_flow_id": payload.redirect_flow_id}
            )
            raise HTTPException(
                status_code=400, 
                detail="Failed to complete the Direct Debit setup. The payment link may have expired or been used already. Please return to checkout and try again."
            )
        
        mandate_id = redirect_flow.get("links", {}).get("mandate")
        
        if not mandate_id:
            await create_audit_log(
                entity_type="system",
                entity_id=payload.order_id or payload.subscription_id or "unknown",
                action="gocardless_mandate_missing",
                actor="system",
                details={"error": "No mandate ID in redirect flow response", "redirect_flow_id": payload.redirect_flow_id}
            )
            raise HTTPException(status_code=400, detail="No mandate ID found in GoCardless response")
        
        # Create payment immediately after mandate setup
        payment_id = None
        
        if payload.order_id:
            # Get order details and create payment
            order = await db.orders.find_one({"id": payload.order_id}, {"_id": 0})
            if order and mandate_id:
                # Create GoCardless payment
                payment = create_payment(
                    amount=order["total"],
                    currency=order.get("currency", "USD"),
                    mandate_id=mandate_id,
                    description=f"Payment for Order {order['order_number']}",
                    metadata={"order_id": order["id"], "order_number": order["order_number"]}
                )
                
                if payment:
                    payment_id = payment["id"]
                    # Payment created successfully - update order to pending_payment
                    await db.orders.update_one(
                        {"id": payload.order_id},
                        {"$set": {
                            "status": "pending_payment",
                            "gocardless_mandate_id": mandate_id,
                            "gocardless_payment_id": payment_id,
                            "updated_at": now_iso(),
                        }}
                    )
                    
                    await create_audit_log(
                        entity_type="order",
                        entity_id=payload.order_id,
                        action="payment_initiated",
                        actor="customer",
                        details={"mandate_id": mandate_id, "payment_id": payment_id, "amount": order["total"]}
                    )
                    
                    # Check payment status immediately (in sandbox it might be instant)
                    import time
                    time.sleep(2)  # Wait 2 seconds for payment to process
                    payment_status = get_payment_status(payment_id)
                    if payment_status:
                        status = payment_status.get("status")
                        await create_audit_log(
                            entity_type="order",
                            entity_id=payload.order_id,
                            action="payment_status_checked",
                            actor="system",
                            details={"payment_status": status, "payment_id": payment_id}
                        )
                        
                        if status in ["confirmed", "paid_out", "submitted"]:
                            # Payment is confirmed
                            await db.orders.update_one(
                                {"id": payload.order_id},
                                {"$set": {"status": "paid", "payment_date": now_iso(), "updated_at": now_iso()}}
                            )
                            await create_audit_log(
                                entity_type="order",
                                entity_id=payload.order_id,
                                action="payment_confirmed",
                                actor="gocardless",
                                details={"payment_status": status, "payment_id": payment_id}
                            )
                else:
                    # Payment creation failed
                    await create_audit_log(
                        entity_type="order",
                        entity_id=payload.order_id,
                        action="payment_creation_failed",
                        actor="system",
                        details={"mandate_id": mandate_id, "error": "Payment creation returned None"}
                    )
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to create payment with GoCardless. Please contact support with your order number."
                    )
        
        if payload.subscription_id:
            # Update subscription status
            subscription = await db.subscriptions.find_one({"id": payload.subscription_id}, {"_id": 0})
            if subscription and mandate_id:
                # Determine charge_date from subscription's start_date
                charge_date = None
                sub_start = subscription.get("start_date")
                if sub_start:
                    try:
                        sd = datetime.fromisoformat(sub_start.replace("Z", "+00:00"))
                        if sd > datetime.now(timezone.utc):
                            charge_date = sd.strftime("%Y-%m-%d")
                    except Exception:
                        pass
                # Create first payment for subscription
                payment = create_payment(
                    amount=subscription["amount"],
                    currency="USD",
                    mandate_id=mandate_id,
                    description=f"Subscription Payment - {subscription['plan_name']}",
                    metadata={"subscription_id": subscription["id"]},
                    charge_date=charge_date
                )
                
                if payment:
                    payment_id = payment["id"]
                    await db.subscriptions.update_one(
                        {"id": payload.subscription_id},
                        {"$set": {
                            "status": "pending_payment",
                            "gocardless_mandate_id": mandate_id,
                            "gocardless_payment_id": payment_id,
                            "updated_at": now_iso(),
                        }}
                    )
                    
                    await create_audit_log(
                        entity_type="subscription",
                        entity_id=payload.subscription_id,
                        action="payment_initiated",
                        actor="customer",
                        details={"mandate_id": mandate_id, "payment_id": payment_id}
                    )
                    
                    # Check if payment is already confirmed
                    import time
                    time.sleep(2)
                    payment_status = get_payment_status(payment_id)
                    if payment_status and payment_status.get("status") in ["confirmed", "paid_out", "submitted"]:
                        await db.subscriptions.update_one(
                            {"id": payload.subscription_id},
                            {"$set": {"status": "active", "updated_at": now_iso()}}
                        )
                        await create_audit_log(
                            entity_type="subscription",
                            entity_id=payload.subscription_id,
                            action="payment_confirmed",
                            actor="gocardless",
                            details={"payment_status": payment_status.get("status")}
                        )
        
        return {
            "message": "Direct Debit setup completed. Payment initiated.",
            "mandate_id": mandate_id,
            "payment_id": payment_id,
            "payment_created": payment_id is not None,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        # Log unexpected errors
        await create_audit_log(
            entity_type="system",
            entity_id=payload.order_id or payload.subscription_id or "unknown",
            action="gocardless_callback_error",
            actor="system",
            details={"error": str(e), "redirect_flow_id": payload.redirect_flow_id}
        )
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred processing your payment setup: {str(e)}"
        )
    
    if not redirect_flow:
        raise HTTPException(status_code=400, detail="Failed to complete GoCardless redirect flow")
    
    mandate_id = redirect_flow.get("links", {}).get("mandate")
    
    # Create payment immediately after mandate setup
    payment_id = None
    
    if payload.order_id:
        # Get order details and create payment
        order = await db.orders.find_one({"id": payload.order_id}, {"_id": 0})
        if order and mandate_id:
            # Create GoCardless payment
            payment = create_payment(
                amount=order["total"],
                currency=order.get("currency", "USD"),
                mandate_id=mandate_id,
                description=f"Payment for Order {order['order_number']}",
                metadata={"order_id": order["id"], "order_number": order["order_number"]}
            )
            
            if payment:
                payment_id = payment["id"]
                # Payment created successfully - update order to pending_payment
                await db.orders.update_one(
                    {"id": payload.order_id},
                    {"$set": {
                        "status": "pending_payment",
                        "gocardless_mandate_id": mandate_id,
                        "gocardless_payment_id": payment_id,
                        "updated_at": now_iso(),
                    }}
                )
                
                await create_audit_log(
                    entity_type="order",
                    entity_id=payload.order_id,
                    action="payment_initiated",
                    actor="customer",
                    details={"mandate_id": mandate_id, "payment_id": payment_id}
                )
                
                # Check payment status immediately (in sandbox it might be instant)
                payment_status = get_payment_status(payment_id)
                if payment_status and payment_status.get("status") in ["confirmed", "paid_out"]:
                    # Payment is already confirmed
                    await db.orders.update_one(
                        {"id": payload.order_id},
                        {"$set": {"status": "paid", "updated_at": now_iso()}}
                    )
                    await create_audit_log(
                        entity_type="order",
                        entity_id=payload.order_id,
                        action="payment_confirmed",
                        actor="gocardless",
                        details={"payment_status": payment_status.get("status")}
                    )
    
    if payload.subscription_id:
        # Update subscription status
        subscription = await db.subscriptions.find_one({"id": payload.subscription_id}, {"_id": 0})
        if subscription and mandate_id:
            # Create first payment for subscription
            payment = create_payment(
                amount=subscription["amount"],
                currency="USD",
                mandate_id=mandate_id,
                description=f"Subscription Payment - {subscription['plan_name']}",
                metadata={"subscription_id": subscription["id"]}
            )
            
            if payment:
                payment_id = payment["id"]
                await db.subscriptions.update_one(
                    {"id": payload.subscription_id},
                    {"$set": {
                        "status": "pending_payment",
                        "gocardless_mandate_id": mandate_id,
                        "gocardless_payment_id": payment_id,
                        "updated_at": now_iso(),
                    }}
                )
                
                await create_audit_log(
                    entity_type="subscription",
                    entity_id=payload.subscription_id,
                    action="payment_initiated",
                    actor="customer",
                    details={"mandate_id": mandate_id, "payment_id": payment_id}
                )
                
                # Check if payment is already confirmed
                payment_status = get_payment_status(payment_id)
                if payment_status and payment_status.get("status") in ["confirmed", "paid_out"]:
                    await db.subscriptions.update_one(
                        {"id": payload.subscription_id},
                        {"$set": {"status": "active", "updated_at": now_iso()}}
                    )
                    await create_audit_log(
                        entity_type="subscription",
                        entity_id=payload.subscription_id,
                        action="payment_confirmed",
                        actor="gocardless",
                        details={"payment_status": payment_status.get("status")}
                    )
    
    return {
        "message": "Direct Debit setup completed. Payment will be processed.",
        "mandate_id": mandate_id,
    }


@api_router.post("/admin/orders/manual")
async def create_manual_order(
    payload: ManualOrderCreate,
    admin: Dict[str, Any] = Depends(require_admin)
):
    # Find customer by email
    user = await db.users.find_one({"email": payload.customer_email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer record not found")
    
    # Verify product exists
    product = await db.products.find_one({"id": payload.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Create order
    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"
    total = round_cents(payload.subtotal - payload.discount + payload.fee)
    
    order_doc = {
        "id": order_id,
        "order_number": order_number,
        "customer_id": customer["id"],
        "type": "manual",
        "status": payload.status,
        "subtotal": round_cents(payload.subtotal),
        "discount_amount": round_cents(payload.discount),
        "fee": round_cents(payload.fee),
        "total": total,
        "currency": customer.get("currency", "USD"),
        "payment_method": "offline",
        "internal_note": payload.internal_note or "",
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
    }
    await db.orders.insert_one(order_doc)
    
    # Create order items
    await db.order_items.insert_one({
        "id": make_id(),
        "order_id": order_id,
        "product_id": payload.product_id,
        "quantity": payload.quantity,
        "metadata_json": payload.inputs,
        "unit_price": round_cents(payload.subtotal / payload.quantity),
        "line_total": round_cents(payload.subtotal),
    })
    
    # Create Zoho sync logs (mocked)
    await db.zoho_sync_logs.insert_one({
        "id": make_id(),
        "entity_type": "manual_order",
        "entity_id": order_id,
        "status": "Sent" if payload.status == "paid" else "Pending",
        "last_error": None,
        "attempts": 1,
        "created_at": now_iso(),
        "mocked": True,
    })
    
    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="created_manual",
        actor=f"admin:{admin['id']}",
        details={"status": payload.status, "total": total, "payment_method": "offline"}
    )
    
    return {
        "message": "Manual order created",
        "order_id": order_id,
        "order_number": order_number,
    }


@api_router.post("/admin/subscriptions/manual")
async def create_manual_subscription(
    payload: ManualSubscriptionCreate,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Create a manual subscription (no Stripe/GoCardless)"""
    user = await db.users.find_one({"email": payload.customer_email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer record not found")
    
    product = await db.products.find_one({"id": payload.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    sub_id = make_id()
    sub_number = f"SUB-{sub_id.split('-')[0].upper()}"
    
    # Parse renewal date
    from datetime import datetime
    try:
        renewal_date_dt = datetime.fromisoformat(payload.renewal_date.replace('Z', '+00:00'))
    except Exception:
        renewal_date_dt = datetime.now(timezone.utc) + timedelta(days=30)
    
    sub_doc = {
        "id": sub_id,
        "subscription_number": sub_number,
        "customer_id": customer["id"],
        "plan_name": product["name"],
        "product_id": product["id"],
        "status": payload.status,
        "payment_method": "offline",
        "amount": payload.amount,
        "renewal_date": renewal_date_dt.isoformat(),
        "start_date": payload.start_date or now_iso(),
        "cancel_at_period_end": False,
        "canceled_at": None,
        "internal_note": payload.internal_note or "",
        "notes": [],
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
        "is_manual": True,
        "contract_end_date": (datetime.fromisoformat((payload.start_date or now_iso()).replace("Z", "+00:00")).replace(tzinfo=timezone.utc) + timedelta(days=365)).isoformat(),
    }
    await db.subscriptions.insert_one(sub_doc)
    
    await create_audit_log(
        entity_type="subscription",
        entity_id=sub_id,
        action="created_manual",
        actor=f"admin:{admin['id']}",
        details={"status": payload.status, "amount": payload.amount, "renewal_date": renewal_date_dt.isoformat()}
    )
    
    return {
        "message": "Manual subscription created",
        "subscription_id": sub_id,
        "subscription_number": sub_number,
    }


@api_router.post("/subscriptions/{subscription_id}/renew-now")
async def renew_subscription_now(
    subscription_id: str,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Create a renewal order for a manual subscription"""
    subscription = await db.subscriptions.find_one({"id": subscription_id}, {"_id": 0})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Create renewal order
    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"
    
    order_doc = {
        "id": order_id,
        "order_number": order_number,
        "customer_id": subscription["customer_id"],
        "subscription_id": subscription_id,
        "subscription_number": subscription.get("subscription_number", ""),
        "type": "subscription_renewal",
        "status": "unpaid",
        "subtotal": subscription["amount"],
        "discount_amount": 0.0,
        "fee": 0.0,
        "total": subscription["amount"],
        "currency": "USD",
        "payment_method": subscription.get("payment_method", "manual"),
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
    }
    await db.orders.insert_one(order_doc)
    
    # Update subscription renewal date
    from datetime import datetime
    current_renewal = datetime.fromisoformat(subscription["renewal_date"].replace('Z', '+00:00'))
    next_renewal = current_renewal + timedelta(days=30)
    
    await db.subscriptions.update_one(
        {"id": subscription_id},
        {"$set": {"renewal_date": next_renewal.isoformat(), "updated_at": now_iso()}}
    )
    
    await create_audit_log(
        entity_type="subscription",
        entity_id=subscription_id,
        action="renewed",
        actor=f"admin:{admin['id']}",
        details={"order_id": order_id, "order_number": order_number, "amount": subscription["amount"]}
    )
    
    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="created_renewal",
        actor=f"admin:{admin['id']}",
        details={"subscription_id": subscription_id, "status": "unpaid"}
    )
    
    return {
        "message": "Renewal order created",
        "order_id": order_id,
        "order_number": order_number,
        "next_renewal_date": next_renewal.isoformat(),
    }


@api_router.put("/admin/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: str,
    payload: SubscriptionUpdate,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Update subscription renewal date or amount"""
    subscription = await db.subscriptions.find_one({"id": subscription_id}, {"_id": 0})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    update_fields = {}
    changes = {}
    
    if payload.renewal_date is not None:
        update_fields["renewal_date"] = payload.renewal_date
        changes["renewal_date"] = {"old": subscription.get("renewal_date"), "new": payload.renewal_date}
    
    if payload.start_date is not None:
        update_fields["start_date"] = payload.start_date
        changes["start_date"] = {"old": subscription.get("start_date"), "new": payload.start_date}
    
    if payload.contract_end_date is not None:
        update_fields["contract_end_date"] = payload.contract_end_date
        changes["contract_end_date"] = {"old": subscription.get("contract_end_date"), "new": payload.contract_end_date}
    
    if payload.amount is not None:
        update_fields["amount"] = payload.amount
        changes["amount"] = {"old": subscription.get("amount"), "new": payload.amount}
    
    if payload.status is not None:
        if payload.status not in ALLOWED_SUBSCRIPTION_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status '{payload.status}'. Allowed: {', '.join(ALLOWED_SUBSCRIPTION_STATUSES)}")
        update_fields["status"] = payload.status
        changes["status"] = {"old": subscription.get("status"), "new": payload.status}
    
    if payload.plan_name is not None:
        update_fields["plan_name"] = payload.plan_name
        changes["plan_name"] = {"old": subscription.get("plan_name"), "new": payload.plan_name}
    
    if payload.customer_id is not None:
        update_fields["customer_id"] = payload.customer_id
        changes["customer_id"] = {"old": subscription.get("customer_id"), "new": payload.customer_id}
    
    if payload.payment_method is not None:
        update_fields["payment_method"] = payload.payment_method
        changes["payment_method"] = {"old": subscription.get("payment_method"), "new": payload.payment_method}
    
    if update_fields:
        update_fields["updated_at"] = now_iso()
        await db.subscriptions.update_one({"id": subscription_id}, {"$set": update_fields})
        
        await create_audit_log(
            entity_type="subscription",
            entity_id=subscription_id,
            action="updated",
            actor=f"admin:{admin['id']}",
            details={"changes": changes}
        )
    
    if payload.new_note:
        note_entry = {
            "text": payload.new_note,
            "timestamp": now_iso(),
            "actor": f"admin:{admin['id']}"
        }
        await db.subscriptions.update_one({"id": subscription_id}, {"$push": {"notes": note_entry}})
        await create_audit_log(
            entity_type="subscription",
            entity_id=subscription_id,
            action="note_added",
            actor=f"admin:{admin['id']}",
            details={"note": payload.new_note}
        )
    
    return {"message": "Subscription updated"}


@api_router.post("/admin/subscriptions/{subscription_id}/cancel")
async def admin_cancel_subscription(
    subscription_id: str,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Admin: Cancel a subscription with audit log"""
    subscription = await db.subscriptions.find_one({"id": subscription_id}, {"_id": 0})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    old_status = subscription.get("status")
    cancelled_at = now_iso()
    
    await db.subscriptions.update_one(
        {"id": subscription_id},
        {"$set": {
            "cancel_at_period_end": True,
            "status": "canceled_pending",
            "canceled_at": cancelled_at,
            "updated_at": cancelled_at
        }}
    )
    
    await create_audit_log(
        entity_type="subscription",
        entity_id=subscription_id,
        action="cancelled",
        actor=f"admin:{admin['id']}",
        details={
            "changes": {
                "status": {"old": old_status, "new": "canceled_pending"}
            },
            "cancelled_at": cancelled_at,
            "note": "Cancelled by admin"
        }
    )
    
    return {"message": "Subscription cancellation scheduled", "cancelled_at": cancelled_at}


# ============ ADMIN: USER MANAGEMENT (SUPER ADMIN ONLY) ============

@api_router.get("/admin/users")
async def admin_list_users(admin: Dict[str, Any] = Depends(require_super_admin)):
    """Super admin only: List all admin/super_admin users"""
    users = await db.users.find(
        {"role": {"$in": ["admin", "super_admin"]}},
        {"_id": 0, "password_hash": 0}
    ).to_list(500)
    return {"users": users}


@api_router.post("/admin/users")
async def admin_create_admin_user(
    payload: AdminCreateUserRequest,
    admin: Dict[str, Any] = Depends(require_super_admin)
):
    """Super admin only: Create a new admin or super_admin user"""
    if payload.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'super_admin'")
    
    existing = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = make_id()
    hashed = pwd_context.hash(payload.password)
    user_doc = {
        "id": user_id,
        "email": payload.email.lower(),
        "password_hash": hashed,
        "full_name": payload.full_name,
        "company_name": payload.company_name or "",
        "job_title": payload.job_title or "",
        "phone": payload.phone or "",
        "is_admin": True,
        "is_verified": True,
        "role": payload.role,
        "must_change_password": True,
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
    }
    await db.users.insert_one(user_doc)
    
    await create_audit_log(
        entity_type="user",
        entity_id=user_id,
        action="admin_user_created",
        actor=f"admin:{admin['id']}",
        details={"email": payload.email, "role": payload.role, "full_name": payload.full_name}
    )
    
    return {"message": "Admin user created", "user_id": user_id, "email": payload.email}


# ============ ADMIN: CREATE CUSTOMER ============

@api_router.post("/admin/customers/create")
async def admin_create_customer(
    payload: AdminCreateCustomerRequest,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Admin: Create a new customer with user account"""
    existing = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = make_id()
    customer_id = make_id()
    hashed = pwd_context.hash(payload.password)
    currency = currency_for_country(payload.country)
    
    user_doc = {
        "id": user_id,
        "email": payload.email.lower(),
        "password_hash": hashed,
        "full_name": payload.full_name,
        "company_name": payload.company_name or "",
        "job_title": payload.job_title or "",
        "phone": payload.phone or "",
        "is_admin": False,
        "is_verified": payload.mark_verified,
        "role": "customer",
        "must_change_password": True,
        "verification_code": None,
        "created_at": now_iso(),
        "created_by_admin": admin["id"],
    }
    await db.users.insert_one(user_doc)
    
    customer_doc = {
        "id": customer_id,
        "user_id": user_id,
        "company_name": payload.company_name or "",
        "phone": payload.phone or "",
        "currency": currency,
        "currency_locked": False,
        "allow_bank_transfer": True,
        "allow_card_payment": False,
        "stripe_customer_id": None,
        "zoho_crm_contact_id": None,
        "zoho_books_contact_id": None,
        "created_at": now_iso(),
    }
    await db.customers.insert_one(customer_doc)
    
    await db.addresses.insert_one({
        "id": make_id(),
        "customer_id": customer_id,
        "line1": payload.line1,
        "line2": payload.line2 or "",
        "city": payload.city,
        "region": payload.region,
        "postal": payload.postal,
        "country": payload.country,
    })
    
    await create_audit_log(
        entity_type="customer",
        entity_id=customer_id,
        action="customer_created_by_admin",
        actor=f"admin:{admin['id']}",
        details={"email": payload.email, "full_name": payload.full_name, "verified": payload.mark_verified}
    )
    
    return {"message": "Customer created", "customer_id": customer_id, "user_id": user_id}


# ============ ADMIN: TOGGLE ACTIVE STATUS ============

@api_router.patch("/admin/users/{user_id}/active")
async def admin_set_user_active(
    user_id: str,
    active: bool,
    admin: Dict[str, Any] = Depends(require_super_admin)
):
    """Super admin only: mark a user active or inactive"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    old_state = user.get("is_active", True)
    await db.users.update_one({"id": user_id}, {"$set": {"is_active": active, "updated_at": now_iso()}})
    
    await create_audit_log(
        entity_type="user",
        entity_id=user_id,
        action="set_active" if active else "set_inactive",
        actor=f"admin:{admin['id']}",
        details={"is_active": {"old": old_state, "new": active}, "email": user.get("email")}
    )
    return {"message": f"User {'activated' if active else 'deactivated'}", "is_active": active}


@api_router.patch("/admin/customers/{customer_id}/active")
async def admin_set_customer_active(
    customer_id: str,
    active: bool,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Admin: mark a customer (and their user account) active or inactive"""
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Prevent admin from deactivating their own account via customer record
    linked_user = await db.users.find_one({"id": customer.get("user_id")}, {"_id": 0})
    if linked_user and linked_user["id"] == admin["id"] and not active:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    
    # Also update the linked user
    user = linked_user
    old_state = user.get("is_active", True) if user else True
    
    await db.customers.update_one({"id": customer_id}, {"$set": {"is_active": active, "updated_at": now_iso()}})
    if user:
        await db.users.update_one({"id": user["id"]}, {"$set": {"is_active": active, "updated_at": now_iso()}})
    
    await create_audit_log(
        entity_type="customer",
        entity_id=customer_id,
        action="set_active" if active else "set_inactive",
        actor=f"admin:{admin['id']}",
        details={"is_active": {"old": old_state, "new": active}, "also_updated_user": bool(user)}
    )
    return {"message": f"Customer {'activated' if active else 'deactivated'}", "is_active": active}


# ============ ADMIN: CSV EXPORTS ============

def _make_csv_response(rows: List[Dict[str, Any]], filename: str) -> StreamingResponse:
    """Helper: convert list of dicts to CSV StreamingResponse"""
    if not rows:
        output = io.StringIO()
        output.write("No data\n")
        output.seek(0)
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    
    # Collect all keys across all rows for complete columns
    all_keys: List[str] = []
    seen: set = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                all_keys.append(k)
                seen.add(k)
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=all_keys, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: str(row.get(k, "")) for k in all_keys})
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@api_router.get("/admin/export/orders")
async def export_orders_csv(
    sort_by: str = "created_at",
    sort_order: str = "desc",
    include_deleted: bool = False,
    product_filter: Optional[str] = None,
    order_number_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    email_filter: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Export all filtered orders as CSV with all DB fields"""
    query: Dict[str, Any] = {}
    if not include_deleted:
        query["deleted_at"] = {"$exists": False}
    if order_number_filter:
        query["order_number"] = {"$regex": order_number_filter, "$options": "i"}
    if status_filter:
        query["status"] = status_filter
    
    sort_dir = -1 if sort_order == "desc" else 1
    orders = await db.orders.find(query, {"_id": 0}).sort(sort_by, sort_dir).to_list(10000)
    
    # Enrich with customer email
    if email_filter or True:  # Always enrich for usability
        customer_ids = list({o.get("customer_id") for o in orders if o.get("customer_id")})
        customers = await db.customers.find({"id": {"$in": customer_ids}}, {"_id": 0}).to_list(1000)
        user_ids = [c.get("user_id") for c in customers]
        users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "password_hash": 0}).to_list(1000)
        customer_map = {c["id"]: c for c in customers}
        user_map = {u["id"]: u for u in users}
        
        enriched = []
        for o in orders:
            cust = customer_map.get(o.get("customer_id"), {})
            user = user_map.get(cust.get("user_id"), {})
            if email_filter and email_filter.lower() not in (user.get("email", "")).lower():
                continue
            o["_customer_email"] = user.get("email", "")
            o["_customer_name"] = user.get("full_name", "")
            enriched.append(o)
        orders = enriched
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _make_csv_response(orders, f"orders_{today}.csv")


@api_router.get("/admin/export/customers")
async def export_customers_csv(admin: Dict[str, Any] = Depends(require_admin)):
    """Export all customers as CSV with all DB fields"""
    customers = await db.customers.find({}, {"_id": 0}).to_list(10000)
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(10000)
    addresses = await db.addresses.find({}, {"_id": 0}).to_list(10000)
    
    user_map = {u["id"]: u for u in users}
    addr_map = {a["customer_id"]: a for a in addresses}
    
    rows = []
    for c in customers:
        u = user_map.get(c.get("user_id"), {})
        a = addr_map.get(c["id"], {})
        row = {**c}
        row["email"] = u.get("email", "")
        row["full_name"] = u.get("full_name", "")
        row["job_title"] = u.get("job_title", "")
        row["phone"] = u.get("phone", "")
        row["is_verified"] = u.get("is_verified", False)
        row["is_active"] = u.get("is_active", True)
        row["role"] = u.get("role", "customer")
        row["line1"] = a.get("line1", "")
        row["line2"] = a.get("line2", "")
        row["city"] = a.get("city", "")
        row["region"] = a.get("region", "")
        row["postal"] = a.get("postal", "")
        row["country"] = a.get("country", "")
        rows.append(row)
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _make_csv_response(rows, f"customers_{today}.csv")


@api_router.get("/admin/export/subscriptions")
async def export_subscriptions_csv(
    sort_by: str = "created_at",
    sort_order: str = "desc",
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Export all filtered subscriptions as CSV with all DB fields"""
    query: Dict[str, Any] = {}
    if created_from:
        query.setdefault("created_at", {})["$gte"] = created_from
    if created_to:
        query.setdefault("created_at", {})["$lte"] = created_to + "T23:59:59"
    
    sort_dir = -1 if sort_order == "desc" else 1
    subs = await db.subscriptions.find(query, {"_id": 0}).sort(sort_by, sort_dir).to_list(10000)
    
    # Enrich with customer email/name
    customer_ids = list({s.get("customer_id") for s in subs if s.get("customer_id")})
    customers = await db.customers.find({"id": {"$in": customer_ids}}, {"_id": 0}).to_list(1000)
    user_ids = [c.get("user_id") for c in customers]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "password_hash": 0}).to_list(1000)
    customer_map = {c["id"]: c for c in customers}
    user_map = {u["id"]: u for u in users}
    
    for s in subs:
        cust = customer_map.get(s.get("customer_id"), {})
        user = user_map.get(cust.get("user_id"), {})
        s["_customer_email"] = user.get("email", "")
        s["_customer_name"] = user.get("full_name", "")
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _make_csv_response(subs, f"subscriptions_{today}.csv")


@api_router.get("/admin/export/catalog")
async def export_catalog_csv(admin: Dict[str, Any] = Depends(require_admin)):
    """Export all products as CSV with all DB fields"""
    products = await db.products.find({}, {"_id": 0}).to_list(10000)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _make_csv_response(products, f"catalog_{today}.csv")


@api_router.get("/admin/orders/{order_id}/logs")
async def get_order_logs(order_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    """Get audit logs for an order"""
    logs = await db.audit_logs.find(
        {"entity_type": "order", "entity_id": order_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"logs": logs}


@api_router.get("/admin/subscriptions/{subscription_id}/logs")
async def get_subscription_logs(subscription_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    """Get audit logs for a subscription"""
    logs = await db.audit_logs.find(
        {"entity_type": "subscription", "entity_id": subscription_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"logs": logs}


# ============ ADMIN: CUSTOMER EDIT ============

@api_router.put("/admin/customers/{customer_id}")
async def update_customer(
    customer_id: str,
    customer_data: CustomerUpdate,
    address_data: AddressUpdate,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Update customer details (country is locked)"""
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    user = await db.users.find_one({"id": customer["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    changes = {}
    
    # Update user fields
    user_updates = {}
    if customer_data.full_name is not None:
        user_updates["full_name"] = customer_data.full_name
        changes["full_name"] = {"old": user.get("full_name"), "new": customer_data.full_name}
    if customer_data.company_name is not None:
        user_updates["company_name"] = customer_data.company_name
        changes["company_name"] = {"old": user.get("company_name"), "new": customer_data.company_name}
    if customer_data.job_title is not None:
        user_updates["job_title"] = customer_data.job_title
        changes["job_title"] = {"old": user.get("job_title"), "new": customer_data.job_title}
    if customer_data.phone is not None:
        user_updates["phone"] = customer_data.phone
        changes["phone"] = {"old": user.get("phone"), "new": customer_data.phone}
    
    if user_updates:
        await db.users.update_one({"id": user["id"]}, {"$set": user_updates})
    
    # Update address fields (country is NOT editable)
    address = await db.addresses.find_one({"customer_id": customer_id}, {"_id": 0})
    if address:
        address_updates = {}
        if address_data.line1 is not None:
            address_updates["line1"] = address_data.line1
            changes["address_line1"] = {"old": address.get("line1"), "new": address_data.line1}
        if address_data.line2 is not None:
            address_updates["line2"] = address_data.line2
            changes["address_line2"] = {"old": address.get("line2"), "new": address_data.line2}
        if address_data.city is not None:
            address_updates["city"] = address_data.city
            changes["city"] = {"old": address.get("city"), "new": address_data.city}
        if address_data.region is not None:
            address_updates["region"] = address_data.region
            changes["region"] = {"old": address.get("region"), "new": address_data.region}
        if address_data.postal is not None:
            address_updates["postal"] = address_data.postal
            changes["postal"] = {"old": address.get("postal"), "new": address_data.postal}
        
        if address_updates:
            await db.addresses.update_one({"customer_id": customer_id}, {"$set": address_updates})
    
    # Log the changes
    await create_audit_log(
        entity_type="customer",
        entity_id=customer_id,
        action="updated",
        actor=f"admin:{admin['id']}",
        details={"changes": changes}
    )
    
    return {"message": "Customer updated successfully"}


# ============ ADMIN: ORDER CRUD ============

@api_router.put("/admin/orders/{order_id}")
async def update_order(
    order_id: str,
    payload: OrderUpdate,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Update order details"""
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Validate status if provided
    if payload.status and not validate_order_status(payload.status):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Allowed: {', '.join(ALLOWED_ORDER_STATUSES)}"
        )
    
    changes = {}
    update_fields = {}
    
    if payload.customer_id is not None:
        update_fields["customer_id"] = payload.customer_id
        changes["customer_id"] = {"old": order.get("customer_id"), "new": payload.customer_id}
    
    if payload.status is not None:
        update_fields["status"] = payload.status
        changes["status"] = {"old": order.get("status"), "new": payload.status}
    
    if payload.payment_method is not None:
        update_fields["payment_method"] = payload.payment_method
        changes["payment_method"] = {"old": order.get("payment_method"), "new": payload.payment_method}
    
    if payload.order_date is not None:
        update_fields["created_at"] = payload.order_date
        changes["order_date"] = {"old": order.get("created_at"), "new": payload.order_date}
    
    if payload.payment_date is not None:
        update_fields["payment_date"] = payload.payment_date
        changes["payment_date"] = {"old": order.get("payment_date"), "new": payload.payment_date}
    
    # Only allow amount edits for manual/offline orders
    is_manual = order.get("payment_method") in ["manual", "offline"]
    if is_manual:
        if payload.subtotal is not None:
            update_fields["subtotal"] = payload.subtotal
            changes["subtotal"] = {"old": order.get("subtotal"), "new": payload.subtotal}
        if payload.fee is not None:
            update_fields["fee"] = payload.fee
            changes["fee"] = {"old": order.get("fee"), "new": payload.fee}
        if payload.total is not None:
            update_fields["total"] = payload.total
            changes["total"] = {"old": order.get("total"), "new": payload.total}
    
    if payload.internal_note is not None:
        # Append note instead of replacing
        existing_note = order.get("internal_note", "")
        new_note = f"{existing_note}\n[{now_iso()}] {payload.internal_note}" if existing_note else payload.internal_note
        update_fields["internal_note"] = new_note
        changes["internal_note_added"] = payload.internal_note
    
    if update_fields:
        update_fields["updated_at"] = now_iso()
        await db.orders.update_one({"id": order_id}, {"$set": update_fields})
        
        await create_audit_log(
            entity_type="order",
            entity_id=order_id,
            action="updated",
            actor=f"admin:{admin['id']}",
            details={"changes": changes}
        )
    
    # Append new note if provided
    if payload.new_note:
        note_entry = {
            "text": payload.new_note,
            "timestamp": now_iso(),
            "actor": f"admin:{admin['id']}"
        }
        await db.orders.update_one({"id": order_id}, {"$push": {"notes": note_entry}})
        await create_audit_log(
            entity_type="order",
            entity_id=order_id,
            action="note_added",
            actor=f"admin:{admin['id']}",
            details={"note": payload.new_note}
        )
    
    return {"message": "Order updated successfully"}


@api_router.delete("/admin/orders/{order_id}")
async def delete_order(
    order_id: str,
    payload: OrderDelete,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Soft delete an order"""
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Soft delete
    await db.orders.update_one(
        {"id": order_id},
        {"$set": {"deleted_at": now_iso(), "deleted_by": admin["id"]}}
    )
    
    await create_audit_log(
        entity_type="order",
        entity_id=order_id,
        action="deleted",
        actor=f"admin:{admin['id']}",
        details={"reason": payload.reason or "No reason provided"}
    )
    
    return {"message": "Order deleted successfully"}


@api_router.post("/admin/orders/{order_id}/auto-charge")
async def auto_charge_order(
    order_id: str,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Attempt to auto-charge an unpaid order"""
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.get("status") == "paid":
        raise HTTPException(status_code=400, detail="Order is already paid")
    
    customer = await db.customers.find_one({"id": order["customer_id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    payment_method = order.get("payment_method")
    result = {"success": False, "message": ""}
    
    try:
        if payment_method == "card":
            # For Stripe card payments, we'd need to create a payment intent or invoice
            # This is a simplified version
            result["message"] = "Card payment auto-charge requires Stripe Payment Intent setup. Please process manually or contact customer."
            result["success"] = False
        
        elif payment_method == "bank_transfer":
            # For GoCardless, check if mandate exists
            mandate_id = order.get("gocardless_mandate_id")
            if not mandate_id:
                result["message"] = "No GoCardless mandate found. Customer must complete Direct Debit setup first."
                result["success"] = False
            else:
                # Create payment
                payment = create_payment(
                    amount=order["total"],
                    currency=order.get("currency", "USD"),
                    mandate_id=mandate_id,
                    description=f"Auto-charge for Order {order['order_number']}",
                    metadata={"order_id": order["id"], "order_number": order["order_number"]}
                )
                
                if payment:
                    await db.orders.update_one(
                        {"id": order_id},
                        {"$set": {
                            "status": "pending_payment",
                            "gocardless_payment_id": payment["id"],
                            "updated_at": now_iso()
                        }}
                    )
                    result["success"] = True
                    result["message"] = f"Payment initiated with GoCardless. Payment ID: {payment['id']}"
                    result["payment_id"] = payment["id"]
                else:
                    result["message"] = "Failed to create GoCardless payment"
                    result["success"] = False
        
        else:
            result["message"] = f"Auto-charge not supported for payment method: {payment_method}"
            result["success"] = False
        
        # Log the attempt
        await create_audit_log(
            entity_type="order",
            entity_id=order_id,
            action="auto_charge_attempt",
            actor=f"admin:{admin['id']}",
            details={"result": result, "payment_method": payment_method}
        )
        
        return result
    
    except Exception as e:
        await create_audit_log(
            entity_type="order",
            entity_id=order_id,
            action="auto_charge_failed",
            actor=f"admin:{admin['id']}",
            details={"error": str(e), "payment_method": payment_method}
        )
        raise HTTPException(status_code=500, detail=f"Auto-charge failed: {str(e)}")






@api_router.get("/admin/products-all")
async def admin_list_all_products(admin: Dict[str, Any] = Depends(require_admin)):
    products = await db.products.find({}, {"_id": 0}).to_list(1000)
    return {"products": products}


# ============ APP SETTINGS ============

@api_router.get("/settings/public")
async def get_public_settings():
    settings = await db.app_settings.find_one({}, {"_id": 0})
    if not settings:
        return {"settings": {}}
    return {"settings": {
        "primary_color": settings.get("primary_color"),
        "secondary_color": settings.get("secondary_color"),
        "accent_color": settings.get("accent_color"),
        "logo_url": settings.get("logo_url"),
        "store_name": settings.get("store_name"),
    }}


@api_router.get("/admin/settings")
async def get_app_settings(admin: Dict[str, Any] = Depends(require_admin)):
    settings = await db.app_settings.find_one({}, {"_id": 0})
    if not settings:
        return {"settings": {}}
    masked = {**settings}
    for key in ["stripe_secret_key", "gocardless_token", "resend_api_key"]:
        if masked.get(key) and not masked[key].startswith("••"):
            masked[key] = "••••••••" + masked[key][-4:]
    return {"settings": masked}


@api_router.put("/admin/settings")
async def update_app_settings(
    payload: AppSettingsUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    for key in ["stripe_secret_key", "gocardless_token", "resend_api_key"]:
        if key in update and update[key].startswith("••"):
            del update[key]
    if not update:
        return {"message": "Nothing to update"}
    await db.app_settings.update_one({}, {"$set": update}, upsert=True)
    return {"message": "Settings updated"}


@api_router.post("/admin/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    admin: Dict[str, Any] = Depends(require_admin),
):
    contents = await file.read()
    b64 = base64.b64encode(contents).decode()
    content_type = file.content_type or "image/png"
    data_url = f"data:{content_type};base64,{b64}"
    await db.app_settings.update_one({}, {"$set": {"logo_url": data_url}}, upsert=True)
    return {"logo_url": data_url}


# ============ CATEGORIES ADMIN CRUD ============

@api_router.get("/admin/categories")
async def admin_list_categories(admin: Dict[str, Any] = Depends(require_admin)):
    cats = await db.categories.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    # Attach product count for each category
    for cat in cats:
        cat["product_count"] = await db.products.count_documents({"category": cat["name"]})
    return {"categories": cats}


@api_router.post("/admin/categories")
async def admin_create_category(
    payload: CategoryCreate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    existing = await db.categories.find_one({"name": payload.name})
    if existing:
        raise HTTPException(status_code=409, detail="Category already exists")
    cat = {
        "id": make_id(),
        "name": payload.name,
        "description": payload.description,
        "is_active": payload.is_active,
        "created_at": now_iso(),
    }
    await db.categories.insert_one(cat)
    cat.pop("_id", None)
    return {"category": cat}


@api_router.put("/admin/categories/{cat_id}")
async def admin_update_category(
    cat_id: str,
    payload: CategoryUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    cat = await db.categories.find_one({"id": cat_id}, {"_id": 0})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    update = {k: v for k, v in payload.dict().items() if v is not None}
    # Allow explicit empty string for description
    if payload.description is not None:
        update["description"] = payload.description
    if update:
        await db.categories.update_one({"id": cat_id}, {"$set": update})
    cat.update(update)
    return {"category": cat}


@api_router.delete("/admin/categories/{cat_id}")
async def admin_delete_category(
    cat_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    cat = await db.categories.find_one({"id": cat_id})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    product_count = await db.products.count_documents({"category": cat["name"]})
    if product_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {product_count} product(s) are linked to this category. Reassign or deactivate them first."
        )
    await db.categories.delete_one({"id": cat_id})
    return {"message": "Category deleted"}


# ============ PRODUCTS ADMIN CREATE ============

@api_router.post("/admin/products")
async def admin_create_product(
    payload: AdminProductCreate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    product_id = make_id()
    sku = f"CUSTOM-{product_id[:8].upper()}"
    product: Dict[str, Any] = {
        "id": product_id,
        "sku": sku,
        "name": payload.name,
        "short_description": payload.short_description,
        "tagline": payload.short_description,
        "description_long": payload.description_long,
        "bullets": payload.bullets,
        "tag": payload.tag,
        "category": payload.category,
        "outcome": payload.outcome,
        "automation_details": payload.automation_details,
        "support_details": payload.support_details,
        "inclusions": payload.inclusions,
        "exclusions": payload.exclusions,
        "requirements": payload.requirements,
        "next_steps": payload.next_steps,
        "faqs": payload.faqs,
        "terms_id": payload.terms_id,
        "base_price": payload.base_price,
        "is_subscription": payload.is_subscription,
        "stripe_price_id": payload.stripe_price_id,
        "pricing_complexity": payload.pricing_complexity,
        "is_active": payload.is_active,
        "visible_to_customers": payload.visible_to_customers,
        "pricing_type": "simple",
        "pricing_rules": {},
        "created_at": now_iso(),
        "is_custom": True,
    }
    product["price_inputs"] = build_price_inputs(product)
    await db.products.insert_one(product)
    product.pop("_id", None)
    return {"product": product}


# ============ QUOTE REQUEST ============

@api_router.post("/products/request-quote")
async def request_quote(
    payload: QuoteRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    quote: Dict[str, Any] = {
        "id": make_id(),
        "product_id": payload.product_id,
        "product_name": payload.product_name,
        "name": payload.name,
        "email": payload.email,
        "company": payload.company,
        "phone": payload.phone,
        "message": payload.message,
        "user_id": user["id"],
        "created_at": now_iso(),
        "status": "pending",
    }
    await db.quote_requests.insert_one(quote)
    quote.pop("_id", None)
    return {"message": "Quote request submitted. We will be in touch shortly.", "quote_id": quote["id"]}


@api_router.get("/admin/quote-requests")
async def admin_list_quote_requests(admin: Dict[str, Any] = Depends(require_admin)):
    quotes = await db.quote_requests.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"quotes": quotes}


@api_router.post("/admin/quote-requests")
async def admin_create_quote_request(
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(require_admin),
):
    quote: Dict[str, Any] = {
        "id": make_id(),
        "product_id": payload.get("product_id", ""),
        "product_name": payload.get("product_name", ""),
        "name": payload.get("name", ""),
        "email": payload.get("email", ""),
        "company": payload.get("company"),
        "phone": payload.get("phone"),
        "message": payload.get("message"),
        "user_id": payload.get("user_id", ""),
        "created_at": payload.get("created_at") or now_iso(),
        "status": payload.get("status", "pending"),
        "created_by_admin": True,
    }
    await db.quote_requests.insert_one(quote)
    quote.pop("_id", None)
    return {"quote": quote}


@api_router.put("/admin/quote-requests/{quote_id}")
async def admin_update_quote_request(
    quote_id: str,
    payload: Dict[str, Any],
    admin: Dict[str, Any] = Depends(require_admin),
):
    quote = await db.quote_requests.find_one({"id": quote_id})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote request not found")
    allowed = ["product_id", "product_name", "name", "email", "company", "phone", "message", "status", "user_id"]
    update = {k: v for k, v in payload.items() if k in allowed}
    if update:
        await db.quote_requests.update_one({"id": quote_id}, {"$set": update})
    quote.update(update)
    quote.pop("_id", None)
    return {"quote": quote}



# ============ BANK TRANSACTIONS ============

@api_router.get("/admin/bank-transactions")
async def list_bank_transactions(
    source: Optional[str] = None,
    status: Optional[str] = None,
    type: Optional[str] = None,
    linked_order_id: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    query: Dict[str, Any] = {}
    if source:
        query["source"] = source
    if status:
        query["status"] = status
    if type:
        query["type"] = type
    if linked_order_id:
        query["linked_order_id"] = linked_order_id
    txns = await db.bank_transactions.find(query, {"_id": 0}).sort("date", -1).to_list(1000)
    return {"transactions": txns}


@api_router.post("/admin/bank-transactions")
async def create_bank_transaction(
    payload: BankTransactionCreate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    txn_id = make_id()
    net = payload.net_amount if payload.net_amount is not None else round(payload.amount - (payload.fees or 0.0), 2)
    txn = {
        "id": txn_id,
        "date": payload.date,
        "source": payload.source,
        "transaction_id": payload.transaction_id,
        "type": payload.type,
        "amount": payload.amount,
        "fees": payload.fees or 0.0,
        "net_amount": net,
        "currency": payload.currency or "USD",
        "status": payload.status,
        "description": payload.description,
        "linked_order_id": payload.linked_order_id,
        "internal_notes": payload.internal_notes,
        "logs": [{"timestamp": now_iso(), "action": "created", "actor": admin["email"], "details": {}}],
        "created_at": now_iso(),
        "created_by": admin["email"],
    }
    await db.bank_transactions.insert_one(txn)
    txn.pop("_id", None)
    return {"transaction": txn}


@api_router.put("/admin/bank-transactions/{txn_id}")
async def update_bank_transaction(
    txn_id: str,
    payload: BankTransactionUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    txn = await db.bank_transactions.find_one({"id": txn_id}, {"_id": 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    updates = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    if "amount" in updates or "fees" in updates:
        amt = updates.get("amount", txn.get("amount", 0))
        fees = updates.get("fees", txn.get("fees", 0))
        updates["net_amount"] = round(amt - fees, 2)
    if updates:
        log_entry = {"timestamp": now_iso(), "action": "updated", "actor": admin["email"], "details": updates}
        await db.bank_transactions.update_one(
            {"id": txn_id},
            {"$set": {**updates, "updated_at": now_iso()}, "$push": {"logs": log_entry}}
        )
    updated = await db.bank_transactions.find_one({"id": txn_id}, {"_id": 0})
    return {"transaction": updated}


@api_router.delete("/admin/bank-transactions/{txn_id}")
async def delete_bank_transaction(
    txn_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    result = await db.bank_transactions.delete_one({"id": txn_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Deleted"}


@api_router.get("/admin/bank-transactions/{txn_id}/logs")
async def get_bank_transaction_logs(
    txn_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    txn = await db.bank_transactions.find_one({"id": txn_id}, {"_id": 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"logs": txn.get("logs", [])}


@api_router.get("/admin/export/bank-transactions")
async def export_bank_transactions(
    admin: Dict[str, Any] = Depends(require_admin),
):
    import csv, io
    txns = await db.bank_transactions.find({}, {"_id": 0}).sort("date", -1).to_list(5000)
    output = io.StringIO()
    fieldnames = ["id", "date", "source", "transaction_id", "type", "amount", "fees", "net_amount",
                  "currency", "status", "description", "linked_order_id", "internal_notes", "created_at", "created_by"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(txns)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=bank_transactions_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.csv"}
    )


# ============ ADMIN: OVERRIDE CODES ============

@api_router.get("/admin/override-codes")
async def list_override_codes(
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    query: Dict[str, Any] = {}
    if customer_id:
        query["customer_id"] = customer_id
    codes = await db.override_codes.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)

    now = datetime.now(timezone.utc)
    results = []
    for oc in codes:
        # Compute effective status: auto-expired if now > expires_at and still "active"
        effective_status = oc.get("status", "active")
        expires_at = oc.get("expires_at")
        if effective_status == "active" and expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if now > exp_dt:
                    effective_status = "expired"
            except Exception:
                pass
        results.append({**oc, "effective_status": effective_status})

    if status:
        results = [r for r in results if r["effective_status"] == status]

    # Enrich with customer info
    customer_ids = list({r["customer_id"] for r in results if r.get("customer_id")})
    customers = await db.customers.find({"id": {"$in": customer_ids}}, {"_id": 0, "id": 1}).to_list(500)
    users = await db.users.find({}, {"_id": 0, "id": 1, "email": 1, "full_name": 1}).to_list(500)
    cust_map = {c["id"]: c for c in customers}
    for r in results:
        cid = r.get("customer_id")
        cust = cust_map.get(cid, {})
        user = next((u for u in users if u["id"] == cust.get("user_id", "")), {})
        r["customer_email"] = user.get("email", "")
        r["customer_name"] = user.get("full_name", "")

    return {"override_codes": results}


@api_router.post("/admin/override-codes")
async def create_override_code(
    payload: OverrideCodeCreate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    # Duplicate code check
    existing = await db.override_codes.find_one({"code": payload.code.strip()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="An override code with this value already exists.")

    # Validate customer
    customer = await db.customers.find_one({"id": payload.customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    code_id = make_id()
    created_at = now_iso()
    expires_at = payload.expires_at or (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()

    await db.override_codes.insert_one({
        "id": code_id,
        "code": payload.code.strip(),
        "customer_id": payload.customer_id,
        "status": "active",
        "created_at": created_at,
        "expires_at": expires_at,
        "used_at": None,
        "used_for_order_id": None,
        "created_by": admin["id"],
    })
    await create_audit_log(
        entity_type="override_code", entity_id=code_id,
        action="created", actor=f"admin:{admin['id']}",
        details={"code": payload.code.strip(), "customer_id": payload.customer_id, "expires_at": expires_at}
    )
    return {"message": "Override code created", "id": code_id}


@api_router.put("/admin/override-codes/{code_id}")
async def update_override_code(
    code_id: str,
    payload: OverrideCodeUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    oc = await db.override_codes.find_one({"id": code_id}, {"_id": 0})
    if not oc:
        raise HTTPException(status_code=404, detail="Override code not found")

    updates: Dict[str, Any] = {}

    if payload.code is not None:
        new_code = payload.code.strip()
        if new_code != oc["code"]:
            dup = await db.override_codes.find_one({"code": new_code, "id": {"$ne": code_id}}, {"_id": 0})
            if dup:
                raise HTTPException(status_code=400, detail="An override code with this value already exists.")
        updates["code"] = new_code

    if payload.customer_id is not None:
        cust = await db.customers.find_one({"id": payload.customer_id}, {"_id": 0})
        if not cust:
            raise HTTPException(status_code=404, detail="Customer not found")
        updates["customer_id"] = payload.customer_id

    if payload.status is not None:
        if payload.status not in ["active", "inactive"]:
            raise HTTPException(status_code=400, detail="Status must be 'active' or 'inactive'")
        updates["status"] = payload.status

    if payload.expires_at is not None:
        updates["expires_at"] = payload.expires_at

    if updates:
        await db.override_codes.update_one({"id": code_id}, {"$set": updates})
        await create_audit_log(
            entity_type="override_code", entity_id=code_id,
            action="updated", actor=f"admin:{admin['id']}",
            details={"updates": updates}
        )

    oc.update(updates)
    oc.pop("_id", None)
    return {"message": "Override code updated", "override_code": oc}


@api_router.delete("/admin/override-codes/{code_id}")
async def deactivate_override_code(
    code_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    oc = await db.override_codes.find_one({"id": code_id}, {"_id": 0})
    if not oc:
        raise HTTPException(status_code=404, detail="Override code not found")
    await db.override_codes.update_one({"id": code_id}, {"$set": {"status": "inactive"}})
    await create_audit_log(
        entity_type="override_code", entity_id=code_id,
        action="deactivated", actor=f"admin:{admin['id']}",
        details={}
    )
    return {"message": "Override code deactivated"}


@api_router.put("/admin/customers/{customer_id}/partner-map")
async def update_customer_partner_map(
    customer_id: str,
    payload: CustomerPartnerMapUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    old_value = customer.get("partner_map")
    await db.customers.update_one({"id": customer_id}, {"$set": {"partner_map": payload.partner_map}})
    await create_audit_log(
        entity_type="customer", entity_id=customer_id,
        action="partner_map_updated", actor=f"admin:{admin['id']}",
        details={"old": old_value, "new": payload.partner_map}
    )
    return {"message": "Partner Map updated"}


@api_router.get("/admin/customers/{customer_id}/notes")
async def get_customer_notes(
    customer_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"notes": customer.get("notes", [])}


# ---------------------------------------------------------------------------
# ARTICLES MODULE
# ---------------------------------------------------------------------------

ARTICLE_CATEGORIES = [
    "Scope - Draft",
    "Scope - Final Lost",
    "Scope - Final Won",
    "Blog",
    "Help",
    "Guide",
    "SOP",
    "Other",
]
SCOPE_FINAL_CATEGORIES = {"Scope - Final Lost", "Scope - Final Won"}


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = _re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = _re.sub(r"\s+", "-", slug)
    slug = _re.sub(r"-+", "-", slug)
    return slug.strip("-")


class ArticleCreate(BaseModel):
    title: str
    slug: Optional[str] = None
    category: str
    price: Optional[float] = None
    content: str = ""
    visibility: str = "all"
    restricted_to: List[str] = []


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    content: Optional[str] = None
    visibility: Optional[str] = None
    restricted_to: Optional[List[str]] = None


class ArticleEmailRequest(BaseModel):
    customer_ids: List[str]
    subject: Optional[str] = None
    message: Optional[str] = None


@api_router.get("/articles/admin/list")
async def list_articles_admin(
    category: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    query: Dict[str, Any] = {"deleted_at": {"$exists": False}}
    if category:
        query["category"] = category
    articles = await db.articles.find(query, {"_id": 0, "content": 0}).sort("created_at", -1).to_list(500)
    return {"articles": articles}


@api_router.get("/articles/public")
async def list_articles_public(
    category: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user),
):
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    customer_id = customer["id"] if customer else None
    query: Dict[str, Any] = {"deleted_at": {"$exists": False}}
    if category:
        query["category"] = category
    articles = await db.articles.find(query, {"_id": 0, "content": 0}).sort("updated_at", -1).to_list(500)
    visible = []
    for a in articles:
        if a.get("visibility") == "all" or not a.get("restricted_to"):
            visible.append(a)
        elif customer_id and customer_id in a.get("restricted_to", []):
            visible.append(a)
    return {"articles": visible}


@api_router.get("/articles/{article_id}/validate-scope")
async def validate_scope_article(
    article_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    # Accept full UUID or short ID (first 8 chars prefix match)
    article = await db.articles.find_one(
        {
            "$or": [
                {"id": article_id},
                {"id": {"$regex": f"^{_re.escape(article_id.lower())}"}},
            ],
            "deleted_at": {"$exists": False},
        },
        {"_id": 0, "content": 0},
    )
    if not article:
        raise HTTPException(status_code=404, detail="Invalid Scope Id")
    if not article.get("category", "").startswith("Scope - Final"):
        raise HTTPException(status_code=400, detail="Invalid Scope Id")
    if not article.get("price"):
        raise HTTPException(status_code=400, detail="Invalid Scope Id")
    return {
        "valid": True,
        "article_id": article["id"],
        "title": article["title"],
        "price": article["price"],
        "slug": article.get("slug"),
        "category": article["category"],
    }


@api_router.get("/articles/{article_id}/logs")
async def get_article_logs(
    article_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    logs = await db.article_logs.find({"article_id": article_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"logs": logs}


@api_router.get("/articles/{article_id}")
async def get_article_by_id(
    article_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    article = await db.articles.find_one(
        {"$or": [{"id": article_id}, {"slug": article_id}], "deleted_at": {"$exists": False}},
        {"_id": 0},
    )
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.get("visibility") != "all" and article.get("restricted_to"):
        customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
        if not customer or customer["id"] not in article.get("restricted_to", []):
            raise HTTPException(status_code=403, detail="You don't have access to this article")
    return {"article": article}


@api_router.post("/articles")
async def create_article(
    payload: ArticleCreate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    if payload.category not in ARTICLE_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category")
    if payload.category in SCOPE_FINAL_CATEGORIES and not payload.price:
        raise HTTPException(status_code=400, detail="Price is required for Scope - Final articles")
    slug = payload.slug or _slugify(payload.title)
    existing = await db.articles.find_one({"slug": slug, "deleted_at": {"$exists": False}})
    if existing:
        slug = f"{slug}-{make_id()[:4]}"
    article_id = make_id()
    now = now_iso()
    doc = {
        "id": article_id,
        "title": payload.title,
        "slug": slug,
        "category": payload.category,
        "price": payload.price if payload.category in SCOPE_FINAL_CATEGORIES else None,
        "content": payload.content,
        "visibility": payload.visibility,
        "restricted_to": payload.restricted_to,
        "created_at": now,
        "updated_at": now,
    }
    await db.articles.insert_one(doc)
    await db.article_logs.insert_one({
        "id": make_id(),
        "article_id": article_id,
        "action": "created",
        "actor": admin.get("email", "admin"),
        "details": {"title": payload.title, "category": payload.category},
        "created_at": now,
    })
    doc.pop("_id", None)
    return {"article": doc}


@api_router.put("/articles/{article_id}")
async def update_article(
    article_id: str,
    payload: ArticleUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    article = await db.articles.find_one({"id": article_id, "deleted_at": {"$exists": False}}, {"_id": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    updates: Dict[str, Any] = {"updated_at": now_iso()}
    changes: Dict[str, Any] = {}
    if payload.title is not None:
        updates["title"] = payload.title
        changes["title"] = payload.title
    if payload.slug is not None:
        existing = await db.articles.find_one({"slug": payload.slug, "id": {"$ne": article_id}, "deleted_at": {"$exists": False}})
        if existing:
            raise HTTPException(status_code=400, detail="Slug already in use")
        updates["slug"] = payload.slug
        changes["slug"] = payload.slug
    effective_category = payload.category if payload.category is not None else article.get("category")
    if payload.category is not None:
        if payload.category not in ARTICLE_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        updates["category"] = payload.category
        changes["category"] = payload.category
    if payload.price is not None:
        updates["price"] = payload.price
        changes["price"] = payload.price
    elif effective_category not in SCOPE_FINAL_CATEGORIES:
        updates["price"] = None
    if payload.content is not None:
        updates["content"] = payload.content
    if payload.visibility is not None:
        updates["visibility"] = payload.visibility
        changes["visibility"] = payload.visibility
    if payload.restricted_to is not None:
        updates["restricted_to"] = payload.restricted_to
        changes["restricted_to_count"] = len(payload.restricted_to)
    await db.articles.update_one({"id": article_id}, {"$set": updates})
    if changes:
        await db.article_logs.insert_one({
            "id": make_id(),
            "article_id": article_id,
            "action": "updated",
            "actor": admin.get("email", "admin"),
            "details": changes,
            "created_at": now_iso(),
        })
    updated = await db.articles.find_one({"id": article_id}, {"_id": 0})
    updated.pop("_id", None)
    return {"article": updated}


@api_router.delete("/articles/{article_id}")
async def delete_article(
    article_id: str,
    admin: Dict[str, Any] = Depends(require_admin),
):
    article = await db.articles.find_one({"id": article_id, "deleted_at": {"$exists": False}}, {"_id": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    now = now_iso()
    await db.articles.update_one({"id": article_id}, {"$set": {"deleted_at": now}})
    await db.article_logs.insert_one({
        "id": make_id(),
        "article_id": article_id,
        "action": "deleted",
        "actor": admin.get("email", "admin"),
        "details": {"title": article.get("title")},
        "created_at": now,
    })
    return {"message": "Article deleted"}


@api_router.post("/articles/{article_id}/email")
async def email_article(
    article_id: str,
    payload: ArticleEmailRequest,
    admin: Dict[str, Any] = Depends(require_admin),
):
    article = await db.articles.find_one({"id": article_id, "deleted_at": {"$exists": False}}, {"_id": 0, "content": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    app_settings = await db.app_settings.find_one({}, {"_id": 0})
    resend_key = (app_settings or {}).get("resend_api_key")
    if not resend_key:
        raise HTTPException(status_code=400, detail="Resend API key not configured. Please add it in Admin > Settings.")
    resend.api_key = resend_key
    customers = await db.customers.find({"id": {"$in": payload.customer_ids}}, {"_id": 0}).to_list(50)
    if not customers:
        raise HTTPException(status_code=404, detail="No customers found")
    user_ids = [c["user_id"] for c in customers if c.get("user_id")]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0}).to_list(50)
    user_email_map = {u["id"]: u["email"] for u in users}
    app_url = os.environ.get("REACT_APP_BACKEND_URL", "").replace("/api", "").rstrip("/")
    article_url = f"{app_url}/articles/{article.get('slug') or article_id}"
    subject = payload.subject or f"Article: {article['title']}"
    sent = []
    errors = []
    now = now_iso()
    for customer in customers:
        email_addr = user_email_map.get(customer.get("user_id"))
        if not email_addr:
            continue
        message_body = payload.message or ""
        price_line = f"<p style='color:#475569;'>Price: <strong>${article['price']}</strong></p>" if article.get("price") else ""
        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
          <h2 style="color:#1e293b;">{article['title']}</h2>
          {"<p style='color:#475569;'>" + message_body + "</p>" if message_body else ""}
          <p style="color:#475569;">Category: <strong>{article['category']}</strong></p>
          {price_line}
          <a href="{article_url}" style="display:inline-block;background:#1e293b;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;margin-top:16px;">
            View Article
          </a>
          <p style="color:#94a3b8;font-size:12px;margin-top:24px;">Your consultant has shared this document with you.</p>
        </div>"""
        try:
            params = {"from": "noreply@automateaccounts.com", "to": [email_addr], "subject": subject, "html": html_body}
            await asyncio.to_thread(resend.Emails.send, params)
            sent.append(email_addr)
            await db.article_logs.insert_one({
                "id": make_id(),
                "article_id": article_id,
                "action": "email_sent",
                "actor": admin.get("email", "admin"),
                "details": {"to": email_addr, "customer_id": customer["id"], "subject": subject},
                "created_at": now,
            })
        except Exception as e:
            errors.append({"email": email_addr, "error": str(e)})
    return {"sent": sent, "errors": errors, "message": f"Sent to {len(sent)} recipient(s)"}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
