"""Pricing calculation service."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException
from core.constants import (
    SERVICE_FEE_RATE,
    PREMIUM_MIGRATION_ITEMS,
    STANDARD_MIGRATION_SOURCES,
)
from core.helpers import (
    round_cents,
    round_to_nearest_99,
    round_nearest_25,
    round_nearest,
)


def calculate_books_migration_price(inputs: Dict[str, Any], rules: Dict[str, Any] = None) -> Dict[str, Any]:
    if rules is None:
        rules = {}
    base_fee = float(rules.get("base_fee", 999.0))
    per_year_up_to_5 = float(rules.get("per_year_up_to_5", 350.0))
    per_year_over_5 = float(rules.get("per_year_over_5", 300.0))
    premium_multiplier = float(rules.get("premium_multiplier", 1.5))
    source_multiplier = float(rules.get("source_multiplier", 1.2))
    standard_sources = set(rules.get("standard_sources", list(STANDARD_MIGRATION_SOURCES)))

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

    base = base_fee
    if years > 1:
        extra = years - 1
        up_to_5 = min(extra, 4)
        over_5 = max(0, extra - 4)
        base += up_to_5 * per_year_up_to_5 + over_5 * per_year_over_5
    if has_premium:
        base *= premium_multiplier
    if source_system not in standard_sources:
        base *= source_multiplier

    price = round_to_nearest_99(base)
    line_items = [{"label": f"Migration ({years}Y + YTD)", "amount": base_fee}]
    if years > 1:
        extra = years - 1
        up_to_5 = min(extra, 4)
        over_5 = max(0, extra - 4)
        if up_to_5:
            line_items.append({"label": f"+{up_to_5} additional year(s) × ${per_year_up_to_5:.0f}", "amount": up_to_5 * per_year_up_to_5})
        if over_5:
            line_items.append({"label": f"+{over_5} additional year(s) × ${per_year_over_5:.0f}", "amount": over_5 * per_year_over_5})
    if has_premium:
        line_items.append({"label": f"Premium features ({premium_multiplier}× multiplier)", "amount": 0})
    if source_system not in standard_sources:
        line_items.append({"label": f"Source system complexity ({source_multiplier}× multiplier)", "amount": 0})
    return {"subtotal": float(price), "line_items": line_items}


def build_price_inputs(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    pricing_type = product.get("pricing_type")
    rules = product.get("pricing_rules", {})
    if pricing_type == "tiered":
        return [{"id": "variant", "label": "Select option", "type": "select", "options": rules.get("variants", [])}]
    if pricing_type == "calculator":
        calc_type = rules.get("calc_type")
        if calc_type == "health_check":
            return [{"id": "creator_extension", "label": "Creator/Catalyst extension", "type": "select", "options": rules.get("add_ons", [])}]
        if calc_type == "hours_pack":
            return [
                {"id": "hours", "label": "Hours per month", "type": "number", "min": rules.get("min_hours"), "max": rules.get("max_hours"), "step": rules.get("step")},
                {"id": "payment_option", "label": "Payment option", "type": "select", "options": [{"id": "pay_now", "label": "Pay Now"}, {"id": "scope_later", "label": "Scope & Pay Later"}]},
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
            return [{"id": "tables", "label": "Tables/Modules", "type": "number", "min": 1}, {"id": "records", "label": "Records", "type": "number", "min": 1}]
        if calc_type == "forms_migration":
            return [
                {"id": "forms_with_validation", "label": "Forms with validation", "type": "number", "min": 0},
                {"id": "forms_without_validation", "label": "Forms without validation", "type": "number", "min": 0},
                {"id": "total_fields", "label": "Total fields", "type": "number", "min": 0},
                {"id": "email_notifications", "label": "Email notifications", "type": "number", "min": 0},
            ]
        if calc_type == "desk_migration":
            return [{"id": "departments", "label": "Departments", "type": "number", "min": 1}, {"id": "tickets", "label": "Tickets", "type": "number", "min": 0}, {"id": "kb_articles", "label": "KB articles", "type": "number", "min": 0}]
        if calc_type == "sign_migration":
            return [{"id": "templates", "label": "Templates", "type": "number", "min": 1}, {"id": "workdrive_docs", "label": "WorkDrive documents", "type": "number", "min": 0}]
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

    if pricing_type in ("fixed", "simple", None, ""):
        subtotal = float(product.get("base_price") or 0.0)
        if subtotal > 0:
            line_items.append({"label": product["name"], "amount": subtotal})

        # Apply intake-based price adjustments (dropdown / multiselect with affects_price=true)
        schema = product.get("intake_schema_json")
        if schema and subtotal >= 0:
            intake_qs = schema.get("questions", {})
            for q_type in ("dropdown", "multiselect"):
                for q in intake_qs.get(q_type, []):
                    if not q.get("affects_price") or not q.get("enabled"):
                        continue
                    price_mode = q.get("price_mode", "add")
                    raw_val = inputs.get(q["key"])
                    if raw_val is None:
                        continue
                    selected = [raw_val] if isinstance(raw_val, str) else (raw_val if isinstance(raw_val, list) else [])
                    for opt in q.get("options", []):
                        if opt.get("value") in selected:
                            pv = float(opt.get("price_value") or 0)
                            if pv == 0:
                                continue
                            if price_mode == "add":
                                subtotal += pv
                                line_items.append({"label": f"{q['label']}: {opt['label']}", "amount": round_cents(pv)})
                            elif price_mode == "multiply":
                                new_sub = round_cents(subtotal * pv)
                                line_items.append({"label": f"{q['label']}: {opt['label']} (×{pv})", "amount": round_cents(new_sub - subtotal)})
                                subtotal = new_sub

        # Product-level price rounding
        price_rounding = product.get("price_rounding")
        if price_rounding and subtotal > 0:
            nearest = {"25": 25, "50": 50, "100": 100}.get(str(price_rounding))
            if nearest:
                subtotal = round_nearest(subtotal, nearest)

    elif pricing_type == "tiered":
        variants = rules.get("variants", [])
        variant_id = inputs.get("variant") or (variants[0]["id"] if variants else None)
        variant = next((v for v in variants if v["id"] == variant_id), variants[0] if variants else None)
        if not variant:
            raise HTTPException(status_code=400, detail="Invalid option")
        subtotal = float(variant["price"])
        line_items.append({"label": f"{product['name']} — {variant['label']}", "amount": subtotal})
    elif pricing_type == "scope_request":
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
            add_on = next((a for a in rules.get("add_ons", []) if a["id"] == add_on_id), rules.get("add_ons", [])[0] if rules.get("add_ons") else None)
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
            forms_with = max(0, int(inputs.get("forms_with_validation", 0)))
            forms_without = max(0, int(inputs.get("forms_without_validation", 0)))
            fields = max(0, int(inputs.get("total_fields", 0)))
            notifications = max(0, int(inputs.get("email_notifications", 0)))
            subtotal = forms_with * 200.0 + forms_without * 100.0 + fields * 1.0 + notifications * 25.0
            line_items += [
                {"label": "Forms with validation", "amount": forms_with * 200.0},
                {"label": "Forms without validation", "amount": forms_without * 100.0},
                {"label": "Total fields", "amount": fields * 1.0},
                {"label": "Email notifications", "amount": notifications * 25.0},
            ]
        elif calc_type == "desk_migration":
            departments = max(1, int(inputs.get("departments", 1)))
            tickets = max(0, int(inputs.get("tickets", 0)))
            kb_articles = max(0, int(inputs.get("kb_articles", 0)))
            subtotal = departments * 499.0 + tickets * 0.10 + kb_articles * 25.0
            line_items += [
                {"label": "Departments", "amount": departments * 499.0},
                {"label": "Tickets", "amount": round_cents(tickets * 0.10)},
                {"label": "KB articles", "amount": kb_articles * 25.0},
            ]
        elif calc_type == "sign_migration":
            templates = max(1, int(inputs.get("templates", 1)))
            workdrive_docs = max(0, int(inputs.get("workdrive_docs", 0)))
            subtotal = templates * 99.0 + workdrive_docs * 5.0
            line_items += [{"label": "Templates", "amount": templates * 99.0}, {"label": "WorkDrive docs", "amount": workdrive_docs * 5.0}]
        elif calc_type == "people_migration":
            base_fee = float(rules.get("base_fee", 999.0))
            leave_policies = max(0, int(inputs.get("leave_policies", 0)))
            leave_requests = max(0, int(inputs.get("leave_requests", 0)))
            timesheets = max(0, int(inputs.get("timesheets", 0)))
            attendance = max(0, int(inputs.get("attendance", 0)))
            employee_docs = max(0, int(inputs.get("employee_docs", 0)))
            employee_profiles = max(0, int(inputs.get("employee_profiles", 0)))
            templates = max(0, int(inputs.get("templates", 0)))
            subtotal = (base_fee + leave_policies * 99.0 + leave_requests * 1.0 + timesheets * 0.10 + attendance * 0.10 + employee_docs * 5.0 + employee_profiles * 50.0 + templates * 50.0)
            line_items += [
                {"label": "Base setup", "amount": base_fee},
                {"label": "Leave policies", "amount": leave_policies * 99.0},
                {"label": "Leave requests", "amount": leave_requests * 1.0},
                {"label": "Timesheets", "amount": round_cents(timesheets * 0.10)},
                {"label": "Attendance", "amount": round_cents(attendance * 0.10)},
                {"label": "Employee docs", "amount": employee_docs * 5.0},
                {"label": "Employee profiles", "amount": employee_profiles * 50.0},
                {"label": "Templates", "amount": templates * 50.0},
            ]
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
