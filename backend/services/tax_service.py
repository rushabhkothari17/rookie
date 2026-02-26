"""Core tax calculation service.

Hierarchy (first match wins):
  1. Customer marked tax_exempt → 0%
  2. Partner tax collection disabled → 0%
  3. Partner-specific override rule (conditions match) → override rate
  4. Destination-based static tax table (CA/US/GB/AU/IN/EU) → static rate
  5. Everything else → 0%
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from db.session import db
from services.tax_tables import (
    CANADA_PROVINCES, CANADA_FEDERAL_GST,
    US_STATES, UK_RATE, AU_RATE, IN_RATE, EU_VAT_RATES, EU_COUNTRY_CODES,
)

logger = logging.getLogger(__name__)


# ── Override rule helpers ──────────────────────────────────────────────────────

def _eval_condition(condition: dict, customer: dict, address: dict) -> bool:
    field = condition.get("field", "")
    operator = condition.get("operator", "equals")
    value = str(condition.get("value", "")).strip()

    field_map: Dict[str, str] = {
        "country": str((address or {}).get("country", "")).strip(),
        "state": str((address or {}).get("region", "")).strip(),
        "email": str(customer.get("email", "")).strip(),
        "company_name": str(customer.get("company_name", "")).strip(),
    }
    actual = field_map.get(field, str(customer.get(field, "")).strip())

    if operator == "equals":
        return actual.lower() == value.lower()
    if operator == "not_equals":
        return actual.lower() != value.lower()
    if operator == "contains":
        return value.lower() in actual.lower()
    if operator == "not_contains":
        return value.lower() not in actual.lower()
    if operator == "empty":
        return not actual
    if operator == "not_empty":
        return bool(actual)
    return False


def _rule_matches(rule: dict, customer: dict, address: dict) -> bool:
    """All conditions must match (AND logic)."""
    conditions = rule.get("conditions", [])
    if not conditions:
        return True  # no conditions → match-all
    return all(_eval_condition(c, customer, address) for c in conditions)


# ── Destination tax logic ──────────────────────────────────────────────────────

def _destination_rate(
    partner_country: str,
    partner_state: str,
    customer_country: str,
    customer_state: str,
) -> Optional[Dict[str, Any]]:
    """Return {rate, label} or None if no tax applies."""
    pc = partner_country.upper()
    ps = partner_state.upper()
    cc = customer_country.upper()
    cs = customer_state.upper()

    # ── Canada ─────────────────────────────────────────────────────────────
    if pc == "CA":
        if cc != "CA":
            return None  # export → 0 %
        province = CANADA_PROVINCES.get(cs)
        if not province:
            return {"rate": CANADA_FEDERAL_GST, "label": "GST"}
        if province["hst"]:
            return {"rate": province["rate"], "label": province["label"]}
        # non-HST province
        if cs == ps:
            return {"rate": province["rate"], "label": province["label"]}
        return {"rate": CANADA_FEDERAL_GST, "label": "GST"}

    # ── United States ───────────────────────────────────────────────────────
    if pc == "US":
        if cc != "US":
            return None
        state = US_STATES.get(cs)
        if not state or state["rate"] == 0:
            return None
        return {"rate": state["rate"], "label": state["label"]}

    # ── United Kingdom ──────────────────────────────────────────────────────
    if pc == "GB":
        if cc == "GB":
            return {"rate": UK_RATE["rate"], "label": UK_RATE["label"]}
        return None

    # ── Australia ───────────────────────────────────────────────────────────
    if pc == "AU":
        if cc == "AU":
            return {"rate": AU_RATE["rate"], "label": AU_RATE["label"]}
        return None

    # ── India ────────────────────────────────────────────────────────────────
    if pc == "IN":
        if cc == "IN":
            return {"rate": IN_RATE["rate"], "label": IN_RATE["label"]}
        return None

    # ── European Union ───────────────────────────────────────────────────────
    if pc in EU_COUNTRY_CODES:
        if cc in EU_VAT_RATES:
            vat = EU_VAT_RATES[cc]
            return {"rate": vat["rate"], "label": vat["label"]}
        return None

    return None


# ── Public API ─────────────────────────────────────────────────────────────────

async def calculate_tax(
    subtotal: float,
    tenant_id: str,
    customer_id: str,
) -> Dict[str, Any]:
    """Calculate tax for a given subtotal.

    Returns:
        {tax_amount, tax_rate, tax_name, tax_details}
    """
    null_result: Dict[str, Any] = {
        "tax_amount": 0.0,
        "tax_rate": 0.0,
        "tax_name": None,
        "tax_details": None,
    }

    if not tenant_id or not customer_id or subtotal <= 0:
        return null_result

    # 1. Customer record + tax-exempt check
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        return null_result
    if customer.get("tax_exempt"):
        return {
            "tax_amount": 0.0, "tax_rate": 0.0,
            "tax_name": "Tax Exempt",
            "tax_details": {"reason": "customer_exempt"},
        }

    # 2. Partner tax settings
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        return null_result
    tax_settings: Dict[str, Any] = tenant.get("tax_settings") or {}
    if not tax_settings.get("enabled", False):
        return null_result

    partner_country = str(tax_settings.get("country", "")).upper().strip()
    partner_state = str(tax_settings.get("state", "")).upper().strip()
    if not partner_country:
        return null_result

    # 3. Customer address
    address = await db.addresses.find_one({"customer_id": customer_id}, {"_id": 0}) or {}
    customer_country = str(address.get("country", "")).upper().strip()
    customer_state = str(address.get("region", "")).upper().strip()

    # 4. Partner override rules (highest priority first)
    rules = await db.tax_override_rules.find(
        {"tenant_id": tenant_id, "enabled": {"$ne": False}},
        {"_id": 0},
    ).sort("priority", -1).to_list(100)

    for rule in rules:
        if _rule_matches(rule, customer, address):
            rate = float(rule.get("tax_rate", 0.0))
            return {
                "tax_amount": round(subtotal * rate, 2),
                "tax_rate": rate,
                "tax_name": rule.get("tax_name", "Tax"),
                "tax_details": {"source": "override", "rule_name": rule.get("name", "")},
            }

    # 5. Destination-based static rates
    rate_data = _destination_rate(partner_country, partner_state, customer_country, customer_state)
    if not rate_data:
        return null_result

    rate = rate_data["rate"]
    return {
        "tax_amount": round(subtotal * rate, 2),
        "tax_rate": rate,
        "tax_name": rate_data["label"],
        "tax_details": {
            "source": "destination",
            "partner_country": partner_country,
            "customer_country": customer_country,
        },
    }
