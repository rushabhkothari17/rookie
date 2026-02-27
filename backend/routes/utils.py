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
