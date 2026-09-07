"""
models.py
---------
Pydantic schemas used throughout the SentinelGraph AI preprocessing pipeline.

These models give us:
  - Type-checked, self-documenting record shapes
  - A single source of truth for what "standardized" means (phone/date/location)
  - A stable schema for the final cleaned_records.json output
"""

from datetime import date
from enum import Enum
from typing import List, Optional, Dict, Any

from ._compat import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class RecordType(str, Enum):
    PERSON = "person"
    FIR = "fir"
    INTEL_REPORT = "intelligence_report"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentType(str, Enum):
    EXTORTION = "extortion"
    ASSAULT = "assault"
    NARCOTICS = "narcotics"
    THEFT = "theft"
    FRAUD = "fraud"
    ILLEGAL_WEAPONS = "illegal_weapons"
    MONEY_LAUNDERING = "money_laundering"
    UNLAWFUL_ASSEMBLY = "unlawful_assembly"


# --------------------------------------------------------------------------- #
# Standardized sub-objects
# --------------------------------------------------------------------------- #
class StandardizedLocation(BaseModel):
    raw_text: str
    street: Optional[str] = None
    city: str = "UNKNOWN"
    region: str = "UNKNOWN"
    country: str = "UNKNOWN"
    normalized: str = ""  # canonical "City, Region, Country" string


class StandardizedContact(BaseModel):
    raw_phone: str
    e164: Optional[str] = None       # e.g. +19231067245
    country_code: Optional[str] = None
    is_valid: bool = False


# --------------------------------------------------------------------------- #
# Core records
# --------------------------------------------------------------------------- #
class StandardizedPerson(BaseModel):
    person_id: str
    full_name: str
    contact: StandardizedContact
    location: StandardizedLocation
    age: Optional[int] = None
    gang_id: Optional[str] = None
    role: Optional[str] = None
    is_hidden_coordinator: bool = False


class FIRDocument(BaseModel):
    """A simulated First Information Report."""
    fir_id: str
    police_station: str
    date_filed: str                  # ISO 8601 date, standardized
    complainant_id: str
    complainant_name: str
    accused_ids: List[str] = Field(default_factory=list)
    gang_id: Optional[str] = None
    incident_type: str
    incident_location: StandardizedLocation
    narrative: str
    status: str = "under_investigation"

    @field_validator("date_filed")
    @classmethod
    def _validate_iso_date(cls, v):
        # Cheap sanity check: must look like YYYY-MM-DD (…optionally with time)
        if not v or len(v) < 10 or v[4] != "-" or v[7] != "-":
            raise ValueError(f"date_filed must be ISO 8601, got: {v}")
        return v


class IntelligenceReport(BaseModel):
    """A synthetic analyst-style intelligence report."""
    report_id: str
    generated_date: str               # ISO 8601
    title: str
    subject_person_ids: List[str] = Field(default_factory=list)
    gang_ids: List[str] = Field(default_factory=list)
    risk_level: str = RiskLevel.MEDIUM.value
    summary: str
    evidence_channels: List[str] = Field(default_factory=list)   # e.g. ["calls", "transactions"]
    confidence_score: float = 0.5

    @field_validator("confidence_score")
    @classmethod
    def _clip_confidence(cls, v):
        return max(0.0, min(1.0, float(v)))


class CleanedRecord(BaseModel):
    """
    Unified, cleaned representation written to cleaned_records.json.
    Every FIR / intelligence report / standardized person passes through
    the cleaning pipeline and comes out as one of these.
    """
    record_id: str
    record_type: str                 # RecordType value
    text: str                        # cleaned narrative/summary/name text
    language: str = "unknown"
    language_confidence: float = 0.0
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
