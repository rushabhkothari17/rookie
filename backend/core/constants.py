"""Application-wide constants. Move runtime-tuneable values to Settings DB over time."""

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

# Pricing
SERVICE_FEE_RATE: float = 0.05  # 5% service fee
PREMIUM_MIGRATION_ITEMS = {"price_list", "multi_currency", "projects", "timesheet"}
STANDARD_MIGRATION_SOURCES = {"quickbooks_online", "sage_50_online", "spreadsheet"}

# Partner tagging
PARTNER_TAG_RESPONSES = ["Yes", "Pre-existing Customer", "Not yet"]

# Articles
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

# Audit
AUDIT_ACTOR_TYPES = ["admin", "user", "system", "webhook"]
AUDIT_SOURCES = ["admin_ui", "customer_ui", "api", "webhook", "cron"]
AUDIT_SEVERITIES = ["info", "warn", "error"]
