from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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
import os
import uuid
import jwt
import secrets

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ["JWT_SECRET"]
STRIPE_API_KEY = os.environ["STRIPE_API_KEY"]
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

app = FastAPI()
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def make_id():
    return str(uuid.uuid4())


def round_cents(value: float) -> float:
    return float(f"{value:.2f}")


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
    return user


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


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


class OrderPreviewRequest(BaseModel):
    items: List[CartItemInput]


class CheckoutSessionRequestBody(BaseModel):
    items: List[CartItemInput]
    checkout_type: str
    origin_url: str
    promo_code: Optional[str] = None
    terms_accepted: bool = False
    terms_id: Optional[str] = None


class BankTransferCheckoutRequest(BaseModel):
    items: List[CartItemInput]
    checkout_type: str
    promo_code: Optional[str] = None
    terms_accepted: bool = False
    terms_id: Optional[str] = None



class ScopeRequestBody(BaseModel):
    items: List[CartItemInput]


class CancelSubscriptionBody(BaseModel):
    reason: Optional[str] = ""


class AdminProductUpdate(BaseModel):
    name: str
    tagline: str
    description_long: str
    bullets_included: List[str]
    bullets_excluded: List[str]
    bullets_needed: List[str]
    next_steps: List[str]
    faqs: List[str]
    pricing_rules: Dict[str, Any]
    stripe_price_id: Optional[str] = None
    is_active: bool = True

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
                "card_bullets": [
                    "Multi-year historical data transfer",
                    "Invetory, Projects, Multi-currency",
                    "Post-migration checks and support and more",
                ],
                "bullets_included": [
                    "Multi-year historical data transfer",
                    "Invetory, Projects, Multi-currency",
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
        period_end = period_start + timedelta(days=30)
        sub_id = make_id()
        
        # Try to create GoCardless customer/mandate
        gocardless_redirect_url = None
        gc_customer_id = customer.get("gocardless_customer_id")
        
        try:
            import requests
            gc_token = os.environ.get("GOCARDLESS_ACCESS_TOKEN")
            if gc_token and not gc_customer_id:
                # Create GoCardless customer
                gc_response = requests.post(
                    "https://api-sandbox.gocardless.com/customers",
                    json={
                        "customers": {
                            "email": user["email"],
                            "given_name": user.get("full_name", "").split()[0] if user.get("full_name") else "Customer",
                            "family_name": user.get("full_name", "").split()[-1] if user.get("full_name") and len(user.get("full_name", "").split()) > 1 else "User",
                            "company_name": user.get("company_name", ""),
                        }
                    },
                    headers={
                        "Authorization": f"Bearer {gc_token}",
                        "GoCardless-Version": "2015-07-06",
                        "Content-Type": "application/json"
                    },
                    timeout=10
                )
                if gc_response.status_code == 201:
                    gc_customer_id = gc_response.json()["customers"]["id"]
                    await db.customers.update_one(
                        {"id": customer["id"]},
                        {"$set": {"gocardless_customer_id": gc_customer_id}}
                    )
        except Exception as e:
            print(f"GoCardless customer creation failed: {e}")
        
        await db.subscriptions.insert_one(
            {
                "id": sub_id,
                "order_id": None,
                "customer_id": customer["id"],
                "plan_name": product["name"],
                "status": "pending_bank_setup",
                "stripe_subscription_id": None,
                "gocardless_customer_id": gc_customer_id,
                "current_period_start": period_start.isoformat(),
                "current_period_end": period_end.isoformat(),
                "cancel_at_period_end": False,
                "canceled_at": None,
                "amount": subtotal,
                "payment_method": "bank_transfer",
                "terms_id_used": terms_id,
                "rendered_terms_text": rendered_terms_text,
                "terms_accepted_at": now_iso(),
            }
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
        return {
            "message": "Subscription request created",
            "subscription_id": sub_id,
            "status": "pending_bank_setup",
            "gocardless_customer_id": gc_customer_id,
            "gocardless_redirect_url": gocardless_redirect_url,
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
        "terms_id_used": terms_id,
        "rendered_terms_text": rendered_terms_text,
        "terms_accepted_at": now_iso(),
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

    return {
        "message": "Bank transfer order created",
        "order_id": order_id,
        "order_number": order_number,
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
    products = await db.products.find({"is_active": True}, {"_id": 0, "category": 1}).to_list(500)
    categories = sorted({p["category"] for p in products})
    return {"categories": categories}


@api_router.get("/products")
async def get_products():
    products = await db.products.find({"is_active": True}, {"_id": 0}).to_list(1000)
    return {"products": products}


@api_router.get("/products/{product_id}")
async def get_product(product_id: str):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
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
            raise HTTPException(status_code=400, detail="Subscription requires valid pricing")

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
        "created_at": now_iso(),
    }
    await db.orders.insert_one(order_doc)

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
        if stripe_price_id:
            checkout_request = CheckoutSessionRequest(
                stripe_price_id=stripe_price_id,
                quantity=order_items[0]["quantity"],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
            )
        else:
            # Use price_data for dynamic subscription pricing
            # Stripe expects monthly recurring for subscriptions
            checkout_request = CheckoutSessionRequest(
                amount=float(discounted_subtotal),  # No fee for subscriptions until renewal
                currency=customer.get("currency", "USD").lower(),
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
                mode="subscription"
            )
    else:
        checkout_request = CheckoutSessionRequest(
            amount=float(total),
            currency=customer.get("currency", "USD").lower(),
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )

    session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)

    await db.payment_transactions.insert_one(
        {
            "id": make_id(),
            "session_id": session.session_id,
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

    return {"url": session.url, "session_id": session.session_id, "order_id": order_id}


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

    if webhook_response.event_type == "invoice.paid" and email_target:
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


@api_router.put("/admin/orders/{order_id}")
async def admin_update_order(
    order_id: str,
    payload: AdminOrderUpdate,
    admin: Dict[str, Any] = Depends(require_admin),
):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    update: Dict[str, Any] = {}
    if payload.manual_status is not None:
        update["manual_status"] = payload.manual_status
    if payload.internal_note is not None:
        update["internal_note"] = payload.internal_note
    if update:
        await db.orders.update_one({"id": order_id}, {"$set": update})
    return {"message": "Order updated"}


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
async def admin_orders(admin: Dict[str, Any] = Depends(require_admin)):
    orders = await db.orders.find({}, {"_id": 0}).to_list(500)
    return {"orders": orders}


@api_router.get("/admin/subscriptions")
async def admin_subscriptions(admin: Dict[str, Any] = Depends(require_admin)):
    subs = await db.subscriptions.find({}, {"_id": 0}).to_list(500)
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
    updated_product = {
        **existing,
        "name": payload.name,
        "tagline": payload.tagline,
        "description_long": payload.description_long,
        "bullets_included": payload.bullets_included,
        "bullets_excluded": payload.bullets_excluded,
        "bullets_needed": payload.bullets_needed,
        "next_steps": payload.next_steps,
        "faqs": payload.faqs,
        "pricing_rules": payload.pricing_rules,
        "stripe_price_id": payload.stripe_price_id,
        "is_active": payload.is_active,
    }
    updated_product["price_inputs"] = build_price_inputs(updated_product)
    await db.products.update_one({"id": product_id}, {"$set": updated_product})
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
    
    return {
        "message": "Manual order created",
        "order_id": order_id,
        "order_number": order_number,
    }


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
