"""
routers/financial.py
--------------------
Financial-flow intelligence API (route group: /api/financial/*).

Helps the analyst trace funds through the account graph:

* account network (ACCOUNT + TRANSFERRED_TO/USES_ACCOUNT edges)
* fund trace from a source account over a time window / hop limit
* flow indicators: fan-in, fan-out, circular flows, rapid pass-through

Outputs are *indicators* derived from observed transactions — never legal
accusations.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, List, Optional

import networkx as nx
from fastapi import APIRouter, Body, HTTPException, Query

from src.api import audit, services

router = APIRouter(prefix="/api/financial", tags=["financial"])


def _account_graph(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Subgraph restricted to ACCOUNT nodes + transfer edges."""
    sub = nx.MultiDiGraph()
    for n, d in graph.nodes(data=True):
        if d.get("entity_type") == "ACCOUNT":
            sub.add_node(n, **d)
    for src, tgt, key, d in graph.edges(keys=True, data=True):
        if d.get("relation") in ("TRANSFERRED_TO", "TRANSFERRED_FUNDS", "USES_ACCOUNT"):
            if src in sub and tgt in sub:
                sub.add_edge(src, tgt, key=key, **d)
    return sub


def _amount_of(edge_data: dict) -> float:
    a = edge_data.get("attributes") or {}
    nested = a.get("attributes") or {}
    raw = a.get("amount") or nested.get("amount")
    if raw is None:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _label(graph: nx.MultiDiGraph, node) -> str:
    return (graph.nodes[node].get("canonical_name")
            or graph.nodes[node].get("label") or str(node))


@router.get("/accounts")
def account_network(
    min_degree: int = Query(1, ge=0),
    limit: int = Query(200, ge=1, le=2000),
):
    """The ACCOUNT layer as a transfer graph (nodes + edges)."""
    graph = services.load_graph()
    sub = _account_graph(graph)
    nodes = []
    for n in sub.nodes():
        degree = sub.degree(n)
        if degree < min_degree:
            continue
        nodes.append({
            "id": n,
            "label": _label(graph, n),
            "total_in": sum(_amount_of(d) for _, _, d in sub.in_edges(n, data=True)),
            "total_out": sum(_amount_of(d) for _, _, d in sub.out_edges(n, data=True)),
            "degree": degree,
            "fan_in": sub.in_degree(n),
            "fan_out": sub.out_degree(n),
        })
    nodes.sort(key=lambda n: -(n["total_in"] + n["total_out"]))
    edges = [
        {"source": s, "target": t, "amount": _amount_of(d),
         "confidence": float((d.get("attributes") or {}).get("confidence", 1.0))}
        for s, t, d in sub.edges(data=True)
    ]
    audit.record_action("financial.accounts")
    return {"nodes": nodes[:limit], "edges": edges[: max(limit * 8, 2000)]}


@router.post("/trace")
def trace_funds(body: Dict[str, Any] = Body(...)):
    """Trace funds from a source account through the transfer graph.

    body: {"source": account_id, "max_hops": int(<=4), "min_amount": float,
           "start": iso?, "end": iso?}
    """
    graph = services.load_graph()
    sub = _account_graph(graph)

    source = body.get("source")
    if source not in sub:
        raise HTTPException(status_code=404, detail=f"Account not found: {source}")
    max_hops = int(body.get("max_hops", 3))
    min_amount = float(body.get("min_amount", 0))
    max_hops = max(1, min(max_hops, 4))

    seed_edges = sub.out_edges(source, data=True)
    paths = []
    frontier = [(source, [])]
    for hop in range(max_hops):
        nxt = []
        for node, path in frontier:
            for _, tgt, d in sub.out_edges(node, data=True):
                amt = _amount_of(d)
                if amt < min_amount:
                    continue
                new_path = path + [{
                    "from": node, "from_label": _label(graph, node),
                    "to": tgt, "to_label": _label(graph, tgt),
                    "amount": amt,
                    "confidence": float((d.get("attributes") or {}).get("confidence", 1.0)),
                    "edge_id": d.get("id", ""),
                }]
                paths.append({"hop": hop + 1, "path": new_path})
                if hop < max_hops - 1:
                    nxt.append((tgt, new_path))
        frontier = nxt
        if not frontier:
            break

    paths.sort(key=lambda p: -max(h["amount"] for h in p["path"]))
    paths = paths[:200]

    # flow indicators at each involved account
    involved = {h["from"] for p in paths for h in p["path"]} | {h["to"] for p in paths for h in p["path"]}
    indicators = []
    for acc in involved:
        fan_in = sub.in_degree(acc)
        fan_out = sub.out_degree(acc)
        rapid = fan_in >= 3 and fan_out >= 3
        indicators.append({
            "account": acc, "label": _label(graph, acc),
            "fan_in": fan_in, "fan_out": fan_out,
            "flag": "RAPID_PASS_THROUGH" if rapid else ("FAN_IN" if fan_in >= 4 else
                                                        "FAN_OUT" if fan_out >= 4 else "NORMAL"),
        })

    audit.record_action("financial.trace", object_ids=[source],
                        detail={"max_hops": max_hops, "min_amount": min_amount})
    return {
        "source": source,
        "source_label": _label(graph, source),
        "max_hops": max_hops,
        "min_amount": min_amount,
        "paths_found": len(paths),
        "paths": paths,
        "flow_indicators": indicators,
        "note": "FUND FLOW TRACE — indicators only, not legal conclusions",
    }


