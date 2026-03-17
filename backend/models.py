"""Pydantic request/response models for Automate Accounts API."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Shared length constants — keep in sync with frontend/src/lib/fieldLimits.tsx
# ---------------------------------------------------------------------------
_NAME    = {"min_length": 1, "max_length": 100}   # entity names, titles, headings
_CODE    = {"min_length": 1, "max_length": 100}   # codes, keys, slugs, enum-like
_DESC    = {"max_length": 10_000}                 # long descriptions
_NOTE    = {"max_length": 5_000}                  # notes, FAQ answers
_SHORT   = {"max_length": 100}                    # enum-like / system codes only
_SUBJECT = {"max_length": 500}                    # email subjects and single-line text
_CONTENT = {"max_length": 500_000}                # rich HTML bodies


class AddressInput(BaseModel):
    line1: str = Field("", max_length=100)
    line2: str = Field("", max_length=100)
    city: str = Field("", max_length=100)
    region: str = Field("", max_length=100)
    postal: str = Field("", max_length=20)
    country: str = Field("", max_length=10)


class RegisterRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=128)
    full_name: Optional[str] = Field(None, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    company_name: str = Field("", max_length=100)
    job_title: str = Field("", max_length=100)
    phone: str = Field("", max_length=50)
    address: AddressInput
    profile_meta: Optional[Dict[str, Any]] = None
    partner_code: Optional[str] = Field(None, max_length=100)

    def get_full_name(self) -> str:
        if self.full_name:
            return self.full_name
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts) if parts else ""


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=128)
    partner_code: Optional[str] = Field(None, max_length=100)
    login_type: Optional[str] = "partner"


class PartnerLoginRequest(BaseModel):
    partner_code: str = Field(max_length=100)
    email: str = Field(max_length=320)
    password: str = Field(max_length=128)


class CustomerLoginRequest(BaseModel):
    partner_code: str = Field(max_length=100)
    email: str = Field(max_length=320)
    password: str = Field(max_length=128)


class TenantCreate(BaseModel):
    name: str = Field(**_NAME)
    code: str = Field(**_CODE)
    status: str = "active"
    owner_email: Optional[str] = None


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    default_reminder_days: Optional[int] = None  # None = use hardcoded default; 0/blank = disable


class CreatePartnerAdminRequest(BaseModel):
    tenant_id: str
    email: str
    full_name: str
    password: str
    role: str = "partner_admin"
    # New per-module permissions format
    module_permissions: Optional[Dict[str, str]] = None
    # Legacy fields (kept for backwards compatibility)
    access_level: Optional[str] = "read_only"
    modules: Optional[List[str]] = None
    preset_role: Optional[str] = None


class VerifyEmailRequest(BaseModel):
    email: Optional[str] = Field(None, max_length=320)
    code: Optional[str] = Field(None, max_length=6)
    partner_code: Optional[str] = Field(None, max_length=100)
    token: Optional[str] = None  # JWT verification token (alternative to email+code)


class ResendVerificationRequest(BaseModel):
    email: str
    partner_code: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=320)
    address: Optional[AddressInput] = None


class PricingCalcRequest(BaseModel):
    product_id: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    partner_code: Optional[str] = None


class CartItemInput(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, description="Must be a positive integer (≥1)")
    inputs: Dict[str, Any] = Field(default_factory=dict)
    price_override: Optional[float] = None


class OrderPreviewRequest(BaseModel):
    items: List[CartItemInput]


class CheckoutSessionRequestBody(BaseModel):
    items: List[CartItemInput]
    checkout_type: str
    origin_url: str
    promo_code: Optional[str] = None
    terms_accepted: bool = False
    terms_id: Optional[str] = None
    start_date: Optional[str] = None
    extra_fields: Optional[Dict[str, Any]] = None


class BankTransferCheckoutRequest(BaseModel):
    items: List[CartItemInput]
    checkout_type: str
    promo_code: Optional[str] = None
    terms_accepted: bool = False
    terms_id: Optional[str] = None
    start_date: Optional[str] = None
    extra_fields: Optional[Dict[str, Any]] = None


class ScopeRequestBody(BaseModel):
    items: List[CartItemInput]


class CancelSubscriptionBody(BaseModel):
    reason: Optional[str] = Field("", max_length=1_000)


class IntakeOption(BaseModel):
    label: str
    value: str
    price_value: float = 0.0


class VisibilityRule(BaseModel):
    depends_on: str = ""
    operator: str = "equals"
    value: str = ""


# ── Product conditional visibility ────────────────────────────────────────────
class ProductVisCondition(BaseModel):
    field: str = ""       # customer field key
    operator: str = "equals"  # equals | not_equals | contains | not_contains | empty | not_empty
    value: str = ""       # empty for empty/not_empty operators


class ProductVisGroup(BaseModel):
    logic: str = "AND"
    conditions: List[ProductVisCondition] = Field(default_factory=list)


class ProductVisRuleSet(BaseModel):
    top_logic: str = "AND"   # "AND" | "OR" — logic between groups
    groups: List[ProductVisGroup] = Field(default_factory=list)


class IntakeQuestion(BaseModel):
    key: str = Field("", max_length=100)
    label: str = Field("", max_length=500)
    helper_text: Optional[str] = Field("", max_length=500)
    tooltip_text: Optional[str] = Field("", max_length=500)
    required: bool = False
    enabled: bool = True
    order: int = 0
    type: str = "single_line"   # dropdown|multiselect|number|boolean|single_line|multi_line|date|file|formula|html_block
    step_group: int = 0         # wizard step grouping (0 = ungrouped)
    # Dropdown / multiselect
    affects_price: bool = False
    price_mode: str = "add"
    options: Optional[List[IntakeOption]] = None
    # Number type — flat or tiered
    price_per_unit: Optional[float] = None
    pricing_mode: str = "flat"
    tiers: Optional[List[Dict[str, Any]]] = None
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    default_value: Optional[float] = None
    # Boolean type
    price_for_yes: Optional[float] = None
    price_for_no: Optional[float] = None
    # Formula type
    formula_expression: Optional[str] = Field(None, max_length=5_000)
    # Date type
    date_format: str = "date"
    # File type
    accept: Optional[str] = None
    max_size_mb: float = 10.0
    # HTML block (no key/pricing — pure content)
    content: Optional[str] = Field(None, max_length=500_000)
    # Conditional visibility — accepts both legacy VisibilityRule and new VisibilityRuleSet {logic, conditions}
    visibility_rule: Optional[Any] = None


class IntakeSchemaJson(BaseModel):
    version: int = 2
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None
    questions: List[IntakeQuestion] = Field(default_factory=list)
    price_floor: Optional[float] = None
    price_ceiling: Optional[float] = None


class CustomSection(BaseModel):
    id: str = Field("", max_length=100)
    name: str = Field(max_length=100)
    content: str = Field("", max_length=500_000)
    icon: Optional[str] = Field(None, max_length=50)
    icon_color: Optional[str] = Field(None, max_length=50)
    tags: List[str] = Field(default_factory=list)
    order: int = 0


class AdminProductUpdate(BaseModel):
    name: str = Field(**_NAME)
    card_tag: Optional[str] = Field(None, max_length=100)
    card_description: Optional[str] = Field(None, **_NOTE)
    card_bullets: Optional[List[str]] = None
    description_long: str = Field("", **_CONTENT)
    bullets: Optional[List[str]] = None
    category: Optional[str] = Field(None, max_length=100)
    faqs: Optional[List[Any]] = None
    terms_id: Optional[str] = None
    base_price: Optional[float] = Field(None, ge=0)
    is_subscription: Optional[bool] = None
    stripe_price_id: Optional[str] = Field(None, max_length=100)
    pricing_type: Optional[str] = "internal"
    external_url: Optional[str] = Field(None, max_length=2048)
    is_active: bool = True
    visible_to_customers: Optional[List[str]] = None
    restricted_to: Optional[List[str]] = None
    visibility_conditions: Optional[ProductVisRuleSet] = None
    intake_schema_json: Optional[IntakeSchemaJson] = None
    price_rounding: Optional[str] = None
    show_price_breakdown: Optional[bool] = False
    custom_sections: Optional[List[CustomSection]] = None
    display_layout: Optional[str] = "standard"
    currency: Optional[str] = Field(None, max_length=10)
    enquiry_form_id: Optional[str] = None
    default_term_months: Optional[int] = Field(None, ge=0, le=300)
    billing_type: Optional[str] = None
    tags: Optional[List[str]] = None


class AdminOrderUpdate(BaseModel):
    manual_status: Optional[str] = Field(None, max_length=100)
    internal_note: Optional[str] = Field(None, max_length=5_000)


class PromoCodeCreate(BaseModel):
    code: str = Field(**_CODE)
    discount_type: str = Field(**_SHORT)
    discount_value: float
    applies_to: str = Field(**_SHORT)
    applies_to_products: str = "all"
    product_ids: List[str] = Field(default_factory=list)
    expiry_date: Optional[str] = None
    max_uses: Optional[int] = Field(None, ge=1)
    one_time_code: bool = False
    enabled: bool = True
    promo_note: Optional[str] = Field(None, **_NOTE)
    currency: Optional[str] = Field(None, max_length=10)

    @field_validator("discount_type")
    @classmethod
    def validate_discount_type(cls, v: str) -> str:
        if v not in ("percentage", "fixed"):
            raise ValueError("discount_type must be 'percentage' or 'fixed'")
        return v

    @field_validator("discount_value")
    @classmethod
    def validate_discount_value(cls, v: float, info: Any) -> float:
        if v < 0:
            raise ValueError("discount_value must be non-negative")
        # Validated against discount_type in a model_validator if needed;
        # per-field we cap percentage at 100 using a separate validator below.
        return v

    @field_validator("discount_value", mode="after")
    @classmethod
    def cap_percentage(cls, v: float, info: Any) -> float:
        dt = (info.data or {}).get("discount_type", "")
        if dt == "percentage" and v > 100:
            raise ValueError("Percentage discount cannot exceed 100%")
        return v


class PromoCodeUpdate(BaseModel):
    discount_type: Optional[str] = Field(None, **_SHORT)
    discount_value: Optional[float] = None
    applies_to: Optional[str] = Field(None, **_SHORT)
    applies_to_products: Optional[str] = None
    product_ids: Optional[List[str]] = None
    expiry_date: Optional[str] = None
    max_uses: Optional[int] = Field(None, ge=1)
    one_time_code: Optional[bool] = None
    enabled: Optional[bool] = None
    promo_note: Optional[str] = Field(None, **_NOTE)
    currency: Optional[str] = Field(None, max_length=10)

    @field_validator("discount_type")
    @classmethod
    def validate_discount_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("percentage", "fixed"):
            raise ValueError("discount_type must be 'percentage' or 'fixed'")
        return v

    @field_validator("discount_value")
    @classmethod
    def validate_discount_value(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("discount_value must be non-negative")
        return v

    @field_validator("discount_value", mode="after")
    @classmethod
    def cap_percentage_update(cls, v: Optional[float], info: Any) -> Optional[float]:
        if v is None:
            return v
        dt = (info.data or {}).get("discount_type", "")
        if dt == "percentage" and v > 100:
            raise ValueError("Percentage discount cannot exceed 100%")
        return v


class TermsCreate(BaseModel):
    title: str = Field(**_NAME)
    content: str = Field(**_CONTENT)
    is_default: bool = False
    status: str = "active"


class TermsUpdate(BaseModel):
    title: Optional[str] = Field(None, **_NAME)
    content: Optional[str] = Field(None, **_CONTENT)
    status: Optional[str] = None
    is_default: Optional[bool] = None


class ManualOrderCreate(BaseModel):
    customer_email: str = Field(max_length=320)
    product_id: str
    quantity: int = 1
    inputs: Dict[str, Any] = Field(default_factory=dict)
    subtotal: float
    discount: float = 0.0
    fee: float = 0.0
    status: str = Field("paid", max_length=100)
    currency: str = Field("USD", max_length=10)
    internal_note: Optional[str] = Field("", max_length=5_000)


class ManualSubscriptionCreate(BaseModel):
    customer_email: str = Field(max_length=320)
    product_id: str
    quantity: int = 1
    inputs: Dict[str, Any] = Field(default_factory=dict)
    amount: float
    currency: str = Field("USD", max_length=10)
    renewal_date: str
    start_date: Optional[str] = None
    status: str = Field("active", max_length=100)
    internal_note: Optional[str] = Field("", max_length=5_000)
    term_months: Optional[int] = Field(None, ge=0, le=300)
    auto_cancel_on_termination: bool = False
    reminder_days: Optional[int] = None


class AdminCreateUserRequest(BaseModel):
    email: str = Field(max_length=320)
    full_name: str = Field(max_length=100)
    company_name: Optional[str] = Field("", max_length=100)
    job_title: Optional[str] = Field("", max_length=100)
    phone: Optional[str] = Field("", max_length=50)
    password: str = Field(max_length=128)
    role: str = Field("partner_admin", max_length=100)
    target_tenant_id: Optional[str] = None
    module_permissions: Optional[Dict[str, str]] = None
    access_level: Optional[str] = Field(None, max_length=100)
    modules: Optional[List[str]] = None
    preset_role: Optional[str] = None


class AdminCreateCustomerRequest(BaseModel):
    full_name: str = Field(max_length=100)
    company_name: Optional[str] = Field("", max_length=100)
    job_title: Optional[str] = Field("", max_length=100)
    email: str = Field(max_length=320)
    phone: Optional[str] = Field("", max_length=50)
    password: str = Field(max_length=128)
    line1: Optional[str] = Field("", max_length=100)
    line2: Optional[str] = Field("", max_length=100)
    city: Optional[str] = Field("", max_length=100)
    region: Optional[str] = Field("", max_length=100)
    postal: Optional[str] = Field("", max_length=20)
    country: Optional[str] = Field("", max_length=10)
    mark_verified: bool = True
    profile_meta: Optional[Dict[str, Any]] = None
    tenant_id: Optional[str] = None


class SubscriptionUpdate(BaseModel):
    renewal_date: Optional[str] = None
    start_date: Optional[str] = None
    contract_end_date: Optional[str] = None
    amount: Optional[float] = None
    status: Optional[str] = Field(None, max_length=100)
    plan_name: Optional[str] = Field(None, max_length=100)
    product_id: Optional[str] = None
    customer_id: Optional[str] = None
    payment_method: Optional[str] = Field(None, max_length=100)
    processor_id: Optional[str] = Field(None, max_length=100)
    new_note: Optional[str] = Field(None, max_length=5_000)
    term_months: Optional[int] = Field(None, ge=-1, le=300)  # -1 sentinel to clear term
    auto_cancel_on_termination: Optional[bool] = None
    reminder_days: Optional[int] = None  # -1 sentinel to clear (set to null)


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)


class AddressUpdate(BaseModel):
    line1: Optional[str] = Field(None, max_length=100)
    line2: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    postal: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=10)


class OrderUpdate(BaseModel):
    customer_id: Optional[str] = None
    status: Optional[str] = Field(None, max_length=100)
    payment_method: Optional[str] = Field(None, max_length=100)
    order_date: Optional[str] = None
    payment_date: Optional[str] = None
    subtotal: Optional[float] = None
    fee: Optional[float] = None
    total: Optional[float] = None
    internal_note: Optional[str] = Field(None, max_length=5_000)
    new_note: Optional[str] = Field(None, max_length=5_000)
    subscription_id: Optional[str] = None
    product_id: Optional[str] = None
    processor_id: Optional[str] = Field(None, max_length=100)


class OrderDelete(BaseModel):
    reason: Optional[str] = Field("", max_length=1_000)


class CompleteGoCardlessRedirect(BaseModel):
    redirect_flow_id: str
    session_token: Optional[str] = None
    order_id: Optional[str] = None
    subscription_id: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    subtotal: Optional[float] = None
    discount: float = 0.0
    fee: float = 0.0
    status: str = "paid"
    internal_note: Optional[str] = ""


class ApplyPromoRequest(BaseModel):
    code: str = Field(**_CODE)
    checkout_type: str = Field(**_SHORT)
    product_ids: List[str] = Field(default_factory=list)
    currency: Optional[str] = Field(None, max_length=10)


class ScopeRequestFormData(BaseModel):
    project_summary: Optional[str] = Field("", **_NOTE)
    desired_outcomes: Optional[str] = Field("", **_NOTE)
    apps_involved: Optional[str] = Field("", **_NOTE)
    timeline_urgency: Optional[str] = Field("", max_length=500)
    budget_range: Optional[str] = Field("", max_length=500)
    additional_notes: Optional[str] = Field("", **_NOTE)
    name: Optional[str] = Field("", max_length=100)
    email: Optional[str] = Field("", max_length=320)
    company: Optional[str] = Field("", **_SHORT)
    phone: Optional[str] = Field("", max_length=50)
    message: Optional[str] = Field("", **_NOTE)
    extra_fields: Optional[Dict[str, Any]] = None


class ScopeRequestWithForm(BaseModel):
    items: List[CartItemInput]
    form_data: ScopeRequestFormData


class CategoryCreate(BaseModel):
    name: str = Field(**_NAME)
    description: str = Field("", **_NOTE)
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, **_NAME)
    description: Optional[str] = Field(None, **_NOTE)
    is_active: Optional[bool] = None


class AdminProductCreate(BaseModel):
    name: str = Field(**_NAME)
    card_tag: Optional[str] = Field(None, max_length=100)
    card_description: Optional[str] = Field(None, **_NOTE)
    card_bullets: Optional[List[str]] = None
    description_long: str = Field("", **_CONTENT)
    bullets: List[str] = Field(default_factory=list)
    category: str = Field("", max_length=100)
    faqs: List[Dict[str, str]] = Field(default_factory=list)
    terms_id: Optional[str] = None
    base_price: float = Field(0.0, ge=0)
    is_subscription: bool = False
    stripe_price_id: Optional[str] = Field(None, max_length=100)
    pricing_type: str = "internal"
    external_url: Optional[str] = Field(None, max_length=2048)
    is_active: bool = True
    visible_to_customers: List[str] = Field(default_factory=list)
    restricted_to: List[str] = Field(default_factory=list)
    visibility_conditions: Optional[ProductVisRuleSet] = None
    intake_schema_json: Optional[IntakeSchemaJson] = None
    price_rounding: Optional[str] = None
    show_price_breakdown: Optional[bool] = False
    custom_sections: Optional[List[CustomSection]] = None
    display_layout: Optional[str] = "standard"
    currency: str = Field("USD", max_length=10)
    enquiry_form_id: Optional[str] = None
    default_term_months: Optional[int] = Field(None, ge=0, le=300)
    billing_type: Optional[str] = "prorata"


class AppSettingsUpdate(BaseModel):
    stripe_public_key: Optional[str] = Field(None, max_length=500)
    stripe_secret_key: Optional[str] = Field(None, max_length=500)
    gocardless_token: Optional[str] = Field(None, max_length=500)
    resend_api_key: Optional[str] = Field(None, max_length=500)
    primary_color: Optional[str] = Field(None, max_length=30)
    secondary_color: Optional[str] = Field(None, max_length=30)
    accent_color: Optional[str] = Field(None, max_length=30)
    danger_color: Optional[str] = Field(None, max_length=30)
    success_color: Optional[str] = Field(None, max_length=30)
    warning_color: Optional[str] = Field(None, max_length=30)
    background_color: Optional[str] = Field(None, max_length=30)
    card_color: Optional[str] = Field(None, max_length=30)
    surface_color: Optional[str] = Field(None, max_length=30)
    text_color: Optional[str] = Field(None, max_length=30)
    border_color: Optional[str] = Field(None, max_length=30)
    muted_color: Optional[str] = Field(None, max_length=30)
    logo_url: Optional[str] = Field(None, max_length=2048)
    favicon_url: Optional[str] = Field(None, max_length=2048)
    store_name: Optional[str] = Field(None, max_length=100)


class WebsiteSettingsUpdate(BaseModel):
    # Store Hero
    hero_label: Optional[str] = None
    hero_title: Optional[str] = None
    hero_subtitle: Optional[str] = None
    # Auth Pages
    login_title: Optional[str] = None
    login_subtitle: Optional[str] = None
    login_portal_label: Optional[str] = None
    register_title: Optional[str] = None
    register_subtitle: Optional[str] = None
    # Contact
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_address: Optional[str] = None
    # Footer & Nav
    footer_tagline: Optional[str] = None
    footer_copyright: Optional[str] = None
    nav_store_label: Optional[str] = None
    nav_articles_label: Optional[str] = None
    nav_portal_label: Optional[str] = None
    nav_intake_label: Optional[str] = None
    nav_intake_enabled: Optional[bool] = None
    # Intake form page
    intake_form_page_title: Optional[str] = None
    intake_form_page_subtitle: Optional[str] = None
    # Forms (text labels)
    scope_form_title: Optional[str] = None
    scope_form_subtitle: Optional[str] = None
    signup_form_title: Optional[str] = None
    signup_form_subtitle: Optional[str] = None
    # Form schemas (JSON strings — larger limit)
    scope_form_schema: Optional[str] = None
    signup_form_schema: Optional[str] = None
    partner_signup_form_schema: Optional[str] = None
    # Email templates
    email_from_name: Optional[str] = None
    email_article_subject_template: Optional[str] = None
    email_article_cta_text: Optional[str] = None
    email_article_footer_text: Optional[str] = None
    email_verification_subject: Optional[str] = None
    email_verification_body: Optional[str] = None
    # Error / UI messages
    msg_cart_empty: Optional[str] = None
    msg_quote_success: Optional[str] = None
    msg_scope_success: Optional[str] = None
    # Payment display
    payment_gocardless_label: Optional[str] = None
    payment_gocardless_description: Optional[str] = None
    payment_stripe_label: Optional[str] = None
    payment_stripe_description: Optional[str] = None
    # Articles hero
    articles_hero_label: Optional[str] = None
    articles_hero_title: Optional[str] = None
    articles_hero_subtitle: Optional[str] = None
    # Checkout page configuration
    checkout_partner_enabled: Optional[bool] = None
    checkout_partner_title: Optional[str] = None
    checkout_partner_description: Optional[str] = None
    checkout_partner_options: Optional[str] = None
    checkout_partner_misrep_warning: Optional[str] = None
    checkout_extra_schema: Optional[str] = None
    # Dynamic checkout sections (JSON list of sections with form fields)
    checkout_sections: Optional[str] = None
    # Checkout success page
    checkout_success_title: Optional[str] = None
    checkout_success_paid_msg: Optional[str] = None
    checkout_success_pending_msg: Optional[str] = None
    checkout_success_expired_msg: Optional[str] = None
    checkout_success_next_steps_title: Optional[str] = None
    checkout_success_step_1: Optional[str] = None
    checkout_success_step_2: Optional[str] = None
    checkout_success_step_3: Optional[str] = None
    checkout_portal_link_text: Optional[str] = None
    # Bank transfer success page
    bank_success_title: Optional[str] = None
    bank_success_message: Optional[str] = None
    bank_instructions_title: Optional[str] = None
    bank_instruction_1: Optional[str] = None
    bank_instruction_2: Optional[str] = None
    bank_instruction_3: Optional[str] = None
    bank_next_steps_title: Optional[str] = None
    bank_next_step_1: Optional[str] = None
    bank_next_step_2: Optional[str] = None
    bank_next_step_3: Optional[str] = None
    # 404 page
    page_404_title: Optional[str] = None
    page_404_link_text: Optional[str] = None
    # GoCardless callback page
    gocardless_processing_title: Optional[str] = None
    gocardless_processing_subtitle: Optional[str] = None
    gocardless_success_title: Optional[str] = None
    gocardless_success_message: Optional[str] = None
    gocardless_error_title: Optional[str] = None
    gocardless_error_message: Optional[str] = None
    gocardless_return_btn_text: Optional[str] = None
    # Verify email page
    verify_email_label: Optional[str] = None
    verify_email_title: Optional[str] = None
    verify_email_subtitle: Optional[str] = None
    # Portal page
    portal_title: Optional[str] = None
    portal_subtitle: Optional[str] = None
    portal_show_stats: Optional[bool] = None
    # Profile page
    profile_label: Optional[str] = None
    profile_title: Optional[str] = None
    profile_subtitle: Optional[str] = None
    # Cart page
    cart_title: Optional[str] = None
    cart_clear_btn_text: Optional[str] = None
    msg_currency_unsupported: Optional[str] = None
    msg_no_payment_methods: Optional[str] = None
    # Footer extras
    footer_about_title: Optional[str] = None
    footer_about_text: Optional[str] = None
    footer_nav_title: Optional[str] = None
    footer_contact_title: Optional[str] = None
    footer_social_title: Optional[str] = None
    social_twitter: Optional[str] = None
    social_linkedin: Optional[str] = None
    social_facebook: Optional[str] = None
    social_instagram: Optional[str] = None
    social_youtube: Optional[str] = None
    # Admin panel page
    admin_page_badge: Optional[str] = None
    admin_page_title: Optional[str] = None
    admin_page_subtitle: Optional[str] = None
    # Documents page customization
    nav_documents_label: Optional[str] = None
    documents_page_title: Optional[str] = None
    documents_page_subtitle: Optional[str] = None
    documents_page_upload_label: Optional[str] = None
    documents_page_upload_hint: Optional[str] = None
    documents_page_empty_text: Optional[str] = None
    # Signup page bullets
    signup_bullet_1: Optional[str] = None
    signup_bullet_2: Optional[str] = None
    signup_bullet_3: Optional[str] = None
    signup_cta: Optional[str] = None

    # JSON schema fields that need a larger budget; body text ≤ 500; title fields ≤ 100
    _JSON_FIELDS = frozenset({
        "scope_form_schema", "signup_form_schema", "partner_signup_form_schema",
        "checkout_extra_schema", "checkout_sections", "email_verification_body",
    })

    from pydantic import model_validator

    @model_validator(mode="before")
    @classmethod
    def _cap_string_lengths(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        json_fields = {
            "scope_form_schema", "signup_form_schema", "partner_signup_form_schema",
            "checkout_extra_schema", "checkout_sections", "email_verification_body",
        }
        body_fields = {
            "hero_subtitle", "articles_hero_subtitle",
            "login_subtitle", "register_subtitle",
            "signup_form_subtitle", "scope_form_subtitle", "intake_form_page_subtitle",
            "verify_email_subtitle", "portal_subtitle", "profile_subtitle",
            "admin_page_subtitle", "documents_page_subtitle",
            "gocardless_processing_subtitle",
            "msg_cart_empty", "msg_quote_success", "msg_scope_success",
            "msg_currency_unsupported", "msg_no_payment_methods",
            "checkout_success_paid_msg", "checkout_success_pending_msg",
            "checkout_success_expired_msg",
            "checkout_success_step_1", "checkout_success_step_2", "checkout_success_step_3",
            "checkout_partner_description", "checkout_partner_misrep_warning",
            "bank_success_message", "bank_instruction_1", "bank_instruction_2", "bank_instruction_3",
            "bank_next_step_1", "bank_next_step_2", "bank_next_step_3",
            "gocardless_success_message", "gocardless_error_message",
            "footer_about_text", "contact_address",
            "payment_gocardless_description", "payment_stripe_description",
            "email_article_footer_text",
            "signup_bullet_1", "signup_bullet_2", "signup_bullet_3",
            "documents_page_upload_hint", "documents_page_empty_text",
            "email_article_subject_template", "email_verification_subject",
            "sdp_configure_price_subtitle", "sdp_wizard_review_subtitle",
        }
        # Social/external URL fields — allow up to 2,048 chars
        url_fields = {
            "social_twitter", "social_linkedin", "social_facebook",
            "social_instagram", "social_youtube",
        }
        # Only validate fields declared in this model (extra fields are ignored by Pydantic)
        declared = set(cls.model_fields.keys())
        for key, val in values.items():
            if key not in declared:
                continue
            if not isinstance(val, str) or not val:
                continue
            if key in json_fields:
                limit = 100_000
            elif key in body_fields:
                limit = 500
            elif key in url_fields:
                limit = 2_048
            else:
                limit = 100
            if len(val) > limit:
                raise ValueError(
                    f"'{key}' exceeds the maximum allowed length of {limit:,} characters "
                    f"(got {len(val):,})"
                )
        return values


class QuoteRequest(BaseModel):
    product_id: str = Field(max_length=100)
    product_name: str = Field(max_length=100)
    name: str = Field(max_length=100)
    email: str = Field(max_length=320)
    company: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    message: Optional[str] = Field(None, max_length=5_000)
    extra_fields: Optional[Dict[str, Any]] = None


class ArticleCreate(BaseModel):
    title: str = Field(**_NAME)
    slug: Optional[str] = Field(None, max_length=100)
    category: str = Field(**_SHORT)
    price: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=10)
    content: str = Field("", **_CONTENT)
    visibility: str = "all"
    restricted_to: List[str] = []


class ArticleUpdate(BaseModel):
    title: Optional[str] = Field(None, **_NAME)
    slug: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, **_SHORT)
    price: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=10)
    content: Optional[str] = Field(None, **_CONTENT)
    visibility: Optional[str] = None
    restricted_to: Optional[List[str]] = None


class ArticleEmailRequest(BaseModel):
    customer_ids: List[str] = Field(max_length=1000)
    subject: Optional[str] = Field(None, max_length=500)
    message: Optional[str] = Field(None, **_NOTE)


class ArticleSendEmailRequest(BaseModel):
    to: List[str] = Field(max_length=200)
    cc: Optional[List[str]] = Field(None, max_length=50)
    bcc: Optional[List[str]] = Field(None, max_length=50)
    subject: str = Field(max_length=500)
    html_body: str = Field(**_CONTENT)
    attach_pdf: bool = False


class ArticleEmailTemplateCreate(BaseModel):
    name: str = Field(**_NAME)
    subject: str = Field(max_length=500)
    html_body: str = Field(**_CONTENT)
    description: Optional[str] = Field("", **_NOTE)


class ArticleEmailTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, **_NAME)
    subject: Optional[str] = Field(None, max_length=500)
    html_body: Optional[str] = Field(None, **_CONTENT)
    description: Optional[str] = None


class ArticleCategoryCreate(BaseModel):
    name: str = Field(**_NAME)
    description: Optional[str] = Field("", **_NOTE)
    color: Optional[str] = Field("", max_length=50)
    is_scope_final: Optional[bool] = False


class ArticleCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, **_NAME)
    description: Optional[str] = Field(None, **_NOTE)
    color: Optional[str] = Field(None, max_length=50)
    is_scope_final: Optional[bool] = None


# ── Tax models ────────────────────────────────────────────────────────────────

class TaxSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    country: Optional[str] = None
    state: Optional[str] = None


class TaxOverrideRuleCreate(BaseModel):
    name: str
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    tax_rate: float
    tax_name: str
    priority: int = 0


class TaxCalculateRequest(BaseModel):
    subtotal: float


# Resource model aliases (Articles renamed to Resources)
ResourceCreate = ArticleCreate
ResourceUpdate = ArticleUpdate
ResourceEmailRequest = ArticleEmailRequest
ResourceSendEmailRequest = ArticleSendEmailRequest
ResourceEmailTemplateCreate = ArticleEmailTemplateCreate
ResourceEmailTemplateUpdate = ArticleEmailTemplateUpdate
ResourceCategoryCreate = ArticleCategoryCreate
ResourceCategoryUpdate = ArticleCategoryUpdate
