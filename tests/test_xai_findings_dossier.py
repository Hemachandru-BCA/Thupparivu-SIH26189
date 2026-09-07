"""Tests for XAI findings and dossier generation (src/xai/findings.py,
src/xai/dossier_generator.py, src/xai/llm_providers.py)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.xai.dossier_generator import (  # noqa: E402
    Dossier,
    DossierGenerator,
    validate_dossier,
)
from src.xai.evidence_tracer import (  # noqa: E402
    EvidenceRecord,
    EvidenceStore,
    make_evidence_id,
)
from src.xai.findings import (  # noqa: E402
    Claim,
    Finding,
    FindingBuilder,
    validate_finding,
)
from src.xai.llm_providers import MockLLMProvider, provider_from_env  # noqa: E402


@pytest.fixture(scope="module")
def store_and_findings():
    from src.api import paths

    if not paths.EVIDENCE_INDEX_PATH.exists() or not paths.GHOST_PREDICTIONS_PATH.exists():
        pytest.skip("artifacts not built - run the pipeline first")
    store = EvidenceStore.from_json(paths.EVIDENCE_INDEX_PATH)
    ghost_doc = json.loads(paths.GHOST_PREDICTIONS_PATH.read_text())
    ghosts = (ghost_doc.get("ghost_nodes") or ghost_doc.get("ghosts") or [])
    builder = FindingBuilder(store)
    findings = builder.build_all(ghosts)
    if not findings:
        pytest.skip("no ghost candidates in artifacts")
    return store, findings


# --------------------------------------------------------------------- findings
def test_finding_structure_and_labels(store_and_findings):
    store, findings = store_and_findings
    f = findings[0]
    assert f.finding_type == "HIDDEN_INTERMEDIARY"
    assert f.status == "HYPOTHESIS"
    assert f.human_review["required"] is True
    labels = {c.label for c in f.observed}
    assert labels <= {"OBSERVED"}
    assert all(c.label == "INFERRED" for c in f.inferred)
    assert f.unknown, "unknowns must be listed"


def test_validate_finding_passes_on_real_data(store_and_findings):
    store, findings = store_and_findings
    for f in findings:
        report = validate_finding(f, store)
        assert report.valid, f.errors


def test_validate_finding_catches_fabricated_evidence(store_and_findings):
    store, findings = store_and_findings
    f = findings[0].model_copy(deep=True)
    f.supporting_evidence_ids.append("EV-does-not-exist")
    report = validate_finding(f, store)
    assert not report.valid
    assert any("not found" in e for e in report.errors)


def test_validate_finding_requires_evidence_for_observed():
    store = EvidenceStore()
    f = Finding(
        id="F-test", finding_type="HIDDEN_INTERMEDIARY", subject_id="G1",
        observed=[Claim(text="a fact", label="OBSERVED", evidence_ids=[])],
    )
    report = validate_finding(f, store)
    assert not report.valid


# --------------------------------------------------------------------- dossier
def test_mock_provider_deterministic():
    p1 = MockLLMProvider().generate("prompt", [{"kind": "subject", "items": [1]}])
    p2 = MockLLMProvider().generate("prompt", [{"kind": "subject", "items": [1]}])
    assert p1 == p2  # offline reproducibility


def test_provider_default_is_mock(monkeypatch):
    monkeypatch.delenv("SENTINELGRAPH_LLM_API_KEY", raising=False)
    assert isinstance(provider_from_env(), MockLLMProvider)


def test_google_provider_is_selected_when_google_url_is_configured(monkeypatch):
    monkeypatch.setenv("SENTINELGRAPH_LLM_API_KEY", "test-google-key")
    monkeypatch.setenv("SENTINELGRAPH_LLM_API_KEY_FALLBACK", "test-google-fallback-key")
    monkeypatch.setenv("SENTINELGRAPH_LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
    monkeypatch.setenv("SENTINELGRAPH_LLM_MODEL", "gemini-2.0-flash")
    provider = provider_from_env()
    assert provider.__class__.__name__ == "GoogleAICompatProvider"
    assert provider.api_keys == ("test-google-key", "test-google-fallback-key")
    assert provider.endpoint.endswith("models/gemini-2.0-flash:generateContent")


def test_dossier_generation_and_validation(store_and_findings, tmp_path):
    store, findings = store_and_findings
    gen = DossierGenerator(store, llm=MockLLMProvider())
    dossier = gen.generate_dossier(findings[0].subject_id)
    assert dossier.status == "DRAFT_FOR_HUMAN_REVIEW"
    assert dossier.human_review["required"] is True
    assert dossier.limitations, "limitations must always be present"
    assert dossier.executive_summary
    report = validate_dossier(dossier, store)
    assert report.valid, report.errors


def test_dossier_fallback_on_broken_llm(store_and_findings):
    """A malformed LLM response must never break the dossier pipeline."""

    class BrokenProvider:
        name = "broken"

        def generate(self, prompt, context):
            return "this is not json at all"

    store, findings = store_and_findings
    gen = DossierGenerator(store, llm=BrokenProvider())
    dossier = gen.generate_dossier(findings[0].subject_id)
    assert dossier.executive_summary  # deterministic fallback used
    assert dossier.model_metadata["llm_provider"] == "broken"
    assert validate_dossier(dossier, store).valid


def test_dossier_never_cites_unknown_evidence(store_and_findings):
    store, findings = store_and_findings
    gen = DossierGenerator(store, llm=MockLLMProvider())
    dossier = gen.generate_dossier(findings[0].subject_id)
    known = set(store.all_ids())
    for eid in dossier.supporting_evidence:
        assert eid in known
    for eid in dossier.counter_evidence:
        assert eid in known
