import os
import sys
import json
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from src.preprocessing.pipeline import PreprocessingPipeline, PipelineConfig


class TestPreprocessingPipeline(unittest.TestCase):
    """
    Runs the full pipeline against a small synthetic fixture (not the full
    5000-person Phase 1 dataset, to keep the test fast) and validates the
    shape and integrity of cleaned_records.json.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp_input = tempfile.mkdtemp()
        cls.tmp_output = tempfile.mkdtemp()

        persons = pd.DataFrame([
            {"person_id": "P1", "full_name": "Alice Boss", "phone_number": "+1-1111111111",
             "address": "1 Main St, Riverport", "age": "40", "gang_id": "G1", "role": "boss",
             "is_hidden_coordinator": "False"},
            {"person_id": "P2", "full_name": "Bob Lieutenant", "phone_number": "+1-2222222222",
             "address": "2 Elm St, Lakeview", "age": "29", "gang_id": "G1", "role": "lieutenant",
             "is_hidden_coordinator": "False"},
            {"person_id": "P3", "full_name": "Carol Civilian", "phone_number": "+1-3333333333",
             "address": "3 Church Rd, Eastgate", "age": "31", "gang_id": "", "role": "",
             "is_hidden_coordinator": "False"},
            {"person_id": "P4", "full_name": "Alice Boss", "phone_number": "+1-4444444444",
             "address": "1 Main St, Riverport", "age": "40", "gang_id": "G1", "role": "boss",
             "is_hidden_coordinator": "False"},  # deliberate near-duplicate of P1's text
        ])
        calls = pd.DataFrame([
            {"call_id": "C1", "caller_id": "P1", "receiver_id": "P2", "timestamp": "2025-01-01T00:00:00"},
        ])
        transactions = pd.DataFrame([
            {"transaction_id": "T1", "sender_id": "P1", "receiver_id": "P2", "amount": "9999"},
        ])
        meetings = pd.DataFrame([
            {"meeting_id": "M1", "location": "Warehouse", "timestamp": "2025-01-01T00:00:00",
             "attendee_ids": "P1|P2"},
        ])

        persons.to_csv(os.path.join(cls.tmp_input, "persons.csv"), index=False)
        calls.to_csv(os.path.join(cls.tmp_input, "calls.csv"), index=False)
        transactions.to_csv(os.path.join(cls.tmp_input, "transactions.csv"), index=False)
        meetings.to_csv(os.path.join(cls.tmp_input, "meetings.csv"), index=False)

        config = PipelineConfig(
            input_dir=cls.tmp_input,
            output_dir=cls.tmp_output,
            num_firs=5,
            ocr_sample_size=2,
        )
        cls.pipeline = PreprocessingPipeline(config)
        cls.summary = cls.pipeline.run()

        with open(os.path.join(cls.tmp_output, "cleaned_records.json"), encoding="utf-8") as f:
            cls.records = json.load(f)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_input, ignore_errors=True)
        shutil.rmtree(cls.tmp_output, ignore_errors=True)

    def test_output_file_created(self):
        self.assertTrue(os.path.exists(os.path.join(self.tmp_output, "cleaned_records.json")))

    def test_record_counts(self):
        persons = [r for r in self.records if r["record_type"] == "person"]
        firs = [r for r in self.records if r["record_type"] == "fir"]
        reports = [r for r in self.records if r["record_type"] == "intelligence_report"]
        self.assertEqual(len(persons), 4)
        self.assertEqual(len(firs), 5)
        self.assertEqual(len(reports), 1)  # only gang G1 present

    def test_every_record_has_required_fields(self):
        required = {"record_id", "record_type", "text", "language",
                    "language_confidence", "is_duplicate", "metadata"}
        for record in self.records:
            self.assertTrue(required.issubset(record.keys()))

    def test_near_duplicate_person_flagged(self):
        p4 = next(r for r in self.records if r["record_id"] == "P4")
        self.assertTrue(p4["is_duplicate"])
        self.assertEqual(p4["duplicate_of"], "P1")

    def test_fir_metadata_has_standardized_date_and_location(self):
        fir = next(r for r in self.records if r["record_type"] == "fir")
        self.assertRegex(fir["metadata"]["date_filed"], r"^\d{4}-\d{2}-\d{2}")
        self.assertIn("normalized", fir["metadata"]["location"])

    def test_summary_object_matches_json(self):
        self.assertEqual(self.summary.num_persons, 4)
        self.assertEqual(self.summary.num_firs, 5)
        self.assertEqual(self.summary.num_reports, 1)
        self.assertGreaterEqual(self.summary.num_duplicates_removed_flagged, 1)


if __name__ == "__main__":
    unittest.main()
