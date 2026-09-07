"""
report_generator.py
---------------------
Generates synthetic analyst-style intelligence reports by aggregating the
Phase 1 datasets (persons, calls, transactions, meetings) per gang. These
reports give the NLP pipeline realistic longer-form prose to clean,
language-detect and translate.
"""

import random
from typing import List, Optional

import pandas as pd

from .models import IntelligenceReport, RiskLevel


class ReportGenerator:
    def __init__(self, rng: Optional[random.Random] = None, generated_date: str = "2026-01-15"):
        self._rng = rng or random.Random(7)
        self._generated_date = generated_date

    def generate(
        self,
        persons_df: pd.DataFrame,
        calls_df: pd.DataFrame,
        transactions_df: pd.DataFrame,
        meetings_df: pd.DataFrame,
    ) -> List[IntelligenceReport]:
        reports = []
        gang_ids = sorted(g for g in persons_df["gang_id"].dropna().unique() if g)

        for idx, gang_id in enumerate(gang_ids):
            members = persons_df[persons_df["gang_id"] == gang_id]
            member_ids = set(members["person_id"])

            gang_calls = calls_df[
                calls_df["caller_id"].isin(member_ids) | calls_df["receiver_id"].isin(member_ids)
            ]
            gang_txns = transactions_df[
                transactions_df["sender_id"].isin(member_ids) | transactions_df["receiver_id"].isin(member_ids)
            ]
            gang_meetings = meetings_df[
                meetings_df["attendee_ids"].apply(lambda ids: bool(set(str(ids).split("|")) & member_ids))
            ]

            total_amount = gang_txns["amount"].astype(float).sum() if not gang_txns.empty else 0.0
            risk_level = self._assess_risk(len(gang_calls), len(gang_txns), total_amount)
            boss_row = members[members["role"] == "boss"]
            boss_name = boss_row.iloc[0]["full_name"] if not boss_row.empty else "unidentified leadership"

            summary = (
                f"This report summarizes observed activity for gang {gang_id} over the "
                f"reporting period. Analysis of communication metadata identified "
                f"{len(gang_calls)} call events and {len(gang_meetings)} physical "
                f"meeting events among {len(members)} known associates. Financial "
                f"intelligence recorded {len(gang_txns)} transactions totaling "
                f"approximately {total_amount:,.2f} across monitored channels. "
                f"Leadership is attributed to {boss_name}. Overall risk assessment "
                f"for this network is classified as {risk_level.upper()}. Continued "
                f"monitoring of financial channels and known associate communications "
                f"is recommended."
            )

            report = IntelligenceReport(
                report_id=f"IR{idx + 1:05d}",
                generated_date=self._generated_date,
                title=f"Gang Activity Assessment: {gang_id}",
                subject_person_ids=list(member_ids)[:25],  # cap for readability
                gang_ids=[gang_id],
                risk_level=risk_level,
                summary=summary,
                evidence_channels=["calls", "transactions", "meetings"],
                confidence_score=self._rng.uniform(0.55, 0.95),
            )
            reports.append(report)

        return reports

    @staticmethod
    def _assess_risk(num_calls: int, num_txns: int, total_amount: float) -> str:
        score = num_calls * 0.02 + num_txns * 0.05 + total_amount / 100000
        if score > 400:
            return RiskLevel.CRITICAL.value
        if score > 200:
            return RiskLevel.HIGH.value
        if score > 80:
            return RiskLevel.MEDIUM.value
        return RiskLevel.LOW.value
