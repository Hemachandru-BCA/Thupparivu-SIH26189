"""Tests for the Phase-3 hybrid entity resolution, alias normalization and
entity-resolution benchmark."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.resolution.alias_normalizer import (  # noqa: E402
    AliasNormalizer,
    compare_aliases,
)
from src.resolution.er_benchmark import (  # noqa: E402
    ErBenchmarkGenerator,
    evaluate_resolution,
)
from src.resolution.hybrid_resolver import (  # noqa: E402
    MATCH,
    NON_MATCH,
    POSSIBLE_MATCH,
    UNKNOWN,
    HybridEntityResolver,
    HybridResolverConfig,
    ResolvableRecord,
)


# ------------------------------------------------------------------ #
# Alias normalization
# ------------------------------------------------------------------ #

def test_phone_normalization():
    n = AliasNormalizer()
    assert n.normalize_phone("+91 98400 12345") == "9840012345"
    assert n.normalize_phone("09840012345") == "9840012345"
    assert n.normalize_phone("9840012345") == "9840012345"


def test_vehicle_normalization():
    n = AliasNormalizer()
    assert n.normalize_vehicle("TN-01-AB-1234") == "TN01AB1234"
    assert n.normalize_vehicle("TN 01 AB 1234") == "TN01AB1234"


def test_address_normalization():
    n = AliasNormalizer()
    a = n.normalize_address("12, Gandhi Road, Chennai")
    b = n.normalize_address("Gandhi Road Chennai")
    assert a == b


def test_transliteration_key():
    n = AliasNormalizer()
    assert n.transliteration_key("Mohammed") == n.transliteration_key("Mohammad")
    # 'Sharma' vs 'Sarma' — sh→s canonical
    assert n.all_keys("Sharma") & n.all_keys("Sarma")


def test_initials_key():
    n = AliasNormalizer()
    assert n.initials_key("J. Doe") == n.initials_key("John Doe")


def test_compare_aliases_phone():
    assert compare_aliases("+91 98400 12345", "9840012345", "PHONE") == 1.0
    assert compare_aliases("9840012345", "9876543210", "PHONE") == 0.0


# ------------------------------------------------------------------ #
# Hybrid resolver
# ------------------------------------------------------------------ #

def test_exact_phone_strong_match():
    resolver = HybridEntityResolver()
    a = ResolvableRecord(record_id="a", name="Ravi Kumar",
                         phone="9840012345", entity_type="PERSON")
    b = ResolvableRecord(record_id="b", name="R. Kumar",
                         phone="9840012345", entity_type="PERSON")
    dec = resolver.decide(a, b)
    assert dec.decision == MATCH


def test_strong_identifier_match():
    resolver = HybridEntityResolver()
    a = ResolvableRecord(record_id="a", name="Ravi Kumar",
                         identifiers={"pan": "ABCDE1234F"})
    b = ResolvableRecord(record_id="b", name="R. Kumar",
                         identifiers={"pan": "ABCDE1234F"})
    dec = resolver.decide(a, b)
    assert dec.decision == MATCH


def test_type_separation_returns_non_match():
    resolver = HybridEntityResolver()
    a = ResolvableRecord(record_id="a", name="Ravi Kumar", entity_type="PERSON")
    b = ResolvableRecord(record_id="b", name="Ravi Kumar", entity_type="LOCATION")
    dec = resolver.decide(a, b)
    assert dec.decision == NON_MATCH


def test_same_name_possible_match_without_context():
    resolver = HybridEntityResolver()
    a = ResolvableRecord(record_id="a", name="Ravi Kumar")
    b = ResolvableRecord(record_id="b", name="Ravi Kumar")
    dec = resolver.decide(a, b)
    assert dec.decision in (MATCH, POSSIBLE_MATCH)


def test_conflicting_types_dont_force_match():
    resolver = HybridEntityResolver()
    a = ResolvableRecord(record_id="a", name="Karthik", entity_type="PERSON")
    b = ResolvableRecord(record_id="b", name="Karthik", entity_type="PHONE")
    dec = resolver.decide(a, b)
    assert dec.decision == NON_MATCH


def test_graph_context_lifts_similarity():
    cfg = HybridResolverConfig(name_weight=0.5, graph_weight=0.5)
    resolver = HybridEntityResolver(
        config=cfg,
        neighborhood={"a": ["x", "y", "z"], "b": ["x", "y", "z"]},
    )
    a = ResolvableRecord(record_id="a", name="Complete Different Name A", entity_type="PERSON")
    b = ResolvableRecord(record_id="b", name="Complete Different Name B", entity_type="PERSON")
    # without graph context the score would be ~0; with full neighborhood
    # overlap the graph weight lifts it substantially
    dec_nograph = HybridEntityResolver(config=cfg).decide(a, b)
    dec_graph = resolver.decide(a, b)
    assert dec_graph.score > dec_nograph.score


def test_resolve_all_deterministic():
    records = [
        ResolvableRecord(record_id="a", name="Ravi Kumar", phone="9840012345"),
        ResolvableRecord(record_id="b", name="R. Kumar", phone="9840012345"),
        ResolvableRecord(record_id="c", name="Priya Sharma", phone="9887712345"),
        ResolvableRecord(record_id="d", name="Priya Sarma", phone="9887712345"),
    ]
    r1 = HybridEntityResolver()
    r2 = HybridEntityResolver()
    d1 = r1.resolve_all(records)
    d2 = r2.resolve_all(records)
    assert [x.to_dict() for x in d1] == [x.to_dict() for x in d2]


def test_never_force_match_unknown_option():
    """With low name similarity and no strong signals, output is UNKNOWN or
    NON_MATCH — never a forced MATCH."""
    resolver = HybridEntityResolver()
    a = ResolvableRecord(record_id="a", name="Arjun Reddy")
    b = ResolvableRecord(record_id="b", name="Meena Verma")
    dec = resolver.decide(a, b)
    assert dec.decision in (UNKNOWN, NON_MATCH)


# ------------------------------------------------------------------ #
# Benchmark
# ------------------------------------------------------------------ #

def test_benchmark_generator_creates_duplicates():
    gen = ErBenchmarkGenerator(seed=7)
    bench = gen.generate(n_clusters=5, duplicates_per_cluster=2)
    assert len(bench.cases) == 5
    for case in bench.cases:
        assert len(case.records) == 3  # base + 2 duplicates


def test_benchmark_pairs_are_labeled():
    gen = ErBenchmarkGenerator(seed=7)
    bench = gen.generate(n_clusters=3, duplicates_per_cluster=2)
    pairs = bench.mention_pairs()
    assert len(pairs) > 0
    for a, b, same in pairs:
        assert isinstance(same, bool)


def test_evaluate_resolution_metrics_shape():
    gen = ErBenchmarkGenerator(seed=7)
    bench = gen.generate(n_clusters=4, duplicates_per_cluster=2)
    resolver = HybridEntityResolver()
    metrics = evaluate_resolution(bench, resolver)
    d = metrics.to_dict()
    assert "precision" in d
    assert "recall" in d
    assert "f1" in d
    assert "false_merge_rate" in d
    assert "false_split_rate" in d
    assert 0.0 <= d["f1"] <= 1.0


def test_evaluate_resolution_perfect_resolver():
    """A resolver that matches on exact record_id should get perfect scores."""
    gen = ErBenchmarkGenerator(seed=7)
    bench = gen.generate(n_clusters=3, duplicates_per_cluster=1)

    class ExactIdResolver:
        """Stub that always decides MATCH for same-cluster records."""
        def decide(self, a, b):
            from src.resolution.hybrid_resolver import ResolutionDecision, PairwiseFeatures
            same = "-".join(a.record_id.split("-")[:2]) == "-".join(
                b.record_id.split("-")[:2])
            return ResolutionDecision(
                left_id=a.record_id,
                right_id=b.record_id,
                decision=MATCH if same else NON_MATCH,
                score=1.0 if same else 0.0,
            )

    metrics = evaluate_resolution(bench, ExactIdResolver())
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0