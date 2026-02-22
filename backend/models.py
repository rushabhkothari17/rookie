"""Pydantic request/response models for Automate Accounts API."""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class AddressInput(BaseModel):
    line1: str
    line2: str = ""
    city: str
    region: str
    postal: str
    country: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    company_name: str = ""
    job_title: str = ""
    phone: str = ""
    address: AddressInput


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


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


class CheckoutSessionRequestBody(BaseModel):
    items: List[CartItemInput]
    checkout_type: str
    origin_url: str
    promo_code: Optional[str] = None
    terms_accepted: bool = False
    terms_id: Optional[str] = None
    start_date: Optional[str] = None
    partner_tag_response: Optional[str] = None
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
    start_date: Optional[str] = None
    partner_tag_response: Optional[str] = None
    override_code: Optional[str] = None
    zoho_subscription_type: Optional[str] = None
    current_zoho_product: Optional[str] = None
    zoho_account_access: Optional[str] = None


class ScopeRequestBody(BaseModel):
    items: List[CartItemInput]


class CancelSubscriptionBody(BaseModel):
    reason: Optional[str] = ""


class IntakeOption(BaseModel):
    label: str
    value: str
    price_value: float = 0.0


class IntakeQuestion(BaseModel):
    key: str
    label: str
    helper_text: Optional[str] = ""
    required: bool = False
    enabled: bool = True
    order: int = 0
    affects_price: bool = False
    price_mode: str = "add"
    options: Optional[List[IntakeOption]] = None


class IntakeQuestionsBlock(BaseModel):
    dropdown: List[IntakeQuestion] = Field(default_factory=list)
    multiselect: List[IntakeQuestion] = Field(default_factory=list)
    single_line: List[IntakeQuestion] = Field(default_factory=list)
    multi_line: List[IntakeQuestion] = Field(default_factory=list)


class IntakeSchemaJson(BaseModel):
    version: int = 1
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None
    questions: IntakeQuestionsBlock = Field(default_factory=IntakeQuestionsBlock)


class CustomSection(BaseModel):
    id: str = ""
    name: str
    content: str = ""
    icon: Optional[str] = None
    icon_color: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    order: int = 0


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
    intake_schema_json: Optional[IntakeSchemaJson] = None
    price_rounding: Optional[str] = None
    custom_sections: Optional[List[CustomSection]] = None


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
    discount_type: str
    discount_value: float
    applies_to: str
    applies_to_products: str = "all"
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
    expires_at: Optional[str] = None


class OverrideCodeUpdate(BaseModel):
    code: Optional[str] = None
    customer_id: Optional[str] = None
    status: Optional[str] = None
    expires_at: Optional[str] = None


class CustomerPartnerMapUpdate(BaseModel):
    partner_map: str


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
    processor_id: Optional[str] = None
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
    processor_id: Optional[str] = None


class OrderDelete(BaseModel):
    reason: Optional[str] = ""


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
    code: str
    checkout_type: str


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
    intake_schema_json: Optional[IntakeSchemaJson] = None
    price_rounding: Optional[str] = None
    custom_sections: Optional[List[CustomSection]] = None


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
    date: str
    source: str
    transaction_id: Optional[str] = None
    type: str
    amount: float
    fees: Optional[float] = 0.0
    net_amount: Optional[float] = None
    currency: Optional[str] = "USD"
    status: str
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
