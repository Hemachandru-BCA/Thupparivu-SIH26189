"""
test_ingestion.py
-------------------
Unit tests for csv_loader.py and api_loader.py.
"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.csv_loader import CsvLoader, DatasetValidationError
from src.ingestion.api_loader import ApiLoader, ApiLoaderError


class TestCsvLoader(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.persons_path = os.path.join(self.tmpdir, "persons.csv")
        with open(self.persons_path, "w") as f:
            f.write("person_id,full_name,phone_number,address,age\n")
            f.write("P000001,John Doe,+1-5551234567,123 Main St,34\n")

        self.bad_path = os.path.join(self.tmpdir, "bad.csv")
        with open(self.bad_path, "w") as f:
            f.write("id,name\n1,Test\n")

    def test_load_valid_file(self):
        loader = CsvLoader(base_dir=self.tmpdir)
        rows = loader.load("persons.csv", required_columns=["person_id", "full_name"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["full_name"], "John Doe")

    def test_missing_file_raises(self):
        loader = CsvLoader(base_dir=self.tmpdir)
        with self.assertRaises(FileNotFoundError):
            loader.load("does_not_exist.csv")

    def test_missing_required_columns_raises(self):
        loader = CsvLoader(base_dir=self.tmpdir)
        with self.assertRaises(DatasetValidationError):
            loader.load("bad.csv", required_columns=["person_id"])

    def test_load_all_only_picks_existing_files(self):
        loader = CsvLoader(base_dir=self.tmpdir)
        datasets = loader.load_all()
        self.assertIn("persons.csv", datasets)
        self.assertNotIn("calls.csv", datasets)  # not created in this fixture


class TestApiLoader(unittest.TestCase):
    def test_headers_include_bearer_token(self):
        loader = ApiLoader(base_url="https://example.com/api", api_key="abc123")
        headers = loader._headers()
        self.assertEqual(headers["Authorization"], "Bearer abc123")

    @patch("src.ingestion.api_loader._HAS_REQUESTS", False)
    @patch("src.ingestion.api_loader.urllib_request.urlopen")
    def test_fetch_page_uses_urllib_fallback(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"results": [{"person_id": "P1"}], "next_page": None}
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        loader = ApiLoader(base_url="https://example.com/api")
        payload = loader.fetch_page("persons", page=1)
        self.assertEqual(payload["results"][0]["person_id"], "P1")

    @patch("src.ingestion.api_loader._HAS_REQUESTS", False)
    @patch("src.ingestion.api_loader.urllib_request.urlopen")
    def test_fetch_all_paginates(self, mock_urlopen):
        pages = [
            {"results": [{"id": 1}], "next_page": 2},
            {"results": [{"id": 2}], "next_page": None},
        ]
        mock_responses = []
        for page in pages:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(page).encode("utf-8")
            mock_responses.append(mock_resp)

        mock_urlopen.return_value.__enter__.side_effect = mock_responses

        loader = ApiLoader(base_url="https://example.com/api")
        records = loader.fetch_all("persons")
        self.assertEqual(len(records), 2)

    @patch("src.ingestion.api_loader._HAS_REQUESTS", False)
    @patch("src.ingestion.api_loader.urllib_request.urlopen", side_effect=Exception("boom"))
    def test_fetch_page_raises_after_retries(self, mock_urlopen):
        loader = ApiLoader(base_url="https://example.com/api", max_retries=1)
        with self.assertRaises(ApiLoaderError):
            loader.fetch_page("persons")


if __name__ == "__main__":
    unittest.main()
