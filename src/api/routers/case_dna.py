"""
routers/case_dna.py
-------------------
Case Similarity / Network DNA API (route group: /api/case-dna/*).

Fingerprint generation, similarity computation, and case comparison.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query

from src.api import audit, services, paths

router = APIRouter(prefix="/api/case-dna", tags=["case-dna"])


def _get_engine(case_id: str = "CASE-0421"):
    from src.analysis.case_dna import CaseDNAEngine
    graph = services.load_graph()
    return CaseDNAEngine(graph, case_id=case_id)


@router.get("/fingerprint")
def fingerprint(case_id: str = Query("CASE-0421")):
    """Generate a case network fingerprint."""
    engine = _get_engine(case_id)
    fp = engine.generate_fingerprint()
    audit.record_action("case-dna.fingerprint", detail={"case_id": case_id})
    return fp.model_dump()


@router.get("/similarity")
def similarity(
    case_id: str = Query("CASE-0421"),
    structural: float = Query(0.35),
    financial: float = Query(0.20),
    temporal: float = Query(0.15),
    entity_composition: float = Query(0.15),
    motif: float = Query(0.15),
):
    """Compute similarity between the current case and all other cases."""
    from src.analysis.case_dna import CaseDNAEngine, compute_similarity
    graph = services.load_graph()
    engine = CaseDNAEngine(graph, case_id=case_id)
    main_fp = engine.generate_fingerprint()

    # Load other case fingerprints (from case files)
    weights = {
        "structural": structural,
        "financial": financial,
        "temporal": temporal,
        "entity_composition": entity_composition,
        "motif": motif,
    }

    results = []
    if paths.CASES_DIR.exists():
        for p in paths.CASES_DIR.glob("*.json"):
            other_id = p.stem
            if other_id == case_id:
                continue
            try:
                data = json.loads(p.read_text())
                other_entities = data.get("entities", [])
                other_graph = _build_case_graph(other_entities)
                other_engine = CaseDNAEngine(other_graph, case_id=other_id)
                other_fp = other_engine.generate_fingerprint()
                sim = compute_similarity(main_fp, other_fp, weights)
                results.append(sim.model_dump())
            except Exception:
                pass

    results.sort(key=lambda r: -r.get("similarity", 0))
    audit.record_action("case-dna.similarity", detail={"case_id": case_id, "compared": len(results)})
    return {"case_id": case_id, "results": results, "total": len(results)}


@router.get("/compare")
def compare(case_a: str = Query("CASE-0421"), case_b: str = Query(...)):
    """Detailed comparison between two cases."""
    from src.analysis.case_dna import CaseDNAEngine, compare_cases
    graph_a = services.load_graph()
    engine_a = CaseDNAEngine(graph_a, case_id=case_a)
    fp_a = engine_a.generate_fingerprint()

    # Build graph for case_b
    other_graph = graph_a  # fallback to same graph for demo
    if paths.CASES_DIR.exists():
        p = paths.CASES_DIR / f"{case_b}.json"
        if p.exists():
            data = json.loads(p.read_text())
            other_graph = _build_case_graph(data.get("entities", []))

    engine_b = CaseDNAEngine(other_graph, case_id=case_b)
    fp_b = engine_b.generate_fingerprint()
    comparison = compare_cases(fp_a, fp_b)
    audit.record_action("case-dna.compare", detail={"a": case_a, "b": case_b})
    return comparison.model_dump()


def _build_case_graph(entities):
    """Build a minimal graph from case entity list for fingerprinting."""
    import networkx as nx
    g = nx.MultiDiGraph()
    for e in entities:
        eid = e.get("id", "")
        g.add_node(eid, canonical_name=e.get("label", eid), entity_type=e.get("type", "UNKNOWN"))
    return g
