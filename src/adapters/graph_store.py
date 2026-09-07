"""
graph_store.py
--------------
GraphStore interface (Phase T).

The local NetworkX implementation is the default and the only one the demo
needs; the interface exists so a Neo4j/PostgreSQL-backed store can be
swapped in later without touching pipeline or API code.
"""

from __future__ import annotations

import json
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, Hashable, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

import networkx as nx

logger = logging.getLogger(__name__)


@runtime_checkable
class GraphStore(Protocol):
    """Conceptual graph interface satisfied by NetworkX today, Neo4j later."""

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]: ...

    def get_neighbors(self, node_id: str, *, limit: int = 100) -> List[Dict[str, Any]]: ...

    def get_subgraph(
        self,
        node_id: str,
        *,
        depth: int = 2,
        max_nodes: int = 500,
    ) -> Dict[str, Any]: ...

    def get_paths(self, source: str, target: str, *, k: int = 3) -> List[Dict[str, Any]]: ...


class NetworkXGraphStore:
    """Local GraphStore over a pickled MultiDiGraph artifact."""

    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self.graph = graph
        self._projection: Optional[nx.Graph] = None

    # ------------------------------------------------------------------ #
    @classmethod
    def from_pkl(cls, path: str | Path) -> "NetworkXGraphStore":
        with Path(path).open("rb") as fh:
            graph = pickle.load(fh)
        return cls(graph)

    @classmethod
    def from_json(cls, path: str | Path) -> "NetworkXGraphStore":
        doc = json.loads(Path(path).read_text())
        graph = nx.node_link_graph(doc, edges="edges", nodes="nodes")
        return cls(graph)

    # ------------------------------------------------------------------ #
    @property
    def projection(self) -> nx.Graph:
        """Undirected weighted projection used for neighbourhood queries."""
        if self._projection is None:
            projection = nx.Graph()
            for u, v, attrs in self.graph.edges(data=True):
                weight = float(attrs.get("weight") or attrs.get("attributes", {}).get("observation_count") or 1)
                if projection.has_edge(u, v):
                    projection[u][v]["weight"] += weight
                else:
                    projection.add_edge(u, v, weight=weight)
            self._projection = projection
        return self._projection

    # ------------------------------------------------------------------ #
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        if node_id not in self.graph:
            return None
        attrs = dict(self.graph.nodes[node_id])
        attrs["id"] = str(node_id)
        attrs["degree"] = self.graph.degree(node_id)
        return _safe(attrs)

    def get_neighbors(self, node_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
        if node_id not in self.graph:
            return []
        out: List[Dict[str, Any]] = []
        for _, v, attrs in sorted(
            self.graph.out_edges(node_id, data=True), key=lambda e: str(e[1])
        ):
            out.append({
                "node_id": str(v),
                "direction": "out",
                "relation": attrs.get("relation"),
                "edge_id": attrs.get("id"),
            })
        for u, _, attrs in sorted(
            self.graph.in_edges(node_id, data=True), key=lambda e: str(e[0])
        ):
            out.append({
                "node_id": str(u),
                "direction": "in",
                "relation": attrs.get("relation"),
                "edge_id": attrs.get("id"),
            })
            if len(out) >= limit * 2:
                break
        return out[:limit]

    def get_subgraph(
        self, node_id: str, *, depth: int = 2, max_nodes: int = 500
    ) -> Dict[str, Any]:
        if node_id not in self.graph:
            raise KeyError(f"node not found: {node_id}")
        projection = self.projection
        visited: Dict[Hashable, int] = {node_id: 0}
        frontier = [node_id]
        for level in range(1, depth + 1):
            nxt: List[Hashable] = []
            for current in frontier:
                for nbr in projection.neighbors(current):
                    if nbr not in visited:
                        visited[nbr] = level
                        nxt.append(nbr)
            frontier = nxt
            if len(visited) >= max_nodes:
                break
        selected = list(visited)[:max_nodes]
        sub = self.graph.subgraph(selected)
        return self._serialize(sub, truncated=len(visited) > max_nodes)

    def get_paths(self, source: str, target: str, *, k: int = 3) -> List[Dict[str, Any]]:
        if source not in self.graph or target not in self.graph:
            raise KeyError("source or target not found")
        projection = self.projection
        out: List[Dict[str, Any]] = []
        try:
            from itertools import islice

            paths = list(islice(nx.shortest_simple_paths(projection, source, target), max(1, k)))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return out
        for path in paths:
            edges = []
            for u, v in zip(path, path[1:]):
                edge_attrs = self._edge_between(u, v)
                edges.append(edge_attrs)
            out.append({
                "path": [str(p) for p in path],
                "length": len(path) - 1,
                "edges": edges,
            })
        return out

    # ------------------------------------------------------------------ #
    def _edge_between(self, u: Hashable, v: Hashable) -> Dict[str, Any]:
        data = self.graph.get_edge_data(u, v) or {}
        if data:
            key = sorted(data.keys())[0]
            attrs = data[key]
            return {
                "edge_id": attrs.get("id", str(key)),
                "relation": attrs.get("relation"),
                "source": str(u),
                "target": str(v),
            }
        return {"edge_id": None, "relation": None, "source": str(u), "target": str(v)}

    def _serialize(self, sub: nx.MultiDiGraph, *, truncated: bool = False) -> Dict[str, Any]:
        nodes = []
        for n, attrs in sub.nodes(data=True):
            payload = dict(attrs)
            payload["id"] = str(n)
            payload["degree"] = sub.degree(n)
            nodes.append(_safe(payload))
        edges = []
        for u, v, attrs in sub.edges(data=True):
            edges.append(_safe({
                "id": attrs.get("id"),
                "source": str(u),
                "target": str(v),
                "type": attrs.get("relation"),
                "attributes": attrs.get("attributes", {}),
            }))
        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": sub.number_of_nodes(),
            "edge_count": sub.number_of_edges(),
            "truncated": truncated,
        }


def _safe(obj: Any) -> Any:
    """JSON-safe conversion for numpy/pickle artifacts."""
    if isinstance(obj, dict):
        return {str(k): _safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_safe(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)
