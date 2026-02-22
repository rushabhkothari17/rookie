"""Pure utility functions — no I/O, no DB access."""
import uuid
import re as _re
from datetime import datetime, timezone
from typing import Any, Dict


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id() -> str:
    return str(uuid.uuid4())


def round_cents(value: float) -> float:
    return float(f"{value:.2f}")


def round_to_nearest_99(amount: float) -> int:
    """Round amount to nearest 'X99' value. Tie goes to high."""
    low = int(amount / 100) * 100 - 1
    high = low + 100
    return high if abs(amount - high) <= abs(amount - low) else low


import math

def round_nearest_25(value: float) -> float:
    return float(round(value / 25) * 25)


def round_nearest(value: float, nearest: int) -> float:
    """Round value to the nearest multiple of `nearest` using conventional rounding (0.5 rounds up)."""
    return float(math.floor(value / nearest + 0.5) * nearest)


def currency_for_country(country: str) -> str:
    c = (country or "").strip().lower()
    if c in ["canada", "ca"]:
        return "CAD"
    if c in ["usa", "us", "united states", "united states of america"]:
        return "USD"
    if c in ["gb", "uk", "united kingdom", "england", "scotland", "wales"]:
        return "GBP"
    if c in ["au", "australia"]:
        return "AUD"
    if c in ["nz", "new zealand"]:
        return "NZD"
    if c in ["sg", "singapore"]:
        return "SGD"
    if c in ["in", "india"]:
        return "INR"
    if c in ["za", "south africa"]:
        return "ZAR"
    if c in ["eu", "de", "fr", "es", "it", "nl", "be", "at", "pt", "ie"]:
        return "EUR"
    return "USD"


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge override into base. Override values win on conflict."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = _re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = _re.sub(r"\s+", "-", slug)
    slug = _re.sub(r"-+", "-", slug)
    return slug.strip("-")
