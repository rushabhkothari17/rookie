"""
Static seed data for global tax tables.
Platform admin can override these rates via the DB (tax_tables collection).
Rates as of 2026 — update when legislation changes.
"""

# ── Canada ─────────────────────────────────────────────────────────────────────
# Rules applied in tax_service.py:
#   1. Customer in HST province → charge that province's HST rate
#   2. Customer in SAME province as partner (non-HST) → combined rate (GST+PST/QST)
#   3. Customer in DIFFERENT non-HST province → 5% federal GST only
#   4. Canadian partner → non-Canadian customer → 0% (export)

CANADA_PROVINCES = {
    "AB": {"rate": 0.05,    "label": "GST",     "name": "Alberta",                "hst": False},
    "BC": {"rate": 0.12,    "label": "GST+PST", "name": "British Columbia",        "hst": False},
    "MB": {"rate": 0.12,    "label": "GST+PST", "name": "Manitoba",                "hst": False},
    "NB": {"rate": 0.15,    "label": "HST",     "name": "New Brunswick",           "hst": True},
    "NL": {"rate": 0.15,    "label": "HST",     "name": "Newfoundland & Labrador", "hst": True},
    "NS": {"rate": 0.15,    "label": "HST",     "name": "Nova Scotia",             "hst": True},
    "NT": {"rate": 0.05,    "label": "GST",     "name": "Northwest Territories",   "hst": False},
    "NU": {"rate": 0.05,    "label": "GST",     "name": "Nunavut",                 "hst": False},
    "ON": {"rate": 0.13,    "label": "HST",     "name": "Ontario",                 "hst": True},
    "PE": {"rate": 0.15,    "label": "HST",     "name": "Prince Edward Island",    "hst": True},
    "QC": {"rate": 0.14975, "label": "GST+QST", "name": "Quebec",                  "hst": False},
    "SK": {"rate": 0.11,    "label": "GST+PST", "name": "Saskatchewan",            "hst": False},
    "YT": {"rate": 0.05,    "label": "GST",     "name": "Yukon",                   "hst": False},
}
CANADA_FEDERAL_GST = 0.05  # Federal GST rate — cross-province non-HST

