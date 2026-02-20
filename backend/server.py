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


class AddressInput(BaseModel):
    line1: str
    line2: Optional[str] = ""
    city: str
    region: str
    postal: str
    country: str


class RegisterRequest(BaseModel):
    full_name: str
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


class CurrencyOverrideRequest(BaseModel):
    customer_email: str
    currency: str


def build_seed_products(external_books_url: str) -> List[Dict[str, Any]]:
    return [
        {
            "id": "prod_zoho_one_express",
            "category": "Start Here",
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
            "category": "Start Here",
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
            "category": "Start Here",
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
            "category": "Start Here",
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
            "category": "Start Here",
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


@app.on_event("startup")
async def startup_tasks():
    await seed_admin_user()
    await seed_products()


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
    customer = await db.customers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    new_currency = currency_for_country(payload.address.country)
    update_fields = {
        "company_name": payload.company_name,
        "phone": payload.phone,
    }
    if not customer.get("currency_locked"):
        update_fields["currency"] = new_currency
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
                "country": payload.address.country,
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
        stripe_price_id = product.get("stripe_price_id")
        if not stripe_price_id:
            raise HTTPException(status_code=400, detail="Subscription checkout requires a Stripe price ID")

    if checkout_type == "one_time":
        for item in order_items:
            if item["pricing"].get("is_subscription"):
                raise HTTPException(status_code=400, detail="One-time checkout cannot include subscriptions")
            if item["pricing"].get("is_scope_request") or item["product"].get("pricing_type") in ["external", "inquiry"]:
                raise HTTPException(status_code=400, detail="Checkout not supported for this item")

    subtotal = sum(i["pricing"]["subtotal"] for i in order_items)
    fee = sum(i["pricing"]["fee"] for i in order_items)
    total = round_cents(subtotal + fee)

    order_id = make_id()
    order_number = f"AA-{order_id.split('-')[0].upper()}"
    order_doc = {
        "id": order_id,
        "order_number": order_number,
        "customer_id": customer["id"],
        "type": "subscription_start" if checkout_type == "subscription" else "one_time",
        "status": "pending",
        "subtotal": round_cents(subtotal),
        "fee": round_cents(fee),
        "total": total,
        "currency": customer.get("currency"),
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
    }

    if checkout_type == "subscription":
        product = order_items[0]["product"]
        checkout_request = CheckoutSessionRequest(
            stripe_price_id=product["stripe_price_id"],
            quantity=order_items[0]["quantity"],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
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
    return {"status": "ok"}


@api_router.get("/admin/customers")
async def admin_customers(admin: Dict[str, Any] = Depends(require_admin)):
    customers = await db.customers.find({}, {"_id": 0}).to_list(500)
    users = await db.users.find({}, {"_id": 0, "id": 1, "email": 1, "full_name": 1}).to_list(500)
    return {"customers": customers, "users": users}


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
