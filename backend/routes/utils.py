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


# Country code → display name mapping
_ISO_TO_NAME = {
    "CA": "Canada",
    "US": "USA",
    "GB": "United Kingdom",
    "AU": "Australia",
    "NZ": "New Zealand",
    "IN": "India",
    "DE": "Germany",
    "FR": "France",
    "NL": "Netherlands",
    "SG": "Singapore",
    "IE": "Ireland",
    "ZA": "South Africa",
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

    # Map ISO codes to display names, filtering out unknowns
    result = []
    for code in sorted(set(codes)):
        name = _ISO_TO_NAME.get(code)
        if name:
            result.append({"value": name, "label": name})
        else:
            result.append({"value": code, "label": code})

    return {"countries": result if result else _FALLBACK_COUNTRIES}
