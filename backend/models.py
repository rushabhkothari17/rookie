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
    profile_meta: Optional[Dict[str, Any]] = None


class LoginRequest(BaseModel):
    email: str
    password: str
    partner_code: Optional[str] = None   # required for partner/customer login
    login_type: Optional[str] = "partner"  # "partner" | "customer"


class PartnerLoginRequest(BaseModel):
    partner_code: str
    email: str
    password: str


class CustomerLoginRequest(BaseModel):
    partner_code: str
    email: str
    password: str


class TenantCreate(BaseModel):
    name: str
    code: str  # unique slug, used at login
    status: str = "active"
    owner_email: Optional[str] = None  # email of initial partner_super_admin


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None


class CreatePartnerAdminRequest(BaseModel):
    tenant_id: str
    email: str
    full_name: str
    password: str
    role: str = "partner_super_admin"


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


class ResendVerificationRequest(BaseModel):
    email: str


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
    extra_fields: Optional[Dict[str, Any]] = None


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
    extra_fields: Optional[Dict[str, Any]] = None


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
    # Permission fields
    access_level: Optional[str] = "full_access"
    modules: Optional[List[str]] = None
    preset_role: Optional[str] = None


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
    extra_fields: Optional[Dict[str, Any]] = None


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
    restricted_to: List[str] = Field(default_factory=list)
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
    danger_color: Optional[str] = None
    success_color: Optional[str] = None
    warning_color: Optional[str] = None
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    border_color: Optional[str] = None
    muted_color: Optional[str] = None
    logo_url: Optional[str] = None
    store_name: Optional[str] = None


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
    # Forms (text labels)
    quote_form_title: Optional[str] = None
    quote_form_subtitle: Optional[str] = None
    quote_form_response_time: Optional[str] = None
    scope_form_title: Optional[str] = None
    scope_form_subtitle: Optional[str] = None
    signup_form_title: Optional[str] = None
    signup_form_subtitle: Optional[str] = None
    # Form schemas (JSON strings)
    quote_form_schema: Optional[str] = None
    scope_form_schema: Optional[str] = None
    signup_form_schema: Optional[str] = None
    # Email templates
    email_from_name: Optional[str] = None
    email_article_subject_template: Optional[str] = None
    email_article_cta_text: Optional[str] = None
    email_article_footer_text: Optional[str] = None
    email_verification_subject: Optional[str] = None
    email_verification_body: Optional[str] = None
    # Error / UI messages
    msg_partner_tagging_prompt: Optional[str] = None
    msg_override_required: Optional[str] = None
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
    checkout_zoho_enabled: Optional[bool] = None
    checkout_zoho_title: Optional[str] = None
    checkout_zoho_subscription_options: Optional[str] = None
    checkout_zoho_product_options: Optional[str] = None
    checkout_zoho_signup_note: Optional[str] = None
    checkout_zoho_access_note: Optional[str] = None
    checkout_zoho_access_delay_warning: Optional[str] = None
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
    # Bank transaction form
    bank_transaction_sources: Optional[str] = None
    bank_transaction_types: Optional[str] = None
    bank_transaction_statuses: Optional[str] = None


class QuoteRequest(BaseModel):
    product_id: str
    product_name: str
    name: str
    email: str
    company: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    extra_fields: Optional[Dict[str, Any]] = None


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


class ArticleSendEmailRequest(BaseModel):
    to: List[str]
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    subject: str
    html_body: str
    attach_pdf: bool = False


class ArticleEmailTemplateCreate(BaseModel):
    name: str
    subject: str
    html_body: str
    description: Optional[str] = ""


class ArticleEmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    html_body: Optional[str] = None
    description: Optional[str] = None


class ArticleCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    color: Optional[str] = ""
    is_scope_final: Optional[bool] = False


class ArticleCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    is_scope_final: Optional[bool] = None
