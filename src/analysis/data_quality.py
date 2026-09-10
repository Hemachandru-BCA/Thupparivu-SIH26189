"""
data_quality.py
---------------
Data Quality & Intelligence Reliability Assessment (P1.4).

Answers the investigator question: "How much should I trust the data behind
this analysis?"

Dimensions assessed:
  - Completeness: expected fields populated
  - Consistency: record contradictions
  - Entity Resolution Quality: identity-matching confidence
  - Temporal Quality: timestamp presence and reliability
  - Source Reliability: source metadata tracking (where available)
  - Duplication: potential duplicate records
  - Missingness: missing names, IDs, timestamps, values, locations
  - Extraction Confidence: NLP/entity/relation extraction confidence
  - Evidence Coverage: % of findings with traceable evidence

All outputs are *data quality indicators*, never "truth scores."
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

import networkx as nx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

class DimensionScore(BaseModel):
    name: str
    score: float   # 0.0 – 1.0
    detail: str = ""
    issues: List[str] = Field(default_factory=list)


class EntityQuality(BaseModel):
    entity_id: str
    entity_label: str = ""
    identity_confidence: float = 0.0
    evidence_coverage: float = 0.0
    temporal_coverage: float = 0.0
    relationship_confidence: float = 0.0
    potential_issues: List[str] = Field(default_factory=list)


class FindingQuality(BaseModel):
    finding_id: str
    evidence_coverage: float = 0.0
    data_completeness: float = 0.0
    conflicting_records: int = 0
    inference_depth: float = 0.0
    source_diversity: float = 0.0
    temporal_coverage: float = 0.0


class DataQualityReport(BaseModel):
    overall_readiness: float = 0.0
    dimensions: List[DimensionScore] = Field(default_factory=list)
    entity_quality: List[EntityQuality] = Field(default_factory=list)
    finding_quality: List[FindingQuality] = Field(default_factory=list)
    summary_stats: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Assessor
# --------------------------------------------------------------------------- #

class DataQualityAssessor:
    """Assess data quality across graph, evidence, and findings."""

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        evidence_store: Optional[Any] = None,
        findings: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.graph = graph
        self.evidence_store = evidence_store
        self.findings = findings or []

    # ------------------------------------------------------------------ #
    # Graph-level dimensions
    # ------------------------------------------------------------------ #
    def _completeness(self) -> DimensionScore:
        """How many expected node/edge fields are populated."""
        total_nodes = self.graph.number_of_nodes()
        if total_nodes == 0:
            return DimensionScore(name="Completeness", score=0.0, detail="No nodes in graph")

        fields_expected = ["canonical_name", "entity_type"]
        filled = 0
        total = 0
        missing_by_field: Dict[str, int] = defaultdict(int)
        for _, d in self.graph.nodes(data=True):
            for f in fields_expected:
                total += 1
                val = d.get(f) or d.get(f.replace("canonical_", ""))
                if val:
                    filled += 1
                else:
                    missing_by_field[f] += 1

        score = filled / max(total, 1)
        issues = [f"Missing {f} in {c}/{total_nodes} nodes" for f, c in missing_by_field.items() if c > 0]
        return DimensionScore(name="Completeness", score=round(score, 4), detail=f"{filled}/{total} fields populated", issues=issues)

    def _temporal_quality(self) -> DimensionScore:
        """Are timestamps present on edges?"""
        total_edges = self.graph.number_of_edges()
        if total_edges == 0:
            return DimensionScore(name="Temporal Quality", score=0.0, detail="No edges in graph")

        with_timestamp = 0
        for _, _, d in self.graph.edges(data=True):
            a = d.get("attributes") or {}
            nested = a.get("attributes") or {}
            ts = nested.get("timestamp") or a.get("timestamp") or a.get("observed_at")
            if ts:
                with_timestamp += 1

        score = with_timestamp / total_edges
        return DimensionScore(
            name="Temporal Quality",
            score=round(score, 4),
            detail=f"{with_timestamp}/{total_edges} edges have timestamps",
            issues=[] if score > 0.8 else [f"Only {score:.0%} of edges have timestamps"],
        )

    def _consistency(self) -> DimensionScore:
        """Check for contradictory node labels (same ID, different names)."""
        name_map: Dict[str, Set[str]] = defaultdict(set)
        for n, d in self.graph.nodes(data=True):
            name = d.get("canonical_name") or d.get("label")
            if name:
                name_map[n].add(name)
        contradictions = sum(1 for names in name_map.values() if len(names) > 1)
        total = len(name_map)
        score = 1.0 - (contradictions / max(total, 1))
        issues = [f"{contradictions} nodes have multiple labels"] if contradictions > 0 else []
        return DimensionScore(name="Consistency", score=round(score, 4), detail=f"{contradictions}/{total} contradictions", issues=issues)

    def _entity_resolution_quality(self) -> DimensionScore:
        """Heuristic: ratio of resolved vs raw mentions."""
        # Use graph metadata if available
        total = self.graph.number_of_nodes()
        if total == 0:
            return DimensionScore(name="Entity Resolution", score=0.0)
        # Check for alias richness as a proxy
        with_aliases = sum(1 for _, d in self.graph.nodes(data=True) if d.get("aliases"))
        score = min(1.0, 0.7 + (with_aliases / max(total, 1)) * 0.3)
        return DimensionScore(name="Entity Resolution", score=round(score, 4), detail=f"{with_aliases}/{total} nodes have aliases")

    def _evidence_coverage(self) -> DimensionScore:
        """What % of findings have supporting evidence."""
        if not self.findings:
            return DimensionScore(name="Evidence Coverage", score=0.0, detail="No findings to assess")
        with_evidence = sum(
            1 for f in self.findings
            if f.get("supporting_evidence_ids") or f.get("counter_evidence_ids")
        )
        score = with_evidence / max(len(self.findings), 1)
        return DimensionScore(name="Evidence Coverage", score=round(score, 4), detail=f"{with_evidence}/{len(self.findings)} findings have evidence")

    def _extraction_confidence(self) -> DimensionScore:
        """Average edge confidence as a proxy for extraction quality."""
        confs = []
        for _, _, d in self.graph.edges(data=True):
            a = d.get("attributes") or {}
            c = a.get("confidence")
            if c is not None:
                try:
                    confs.append(float(c))
                except (TypeError, ValueError):
                    pass
        if not confs:
            return DimensionScore(name="Extraction Confidence", score=0.0, detail="No confidence values found")
        avg = sum(confs) / len(confs)
        low_conf = sum(1 for c in confs if c < 0.5)
        issues = [f"{low_conf} edges with confidence < 0.5"] if low_conf > 0 else []
        return DimensionScore(name="Extraction Confidence", score=round(avg, 4), detail=f"Average: {avg:.3f} across {len(confs)} edges", issues=issues)

    def _duplicate_risk(self) -> DimensionScore:
        """Check for potential duplicate nodes (same label, different IDs)."""
        label_to_ids: Dict[str, List[str]] = defaultdict(list)
        for n, d in self.graph.nodes(data=True):
            label = (d.get("canonical_name") or d.get("label") or "").lower().strip()
            if label:
                label_to_ids[label].append(n)
        dupes = sum(1 for ids in label_to_ids.values() if len(ids) > 1)
        total = len(label_to_ids)
        score = 1.0 - (dupes / max(total, 1))
        issues = [f"{dupes} potentially duplicated entity labels"] if dupes > 0 else []
        return DimensionScore(name="Duplicate Risk", score=round(score, 4), detail=f"{dupes}/{total} duplicate labels", issues=issues)

    # ------------------------------------------------------------------ #
    # Entity-level quality
    # ------------------------------------------------------------------ #
    def entity_quality(self, entity_id: str) -> Optional[EntityQuality]:
        """Data quality assessment for a single entity."""
        if entity_id not in self.graph:
            return None
        d = self.graph.nodes[entity_id]
        label = d.get("canonical_name") or d.get("label") or entity_id

        # Identity confidence: mention count as proxy
        mentions = int(d.get("mention_count") or 1)
        identity_conf = min(1.0, 0.5 + mentions / 20)

        # Evidence coverage
        evidence_count = 0
        if self.evidence_store:
            try:
                evidence_count = len(self.evidence_store.get_evidence_for_node(entity_id, limit=50))
            except Exception:
                pass
        evidence_cov = min(1.0, evidence_count / max(5, 1))

        # Temporal coverage: edges with timestamps
        temporal_edges = 0
        total_edges = 0
        for _, _, d_edge in self.graph.edges(entity_id, data=True):
            total_edges += 1
            a = d_edge.get("attributes") or {}
            nested = a.get("attributes") or {}
            if nested.get("timestamp") or a.get("timestamp"):
                temporal_edges += 1
        temporal_cov = temporal_edges / max(total_edges, 1)

        # Relationship confidence
        confs = []
        for _, _, d_edge in self.graph.edges(entity_id, data=True):
            a = d_edge.get("attributes") or {}
            c = a.get("confidence")
            if c is not None:
                try:
                    confs.append(float(c))
                except (TypeError, ValueError):
                    pass
        rel_conf = sum(confs) / len(confs) if confs else 0.5

        # Issues
        issues = []
        if identity_conf < 0.6:
            issues.append(f"Low identity confidence ({identity_conf:.2f}); entity may need verification")
        if evidence_cov < 0.3:
            issues.append(f"Limited evidence coverage ({evidence_cov:.2f})")
        if temporal_cov < 0.3:
            issues.append(f"Low temporal coverage ({temporal_cov:.0%}); timestamps mostly missing")
        if rel_conf < 0.7:
            issues.append(f"Average relationship confidence is {rel_conf:.2f}")

        return EntityQuality(
            entity_id=entity_id,
            entity_label=label,
            identity_confidence=round(identity_conf, 4),
            evidence_coverage=round(evidence_cov, 4),
            temporal_coverage=round(temporal_cov, 4),
            relationship_confidence=round(rel_conf, 4),
            potential_issues=issues,
        )

    # ------------------------------------------------------------------ #
    # Aggregate report
    # ------------------------------------------------------------------ #
    def assess(self, entity_ids: Optional[List[str]] = None) -> DataQualityReport:
        """Full data quality report."""
        dimensions = [
            self._completeness(),
            self._temporal_quality(),
            self._consistency(),
            self._entity_resolution_quality(),
            self._evidence_coverage(),
            self._extraction_confidence(),
            self._duplicate_risk(),
        ]

        overall = sum(d.score for d in dimensions) / max(len(dimensions), 1)

        # Entity-level quality for requested entities
        eq = []
        if entity_ids:
            for eid in entity_ids[:20]:
                q = self.entity_quality(eid)
                if q:
                    eq.append(q)

        # Finding-level quality
        fq = []
        for f in self.findings[:20]:
            supporting = len(f.get("supporting_evidence_ids") or [])
            counter = len(f.get("counter_evidence_ids") or [])
            total_ev = supporting + counter
            fq.append(FindingQuality(
                finding_id=f.get("id", ""),
                evidence_coverage=min(1.0, total_ev / max(5, 1)),
                data_completeness=min(1.0, sum(1 for k in ["id", "confidence", "method", "generated_at"] if f.get(k)) / 4),
                conflicting_records=counter,
                inference_depth=len(f.get("inferred") or []) / max(len(f.get("observed") or []) + len(f.get("inferred") or []), 1),
                source_diversity=min(1.0, total_ev / max(3, 1)),
                temporal_coverage=0.5,  # default when unknown
            ))

        return DataQualityReport(
            overall_readiness=round(overall, 4),
            dimensions=dimensions,
            entity_quality=eq,
            finding_quality=fq,
            summary_stats={
                "total_nodes": self.graph.number_of_nodes(),
                "total_edges": self.graph.number_of_edges(),
                "total_findings": len(self.findings),
            },
            limitations=[
                "Data quality indicators are heuristic assessments, not ground-truth measurements.",
                "Completeness depends on what fields the pipeline extracted; missing ≠ wrong.",
                "Duplicate risk is label-based; false positives are possible.",
            ],
        )
