"""
resolution/er_benchmark.py
--------------------------
Entity-resolution benchmark generation + metrics (Phase 3, requirement 7).

Generates controlled duplicate record sets with:

* typos
* missing fields
* transliteration
* abbreviations
* conflicting attributes
* partial records

and measures precision / recall / F1 / false-merge rate / false-split rate
for any resolver that exposes a ``decide(a, b) -> decision`` interface
(our :class:`HybridEntityResolver` does exactly that).
"""

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from src.resolution.hybrid_resolver import (
    MATCH,
    POSSIBLE_MATCH,
    NON_MATCH,
    UNKNOWN,
    HybridEntityResolver,
    ResolvableRecord,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Ground-truth generation
# --------------------------------------------------------------------------- #

_NAME_PARTS = ["Ravi", "Kumar", "Priya", "Sharma", "Arjun", "Reddy", "Meena",
               "Verma", "Karthik", "Iyengar", "Lakshmi", "Nair", "Vijay",
               "Menon", "Divya", "Patil", "Suresh", "Gupta", "Anita", "Rao"]

_PHONE_PREFIXES = ["98", "97", "96", "99", "94", "90", "81", "88"]

_STREETS = ["Gandhi Road", "Nehru Street", "Anna Salai", "Mount Road",
            "Park Street", "Church Street", "MG Road", "Link Road"]
_CITIES = ["Chennai", "Coimbatore", "Madurai", "Trichy", "Salem"]
_ORGS = ["Tamil Nadu Traders", "Chennai Logistics", "Madurai Metals",
         "Kovai Textiles", "Coastal Fisheries"]

#: Common typo operators
_TYPO_OPS = [
    lambda s: s[:-1] if len(s) > 4 else s,                       # drop last char
    lambda s: s[:1] + s[2:] if len(s) > 2 else s,                # drop 2nd char
    lambda s: s[: len(s)//2] + "x" + s[len(s)//2+1:] if len(s) > 2 else s,  # swap middle
    lambda s: s[::-1] if len(s) <= 10 else s,                    # reverse short names
    lambda s: re.sub(r"i", "ee", s),                              # translit
    lambda s: re.sub(r"h", "", s),                                # drop h
]

_TRANSLITERATION_PAIRS = [
    ("Kumar", "Kumaar"),
    ("Priya", "Priyaa"),
    ("Sharma", "Sarma"),
    ("Karthik", "Karthick"),
    ("Ravi", "Ravie"),
]


@dataclass
class ErBenchmarkCase:
    """One controlled resolution case with the true cluster id."""

    cluster_id: str
    records: List[ResolvableRecord]

    def canonical_name(self) -> str:
        return self.records[0].name


@dataclass
class ErBenchmark:
    """A synthetic entity-resolution benchmark set."""

    cases: List[ErBenchmarkCase]
    seed: int = 42

    # ------------------------------------------------------------------ #
    def mention_pairs(self) -> List[Tuple[ResolvableRecord, ResolvableRecord, bool]]:
        """All record pairs across the whole benchmark with a true label.

        True positive pairs share a cluster_id; negative pairs come from
        different clusters (sampled to keep the set tractable).
        """
        positives: List[Tuple[ResolvableRecord, ResolvableRecord, bool]] = []
        negatives: List[Tuple[ResolvableRecord, ResolvableRecord, bool]] = []
        for case in self.cases:
            records = case.records
            for i in range(len(records)):
                for j in range(i + 1, len(records)):
                    positives.append((records[i], records[j], True))

        # negative pairs: different clusters, capped for tractability
        rng = random.Random(self.seed)
        cluster_ids = list(range(len(self.cases)))
        sampled = 0
        target = min(1000, len(positives) * 3)
        seen: set = set()
        while sampled < target and len(cluster_ids) >= 2:
            ci, cj = rng.sample(cluster_ids, 2)
            ri = self.cases[ci].records[rng.randrange(len(self.cases[ci].records))]
            rj = self.cases[cj].records[rng.randrange(len(self.cases[cj].records))]
            key = (ri.record_id, rj.record_id)
            if key not in seen:
                seen.add(key)
                negatives.append((ri, rj, False))
                sampled += 1
        return positives + negatives


# --------------------------------------------------------------------------- #
# Generator
# --------------------------------------------------------------------------- #

class ErBenchmarkGenerator:
    """Generates controlled duplicate sets for entity-resolution testing."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)
        self.seed = seed

    def _make_base(self, cluster_id: str, index: int) -> ResolvableRecord:
        first = self.rng.choice(_NAME_PARTS)
        last = self.rng.choice(_NAME_PARTS)
        phone = self.rng.choice(_PHONE_PREFIXES) + "".join(
            str(self.rng.randint(0, 9)) for _ in range(8))
        email = f"person{index}@example.com"
        addr = f"{self.rng.choice(_STREETS)}, {self.rng.choice(_CITIES)}"
        return ResolvableRecord(
            record_id=f"{cluster_id}-rec{index}",
            name=f"{first} {last}",
            entity_type="PERSON",
            phone=phone,
            email=email,
            address=addr,
            organization=self.rng.choice(_ORGS),
            identifiers={"uid": f"UID-{index}"},
            locations=[self.rng.choice(_CITIES)],
        )

    def _duplicate(self, base: ResolvableRecord, variant: str) -> ResolvableRecord:
        """Produce a duplicate record of the base with the given perturbation."""
        r = ResolvableRecord(
            record_id=f"{base.record_id}-{variant}",
            name=base.name,
            entity_type="PERSON",
            phone=base.phone,
            email=base.email,
            address=base.address,
            organization=base.organization,
            identifiers=dict(base.identifiers),
            locations=list(base.locations),
        )
        if variant == "typo":
            r.name = self.rng.choice(_TYPO_OPS)(base.name)
        elif variant == "missing_phone":
            r.phone = None
        elif variant == "missing_address":
            r.address = None
        elif variant == "transliteration":
            for a, b in _TRANSLITERATION_PAIRS:
                if a.lower() in r.name.lower():
                    r.name = re.sub(a, b, r.name, flags=re.IGNORECASE)
                    break
        elif variant == "abbreviation":
            parts = r.name.split()
            if len(parts) >= 2:
                r.name = f"{parts[0][0]}. {parts[-1]}"
        elif variant == "conflicting_phone":
            r.phone = self.rng.choice(_PHONE_PREFIXES) + "".join(
                str(self.rng.randint(0, 9)) for _ in range(8))
        elif variant == "partial":
            r.email = None
            r.organization = None
        return r

    def generate(self, n_clusters: int = 20, duplicates_per_cluster: int = 3,
                 variants: Optional[List[str]] = None) -> ErBenchmark:
        """Generate a benchmark with ``n_clusters`` true entities."""
        variants = variants or ["typo", "missing_phone", "transliteration",
                                "abbreviation", "partial", "conflicting_phone"]
        cases: List[ErBenchmarkCase] = []
        for c in range(n_clusters):
            cluster_id = f"CL-{c:03d}"
            base = self._make_base(cluster_id, c * 10)
            records = [base]
            for d in range(1, duplicates_per_cluster + 1):
                variant = variants[(c + d) % len(variants)]
                records.append(self._duplicate(base, variant))
            cases.append(ErBenchmarkCase(cluster_id=cluster_id, records=records))
        return ErBenchmark(cases=cases, seed=self.seed)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #

@dataclass
class ErMetrics:
    """Precision / recall / F1 + merge/split error rates."""

    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    false_merge_rate: float = 0.0
    false_split_rate: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "false_merge_rate": round(self.false_merge_rate, 4),
            "false_split_rate": round(self.false_split_rate, 4),
        }


def evaluate_resolution(
    benchmark: ErBenchmark,
    resolver: HybridEntityResolver,
    *,
    counts_only: bool = False,
    extras: Optional[Dict[str, List[ResolvableRecord]]] = None,
) -> ErMetrics:
    """Evaluate a resolver against a benchmark.

    A decision counts as:

    * TP  — true same-cluster pair decided MATCH or POSSIBLE_MATCH
    * FP  — different-cluster pair decided MATCH or POSSIBLE_MATCH
    * FN  — true pair decided NON_MATCH or UNKNOWN
    * TN  — different pair decided NON_MATCH or UNKNOWN

    False-merge rate = FP / (TN + FP); false-split = FN / (TP + FN).
    """
    pairs = benchmark.mention_pairs()
    tp = fp = fn = tn = 0
    for a, b, same in pairs:
        decision = resolver.decide(a, b)
        positive = decision.decision in (MATCH, POSSIBLE_MATCH)
        if same and positive:
            tp += 1
        elif same and not positive:
            fn += 1
        elif not same and positive:
            fp += 1
        else:
            tn += 1

    metrics = ErMetrics(
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
    )
    metrics.precision = tp / (tp + fp) if (tp + fp) else 0.0
    metrics.recall = tp / (tp + fn) if (tp + fn) else 0.0
    metrics.f1 = (2 * metrics.precision * metrics.recall /
                  (metrics.precision + metrics.recall)
                  if (metrics.precision + metrics.recall) else 0.0)
    metrics.false_merge_rate = fp / (fp + tn) if (fp + tn) else 0.0
    metrics.false_split_rate = fn / (tp + fn) if (tp + fn) else 0.0
    _ = counts_only
    _ = extras
    return metrics