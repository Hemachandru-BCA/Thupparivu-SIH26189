"""ner.py tests - rule layers run without a model; PERSON tests skip cleanly."""

import pytest
import spacy

from src.extraction.ner import EntityExtractor

HAS_MODEL = spacy.util.is_package("en_core_web_sm")
requires_model = pytest.mark.skipif(
    not HAS_MODEL, reason="spaCy model 'en_core_web_sm' is not installed")


@pytest.fixture(scope="module")
def rules_only():
    return EntityExtractor(model_name=None)


@pytest.fixture(scope="module")
def with_model():
    if not HAS_MODEL:
        pytest.skip("spaCy model 'en_core_web_sm' is not installed")
    return EntityExtractor(model_name="en_core_web_sm")


# ------------- rule layers (no model required) ------------- #

def test_phone_international(rules_only):
    entities = rules_only.extract("Sunil called from +91-98765-43210 today.")
    assert "+91-98765-43210" in [e.text for e in entities if e.label == "PHONE"]


def test_phone_us_style(rules_only):
    entities = rules_only.extract("Reach him at 555-555-0134 or the office.")
    assert "555-555-0134" in [e.text for e in entities if e.label == "PHONE"]


def test_vehicle_brand_model_color(rules_only):
    entities = rules_only.extract("Vikram drives a black Toyota Camry.")
    assert "black Toyota Camry" in [e.text for e in entities if e.label == "VEHICLE"]


def test_vehicle_generic_type(rules_only):
    entities = rules_only.extract("They left in a blue SUV.")
    assert "blue SUV" in [e.text for e in entities if e.label == "VEHICLE"]


def test_vehicle_license_plate(rules_only):
    entities = rules_only.extract("The car bore plate MH 12 AB 1234.")
    assert "MH 12 AB 1234" in [e.text for e in entities if e.label == "VEHICLE"]


def test_tower_id_is_location(rules_only):
    entities = rules_only.extract("Signal bounced off TWR-012.")
    assert "TWR-012" in [e.text for e in entities if e.label == "LOCATION"]


def test_known_location_phrase(rules_only):
    entities = rules_only.extract("They gathered at the warehouse district.")
    assert "warehouse district" in [e.text.lower() for e in entities
                                    if e.label == "LOCATION"]


def test_organisation_suffix(rules_only):
    entities = rules_only.extract("He works for the Cobra Gang now.")
    assert "Cobra Gang" in [e.text for e in entities if e.label == "ORGANIZATION"]


def test_amounts_are_not_phones_or_vehicles(rules_only):
    entities = rules_only.extract("Ramesh transferred 5000 to Akash.")
    assert not [e for e in entities if e.label in ("PHONE", "VEHICLE")]


def test_extract_batch(rules_only):
    results = rules_only.extract_batch(["Call +1-202-555-0134.", "Nothing here."])
    assert results[0] and not results[1]


# ------------- statistical layer (model required) ------------- #

@requires_model
def test_person_entities(with_model):
    entities = with_model.extract("Ramesh transferred 5000 to Akash.")
    persons = [e.text for e in entities if e.label == "PERSON"]
    assert "Ramesh" in persons and "Akash" in persons


@requires_model
def test_gpe_canonicalised_to_location(with_model):
    entities = with_model.extract("The consignment passed through Mumbai and Delhi.")
    locations = [e.text for e in entities if e.label == "LOCATION"]
    assert "Mumbai" in locations and "Delhi" in locations


@requires_model
def test_gazetteer_organisation(with_model):
    entities = with_model.extract("He met the board of Blue Horizon Trading.")
    assert "Blue Horizon Trading" in [e.text for e in entities
                                      if e.label == "ORGANIZATION"]
