"""
fir_simulator.py
------------------
Generates synthetic First Information Report (FIR) documents from the
Phase 1 person/gang data, so downstream NLP components (OCR, cleaning,
translation, NER, etc.) have realistic police-style narrative text to work
with.

An FIR here is a fully fictional record tied to synthetic person_ids only
-- it does not reference any real individual, location, or event.
"""

import random
from typing import List, Optional

import pandas as pd

from .models import FIRDocument, IncidentType
from .standardizer import RecordStandardizer

_POLICE_STATIONS = [
    "Riverport Central PS", "Eastgate Precinct 4", "Westfield Division HQ",
    "Lakeview Metro PS", "Grantville Sector 2", "Milbrook Community PS",
]

_NARRATIVE_TEMPLATES = {
    IncidentType.EXTORTION.value: (
        "On {date}, the complainant, {complainant}, reported that unknown "
        "individuals associated with a local criminal network demanded "
        "protection money under threat of harm. The complainant identified "
        "{accused} as being involved. Investigation has been initiated "
        "under relevant extortion statutes."
    ),
    IncidentType.ASSAULT.value: (
        "The complainant {complainant} stated that on {date}, {accused} and "
        "associates physically assaulted them near {location}. Medical "
        "examination was conducted and injuries were documented. A case "
        "has been registered for further investigation."
    ),
    IncidentType.NARCOTICS.value: (
        "Acting on a tip received on {date}, officers intercepted a suspect "
        "believed to be {accused} near {location} in connection with "
        "suspected narcotics distribution. {complainant} was recorded as "
        "the reporting officer. Samples have been sent for forensic analysis."
    ),
    IncidentType.THEFT.value: (
        "{complainant} reported the theft of personal property on {date} "
        "near {location}. Preliminary inquiry points to involvement of "
        "{accused}. CCTV footage from the area is being reviewed."
    ),
    IncidentType.FRAUD.value: (
        "A financial fraud complaint was lodged by {complainant} on {date}, "
        "alleging that {accused} orchestrated a scheme resulting in "
        "unauthorized transfer of funds. Bank records are being subpoenaed "
        "as part of the investigation."
    ),
    IncidentType.ILLEGAL_WEAPONS.value: (
        "On {date}, a search near {location} led to the recovery of "
        "unlicensed firearms allegedly linked to {accused}. {complainant} "
        "filed the report following a community tip. Ballistics analysis "
        "is pending."
    ),
    IncidentType.MONEY_LAUNDERING.value: (
        "{complainant}, an investigating officer, filed this report on "
        "{date} after financial intelligence flagged a pattern of "
        "transactions linked to {accused} consistent with money "
        "laundering. The matter has been escalated to the financial crimes "
        "unit."
    ),
    IncidentType.UNLAWFUL_ASSEMBLY.value: (
        "On {date}, {complainant} reported an unlawful assembly near "
        "{location} involving individuals believed to include {accused}. "
        "Local police were dispatched to disperse the gathering and this "
        "FIR was subsequently registered."
    ),
}


class FirSimulator:
    """
    Builds synthetic FIRDocument records from a persons DataFrame (and
    optionally a gangs lookup), producing realistic narrative text ready
    for the OCR / cleaning / translation stages.
    """

    def __init__(self, rng: Optional[random.Random] = None,
                 standardizer: Optional[RecordStandardizer] = None,
                 start_year: int = 2025):
        self._rng = rng or random.Random(42)
        self._standardizer = standardizer or RecordStandardizer()
        self._start_year = start_year

    def generate(self, persons_df: pd.DataFrame, num_firs: int) -> List[FIRDocument]:
        gang_members = persons_df[persons_df["gang_id"].notna() & (persons_df["gang_id"] != "")]
        civilians = persons_df[persons_df["gang_id"].isna() | (persons_df["gang_id"] == "")]

        if gang_members.empty:
            raise ValueError("persons_df has no gang-affiliated members to draw an accused from")

        firs = []
        for i in range(num_firs):
            accused_row = gang_members.sample(1, random_state=self._rng.randint(0, 10 ** 6)).iloc[0]

            # complainant is usually a civilian, occasionally a rival gang member
            if not civilians.empty and self._rng.random() < 0.7:
                complainant_row = civilians.sample(1, random_state=self._rng.randint(0, 10 ** 6)).iloc[0]
            else:
                complainant_row = persons_df.sample(1, random_state=self._rng.randint(0, 10 ** 6)).iloc[0]

            incident_type = self._rng.choice(list(_NARRATIVE_TEMPLATES.keys()))
            raw_date = self._random_raw_date()
            location = self._standardizer.location.standardize(accused_row["address"])

            narrative = _NARRATIVE_TEMPLATES[incident_type].format(
                date=raw_date,
                complainant=complainant_row["full_name"],
                accused=accused_row["full_name"],
                location=location.normalized,
            )

            fir = FIRDocument(
                fir_id=f"FIR{i + 1:06d}",
                police_station=self._rng.choice(_POLICE_STATIONS),
                date_filed=self._standardizer.date.standardize(raw_date, assume_date_only=True),
                complainant_id=complainant_row["person_id"],
                complainant_name=complainant_row["full_name"],
                accused_ids=[accused_row["person_id"]],
                gang_id=accused_row["gang_id"] if pd.notna(accused_row["gang_id"]) and accused_row["gang_id"] else None,
                incident_type=incident_type,
                incident_location=location,
                narrative=narrative,
            )
            firs.append(fir)

        return firs

    def _random_raw_date(self) -> str:
        month = self._rng.randint(1, 12)
        day = self._rng.randint(1, 28)
        # Deliberately vary the raw format to exercise the DateStandardizer
        fmt = self._rng.choice(["{d}/{m}/{y}", "{y}-{m:02d}-{d:02d}", "{m}/{d}/{y}"])
        return fmt.format(d=day, m=month, y=self._start_year)
