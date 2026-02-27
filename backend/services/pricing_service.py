"""Pricing calculation service — simplified data-driven model.

Pricing types:
  internal  — base_price + intake question add-ons/multipliers → checkout
  external  — redirects to external_url, no checkout
  enquiry   — contact/scoping form, no checkout
"""

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional
from fastapi import HTTPException

SERVICE_FEE_RATE = 0.0


def round_cents(v: float) -> float:
    return math.ceil(v * 100) / 100


def round_nearest(v: float, nearest: int) -> float:
    return math.ceil(v / nearest) * nearest


def _calculate_tiered_price(val: float, tiers: List[Dict]) -> float:
    """Progressive tiered pricing — each tier covers its quantity range."""
    total = 0.0
    for tier in sorted(tiers, key=lambda t: float(t.get("from", 0))):
        from_v = float(tier.get("from", 0))
        to_v = tier.get("to")
        ppu = float(tier.get("price_per_unit", 0))
        if val <= from_v:
            break
        qty_in_tier = (val - from_v) if to_v is None else (min(val, float(to_v)) - from_v)
        if qty_in_tier > 0:
            total += qty_in_tier * ppu
    return round_cents(total)


# ── Safe formula evaluator ─────────────────────────────────────────────────────
import ast
import operator as _op

_SAFE_OPS = {
    ast.Add: _op.add, ast.Sub: _op.sub,
    ast.Mult: _op.mul, ast.Div: _op.truediv,
}


def _eval_formula_node(node: ast.AST, ctx: Dict[str, float]) -> float:
    """Recursively evaluate a safe AST node. Supports +,-,*,/ and field refs."""
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        return float(ctx.get(node.id, 0) or 0)
    if isinstance(node, ast.BinOp):
        fn = _SAFE_OPS.get(type(node.op))
        if fn is None:
            return 0.0
        r = _eval_formula_node(node.right, ctx)
        if isinstance(node.op, ast.Div) and r == 0:
            return 0.0
        return fn(_eval_formula_node(node.left, ctx), r)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_formula_node(node.operand, ctx)
    return 0.0


def eval_formula_expression(expr: str, ctx: Dict[str, float]) -> float:
    """Safely evaluate formula like 'employees * monthly_rate * 0.8'."""
    try:
        tree = ast.parse(expr.strip(), mode="eval")
        result = _eval_formula_node(tree.body, ctx)
        return round_cents(max(0.0, result))
    except Exception:
        return 0.0


# ── Intake schema helpers ──────────────────────────────────────────────────────

def _get_intake_questions(schema: Any) -> List[Dict]:
    """Return a flat, ordered list of intake questions.

    Handles both the legacy grouped format (dict with dropdown/multiselect/
    single_line/multi_line keys) and the new flat array format.
    """
    if not schema:
        return []
    questions = schema.get("questions", [])

    if isinstance(questions, dict):
        # Legacy grouped format → flatten with type field
        flat: List[Dict] = []
        type_map = {
            "dropdown": "dropdown",
            "multiselect": "multiselect",
            "single_line": "single_line",
            "multi_line": "multi_line",
        }
        for key, q_type in type_map.items():
            for q in questions.get(key, []):
                flat.append({**q, "type": q_type})
        return sorted(flat, key=lambda x: x.get("order", 0))

    # New flat format — already typed
    return sorted(questions, key=lambda x: x.get("order", 0))


# ── Main calculator ────────────────────────────────────────────────────────────

