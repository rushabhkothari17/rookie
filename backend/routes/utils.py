"""Public utility endpoints — province/state lists, country lists from tax tables, etc."""
from fastapi import APIRouter, Query
from db.session import db

router = APIRouter(prefix="/api", tags=["utils"])

_CANADA_PROVINCES = [
    {"value": "AB", "label": "Alberta"},
    {"value": "BC", "label": "British Columbia"},
    {"value": "MB", "label": "Manitoba"},
    {"value": "NB", "label": "New Brunswick"},
    {"value": "NL", "label": "Newfoundland and Labrador"},
    {"value": "NS", "label": "Nova Scotia"},
    {"value": "NT", "label": "Northwest Territories"},
    {"value": "NU", "label": "Nunavut"},
    {"value": "ON", "label": "Ontario"},
    {"value": "PE", "label": "Prince Edward Island"},
    {"value": "QC", "label": "Quebec"},
    {"value": "SK", "label": "Saskatchewan"},
    {"value": "YT", "label": "Yukon"},
]

_USA_STATES = [
    {"value": "AL", "label": "Alabama"}, {"value": "AK", "label": "Alaska"},
    {"value": "AZ", "label": "Arizona"}, {"value": "AR", "label": "Arkansas"},
    {"value": "CA", "label": "California"}, {"value": "CO", "label": "Colorado"},
    {"value": "CT", "label": "Connecticut"}, {"value": "DE", "label": "Delaware"},
    {"value": "DC", "label": "District of Columbia"}, {"value": "FL", "label": "Florida"},
    {"value": "GA", "label": "Georgia"}, {"value": "HI", "label": "Hawaii"},
    {"value": "ID", "label": "Idaho"}, {"value": "IL", "label": "Illinois"},
    {"value": "IN", "label": "Indiana"}, {"value": "IA", "label": "Iowa"},
    {"value": "KS", "label": "Kansas"}, {"value": "KY", "label": "Kentucky"},
    {"value": "LA", "label": "Louisiana"}, {"value": "ME", "label": "Maine"},
    {"value": "MD", "label": "Maryland"}, {"value": "MA", "label": "Massachusetts"},
    {"value": "MI", "label": "Michigan"}, {"value": "MN", "label": "Minnesota"},
    {"value": "MS", "label": "Mississippi"}, {"value": "MO", "label": "Missouri"},
    {"value": "MT", "label": "Montana"}, {"value": "NE", "label": "Nebraska"},
    {"value": "NV", "label": "Nevada"}, {"value": "NH", "label": "New Hampshire"},
    {"value": "NJ", "label": "New Jersey"}, {"value": "NM", "label": "New Mexico"},
    {"value": "NY", "label": "New York"}, {"value": "NC", "label": "North Carolina"},
    {"value": "ND", "label": "North Dakota"}, {"value": "OH", "label": "Ohio"},
    {"value": "OK", "label": "Oklahoma"}, {"value": "OR", "label": "Oregon"},
    {"value": "PA", "label": "Pennsylvania"}, {"value": "RI", "label": "Rhode Island"},
    {"value": "SC", "label": "South Carolina"}, {"value": "SD", "label": "South Dakota"},
    {"value": "TN", "label": "Tennessee"}, {"value": "TX", "label": "Texas"},
    {"value": "UT", "label": "Utah"}, {"value": "VT", "label": "Vermont"},
    {"value": "VA", "label": "Virginia"}, {"value": "WA", "label": "Washington"},
    {"value": "WV", "label": "West Virginia"}, {"value": "WI", "label": "Wisconsin"},
    {"value": "WY", "label": "Wyoming"},
]

_COUNTRY_MAP = {
    "CA": _CANADA_PROVINCES,
    "CANADA": _CANADA_PROVINCES,
    "US": _USA_STATES,
    "USA": _USA_STATES,
    "UNITED STATES": _USA_STATES,
}


@router.get("/utils/provinces")
async def get_provinces(country_code: str = Query(..., description="ISO country code (CA, US) or country name")):
    """Return list of provinces/states for a given country."""
    key = country_code.upper().strip()
    regions = _COUNTRY_MAP.get(key, [])
    return {"country_code": key, "regions": regions}


# Country code → display name mapping (covers ISO 2-letter codes used in EU VAT tables)
_ISO_TO_NAME = {
    "AT": "Austria", "AU": "Australia", "BE": "Belgium", "BG": "Bulgaria",
    "CA": "Canada", "CY": "Cyprus", "CZ": "Czech Republic", "DE": "Germany",
    "DK": "Denmark", "EE": "Estonia", "ES": "Spain", "FI": "Finland",
    "FR": "France", "GB": "United Kingdom", "GR": "Greece", "HR": "Croatia",
    "HU": "Hungary", "IE": "Ireland", "IN": "India", "IT": "Italy",
    "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta",
    "NL": "Netherlands", "NZ": "New Zealand", "PL": "Poland", "PT": "Portugal",
    "RO": "Romania", "SE": "Sweden", "SG": "Singapore", "SI": "Slovenia",
    "SK": "Slovakia", "US": "United States", "ZA": "South Africa",
    # Aliases stored as full names or alternate codes in some tenants' tax tables
    "CANADA": "Canada", "USA": "United States", "UNITED STATES": "United States",
    "UNITED KINGDOM": "United Kingdom", "AUSTRALIA": "Australia",
}

_FALLBACK_COUNTRIES = [
    {"value": "Canada", "label": "Canada"},
    {"value": "USA", "label": "United States"},
]


@router.get("/utils/countries")
async def get_countries(partner_code: str = Query(None, description="Partner code to scope tax-table lookup")):
    """Return list of countries present in the tax tables.
    Falls back to default list if no tax data found or partner_code not provided.
    """
    codes: list = []
    try:
        query = {}
        if partner_code:
            from bson import ObjectId
            tenant = await db.tenants.find_one({"code": partner_code.strip().lower()}, {"_id": 1})
            if tenant:
                query["tenant_id"] = str(tenant["_id"])
        raw = await db.tax_tables.distinct("country_code", query)
        codes = [c.upper() for c in raw if c]
    except Exception:
        pass

    if not codes:
        # Try global tax_tables (no tenant filter) as a fallback
        try:
            raw = await db.tax_tables.distinct("country_code", {})
            codes = [c.upper() for c in raw if c]
        except Exception:
            pass

    if not codes:
        return {"countries": _FALLBACK_COUNTRIES}

    # Normalise: map ISO codes to display names; pass-through already-readable names
    seen_names: set = set()
    result = []
    for raw_code in sorted(set(codes)):
        code = raw_code.upper().strip()
        # Direct ISO lookup
        name = _ISO_TO_NAME.get(code)
        if not name:
            # Check if the raw value is already a readable full name (e.g. "Australia")
            title = raw_code.strip().title()
            # Accept as-is if it looks like a real name (not a 2-3 char code)
            name = title if len(raw_code.strip()) > 3 else raw_code.strip()
        if name and name not in seen_names:
            seen_names.add(name)
            result.append({"value": name, "label": name})

    result.sort(key=lambda x: x["label"])
    return {"countries": result if result else _FALLBACK_COUNTRIES}
