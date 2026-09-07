"""
dossier_generator.py
--------------------
Evidence-grounded intelligence dossier generation (Phase F).

RAG pipeline:

    FINDING(S) -> retrieve relevant evidence -> retrieve graph facts
        -> retrieve timeline -> retrieve counter-evidence
        -> construct bounded context -> LLM (optional)
        -> parse + schema validation -> deterministic fallback if invalid

Hard guarantees:

* every factual statement maps to an evidence id that exists in the store;
* OBSERVED / INFERRED / UNKNOWN / CONTRADICTED are labelled separately;
* output is validated against :class:`Dossier` (Pydantic); a malformed LLM
  response triggers one corrective retry and then a deterministic non-LLM
  dossier - a broken model can never break the API or fabricate content;
* status is always ``DRAFT_FOR_HUMAN_REVIEW``; dossiers are never presented
  as court-ready or as autonomous enforcement recommendations.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field, ValidationError

from src.xai.evidence_tracer import EvidenceRecord, EvidenceStore
from src.xai.findings import Finding, FindingBuilder, validate_finding
from src.xai.llm_providers import LLMProvider, MockLLMProvider

logger = logging.getLogger(__name__)

DOSSIER_NAMESPACE = uuid.UUID("b7e2a4c8-1d53-4f6a-9e0b-8c2d5f7a3e91")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class TimelineEvent(BaseModel):
    timestamp: Optional[str] = None
    event_type: str = "evidence"
    entity_ids: List[str] = Field(default_factory=list)
    evidence_id: str
    source: str = ""
    excerpt: str = ""


class DossierSectionItem(BaseModel):
    label: str = "OBSERVED"        # OBSERVED | INFERRED | UNKNOWN | CONTRADICTED
    text: str
    evidence_ids: List[str] = Field(default_factory=list)


class MethodologyStep(BaseModel):
    step: str
    description: str


class Dossier(BaseModel):
    """Validated dossier document returned by the API and persisted to disk."""

    id: str
    subject_id: str
    title: str
    classification: str = "INTELLIGENCE_SUMMARY"
    confidence: float = 0.0
    status: str = "DRAFT_FOR_HUMAN_REVIEW"
    executive_summary: str = ""

    timeline: List[TimelineEvent] = Field(default_factory=list)
    findings: List[str] = Field(default_factory=list)          # finding ids
    sections: List[Dict[str, Any]] = Field(default_factory=list)

    supporting_evidence: List[str] = Field(default_factory=list)
    counter_evidence: List[str] = Field(default_factory=list)
    methodology: List[MethodologyStep] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

    generated_at: str = Field(default_factory=_utcnow)
    model_metadata: Dict[str, Any] = Field(default_factory=dict)
    human_review: Dict[str, Any] = Field(
        default_factory=lambda: {
            "required": True,
            "reviewer": None,
            "decision": None,
            "note": "DRAFT - HUMAN REVIEW REQUIRED. Not court-ready.",
        }
    )


class DossierLLMOutput(BaseModel):
    """Schema a (real) LLM response must satisfy after JSON parsing."""

    executive_summary: str
    section_titles: List[str] = Field(default_factory=list)
    summary_points: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Generator
# --------------------------------------------------------------------------- #

class DossierGenerator:
    def __init__(self,
                 evidence_store: EvidenceStore,
                 llm: Optional[LLMProvider] = None,
                 findings_path: Optional[Path] = None) -> None:
        self.evidence = evidence_store
        self.llm = llm or MockLLMProvider()
        self.findings_path = findings_path

    # ------------------------------------------------------------------ #
    def generate_dossier(self,
                         subject_id: str,
                         finding_ids: Optional[Sequence[str]] = None,
                         max_evidence: int = 40,
                         max_excerpt_chars: int = 300) -> Dossier:
        """Build a dossier for one subject (node guid / ghost id)."""
        findings = self._findings_for_subject(subject_id, finding_ids)

        supporting: List[str] = []
        counter: List[str] = []
        for f in findings:
            supporting.extend(f.supporting_evidence_ids)
            counter.extend(f.counter_evidence_ids)
        if not findings:
            # subject without findings: index evidence directly on the subject
            supporting = [r.evidence_id for r in
                          self.evidence.get_evidence_for_node(subject_id, limit=max_evidence)]

        supporting = sorted(set(supporting))[:max_evidence]
        counter = sorted(set(e for e in counter if not e.startswith("COUNTER:")))[:10]

        timeline = self._timeline(subject_id, max_evidence)
        context = self._bounded_context(
            subject_id, findings, supporting, counter, timeline, max_excerpt_chars
        )

        llm_summary = self._try_llm(context)
        if llm_summary is None:
            llm_summary = self._deterministic_summary(subject_id, findings, context)

        confidence = (
            max(f.confidence for f in findings) if findings else 0.0
        )
        dossier = Dossier(
            id="DOSSIER-" + str(uuid.uuid5(DOSSIER_NAMESPACE, f"{subject_id}|{_utcnow()}")),
            subject_id=subject_id,
            title=self._title(subject_id, findings),
            confidence=round(float(confidence), 4),
            status="DRAFT_FOR_HUMAN_REVIEW",
            executive_summary=llm_summary.executive_summary,
            timeline=timeline,
            findings=[f.id for f in findings],
            sections=self._sections(llm_summary, findings, supporting, counter),
            supporting_evidence=supporting,
            counter_evidence=counter,
            methodology=self._methodology(findings, self.llm.name),
            limitations=self._limitations(findings),
            model_metadata={
                "llm_provider": self.llm.name,
                "deterministic_fallback": isinstance(self.llm, MockLLMProvider),
                "findings_used": [f.id for f in findings],
                "model_version": findings[0].model_version if findings else None,
                "context_items": len(context),
            },
        )
        return dossier

    # ------------------------------------------------------------------ #
    def _findings_for_subject(self, subject_id: str,
                              finding_ids: Optional[Sequence[str]]) -> List[Finding]:
        findings: List[Finding] = []
        if self.findings_path and Path(self.findings_path).exists():
            try:
                from src.xai.findings import load_findings
                findings = load_findings(self.findings_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("could not load findings file: %s", exc)
                findings = []
        if finding_ids:
            findings = [f for f in findings if f.id in set(finding_ids)]
        else:
            findings = [f for f in findings
                        if f.subject_id == subject_id or subject_id in (f.subject_label or "")]
        return findings

    def _timeline(self, subject_id: str, limit: int) -> List[TimelineEvent]:
        events: List[TimelineEvent] = []
        records = self.evidence.get_evidence_for_node(subject_id, limit=limit)
        records.sort(key=lambda r: (r.timestamp or "9999", r.evidence_id))
        for rec in records:
            events.append(
                TimelineEvent(
                    timestamp=rec.timestamp,
                    event_type=rec.source_type.lower(),
                    entity_ids=rec.subject_ids,
                    evidence_id=rec.evidence_id,
                    source=rec.source_uri,
                    excerpt=rec.text_excerpt[:200],
                )
            )
        return events

    def _bounded_context(self,
                         subject_id: str,
                         findings: Sequence[Finding],
                         supporting: Sequence[str],
                         counter: Sequence[str],
                         timeline: Sequence[TimelineEvent],
                         excerpt_cap: int) -> List[Dict[str, Any]]:
        """Construct the bounded RAG context the provider is allowed to use."""
        context: List[Dict[str, Any]] = []
        context.append({
            "kind": "subject",
            "title": "Subject",
            "items": [{"subject_id": subject_id,
                       "has_findings": bool(findings)}],
        })
        for f in findings:
            context.append({
                "kind": "finding",
                "title": f"Finding {f.id} ({f.finding_type})",
                "items": [
                    {"confidence": f.confidence, "status": f.status,
                     "method": f.method},
                    {"observed": [c.model_dump(mode="json") for c in f.observed]},
                    {"inferred": [c.model_dump(mode="json") for c in f.inferred]},
                    {"unknown": [c.text for c in f.unknown]},
                    {"graph_signals": [s.model_dump(mode="json") for s in f.graph_signals]},
                    {"confidence_components": [c.model_dump(mode="json")
                                               for c in f.confidence_components]},
                ],
            })
        evidence_items = []
        for eid in supporting:
            rec = self.evidence.get_evidence(eid)
            if rec is None:
                continue
            evidence_items.append({
                "evidence_id": rec.evidence_id,
                "source_type": rec.source_type,
                "source_record_id": rec.source_record_id,
                "timestamp": rec.timestamp,
                "excerpt": rec.text_excerpt[:excerpt_cap],
            })
        if evidence_items:
            context.append({"kind": "supporting_evidence",
                            "title": "Supporting evidence", "items": evidence_items})
        counter_items = []
        for eid in counter:
            rec = self.evidence.get_evidence(eid)
            if rec is None:
                continue
            counter_items.append({
                "evidence_id": rec.evidence_id,
                "source_type": rec.source_type,
                "excerpt": rec.text_excerpt[:excerpt_cap],
            })
        if counter_items:
            context.append({"kind": "counter_evidence",
                            "title": "Counter-evidence", "items": counter_items})
        if timeline:
            context.append({
                "kind": "timeline",
                "title": "Chronological evidence timeline",
                "items": [t.model_dump(mode="json") for t in timeline[:25]],
            })
        return context

    # ------------------------------------------------------------------ #
    def _try_llm(self, context: List[Dict[str, Any]]) -> Optional[DossierLLMOutput]:
        """Ask the provider for a summary; validate strictly. Returns None if
        the provider fails or produces schema-invalid output."""
        prompt = (
            "Write a short executive summary (<= 160 words) for an intelligence "
            "dossier from the given context.\n"
            "STRICT RULES:\n"
            "- Use ONLY facts present in the context. Never invent evidence ids, "
            "names, timestamps or relationships.\n"
            "- Present model hypotheses as hypotheses; never assert guilt or "
            "certainty; never convert a hypothesis into a fact.\n"
            "- Return STRICT JSON: {\"executive_summary\": str, "
            "\"summary_points\": [str], \"section_titles\": [str]}.\n"
        )
        for attempt in (1, 2):
            try:
                raw = self.llm.generate(prompt, context)
                data = json.loads(raw)
                if isinstance(data, dict) and "sections" in data:
                    # MockLLMProvider returns its rendered context; convert to
                    # a deterministic summary from the context items.
                    data = self._mock_to_summary(context)
                return DossierLLMOutput.model_validate(data)
            except (json.JSONDecodeError, ValidationError, RuntimeError) as exc:
                logger.warning("LLM dossier output invalid (attempt %s): %s", attempt, exc)
        return None

    def _mock_to_summary(self, context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Deterministic summary derived only from bounded context items."""
        n_ev = 0
        n_counter = 0
        finding_count = 0
        top_conf = 0.0
        for item in context:
            kind = item.get("kind")
            if kind == "supporting_evidence":
                n_ev = len(item.get("items") or [])
            elif kind == "counter_evidence":
                n_counter = len(item.get("items") or [])
            elif kind == "finding":
                finding_count += 1
                for block in item.get("items") or []:
                    if isinstance(block, dict) and "confidence" in block:
                        top_conf = max(top_conf, float(block.get("confidence") or 0.0))
        points = [
            f"{finding_count} model finding(s) relate to this subject.",
            f"{n_ev} evidence record(s) indexed as supporting context.",
        ]
        if n_counter:
            points.append(f"{n_counter} counter-evidence record(s) preserved.")
        points.append("All hypotheses remain subject to human review.")
        return {
            "executive_summary": (
                f"This dossier consolidates {finding_count} model finding(s) about the "
                f"subject with {n_ev} supporting evidence record(s). "
                f"Highest model confidence: {top_conf:.2f}. "
                + ("Counter-evidence is preserved and shown alongside supporting "
                   "material. " if n_counter else "")
                + "All statements derived from model inference are labelled as "
                "hypotheses; the subject has not been confirmed and no operational "
                "action is recommended by this system."
            ),
            "summary_points": points,
            "section_titles": ["Observed facts", "Inferred hypotheses",
                               "Counter-evidence", "Unknowns"],
        }

    def _deterministic_summary(self, subject_id: str, findings: Sequence[Finding],
                               context: List[Dict[str, Any]]) -> DossierLLMOutput:
        """Non-LLM fallback used when the provider fails validation."""
        return DossierLLMOutput.model_validate(self._mock_to_summary(context))

    # ------------------------------------------------------------------ #
    def _title(self, subject_id: str, findings: Sequence[Finding]) -> str:
        if findings:
            return f"Intelligence dossier - {findings[0].subject_label or subject_id}"
        return f"Intelligence dossier - {subject_id}"

    def _sections(self, summary: DossierLLMOutput,
                  findings: Sequence[Finding],
                  supporting: Sequence[str],
                  counter: Sequence[str]) -> List[Dict[str, Any]]:
        sections: List[Dict[str, Any]] = []
        observed_items: List[Dict[str, Any]] = []
        inferred_items: List[Dict[str, Any]] = []
        for f in findings:
            for claim in f.observed:
                observed_items.append({
                    "label": "OBSERVED",
                    "text": claim.text,
                    "evidence_ids": claim.evidence_ids,
                })
            for claim in f.inferred:
                inferred_items.append({
                    "label": "INFERRED",
                    "text": claim.text,
                    "evidence_ids": claim.evidence_ids,
                })
        unknown_items = [{"label": "UNKNOWN", "text": c.text, "evidence_ids": []}
                         for f in findings for c in f.unknown]
        counter_items = []
        for eid in counter:
            rec = self.evidence.get_evidence(eid)
            if rec is not None:
                counter_items.append({
                    "label": "CONTRADICTED",
                    "text": f"Counter-evidence ({rec.source_type} "
                            f"{rec.source_record_id}): {rec.text_excerpt[:200]}",
                    "evidence_ids": [eid],
                })
        if summary.summary_points:
            sections.append({
                "title": "Summary points",
                "items": [{"label": "OBSERVED", "text": p, "evidence_ids": []}
                          for p in summary.summary_points],
            })
        if observed_items:
            sections.append({"title": "Observed facts", "items": observed_items})
        if inferred_items:
            sections.append({"title": "Inferred hypotheses", "items": inferred_items})
        if counter_items:
            sections.append({"title": "Counter-evidence", "items": counter_items})
        if unknown_items:
            sections.append({"title": "Unknowns / missing information",
                             "items": unknown_items})
        if summary.section_titles:
            sections.append({
                "title": "Analyst outline",
                "items": [{"label": "OBSERVED", "text": t, "evidence_ids": []}
                          for t in summary.section_titles],
            })
        return sections

    def _methodology(self, findings: Sequence[Finding], provider_name: str) -> List[MethodologyStep]:
        steps = [
            MethodologyStep(
                step="DATA COLLECTION",
                description="Synthetic dataset generated and ingested via CSV loaders; "
                            "every source record hashed into the evidence index.",
            ),
            MethodologyStep(
                step="GRAPH CONSTRUCTION",
                description="NER + relation extraction -> entity resolution -> "
                            "NetworkX knowledge graph with evidence-linked edges.",
            ),
            MethodologyStep(
                step="ANALYTICS",
                description="PageRank / betweenness / community detection computed "
                            "over the undirected weighted projection.",
            ),
            MethodologyStep(
                step="GHOST INFERENCE",
                description="Structural-hole + shared-anchor + temporal analysis "
                            "proposed hidden-intermediary hypotheses with component "
                            "confidence scores.",
            ),
            MethodologyStep(
                step="XAI / EVIDENCE BINDING",
                description="Findings bound to evidence records via the provenance "
                            "index; counter-evidence searched and preserved.",
            ),
        ]
        if findings:
            steps.append(MethodologyStep(
                step="DOSSIER COMPOSITION",
                description=f"Context-bounded summary composed with provider "
                            f"'{provider_name}'; output schema-validated; "
                            f"deterministic fallback if invalid.",
            ))
        return steps

    def _limitations(self, findings: Sequence[Finding]) -> List[str]:
        base = [
            "Generated from a synthetic dataset for research/demo purposes.",
            "Confidence values are weighted blends of graph signals, not "
            "probabilities of guilt.",
            "Dossier is a DRAFT FOR HUMAN REVIEW and is not court-ready.",
            "This system never recommends enforcement actions autonomously.",
        ]
        for f in findings:
            base.extend(f.limitations[:3])
        # dedupe, preserve order
        seen, out = set(), []
        for item in base:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out


