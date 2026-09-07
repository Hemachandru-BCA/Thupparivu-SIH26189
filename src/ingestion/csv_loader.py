"""
csv_loader.py
-------------
Ingestion module responsible for loading the CriminalAnalysis AI synthetic
CSV datasets (persons, calls, transactions, meetings) into memory as lists
of dicts, with light validation and optional pandas DataFrame conversion.
"""

import csv
import os
from typing import List, Dict, Optional


class DatasetValidationError(Exception):
    pass


class CsvLoader:
    """
    Loads one or more CSV files from a directory into structured records.

    Example:
        loader = CsvLoader(base_dir="data/synthetic")
        persons = loader.load("persons.csv", required_columns=["person_id", "full_name"])
        all_data = loader.load_all()
    """

    EXPECTED_FILES: Dict[str, List[str]] = {
        "persons.csv": ["person_id", "full_name", "phone_number", "address", "age"],
        "calls.csv": ["call_id", "caller_id", "receiver_id", "timestamp"],
        "transactions.csv": ["transaction_id", "sender_id", "receiver_id", "amount"],
        "meetings.csv": ["meeting_id", "location", "timestamp", "attendee_ids"],
    }

    def __init__(self, base_dir: str = "data/synthetic"):
        self.base_dir = base_dir

    def load(self, filename: str, required_columns: Optional[List[str]] = None) -> List[Dict]:
        filepath = os.path.join(self.base_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Dataset file not found: {filepath}")

        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if required_columns:
            self._validate_columns(filename, reader.fieldnames or [], required_columns)

        return rows

    def load_all(self) -> Dict[str, List[Dict]]:
        """Load every expected dataset file found in base_dir."""
        datasets = {}
        for filename, required_cols in self.EXPECTED_FILES.items():
            filepath = os.path.join(self.base_dir, filename)
            if os.path.exists(filepath):
                datasets[filename] = self.load(filename, required_columns=required_cols)
        return datasets

    def load_as_dataframe(self, filename: str):
        """Optional convenience method; requires pandas to be installed."""
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "pandas is required for load_as_dataframe(); pip install pandas"
            ) from exc

        filepath = os.path.join(self.base_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Dataset file not found: {filepath}")
        return pd.read_csv(filepath)

    @staticmethod
    def _validate_columns(filename: str, actual_columns: List[str], required_columns: List[str]) -> None:
        missing = [c for c in required_columns if c not in actual_columns]
        if missing:
            raise DatasetValidationError(
                f"{filename} is missing required columns: {missing}"
            )
