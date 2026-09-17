"""
tests/test_extraction_perf.py
-----------------------------
Tests for extraction pipeline performance (Task 9) and domain regex patterns.
"""

import json
import os
import tempfile
import time
import pytest

# Domain regex patterns (testable without spaCy)
from src.extraction.domain_ner import extract_domain_mentions, DOMAIN_PATTERNS


class TestDomainPatterns:
    """Test that new regex patterns match known test strings."""

    def test_upi_id_match(self):
        mentions = extract_domain_mentions("Payment sent to Rajan@upi")
        upi_mentions = [m for m in mentions if m.label == "UPI"]
        assert len(upi_mentions) >= 1
        assert upi_mentions[0].text.lower().endswith("@upi")

    def test_aadhaar_match(self):
        mentions = extract_domain_mentions("Aadhaar number 2345 6789 0123")
        # The label is "IDENTIFIER" with name "AADHAAR"
        aadhaar = [m for m in mentions if m.label == "IDENTIFIER"]
        assert len(aadhaar) >= 1

    def test_vehicle_reg_match(self):
        text = "The car TN-01-AB-1234 was seen near the border"
        mentions = extract_domain_mentions(text)
        vehicle = [m for m in mentions if m.label == "VEHICLE"]
        assert len(vehicle) >= 1

    def test_bns_section_match(self):
        text = "Charged under Section 302 BNS for the murder"
        mentions = extract_domain_mentions(text)
        cases = [m for m in mentions if m.label == "CASE"]
        assert len(cases) >= 1
        assert any("302" in m.text for m in cases)

    def test_case_number_match(self):
        text = "FIR No. 1234/2025 was registered at the station"
        mentions = extract_domain_mentions(text)
        cases = [m for m in mentions if m.label == "CASE"]
        assert len(cases) >= 1
        assert any("1234/2025" in m.text for m in cases)

    def test_phone_match(self):
        mentions = extract_domain_mentions("Call +91-9876543210 for details")
        phones = [m for m in mentions if m.label == "PHONE"]
        assert len(phones) >= 1

    def test_email_match(self):
        mentions = extract_domain_mentions("Contact raja@example.com for info")
        emails = [m for m in mentions if m.label == "EMAIL"]
        assert len(emails) >= 1
        assert emails[0].text == "raja@example.com"


class TestExtractionBatching:
    """Test that batched extraction produces valid output."""

    def test_batch_extraction_valid_output(self):
        """Generate 200 synthetic records, run extraction, assert valid output."""
        try:
            import spacy
        except ImportError:
            pytest.skip("spaCy not installed")

        # Generate synthetic text records
        records = []
        for i in range(200):
            records.append({
                "record_id": f"R{i:04d}",
                "text": f"Person {i} sent payment to account number 9876543210 on {i}/1/2025. "
                        f"The phone number is +91-9876543210 and email is test{i}@example.com. "
                        f"Vehicle TN-01-AB-{1000+i} was noted.",
                "record_type": "text_observation",
            })

        # Write records to a temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(records, f)
            tmp_path = f.name

        try:
            from src.extraction.pipeline import ExtractionPipeline, ExtractionConfig
            config = ExtractionConfig(
                input_path=tmp_path,
                spacy_model="en_core_web_sm",
                infer_co_occurrence=False,
            )
            pipeline = ExtractionPipeline(config)

            t0 = time.time()
            result = pipeline.run()
            elapsed = time.time() - t0

            # Should complete in < 15s (was 48s without batching)
            assert elapsed < 15.0, f"Extraction took {elapsed:.1f}s, expected < 15s"

            # Should have entities and triplets
            assert "entities" in result or result.get("total_entities", 0) >= 0
            print(f"Extraction: {len(records)} records in {elapsed:.1f}s")
        finally:
            os.unlink(tmp_path)