# ── United States ───────────────────────────────────────────────────────────────
# State-level combined average rates (state + avg local).
# Applied to ALL US→US transactions regardless of nexus (simplified approach).
US_STATES = {
    "AL": {"rate": 0.09, "label": "Sales Tax", "name": "Alabama"},
    "AK": {"rate": 0.00, "label": "No Tax",    "name": "Alaska"},
    "AZ": {"rate": 0.084,"label": "Sales Tax", "name": "Arizona"},
    "AR": {"rate": 0.095,"label": "Sales Tax", "name": "Arkansas"},
    "CA": {"rate": 0.088,"label": "Sales Tax", "name": "California"},
    "CO": {"rate": 0.077,"label": "Sales Tax", "name": "Colorado"},
    "CT": {"rate": 0.063,"label": "Sales Tax", "name": "Connecticut"},
    "DE": {"rate": 0.00, "label": "No Tax",    "name": "Delaware"},
    "FL": {"rate": 0.07, "label": "Sales Tax", "name": "Florida"},
    "GA": {"rate": 0.073,"label": "Sales Tax", "name": "Georgia"},
    "HI": {"rate": 0.044,"label": "GET",       "name": "Hawaii"},
    "ID": {"rate": 0.06, "label": "Sales Tax", "name": "Idaho"},
    "IL": {"rate": 0.089,"label": "Sales Tax", "name": "Illinois"},
    "IN": {"rate": 0.07, "label": "Sales Tax", "name": "Indiana"},
    "IA": {"rate": 0.069,"label": "Sales Tax", "name": "Iowa"},
    "KS": {"rate": 0.087,"label": "Sales Tax", "name": "Kansas"},
    "KY": {"rate": 0.06, "label": "Sales Tax", "name": "Kentucky"},
    "LA": {"rate": 0.099,"label": "Sales Tax", "name": "Louisiana"},
    "ME": {"rate": 0.055,"label": "Sales Tax", "name": "Maine"},
    "MD": {"rate": 0.06, "label": "Sales Tax", "name": "Maryland"},
    "MA": {"rate": 0.0625,"label": "Sales Tax","name": "Massachusetts"},
    "MI": {"rate": 0.06, "label": "Sales Tax", "name": "Michigan"},
    "MN": {"rate": 0.075,"label": "Sales Tax", "name": "Minnesota"},
    "MS": {"rate": 0.07, "label": "Sales Tax", "name": "Mississippi"},
    "MO": {"rate": 0.082,"label": "Sales Tax", "name": "Missouri"},
    "MT": {"rate": 0.00, "label": "No Tax",    "name": "Montana"},
    "NE": {"rate": 0.069,"label": "Sales Tax", "name": "Nebraska"},
    "NV": {"rate": 0.082,"label": "Sales Tax", "name": "Nevada"},
    "NH": {"rate": 0.00, "label": "No Tax",    "name": "New Hampshire"},
    "NJ": {"rate": 0.066,"label": "Sales Tax", "name": "New Jersey"},
    "NM": {"rate": 0.078,"label": "Sales Tax", "name": "New Mexico"},
    "NY": {"rate": 0.088,"label": "Sales Tax", "name": "New York"},
    "NC": {"rate": 0.069,"label": "Sales Tax", "name": "North Carolina"},
    "ND": {"rate": 0.069,"label": "Sales Tax", "name": "North Dakota"},
    "OH": {"rate": 0.072,"label": "Sales Tax", "name": "Ohio"},
    "OK": {"rate": 0.089,"label": "Sales Tax", "name": "Oklahoma"},
    "OR": {"rate": 0.00, "label": "No Tax",    "name": "Oregon"},
    "PA": {"rate": 0.063,"label": "Sales Tax", "name": "Pennsylvania"},
    "RI": {"rate": 0.07, "label": "Sales Tax", "name": "Rhode Island"},
    "SC": {"rate": 0.075,"label": "Sales Tax", "name": "South Carolina"},
    "SD": {"rate": 0.064,"label": "Sales Tax", "name": "South Dakota"},
    "TN": {"rate": 0.095,"label": "Sales Tax", "name": "Tennessee"},
    "TX": {"rate": 0.082,"label": "Sales Tax", "name": "Texas"},
    "UT": {"rate": 0.072,"label": "Sales Tax", "name": "Utah"},
    "VT": {"rate": 0.063,"label": "Sales Tax", "name": "Vermont"},
    "VA": {"rate": 0.057,"label": "Sales Tax", "name": "Virginia"},
    "WA": {"rate": 0.092,"label": "Sales Tax", "name": "Washington"},
    "WV": {"rate": 0.065,"label": "Sales Tax", "name": "West Virginia"},
    "WI": {"rate": 0.054,"label": "Sales Tax", "name": "Wisconsin"},
    "WY": {"rate": 0.054,"label": "Sales Tax", "name": "Wyoming"},
    "DC": {"rate": 0.06, "label": "Sales Tax", "name": "District of Columbia"},
}

# ── United Kingdom ──────────────────────────────────────────────────────────────
UK_RATE = {"rate": 0.20, "label": "VAT", "name": "United Kingdom"}

# ── Australia ───────────────────────────────────────────────────────────────────
AU_RATE = {"rate": 0.10, "label": "GST", "name": "Australia"}

# ── India ────────────────────────────────────────────────────────────────────────
# Standard GST rate for services. Same rate applies inter-state (IGST) and intra-state (CGST+SGST).
IN_RATE = {"rate": 0.18, "label": "GST", "name": "India"}

INDIA_STATES = {
    "AN": "Andaman and Nicobar Islands", "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh",
    "AS": "Assam", "BR": "Bihar", "CH": "Chandigarh", "CT": "Chhattisgarh",
    "DN": "Dadra and Nagar Haveli and Daman and Diu", "DL": "Delhi",
    "GA": "Goa", "GJ": "Gujarat", "HR": "Haryana", "HP": "Himachal Pradesh",
    "JK": "Jammu and Kashmir", "JH": "Jharkhand", "KA": "Karnataka",
    "KL": "Kerala", "LA": "Ladakh", "LD": "Lakshadweep", "MP": "Madhya Pradesh",
    "MH": "Maharashtra", "MN": "Manipur", "ML": "Meghalaya", "MZ": "Mizoram",
    "NL": "Nagaland", "OR": "Odisha", "PY": "Puducherry", "PB": "Punjab",
    "RJ": "Rajasthan", "SK": "Sikkim", "TN": "Tamil Nadu", "TG": "Telangana",
    "TR": "Tripura", "UP": "Uttar Pradesh", "UT": "Uttarakhand", "WB": "West Bengal",
}

