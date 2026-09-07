"""
standardizer.py
-----------------
Standardizes three messy real-world fields into consistent formats:

  * Phone numbers -> E.164-ish format (+<countrycode><digits>)
  * Dates          -> ISO 8601 (YYYY-MM-DD or full timestamp)
  * Locations      -> structured {street, city, region, country}

Uses `python-dateutil` for flexible date parsing (it ships in most
environments); phone/location standardization is dependency-free regex +
gazetteer lookups so the module works without network access.
"""

import re
from typing import Optional, Dict

from dateutil import parser as dateutil_parser

from .models import StandardizedContact, StandardizedLocation

# A tiny gazetteer mapping the synthetic city names (from Phase 1's
# FakeDataProvider) to a region/country. In production this would be backed
# by a real geocoding service or a proper gazetteer database.
_GAZETTEER: Dict[str, Dict[str, str]] = {
    "riverport": {"region": "Coastal Province", "country": "USA"},
    "newham": {"region": "Eastern Province", "country": "USA"},
    "eastgate": {"region": "Eastern Province", "country": "USA"},
    "westfield": {"region": "Western Province", "country": "USA"},
    "lakeview": {"region": "Northern Province", "country": "USA"},
    "fort dale": {"region": "Southern Province", "country": "USA"},
    "milbrook": {"region": "Central Province", "country": "USA"},
    "grantville": {"region": "Central Province", "country": "USA"},
    "cedar falls": {"region": "Northern Province", "country": "USA"},
}

_DEFAULT_COUNTRY_CODE = "1"  # matches Phase 1's "+1-XXXXXXXXXX" phone format


class PhoneStandardizer:
    """Normalizes phone numbers to a simple E.164-like representation."""

    _DIGITS_RE = re.compile(r"\d+")

    def __init__(self, default_country_code: str = _DEFAULT_COUNTRY_CODE):
        self.default_country_code = default_country_code

    def standardize(self, raw_phone: str) -> StandardizedContact:
        if not raw_phone or not raw_phone.strip():
            return StandardizedContact(raw_phone=raw_phone or "", e164=None,
                                        country_code=None, is_valid=False)

        digits = "".join(self._DIGITS_RE.findall(raw_phone))

        # Heuristic: if the raw string already carries a leading '+', trust
        # whatever country code precedes the last 10 digits; otherwise assume
        # the default country code.
        if raw_phone.strip().startswith("+") and len(digits) > 10:
            country_code = digits[:-10]
            subscriber = digits[-10:]
        else:
            country_code = self.default_country_code
            subscriber = digits[-10:] if len(digits) >= 10 else digits

        is_valid = len(subscriber) == 10
        e164 = f"+{country_code}{subscriber}" if is_valid else None

        return StandardizedContact(
            raw_phone=raw_phone,
            e164=e164,
            country_code=country_code if is_valid else None,
            is_valid=is_valid,
        )


class DateStandardizer:
    """Normalizes assorted date/timestamp strings to ISO 8601."""

    def standardize(self, raw_date: str, assume_date_only: bool = False) -> Optional[str]:
        if not raw_date or not raw_date.strip():
            return None
        try:
            parsed = dateutil_parser.parse(raw_date, fuzzy=True)
        except (ValueError, OverflowError, TypeError):
            return None

        if assume_date_only:
            return parsed.date().isoformat()
        return parsed.isoformat()


class LocationStandardizer:
    """
    Parses a free-text address like "3241 Main St, Grantville" into a
    structured StandardizedLocation, resolving the city against a small
    gazetteer.
    """

    def __init__(self, gazetteer: Optional[Dict[str, Dict[str, str]]] = None):
        self.gazetteer = gazetteer or _GAZETTEER

    def standardize(self, raw_address: str) -> StandardizedLocation:
        raw_address = (raw_address or "").strip()
        if not raw_address:
            return StandardizedLocation(raw_text=raw_address, normalized="UNKNOWN")

        parts = [p.strip() for p in raw_address.split(",") if p.strip()]
        street = parts[0] if len(parts) >= 1 else None
        city_raw = parts[1] if len(parts) >= 2 else (parts[0] if len(parts) == 1 else None)

        city = (city_raw or "UNKNOWN").title()
        lookup_key = (city_raw or "").strip().lower()
        geo = self.gazetteer.get(lookup_key, {"region": "UNKNOWN", "country": "UNKNOWN"})

        normalized = f"{city}, {geo['region']}, {geo['country']}"

        return StandardizedLocation(
            raw_text=raw_address,
            street=street,
            city=city,
            region=geo["region"],
            country=geo["country"],
            normalized=normalized,
        )


class RecordStandardizer:
    """Convenience facade bundling all three standardizers together."""

    def __init__(self, default_country_code: str = _DEFAULT_COUNTRY_CODE,
                 gazetteer: Optional[Dict[str, Dict[str, str]]] = None):
        self.phone = PhoneStandardizer(default_country_code)
        self.date = DateStandardizer()
        self.location = LocationStandardizer(gazetteer)
