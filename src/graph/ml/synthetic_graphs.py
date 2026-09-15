"""
graph/ml/synthetic_graphs.py
----------------------------
Varied synthetic graph generator for ghost-coordinator classifier training.

Extends the original seed=42 generator into a *distribution over topologies*:

* network sizes (small/medium/large)
* number of planted hidden coordinators
* community structure (dense vs sparse)
* observed-to-hidden edge ratio (how well the coordinator is hidden)

Every graph is deterministic for a given (seed, params) tuple so training is
reproducible.  Each generated graph contains *planted* hidden coordinators
with known ground-truth labels, which is what makes supervised training
possible.

The generator produces a *NetworkX MultiDiGraph* directly (no CSV round-trip)
so the training loop is fast enough to cover 30-50 graphs on CPU.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Set, Tuple

import networkx as nx

from src.generator.entities import Person


@dataclass
class GraphParams:
    """Controls the structure of one synthetic graph."""

    n_gangs: int = 10
    n_people: int = 300
    n_calls: int = 1200
    n_transactions: int = 600
    n_meetings: int = 250
    n_coordinators: int = 3
    min_gangs_per_coordinator: int = 2
    max_gangs_per_coordinator: int = 4
    #: fraction of coordinator-linked edges to keep observable (higher = more
    #: visible signal; lower = better hidden)
    observed_edge_ratio: float = 0.35
    #: intra-gang call density multiplier (higher = denser communities)
    density: float = 1.0
    #: fraction of gang members that are civilians (0 -> all gang-affiliated,
    #: high -> more noise in the graph)
    civilian_ratio: float = 0.20
    direct_cross_gang_edges: int = 0   # noise edges between gangs
    temporal_window_days: int = 90
    seed: int = 42


# Canonical strength ordering for roles — used by generators.
_ROLE_ORDER = {"boss": 3, "lieutenant": 2, "member": 1, "associate": 0}

_MAJOR_CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Kolkata",
    "Jaipur", "Pune", "Ahmedabad", "Lucknow",
]


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def generate_varied_graph(params: GraphParams) -> Tuple[nx.MultiDiGraph, Dict[str, bool], List[Person]]:
    """Generate one synthetic graph with planted hidden coordinators.

    Returns ``(graph, label_of_node, persons)`` where ``label_of_node`` maps a
    node GUID to ``True`` iff that node is a planted hidden coordinator.
    """
    rng = _rng(params.seed)
    graph = nx.MultiDiGraph()
    persons: List[Person] = []
    gangs: List[str] = []
    label_of: Dict[str, bool] = {}

    def guid(pid: str) -> str:
        return f"P-{pid}"

    # ---- gangs ------------------------------------------------------------
    for g in range(1, params.n_gangs + 1):
        gangs.append(f"G{g:03d}")

    # ---- population -------------------------------------------------------
    n_coords = params.n_coordinators
    n_affiliated = max(
        params.n_gangs * 2,
        int(params.n_people * (1.0 - params.civilian_ratio)) - n_coords,
    )
    n_civilians = max(0, params.n_people - n_affiliated - n_coords)

    member_of_gang: Dict[str, str] = {}          # person_id -> gang
    role_of: Dict[str, str] = {}                 # person_id -> role

    idx = 0
    # affiliated members distributed round-robin across gangs, with a boss +
    # several lieutenants guaranteed per gang
    for i in range(n_affiliated):
        gang = gangs[i % len(gangs)]
        pid = f"P{idx:06d}"
        idx += 1
        in_gang = member_of_gang
        members_in_gang = [p for p in in_gang if in_gang[p] == gang]
        if not members_in_gang:
            role = "boss"
        elif len(members_in_gang) < 3:
            role = "lieutenant"
        else:
            role = rng.choices(
                ["lieutenant", "member", "associate"], weights=[0.15, 0.65, 0.20]
            )[0]
        member_of_gang[pid] = gang
        role_of[pid] = role
        persons.append(Person(
            person_id=pid, full_name=f"Person {pid}", phone_number=f"+91-{pid}",
            address=f"{rng.choice(_MAJOR_CITIES)}", age=rng.randint(18, 70),
            gang_id=gang, role=role, is_hidden_coordinator=False,
        ))
        guid(pid)
        graph.add_node(guid(pid), entity_type="PERSON", canonical_name=f"Person {pid}")
        label_of[guid(pid)] = False

    # civilians (noise)
    for _ in range(n_civilians):
        pid = f"P{idx:06d}"
        idx += 1
        persons.append(Person(
            person_id=pid, full_name=f"Civilian {pid}", phone_number=f"+91-{pid}",
            address=f"{rng.choice(_MAJOR_CITIES)}", age=rng.randint(18, 80),
            gang_id=None, role=None, is_hidden_coordinator=False,
        ))
        guid(pid)
        graph.add_node(guid(pid), entity_type="PERSON", canonical_name=f"Civilian {pid}")
        label_of[guid(pid)] = False

    # hidden coordinators (unaffiliated, planted)
    coordinators: List[str] = []
    for _ in range(n_coords):
        pid = f"P{idx:06d}"
        idx += 1
        coordinators.append(pid)
        persons.append(Person(
            person_id=pid, full_name=f"Coordinator {pid}", phone_number=f"+91-{pid}",
            address=f"{rng.choice(_MAJOR_CITIES)}", age=rng.randint(30, 65),
            gang_id=None, role=None, is_hidden_coordinator=True,
        ))
        guid(pid)
        graph.add_node(guid(pid), entity_type="PERSON", canonical_name=f"Coordinator {pid}")
        label_of[guid(pid)] = True

    # ---- lieutenants (proxies) --------------------------------------------
    lieutenants_by_gang: Dict[str, List[str]] = {}
    for pid, gang in member_of_gang.items():
        if role_of.get(pid) in ("lieutenant", "boss"):
            lieutenants_by_gang.setdefault(gang, []).append(pid)

    proxy_of: Dict[str, List[str]] = {}          # coordinator -> [lieutenants]
    for coord in coordinators:
        n_ctrl = rng.randint(
            params.min_gangs_per_coordinator,
            min(params.max_gangs_per_coordinator, len(gangs)),
        )
        controlled = rng.sample(gangs, k=n_ctrl)
        coord_proxies: List[str] = []
        for gang in controlled:
            candidates = lieutenants_by_gang.get(gang, [])
            if not candidates:
                continue
            k = min(len(candidates), rng.randint(1, 2))
            chosen = rng.sample(candidates, k=k)
            coord_proxies.extend(chosen)
            # coordinator <-> lieutenant edges (observable fraction)
            for lt in chosen:
                if rng.random() < params.observed_edge_ratio:
                    graph.add_edge(guid(coord), guid(lt), relation="CALLED",
                                   attributes={"timestamp": _rand_ts(rng, params)})
                    graph.add_edge(guid(lt), guid(coord), relation="CALLED",
                                   attributes={"timestamp": _rand_ts(rng, params)})
        proxy_of[coord] = coord_proxies

    # ---- intra-gang communication -----------------------------------------
    start = datetime(2025, 1, 1)
    span = timedelta(days=params.temporal_window_days)
    budget = params.n_calls
    coordinator_budget = int(budget * 0.05) if coordinators else 0
    regular_budget = budget - coordinator_budget

    by_gang: Dict[str, List[str]] = {}
    for pid, gang in member_of_gang.items():
        by_gang.setdefault(gang, []).append(pid)

    for _ in range(regular_budget):
        gang = rng.choice(gangs)
        members = by_gang[gang]
        if len(members) < 2:
            continue
        a, b = rng.sample(members, 2)
        ts = (start + rng.random() * span).isoformat()
        if rng.random() < 0.5:
            a, b = b, a
        graph.add_edge(guid(a), guid(b), relation="CALLED",
                       attributes={"timestamp": ts, "duration_sec": rng.randint(10, 1800)})

    # ---- transactions (money flows, anchored to accounts) ------------------
    txn_budget = params.n_transactions
    coord_txn_budget = int(txn_budget * 0.05) if coordinators else 0
    regular_txn_budget = txn_budget - coord_txn_budget

    def account_for(pid: str) -> str:
        return f"ACC-{guid(pid)}"

    for _ in range(regular_txn_budget):
        gang = rng.choice(gangs)
        members = by_gang[gang]
        if len(members) < 2:
            continue
        a, b = rng.sample(members, 2)
        account = account_for(a)
        graph.add_edge(guid(a), guid(b), relation="TRANSFERS_TO",
                       attributes={"timestamp": _rand_ts(rng, params),
                                   "account_id": account,
                                   "amount": round(rng.uniform(500, 50000), 2)})

    # coordinator -> lieutenant transactions (larger amounts)
    for _ in range(coord_txn_budget):
        if not proxy_of:
            break
        coord = rng.choice(list(proxy_of.keys()))
        proxies = proxy_of.get(coord, [])
        if not proxies:
            continue
        lt = rng.choice(proxies)
        graph.add_edge(guid(coord), guid(lt), relation="TRANSFERS_TO",
                       attributes={"timestamp": _rand_ts(rng, params),
                                   "account_id": account_for(coord),
                                   "amount": round(rng.uniform(5000, 100000), 2)})

    # ---- meetings / locations ----------------------------------------------
    meeting_budget = params.n_meetings
    for _ in range(meeting_budget):
        gang = rng.choice(gangs)
        members = by_gang[gang]
        if not members:
            continue
        loc = rng.choice(_MAJOR_CITIES)
        sample = rng.sample(members, min(len(members), rng.randint(2, 5)))
        ts = _rand_ts(rng, params)
        for pid in sample:
            graph.add_edge(guid(pid), f"LOC-{loc}", relation="SEEN_IN",
                           attributes={"timestamp": ts, "location": loc})
        if not graph.has_node(f"LOC-{loc}"):
            graph.add_node(f"LOC-{loc}", entity_type="LOCATION", canonical_name=loc)

    # ---- cross-gang noise edges (optional) -----------------------------------
    for _ in range(params.direct_cross_gang_edges):
        gang_a, gang_b = rng.sample(gangs, 2)
        ma, mb = by_gang[gang_a], by_gang[gang_b]
        if not ma or not mb:
            continue
        a, b = rng.choice(ma), rng.choice(mb)
        graph.add_edge(guid(a), guid(b), relation="CALLED",
                       attributes={"timestamp": _rand_ts(rng, params)})

    # ---- make sure location nodes exist -------------------------------------
    for loc in _MAJOR_CITIES:
        if not graph.has_node(f"LOC-{loc}"):
            graph.add_node(f"LOC-{loc}", entity_type="LOCATION", canonical_name=loc)

    return graph, label_of, persons


def _rand_ts(rng: random.Random, params: GraphParams) -> str:
    start = datetime(2025, 1, 1)
    span = timedelta(days=params.temporal_window_days)
    return (start + rng.random() * span).isoformat()


def generate_graph_bundle(
    n_graphs: int = 40,
    base_seed: int = 1000,
    sizes: Sequence[Tuple[int, int]] = ((250, 1000), (400, 2000), (700, 4000)),
) -> List[Tuple[GraphParams, nx.MultiDiGraph, Dict[str, bool]]]:
    """Generate a bundle of varied synthetic graphs for training/eval.

    Sweeps graph size, coordinator count, density, and observed-edge ratio.
    Returns a list of ``(params, graph, label_of)`` tuples, deterministic for
    a given ``base_seed``.
    """
    results: List[Tuple[GraphParams, nx.MultiDiGraph, Dict[str, bool]]] = []
    rng = _rng(base_seed)
    for i in range(n_graphs):
        n_people, n_calls = sizes[i % len(sizes)]
        params = GraphParams(
            n_people=n_people,
            n_calls=n_calls,
            n_transactions=int(n_calls * 0.5),
            n_meetings=int(n_calls * 0.2),
            n_gangs=rng.randint(6, 14),
            n_coordinators=rng.randint(2, 6),
            min_gangs_per_coordinator=rng.randint(2, 3),
            max_gangs_per_coordinator=rng.randint(3, 5),
            observed_edge_ratio=rng.choice([0.2, 0.35, 0.5, 0.65]),
            density=rng.choice([0.6, 1.0, 1.4]),
            civilian_ratio=rng.choice([0.1, 0.2, 0.3]),
            direct_cross_gang_edges=rng.randint(0, 8),
            seed=base_seed * 1000 + i,
        )
        graph, label_of, _persons = generate_varied_graph(params)
        results.append((params, graph, label_of))
    return results