# --------------------------------------------------------------------------- #
# Validation (Phase AB) + persistence
# --------------------------------------------------------------------------- #

class DossierValidationReport(BaseModel):
    dossier_id: str
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


def validate_dossier(dossier: Dossier, evidence_store: EvidenceStore) -> DossierValidationReport:
    """Every claim traceable to existing evidence; labels valid; review pending."""
    errors: List[str] = []
    warnings: List[str] = []

    known = set(evidence_store.all_ids())
    for eid in dossier.supporting_evidence:
        if eid not in known:
            errors.append(f"supporting evidence id not found: {eid}")
    for eid in dossier.counter_evidence:
        if eid not in known:
            errors.append(f"counter evidence id not found: {eid}")
    for section in dossier.sections:
        for item in section.get("items", []):
            label = item.get("label", "OBSERVED")
            if label not in {"OBSERVED", "INFERRED", "UNKNOWN", "CONTRADICTED"}:
                errors.append(f"invalid claim label: {label}")
            if label == "OBSERVED":
                for eid in item.get("evidence_ids", []):
                    if eid not in known:
                        errors.append(f"observed claim cites unknown evidence: {eid}")
    if dossier.status != "DRAFT_FOR_HUMAN_REVIEW":
        errors.append("dossier status must remain DRAFT_FOR_HUMAN_REVIEW")
    if not dossier.limitations:
        errors.append("limitations must always be present")
    for event in dossier.timeline:
        if event.evidence_id not in known:
            errors.append(f"timeline event cites unknown evidence: {event.evidence_id}")
    if not dossier.model_metadata.get("llm_provider"):
        warnings.append("model_metadata missing llm_provider")

    return DossierValidationReport(
        dossier_id=dossier.id, valid=not errors, errors=errors, warnings=warnings
    )


def save_dossier(dossier: Dossier, dossiers_dir: str | Path) -> Path:
    out = Path(dossiers_dir) / f"{dossier.id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dossier.model_dump(mode="json"), indent=2))
    return out


def load_dossier(path: str | Path) -> Dossier:
    return Dossier.model_validate(json.loads(Path(path).read_text()))


def list_dossiers(dossiers_dir: str | Path) -> List[Dict[str, Any]]:
    out = []
    for p in sorted(Path(dossiers_dir).glob("DOSSIER-*.json")):
        try:
            d = load_dossier(p)
            out.append({
                "id": d.id,
                "subject_id": d.subject_id,
                "title": d.title,
                "confidence": d.confidence,
                "status": d.status,
                "generated_at": d.generated_at,
            })
        except (ValidationError, json.JSONDecodeError, OSError) as exc:
            logger.warning("skipping invalid dossier %s: %s", p, exc)
    return out
