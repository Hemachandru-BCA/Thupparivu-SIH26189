import os
import sys
import unittest
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from src.preprocessing.fir_simulator import FirSimulator
from src.preprocessing.report_generator import ReportGenerator
from src.preprocessing.models import FIRDocument, IntelligenceReport


def _make_persons_df():
    return pd.DataFrame([
        {"person_id": "P1", "full_name": "Alice Boss", "phone_number": "+1-1111111111",
         "address": "1 Main St, Riverport", "age": "40", "gang_id": "G1", "role": "boss",
         "is_hidden_coordinator": "False"},
        {"person_id": "P2", "full_name": "Bob Member", "phone_number": "+1-2222222222",
         "address": "2 Elm St, Lakeview", "age": "25", "gang_id": "G1", "role": "member",
         "is_hidden_coordinator": "False"},
        {"person_id": "P3", "full_name": "Carol Civilian", "phone_number": "+1-3333333333",
         "address": "3 Church Rd, Eastgate", "age": "31", "gang_id": "", "role": "",
         "is_hidden_coordinator": "False"},
    ])


def _make_calls_df():
    return pd.DataFrame([
        {"call_id": "C1", "caller_id": "P1", "receiver_id": "P2", "timestamp": "2025-01-01T00:00:00"},
        {"call_id": "C2", "caller_id": "P2", "receiver_id": "P3", "timestamp": "2025-01-02T00:00:00"},
    ])


def _make_transactions_df():
    return pd.DataFrame([
        {"transaction_id": "T1", "sender_id": "P1", "receiver_id": "P2", "amount": "5000"},
    ])


def _make_meetings_df():
    return pd.DataFrame([
        {"meeting_id": "M1", "location": "Warehouse", "timestamp": "2025-01-01T00:00:00",
         "attendee_ids": "P1|P2"},
    ])


class TestFirSimulator(unittest.TestCase):
    def setUp(self):
        self.sim = FirSimulator(rng=random.Random(1))
        self.persons_df = _make_persons_df()

    def test_generates_requested_count(self):
        firs = self.sim.generate(self.persons_df, 5)
        self.assertEqual(len(firs), 5)

    def test_each_fir_is_valid_model(self):
        firs = self.sim.generate(self.persons_df, 3)
        for fir in firs:
            self.assertIsInstance(fir, FIRDocument)
            self.assertTrue(fir.narrative)
            self.assertRegex(fir.date_filed, r"^\d{4}-\d{2}-\d{2}")

    def test_accused_always_gang_affiliated(self):
        firs = self.sim.generate(self.persons_df, 10)
        gang_ids = set(self.persons_df[self.persons_df["gang_id"] != ""]["person_id"])
        for fir in firs:
            for accused_id in fir.accused_ids:
                self.assertIn(accused_id, gang_ids)

    def test_raises_when_no_gang_members(self):
        civilians_only = self.persons_df[self.persons_df["gang_id"] == ""]
        with self.assertRaises(ValueError):
            self.sim.generate(civilians_only, 1)


class TestReportGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = ReportGenerator(rng=random.Random(1))

    def test_one_report_per_gang(self):
        reports = self.gen.generate(
            _make_persons_df(), _make_calls_df(), _make_transactions_df(), _make_meetings_df()
        )
        self.assertEqual(len(reports), 1)  # only G1 has members

    def test_report_is_valid_model_with_summary(self):
        reports = self.gen.generate(
            _make_persons_df(), _make_calls_df(), _make_transactions_df(), _make_meetings_df()
        )
        report = reports[0]
        self.assertIsInstance(report, IntelligenceReport)
        self.assertIn("G1", report.summary)
        self.assertTrue(0.0 <= report.confidence_score <= 1.0)

    def test_risk_level_is_valid_value(self):
        reports = self.gen.generate(
            _make_persons_df(), _make_calls_df(), _make_transactions_df(), _make_meetings_df()
        )
        self.assertIn(reports[0].risk_level, {"low", "medium", "high", "critical"})


if __name__ == "__main__":
    unittest.main()