# --------------------------------------------------------------------------- #
# Financial Intelligence Pattern Endpoints (Task 13)
# --------------------------------------------------------------------------- #

@router.get("/patterns")
def list_patterns(
    pattern_type: Optional[str] = Query(None, description="Filter by pattern type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Paginated list of detected financial patterns."""
    from src.intelligence.financial import OUTPUT_PATH
    if not OUTPUT_PATH.exists():
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    data = json.loads(OUTPUT_PATH.read_text())
    if pattern_type:
        data = [p for p in data if p.get("pattern_type") == pattern_type.upper()]
    if severity:
        data = [p for p in data if p.get("severity") == severity.upper()]
    total = len(data)
    start = (page - 1) * page_size
    items = data[start:start + page_size]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/patterns/{pattern_id}")
def get_pattern(pattern_id: str):
    """Single financial pattern record."""
    from src.intelligence.financial import OUTPUT_PATH
    if not OUTPUT_PATH.exists():
        raise HTTPException(status_code=404, detail="No patterns computed")
    data = json.loads(OUTPUT_PATH.read_text())
    for p in data:
        if p.get("pattern_id") == pattern_id:
            return p
    raise HTTPException(status_code=404, detail=f"Pattern not found: {pattern_id}")


@router.get("/accounts/{account_id}/risk")
def account_risk(account_id: str):
    """Risk score for an account based on implicated patterns."""
    from src.intelligence.financial import OUTPUT_PATH
    if not OUTPUT_PATH.exists():
        return {
            "account_id": account_id,
            "risk_score": 0.0,
            "pattern_count": 0,
            "highest_severity": "NONE",
            "implicated_patterns": [],
            "disclaimer": "RISK INDICATOR — NOT AN ASSESSMENT OF GUILT",
        }
    data = json.loads(OUTPUT_PATH.read_text())
    implicated = [p for p in data if account_id in p.get("implicated_accounts", [])]
    if not implicated:
        return {
            "account_id": account_id,
            "risk_score": 0.0,
            "pattern_count": 0,
            "highest_severity": "NONE",
            "implicated_patterns": [],
            "disclaimer": "RISK INDICATOR — NOT AN ASSESSMENT OF GUILT",
        }
    severity_weights = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2}
    total = sum(severity_weights.get(p.get("severity", "LOW"), 0.2) * p.get("confidence", 0.5) for p in implicated)
    risk_score = min(1.0, total / max(len(implicated), 1))
    highest = max((severity_weights.get(p.get("severity", "LOW"), 0) for p in implicated), default=0)
    highest_sev = "HIGH" if highest >= 1.0 else ("MEDIUM" if highest >= 0.5 else "LOW")
    return {
        "account_id": account_id,
        "risk_score": risk_score,
        "pattern_count": len(implicated),
        "highest_severity": highest_sev,
        "implicated_patterns": [p.get("pattern_id", "") for p in implicated],
        "disclaimer": "RISK INDICATOR — NOT AN ASSESSMENT OF GUILT",
    }


@router.get("/summary")
def financial_summary():
    """Counts by pattern type, top 5 highest-risk accounts."""
    from src.intelligence.financial import OUTPUT_PATH
    if not OUTPUT_PATH.exists():
        return {"by_type": {}, "top_risk_accounts": []}
    data = json.loads(OUTPUT_PATH.read_text())
    by_type = {}
    account_risks: Dict[str, float] = defaultdict(float)
    for p in data:
        t = p.get("pattern_type", "UNKNOWN")
        by_type[t] = by_type.get(t, 0) + 1
        for acc in p.get("implicated_accounts", []):
            account_risks[acc] += p.get("confidence", 0.5)
    top5 = sorted(account_risks.items(), key=lambda x: -x[1])[:5]
    return {
        "by_type": by_type,
        "top_risk_accounts": [{"account_id": a, "risk_score": min(1.0, r)} for a, r in top5],
    }


@router.post("/run")
def run_financial_analysis():
    """Trigger financial intelligence analysis on current artifacts."""
    import pickle
    from src.api.jobs import job_manager
    from src.intelligence.financial import run_financial_intelligence

    def _job():
        graph = services.load_graph()
        return run_financial_intelligence(graph)

    job = job_manager.submit("financial_intelligence", _job)
    return job.to_dict()