# ── European Union ───────────────────────────────────────────────────────────────
EU_VAT_RATES = {
    "AT": {"rate": 0.20, "label": "VAT", "name": "Austria"},
    "BE": {"rate": 0.21, "label": "VAT", "name": "Belgium"},
    "BG": {"rate": 0.20, "label": "VAT", "name": "Bulgaria"},
    "HR": {"rate": 0.25, "label": "VAT", "name": "Croatia"},
    "CY": {"rate": 0.19, "label": "VAT", "name": "Cyprus"},
    "CZ": {"rate": 0.21, "label": "VAT", "name": "Czech Republic"},
    "DK": {"rate": 0.25, "label": "VAT", "name": "Denmark"},
    "EE": {"rate": 0.22, "label": "VAT", "name": "Estonia"},
    "FI": {"rate": 0.255,"label": "VAT", "name": "Finland"},
    "FR": {"rate": 0.20, "label": "TVA", "name": "France"},
    "DE": {"rate": 0.19, "label": "MwSt","name": "Germany"},
    "GR": {"rate": 0.24, "label": "VAT", "name": "Greece"},
    "HU": {"rate": 0.27, "label": "ÁFA", "name": "Hungary"},
    "IE": {"rate": 0.23, "label": "VAT", "name": "Ireland"},
    "IT": {"rate": 0.22, "label": "IVA", "name": "Italy"},
    "LV": {"rate": 0.21, "label": "VAT", "name": "Latvia"},
    "LT": {"rate": 0.21, "label": "VAT", "name": "Lithuania"},
    "LU": {"rate": 0.17, "label": "TVA", "name": "Luxembourg"},
    "MT": {"rate": 0.18, "label": "VAT", "name": "Malta"},
    "NL": {"rate": 0.21, "label": "BTW", "name": "Netherlands"},
    "PL": {"rate": 0.23, "label": "VAT", "name": "Poland"},
    "PT": {"rate": 0.23, "label": "IVA", "name": "Portugal"},
    "RO": {"rate": 0.19, "label": "TVA", "name": "Romania"},
    "SK": {"rate": 0.20, "label": "DPH", "name": "Slovakia"},
    "SI": {"rate": 0.22, "label": "DDV", "name": "Slovenia"},
    "ES": {"rate": 0.21, "label": "IVA", "name": "Spain"},
    "SE": {"rate": 0.25, "label": "Moms","name": "Sweden"},
}

EU_COUNTRY_CODES = set(EU_VAT_RATES.keys())


def get_seed_tax_table() -> list:
    """Return all tax table entries as a flat list for DB seeding."""
    entries = []
    for code, data in CANADA_PROVINCES.items():
        entries.append({"country_code": "CA", "state_code": code, "state_name": data["name"],
                        "rate": data["rate"], "label": data["label"]})
    for code, data in US_STATES.items():
        entries.append({"country_code": "US", "state_code": code, "state_name": data["name"],
                        "rate": data["rate"], "label": data["label"]})
    entries.append({"country_code": "GB", "state_code": "", "state_name": "United Kingdom",
                    "rate": UK_RATE["rate"], "label": UK_RATE["label"]})
    entries.append({"country_code": "AU", "state_code": "", "state_name": "Australia",
                    "rate": AU_RATE["rate"], "label": AU_RATE["label"]})
    entries.append({"country_code": "IN", "state_code": "", "state_name": "India",
                    "rate": IN_RATE["rate"], "label": IN_RATE["label"]})
    for code, data in EU_VAT_RATES.items():
        entries.append({"country_code": code, "state_code": "", "state_name": data["name"],
                        "rate": data["rate"], "label": data["label"]})
    return entries
