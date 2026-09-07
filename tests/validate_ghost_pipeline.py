"""Lightweight validation for the synthetic ghost-node detector.
Uses the already-generated dataset/artifacts; does not regenerate the dataset.
"""
from __future__ import annotations

import csv
import json
import math
import pickle
import sys
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.graph.ghost_nodes import GhostConfig, detect_ghost_nodes, _mask_nodes, detect_communities
from src.graph.graph_embeddings import undirected_weighted_projection


def synthetic_ground_truth() -> dict[str, set[str]]:
    persons = ROOT / "data/synthetic/persons.csv"
    out = {}
    with persons.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("is_hidden_coordinator", "").strip().lower() == "true":
                out[row["person_id"]] = {f"ACC-COORD-{row['person_id']}"}
    return out


def full_dataset_check() -> dict:
    graph = pickle.load((ROOT / "data/exports/graph.pkl").open("rb"))
    truth = synthetic_ground_truth()
    hidden_names = set()
    with (ROOT / "data/synthetic/persons.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("is_hidden_coordinator", "").strip().lower() == "true":
                hidden_names.add(row["full_name"])
    observed = _mask_nodes(graph, hidden_names)
    config = GhostConfig()
    projection = undirected_weighted_projection(observed).subgraph([n for n, data in observed.nodes(data=True) if str(data.get("entity_type", "")).upper() not in {"LOCATION", "ACCOUNT"}]).copy()
    communities = detect_communities(projection, seed=config.seed)
    community_of = {node: idx for idx, comm in enumerate(communities) for node in comm}

    persons = {}
    with (ROOT / "data/synthetic/persons.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            persons[row["person_id"]] = row["full_name"]
    name_to_guid = {d.get("canonical_name"): n for n, d in observed.nodes(data=True)}
    tx_rows = []
    with (ROOT / "data/synthetic/transactions.csv").open(newline="", encoding="utf-8") as fh:
        tx_rows.extend(csv.DictReader(fh))
    truth_pairs = set()
    for coord_id in truth:
        account = f"ACC-COORD-{coord_id}"
        endpoint_comms = set()
        for row in tx_rows:
            if row.get("account_id") != account:
                continue
            for pid in (row.get("sender_id"), row.get("receiver_id")):
                if pid == coord_id:
                    continue
                node = name_to_guid.get(persons.get(pid, ""))
                if node in community_of:
                    endpoint_comms.add(community_of[node])
        truth_pairs.update(tuple(sorted(pair)) for pair in __import__("itertools").combinations(sorted(endpoint_comms), 2))

    doc = detect_ghost_nodes(observed, config)
    predicted_pairs = {tuple(g["between_communities"]) for g in doc["ghost_nodes"]}
    hits = predicted_pairs & truth_pairs
    precision = len(hits) / len(predicted_pairs) if predicted_pairs else 0.0
    recall = len(hits) / len(truth_pairs) if truth_pairs else 0.0
    predicted_accounts = {
        item["anchor_name"]
        for ghost in doc["ghost_nodes"]
        for item in ghost.get("evidence", [])
        if item.get("anchor_type") == "ACCOUNT" and str(item.get("anchor_name", "")).startswith("ACC-COORD-")
    }
    planted_accounts = {next(iter(v)) for v in truth.values()}
    hits_accounts = predicted_accounts & planted_accounts
    false_positive_ghosts = [
        ghost for ghost in doc["ghost_nodes"]
        if not any(str(item.get("anchor_name", "")).startswith("ACC-COORD-") for item in ghost.get("evidence", []))
    ]
    return {
        "hidden_coordinators": len(planted_accounts),
        "ground_truth_pairs": len(truth_pairs),
        "ghost_candidates": len(doc["ghost_nodes"]),
        "true_positive_pairs": len(hits),
        "false_positive_pairs": len(predicted_pairs - truth_pairs),
        "pair_precision": round(precision, 3),
        "pair_recall": round(recall, 3),
        "predicted_planted_accounts": len(hits_accounts),
        "coordinator_account_recall": round(len(hits_accounts) / len(planted_accounts), 3) if planted_accounts else 0.0,
        "ghost_precision_by_planted_account": round((len(doc["ghost_nodes"]) - len(false_positive_ghosts)) / len(doc["ghost_nodes"]), 3) if doc["ghost_nodes"] else 1.0,
        "detected_accounts": sorted(hits_accounts),
        "ghost_ids": [g["ghost_id"] for g in doc["ghost_nodes"]],
    }

def mini_case(shared_relation: str) -> dict:
    g = nx.MultiDiGraph()
    if shared_relation == "money":
        sides = ("A", "B")
        for side in sides:
            for i in range(6):
                g.add_node(f"{side}{i}", guid=f"{side}{i}", canonical_name=f"{side}{i}", entity_type="PERSON")
            for u, v in zip([f"{side}{i}" for i in range(6)], [f"{side}{i}" for i in range(1, 6)]):
                g.add_edge(u, v, relation="CALLED", attributes={"timestamp": "2025-01-01T00:00:00"})
        anchor = "ACC-PLANTED-1"
        g.add_node(anchor, guid=anchor, canonical_name=anchor, entity_type="ACCOUNT")
        for side in sides:
            for i in (0, 1, 2):
                g.add_edge(f"{side}{i}", anchor, relation="USES_ACCOUNT", attributes={"account_id": anchor, "timestamp": f"2025-01-0{i+2}T00:00:00"})
    else:
        for side in ("A", "B", "C", "D"):
            for i in range(4):
                g.add_node(f"{side}{i}", guid=f"{side}{i}", canonical_name=f"{side}{i}", entity_type="PERSON")
            for u, v in zip([f"{side}{i}" for i in range(4)], [f"{side}{i}" for i in range(1, 4)]):
                g.add_edge(u, v, relation="CALLED", attributes={"timestamp": "2025-01-01T00:00:00"})
        anchor = "Central Station"
        g.add_node(anchor, guid=anchor, canonical_name=anchor, entity_type="LOCATION")
        for side in ("A", "B", "C", "D"):
            for i in (0, 1, 2):
                g.add_edge(f"{side}{i}", anchor, relation="LOCATED_IN", attributes={"location": anchor, "timestamp": "2025-01-02T00:00:00"})
    doc = detect_ghost_nodes(g, GhostConfig())
    return {"case": shared_relation, "ghost_candidates": len(doc["ghost_nodes"])}


if __name__ == "__main__":
    result = {
        "full_dataset": full_dataset_check(),
        "planted_money_anchor": mini_case("money"),
        "common_location_only": mini_case("location"),
    }
    print(json.dumps(result, indent=2))
