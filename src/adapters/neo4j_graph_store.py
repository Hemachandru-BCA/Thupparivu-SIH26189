"""
neo4j_graph_store.py
--------------------
Optional Neo4j adapter (Phase U) implementing the GraphStore interface.

Graph schema:

    (:Person) (:Organization) (:Location) (:Phone) (:Account)
    (:Vehicle) (:Event) (:Document) (:GhostCandidate)

Relationships:

    [:CALLED] [:TRANSFERRED_FUNDS] [:MET_AT] [:ASSOCIATED_WITH]
    [:LOCATED_AT] [:OWNS] [:MENTIONED_IN] [:SUPPORTED_BY]
    [:PREDICTED_RELATION]

Inferred (model-generated) relationships carry ``inferred: true`` and ghost
candidates are :GhostCandidate nodes - observed and inferred are never
mixed.  Requires the ``neo4j`` driver and connection settings; disabled by
default, the local demo uses NetworkX.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from src.adapters.graph_store import _safe
from src.adapters.postgres_repository import AdapterNotConfigured

logger = logging.getLogger(__name__)


class Neo4jGraphStore:
    """Neo4j-backed GraphStore (neo4j driver, lazy import)."""

    NODE_LABEL_BY_TYPE = {
        "PERSON": "Person",
        "ORGANIZATION": "Organization",
        "LOCATION": "Location",
        "PHONE": "Phone",
        "ACCOUNT": "Account",
        "VEHICLE": "Vehicle",
        "EVENT": "Event",
        "DOCUMENT": "Document",
        "GHOST": "GhostCandidate",
    }

    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None,
                 password: Optional[str] = None, database: str = "neo4j") -> None:
        try:
            import neo4j  # noqa: F401
        except ImportError as exc:
            raise AdapterNotConfigured(
                "neo4j driver is not installed. Install with: pip install neo4j"
            ) from exc
        self.uri = uri or os.environ.get("SENTINELGRAPH_NEO4J_URI")
        self.user = user or os.environ.get("SENTINELGRAPH_NEO4J_USER", "neo4j")
        self.password = password or os.environ.get("SENTINELGRAPH_NEO4J_PASSWORD")
        self.database = database
        if not self.uri or not self.password:
            raise AdapterNotConfigured(
                "SENTINELGRAPH_NEO4J_URI and SENTINELGRAPH_NEO4J_PASSWORD are required"
            )
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    # ------------------------------------------------------------- schema --
    def ensure_constraints(self) -> None:
        with self.driver.session(database=self.database) as session:
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) "
                "REQUIRE n.guid IS UNIQUE"
            )

    # -------------------------------------------------------------- sync --
    def import_networkx(self, graph, *, batch_size: int = 500) -> Dict[str, int]:
        """Bulk-import a NetworkX MultiDiGraph produced by the pipeline.

        Observed edges are written with ``inferred: false``; ghost predicted
        edges as ``[:PREDICTED_RELATION {inferred: true}]``.
        """
        stats = {"nodes": 0, "edges": 0}
        with self.driver.session(database=self.database) as session:
            for idx, (node, attrs) in enumerate(graph.nodes(data=True)):
                label = self.NODE_LABEL_BY_TYPE.get(
                    str(attrs.get("entity_type", "")).upper(), "Entity"
                )
                safe_label = "".join(c for c in label if c.isalnum())
                session.run(
                    f"MERGE (n:Entity:{safe_label} {{guid: $guid}}) SET n += $attrs",
                    guid=str(node),
                    attrs=_safe(dict(attrs)),
                )
                stats["nodes"] += 1
        with self.driver.session(database=self.database) as session:
            for u, v, attrs in graph.edges(data=True):
                relation = str(attrs.get("relation", "RELATED_TO"))
                inferred = bool(attrs.get("attributes", {}).get("inferred", False))
                rel_type = "PREDICTED_RELATION" if inferred else relation
                session.run(
                    "MATCH (a:Entity {guid: $u}), (b:Entity {guid: $v}) "
                    f"MERGE (a)-[r:{rel_type}]->(b) "
                    "SET r.inferred = $inferred, r.edge_id = $edge_id",
                    u=str(u), v=str(v), inferred=inferred,
                    edge_id=str(attrs.get("id", "")),
                )
                stats["edges"] += 1
        return stats

    # ---------------------------------------------------------- GraphStore --
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            rec = session.run(
                "MATCH (n:Entity {guid: $guid}) RETURN properties(n) AS props",
                guid=node_id,
            ).single()
        return dict(rec["props"]) if rec else None

    def get_neighbors(self, node_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.run(
                "MATCH (n:Entity {guid: $guid})-[r]-(m:Entity) "
                "RETURN type(r) AS rel, properties(m) AS props LIMIT $limit",
                guid=node_id, limit=limit,
            )
            return [{"relation": rec["rel"], **dict(rec["props"])} for rec in result]

    def get_subgraph(self, node_id: str, *, depth: int = 2,
                     max_nodes: int = 500) -> Dict[str, Any]:
        depth = max(1, min(int(depth), 6))
        max_nodes = max(1, min(int(max_nodes), 5000))
        with self.driver.session(database=self.database) as session:
            result = session.run(
                f"MATCH (n:Entity {{guid: $guid}})-[rels*1..{depth}]-(m:Entity) "
                f"WITH collect(DISTINCT m)[..{max_nodes}] AS ms, n "
                "RETURN [n] + ms AS nodes",
                guid=node_id,
            )
            rec = result.single()
        nodes = [dict(r) for r in (rec["nodes"] if rec else [])]
        return {"nodes": nodes, "edges": [], "truncated": len(nodes) >= max_nodes}

    def get_paths(self, source: str, target: str, *, k: int = 3) -> List[Dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.run(
                "MATCH p = shortestPath((a:Entity {guid: $src})-[*..6]-(b:Entity {guid: $tgt})) "
                "RETURN [n IN nodes(p) | n.guid] AS path",
                src=source, tgt=target,
            )
            return [{"path": rec["path"], "length": len(rec["path"]) - 1, "edges": []}
                    for rec in result]