def calculate_price(
    product: Dict[str, Any],
    inputs: Dict[str, Any],
    fee_rate: float = SERVICE_FEE_RATE,
) -> Dict[str, Any]:
    pricing_type = product.get("pricing_type", "internal")
    is_subscription = bool(product.get("is_subscription"))

    # ── External ──────────────────────────────────────────────────────────────
    if pricing_type == "external":
        external_url = (
            product.get("external_url")
            or product.get("pricing_rules", {}).get("external_url")
        )
        return {
            "subtotal": 0.0,
            "fee": 0.0,
            "total": 0.0,
            "line_items": [],
            "requires_checkout": False,
            "is_subscription": is_subscription,
            "is_enquiry": False,
            "external_url": external_url,
        }

    # ── Enquiry ───────────────────────────────────────────────────────────────
    if pricing_type == "enquiry":
        return {
            "subtotal": 0.0,
            "fee": 0.0,
            "total": 0.0,
            "line_items": [],
            "requires_checkout": False,
            "is_subscription": is_subscription,
            "is_enquiry": True,
            "external_url": None,
        }

    # ── Internal ──────────────────────────────────────────────────────────────
    base = float(product.get("base_price") or 0.0)
    subtotal = base
    line_items: List[Dict] = []
    if base > 0:
        line_items.append({"label": product.get("name", "Service"), "amount": base})

    schema = product.get("intake_schema_json")
    questions = _get_intake_questions(schema)

    for q in questions:
        if not q.get("enabled", True):
            continue
        q_type = q.get("type", "single_line")
        key = q.get("key", "")

        # ── Number question — flat rate or tiered pricing ────────────────
        if q_type == "number":
            raw = inputs.get(key)
            if raw is None:
                continue
            min_v = float(q.get("min", 0))
            max_v = float(q.get("max", 9_999_999))
            val = max(min_v, min(max_v, float(raw or min_v)))

            pricing_mode = q.get("pricing_mode", "flat")
            if pricing_mode == "tiered":
                tiers = q.get("tiers", [])
                amount = _calculate_tiered_price(val, tiers)
            else:
                rate = float(q.get("price_per_unit") or 0.0)
                if rate == 0:
                    continue
                amount = round_cents(val * rate)

            if amount > 0:
                subtotal += amount
                line_items.append({"label": q.get("label", key), "amount": amount})

        # ── Boolean question — affects_price like a dropdown ──────────────
        elif q_type == "boolean" and (q.get("affects_price") or q.get("affects_price_boolean")):
            raw = inputs.get(key)
            if raw is None:
                continue
            # price_for_yes / price_for_no on the question, or options list
            yes_val = float(q.get("price_for_yes") or 0.0)
            no_val = float(q.get("price_for_no") or 0.0)
            pv = yes_val if str(raw).lower() in ("yes", "true", "1") else no_val
            if pv != 0:
                subtotal += pv
                line_items.append({
                    "label": f"{q.get('label', key)}: {'Yes' if str(raw).lower() in ('yes','true','1') else 'No'}",
                    "amount": round_cents(pv),
                })

        # ── Dropdown / Multiselect — affects_price ────────────────────────
        elif q_type in ("dropdown", "multiselect") and q.get("affects_price"):
            price_mode = q.get("price_mode", "add")
            raw = inputs.get(key)
            if raw is None:
                continue
            selected = [raw] if isinstance(raw, str) else (raw if isinstance(raw, list) else [])
            for opt in q.get("options", []):
                if opt.get("value") not in selected:
                    continue
                pv = float(opt.get("price_value") or 0)
                if pv == 0:
                    continue
                if price_mode == "add":
                    subtotal += pv
                    line_items.append({
                        "label": f"{q.get('label', key)}: {opt.get('label', '')}",
                        "amount": round_cents(pv),
                    })
                elif price_mode == "multiply":
                    new_sub = round_cents(subtotal * pv)
                    line_items.append({
                        "label": f"{q.get('label', key)}: {opt.get('label', '')} (×{pv})",
                        "amount": round_cents(new_sub - subtotal),
                    })
                    subtotal = new_sub

        # ── Formula question — cross-field calculation ────────────────────
        elif q_type == "formula":
            expr = q.get("formula_expression", "")
            if not expr:
                continue
            # Build context from all numeric inputs
            ctx: Dict[str, float] = {}
            for k, v in inputs.items():
                try:
                    ctx[k] = float(v or 0)
                except (TypeError, ValueError):
                    ctx[k] = 0.0
            amount = eval_formula_expression(expr, ctx)
            if amount > 0:
                subtotal += amount
                line_items.append({"label": q.get("label", key) or "Formula calculation", "amount": amount})

    # Price rounding (optional product-level config)
    price_rounding = product.get("price_rounding")
    if price_rounding and subtotal > 0:
        nearest = {"25": 25, "50": 50, "100": 100}.get(str(price_rounding))
        if nearest:
            subtotal = round_nearest(subtotal, nearest)

    # Price ceiling cap (optional schema-level config) — floor removed, base_price is the minimum
    price_ceiling = float((schema or {}).get("price_ceiling") or 0)
    if price_ceiling > 0 and subtotal > price_ceiling:
        diff = subtotal - price_ceiling
        line_items.append({"label": "Maximum pricing cap applied", "amount": round_cents(-diff)})
        subtotal = price_ceiling

    subtotal = round_cents(subtotal)
    requires_checkout = subtotal > 0
    fee = round_cents(subtotal * fee_rate) if requires_checkout else 0.0

    return {
        "subtotal": subtotal,
        "fee": fee,
        "total": round_cents(subtotal + fee),
        "line_items": line_items,
        "requires_checkout": requires_checkout,
        "is_subscription": is_subscription,
        "is_enquiry": False,
        "external_url": None,
    }


# ── Starting price helper (for catalog cards) ─────────────────────────────────

def get_starting_price(product: Dict[str, Any]) -> Optional[float]:
    """Return the minimum possible price for catalog card display, or None."""
    pricing_type = product.get("pricing_type", "internal")
    if pricing_type in ("external", "enquiry"):
        return None

    base = float(product.get("base_price") or 0.0)
    schema = product.get("intake_schema_json")
    questions = _get_intake_questions(schema)

    has_required_priced_question = False
    min_add = 0.0

    for q in questions:
        if not q.get("enabled", True):
            continue
        q_type = q.get("type", "single_line")
        if q_type == "number" and float(q.get("price_per_unit") or 0) > 0:
            if q.get("required"):
                min_val = float(q.get("min", 0))
                min_add += round_cents(min_val * float(q["price_per_unit"]))
                has_required_priced_question = True
        elif q_type in ("dropdown", "multiselect") and q.get("affects_price") and q.get("required"):
            prices = [float(o.get("price_value") or 0) for o in q.get("options", [])]
            if prices:
                has_required_priced_question = True
                min_add += min(p for p in prices if p > 0) if any(p > 0 for p in prices) else 0

    if base > 0 or has_required_priced_question:
        starting = round_cents(base + min_add)
        # Apply product-level price rounding
        price_rounding = product.get("price_rounding")
        if price_rounding and starting > 0:
            nearest = {"25": 25, "50": 50, "100": 100}.get(str(price_rounding))
            if nearest:
                starting = round_nearest(starting, nearest)
        return starting
    return None
