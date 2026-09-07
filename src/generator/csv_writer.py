"""
csv_writer.py
-------------
Small helper that writes a list of objects exposing `.to_row()` to a CSV
file, creating parent directories as needed.
"""

import csv
import os
from typing import List, Any


class CsvWriter:
    @staticmethod
    def write(objects: List[Any], filepath: str) -> None:
        if not objects:
            raise ValueError(f"Nothing to write for {filepath} (empty list).")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        rows = [obj.to_row() for obj in objects]
        fieldnames = list(rows[0].keys())

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
