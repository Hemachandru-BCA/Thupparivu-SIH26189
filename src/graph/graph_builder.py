"""Graph construction pipeline: triplet loading -> entity resolution -> NetworkX.

This module turns a ``graph_triplets.json`` file into:

- a resolved, GUID-keyed :class:`networkx.MultiDiGraph` (saved as ``graph.pkl``)
- a FastAPI/React-friendly JSON document (saved as ``graph_data.json``)

It also exposes cached, reusable loaders (``load_graph``, ``get_graph_data``,
``get_node``, ``get_edges``, ``get_neighbors``) that a FastAPI backend can
import directly *without* running the pipeline — the functions only read the
artifacts from disk.

Run as a script::

    python graph_builder.py --input data/graph_triplets.json --output-dir output

(Analytics are produced by :mod:`analytics`; ``run_pipeline`` chains both.)
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import networkx as nx

from src.resolution.entity_matcher import (
    EntityMention,
    EntityResolver,
    MatchConfig,
    ResolutionResult,
)
from src.graph.ontology import normalize_relation

logger = logging.getLogger(__name__)

__all__ = [
    "GraphBuilderError",
    "InputDataError",
    "ArtifactNotFoundError",
    "TripletRecord",
    "LoadReport",
    "PipelineResult",
    "load_triplets",
    "resolve_entities",
    "build_graph",
    "graph_to_fastapi_json",
    "save_artifacts",
    "run_pipeline",
    "load_graph",
    "get_graph_data",
    "get_node",
    "get_edges",
    "get_neighbors",
    "get_entity_mapping",
]

GRAPH_PKL_NAME = "graph.pkl"
GRAPH_DATA_NAME = "graph_data.json"
GRAPH_METRICS_NAME = "graph_metrics.json"

#: Environment variable that overrides the artifact search directory.
ARTIFACT_DIR_ENV = "GRAPH_PIPELINE_DIR"

_MODULE_DIR = Path(__file__).resolve().parents[2] / "data" / "exports"


class GraphBuilderError(RuntimeError):
    """Base class for graph-building failures."""


class InputDataError(GraphBuilderError):
    """Raised when the triplet input file is missing or unreadable."""


class ArtifactNotFoundError(GraphBuilderError):
    """Raised when a pipeline artifact (pkl/json) cannot be located."""


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

#: Accepted keys (checked in order, case-insensitively) for each role.
_HEAD_KEYS = ("head", "subject", "source", "from", "src")
_TAIL_KEYS = ("tail", "object", "target", "to", "dst")
_RELATION_KEYS = ("relation", "predicate", "relationship", "type", "label", "rel")
_NAME_KEYS = ("name", "entity", "value", "label", "text", "canonical_name", "id")
_TYPE_KEYS = ("type", "entity_type", "category", "kind")
_CONTAINER_KEYS = ("triplets", "triples", "edges", "relationships", "records", "data")


@dataclass
class TripletRecord:
    """One normalized (head, relation, tail) record from the input file.

    ``attributes`` holds every extra key that was present on the record but
    is not part of head/tail/relation, so no information is lost.
    """

    index: int
    head: EntityMention
    tail: EntityMention
    relation: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadReport:
    """Structured outcome of :func:`load_triplets` (loaded vs skipped rows)."""

    total_records: int = 0
    loaded: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable form."""
        return {
            "total_records": self.total_records,
            "loaded": self.loaded,
            "skipped": self.skipped,
            "errors": list(self.errors),
        }


def _find_key(mapping: Mapping[str, Any], candidates: Sequence[str]) -> Optional[str]:
    """Return the actual key of ``mapping`` matching any candidate (case-insensitive)."""
    lowered = {str(k).lower(): k for k in mapping}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def _extract_mention(
    value: Any, where: str, *, sibling_type: Optional[str] = None
) -> Tuple[Optional[EntityMention], Optional[str]]:
    """Convert a head/tail value (string or dict) into an :class:`EntityMention`.

    ``sibling_type`` is an entity-type hint carried on a *sibling* key of the
    record (e.g. ``source_type``/``target_type`` next to a plain-string
    ``source``/``target``) -- the shape emitted by
    :meth:`extraction.relation_extractor.Triplet.to_dict`. It is only used
    when the endpoint value itself is a bare string (dict endpoints carry
    their own type key and take precedence).

    Returns ``(mention, None)`` on success or ``(None, error_message)`` on
    failure so callers can skip the record gracefully.
    """
    if isinstance(value, str):
        if not value.strip():
            return None, f"{where}: empty name string"
        entity_type = sibling_type.strip() if sibling_type and sibling_type.strip() else None
        return EntityMention(name=value.strip(), entity_type=entity_type), None

    if isinstance(value, Mapping):
        name_key = _find_key(value, _NAME_KEYS)
        if name_key is None or not str(value[name_key]).strip():
            return None, f"{where}: entity object {dict(value)!r} has no usable name key"
        name = str(value[name_key]).strip()

        entity_type: Optional[str] = None
        type_key = _find_key(value, _TYPE_KEYS)
        if type_key is not None and value[type_key] is not None:
            entity_type = str(value[type_key]).strip() or None

        reserved = {name_key, type_key} - {None}
        attributes = {k: v for k, v in value.items() if k not in reserved}
        return EntityMention(name=name, entity_type=entity_type, attributes=attributes), None

    return None, f"{where}: unsupported entity value type {type(value).__name__}"


def _extract_container(payload: Any) -> Tuple[List[Any], Optional[str]]:
    """Locate the triplet list inside the parsed JSON payload."""
    if isinstance(payload, list):
        return payload, None
    if isinstance(payload, Mapping):
        container_key = _find_key(payload, _CONTAINER_KEYS)
        if container_key is not None and isinstance(payload[container_key], list):
            return payload[container_key], None
        return [], "no list of triplets found (looked for keys: triplets/triples/edges/relationships/records/data or a top-level list)"
    return [], f"top-level JSON must be a list or object, got {type(payload).__name__}"


def load_triplets(path: str | os.PathLike[str]) -> Tuple[List[TripletRecord], LoadReport]:
    """Load and normalize triplet records from a JSON file.

    The loader is deliberately schema-flexible. Accepted shapes:

    - Top-level list of records, or an object holding them under one of
      ``triplets`` / ``triples`` / ``edges`` / ``relationships`` / ``records`` / ``data``.
    - Endpoint roles: ``head``/``subject``/``source``/``from``/``src`` and
      ``tail``/``object``/``target``/``to``/``dst`` (case-insensitive).
    - Relation: ``relation``/``predicate``/``relationship``/``type``/``label``/``rel``.
      Missing relations default to ``RELATED_TO``.
    - Endpoints may be plain strings or objects with a name key
      (``name``/``entity``/``value``/``label``/``text``/``id``), an optional
      type key (``type``/``entity_type``/``category``/``kind``) and any number
      of extra attribute keys.
    - Every leftover key on the record becomes an edge attribute.

    Malformed records are **skipped and reported** (never crash the pipeline).

    Returns:
        ``(records, report)`` tuple.

    Raises:
        InputDataError: If the file does not exist or is not valid JSON.
    """
    path = Path(path)
    if not path.exists():
        raise InputDataError(f"Input file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError as exc:
        raise InputDataError(f"Invalid JSON in {path}: {exc}") from exc

    raw_items, container_error = _extract_container(payload)
    report = LoadReport(total_records=len(raw_items) if isinstance(raw_items, list) else 0)
    if container_error:
        report.errors.append(container_error)
        report.skipped = 1
        return [], report

    records: List[TripletRecord] = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, Mapping):
            report.skipped += 1
            report.errors.append(f"record {index}: expected an object, got {type(item).__name__}")
            continue

        head_key = _find_key(item, _HEAD_KEYS)
        tail_key = _find_key(item, _TAIL_KEYS)
        relation_key = _find_key(item, _RELATION_KEYS)

        if head_key is None or tail_key is None:
            report.skipped += 1
            report.errors.append(f"record {index}: missing head/tail endpoint keys")
            continue

        # Sibling type hints for plain-string endpoints, e.g. "source_type"
        # next to "source" -- the shape produced by Triplet.to_dict().
        head_type_key = _find_key(item, (f"{head_key}_type",))
        tail_type_key = _find_key(item, (f"{tail_key}_type",))
        head_sibling_type = str(item[head_type_key]) if head_type_key else None
        tail_sibling_type = str(item[tail_type_key]) if tail_type_key else None

        head, head_err = _extract_mention(
            item[head_key], f"record {index} head", sibling_type=head_sibling_type
        )
        tail, tail_err = _extract_mention(
            item[tail_key], f"record {index} tail", sibling_type=tail_sibling_type
        )
        if head_err or tail_err:
            report.skipped += 1
            report.errors.append(head_err or tail_err or f"record {index}: invalid endpoints")
            continue

        relation = "RELATED_TO"
        if relation_key is not None and item[relation_key] is not None:
            relation = normalize_relation(str(item[relation_key]))

        reserved = {head_key, tail_key, relation_key, head_type_key, tail_type_key} - {None}
        attributes = {k: v for k, v in item.items() if k not in reserved}

        head.source_index = index
        tail.source_index = index
        records.append(
            TripletRecord(
                index=index,
                head=head,
                tail=tail,
                relation=relation,
                attributes=attributes,
            )
        )
        report.loaded += 1

    if report.skipped:
        logger.warning("Loaded %d/%d triplets (%d skipped): %s",
                       report.loaded, report.total_records, report.skipped,
                       "; ".join(report.errors[:5]))
    else:
        logger.info("Loaded %d triplets from %s", report.loaded, path)
    return records, report


# --------------------------------------------------------------------------
# Resolution + graph construction
# --------------------------------------------------------------------------

def resolve_entities(
    records: Sequence[TripletRecord],
    match_config: Optional[MatchConfig] = None,
    *,
    guid_namespace: Optional[str] = None,
    strict_type_separation: bool = True,
) -> ResolutionResult:
    """Resolve all head/tail mentions of ``records`` into canonical entities."""
    resolver = EntityResolver(
        match_config,
        guid_namespace=guid_namespace,
        strict_type_separation=strict_type_separation,
    )
    mentions: List[EntityMention] = []
    for record in records:
        mentions.append(record.head)
        mentions.append(record.tail)
    return resolver.resolve(mentions)


def _edge_id(source: str, relation: str, target: str, index: int) -> str:
    """Deterministic edge id (uuid5) from its coordinates."""
    return str(uuid.uuid5(GRAPH_BUILDER_NAMESPACE, f"{source}|{relation}|{target}|{index}"))


GRAPH_BUILDER_NAMESPACE: uuid.UUID = uuid.uuid5(
    uuid.NAMESPACE_URL, "entity-resolution/graph-builder/v1"
)


def build_graph(
    records: Sequence[TripletRecord],
    resolution: ResolutionResult,
    *,
    graph_name: str = "resolved_knowledge_graph",
    source_file: Optional[str] = None,
) -> nx.MultiDiGraph:
    """Build a GUID-keyed :class:`networkx.MultiDiGraph` from resolved records.

    Nodes carry ``guid``, ``canonical_name``, ``aliases``, ``entity_type``,
    merged ``attributes``, ``mention_count`` and an empty ``metrics`` dict
    that :mod:`analytics` fills in later.

    Edges carry the relation (``relation``/``type``), a deterministic edge
    ``id`` and the record's ``attributes``. Parallel edges between the same
    node pair (different relations) are preserved — hence a MultiDiGraph.
    """
    graph = nx.MultiDiGraph()
    graph.graph.update(
        {
            "name": graph_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_file": str(source_file) if source_file else None,
            "directed": True,
            "multigraph": True,
        }
    )

    for entity in resolution.entities:
        graph.add_node(
            entity.guid,
            guid=entity.guid,
            canonical_name=entity.canonical_name,
            aliases=list(entity.aliases),
            entity_type=entity.entity_type,
            attributes=dict(entity.attributes),
            mention_count=entity.mention_count,
            metrics={},
        )

    for record in records:
        source_guid = resolution.normalized_to_guid.get(
            _norm_of(record.head)
        )
        target_guid = resolution.normalized_to_guid.get(
            _norm_of(record.tail)
        )
        if source_guid is None or target_guid is None:
            logger.warning("record %d: unresolved endpoint(s), edge skipped", record.index)
            continue
        edge_id = _edge_id(source_guid, record.relation, target_guid, record.index)
        graph.add_edge(
            source_guid,
            target_guid,
            key=edge_id,
            id=edge_id,
            relation=record.relation,
            source_name=record.head.name,
            target_name=record.tail.name,
            source_index=record.index,
            attributes=dict(record.attributes),
        )

    logger.info(
        "Built graph: %d nodes / %d edges", graph.number_of_nodes(), graph.number_of_edges()
    )
    return graph


def _norm_of(mention: EntityMention) -> str:
    """Normalized lookup key for a mention (mirrors entity_matcher logic)."""
    from src.resolution.entity_matcher import normalize_name

    return normalize_name(mention.name)


# --------------------------------------------------------------------------
# FastAPI-friendly serialization
# --------------------------------------------------------------------------

def graph_to_fastapi_json(
    graph: nx.MultiDiGraph,
    resolution: Optional[ResolutionResult] = None,
    *,
    include_entity_mapping: bool = True,
) -> Dict[str, Any]:
    """Serialize the graph into the FastAPI/React-friendly document.

    Structure::

        {
          "directed": true, "multigraph": true,
          "metadata": {...},
          "nodes":  [{"id", "label", "type", "aliases", "attributes", "metrics"}],
          "edges":  [{"id", "source", "target", "type", "label", "attributes"}],
          "entity_mapping": {"<original name>": "<guid>"}
        }

    Every value is plain JSON (str/int/float/bool/None/list/dict), so FastAPI
    endpoints can ``return`` it directly.
    """
    nodes: List[Dict[str, Any]] = []
    for _, attrs in graph.nodes(data=True):
        nodes.append(
            {
                "id": attrs.get("guid"),
                "label": attrs.get("canonical_name"),
                "type": (attrs.get("entity_type") or "unknown"),
                "aliases": list(attrs.get("aliases", [])),
                "attributes": dict(attrs.get("attributes", {})),
                "mention_count": int(attrs.get("mention_count", 0)),
                "metrics": dict(attrs.get("metrics", {})),
            }
        )
    nodes.sort(key=lambda n: (n["label"] or "").lower())

    edges: List[Dict[str, Any]] = []
    for source, target, keys, attrs in graph.edges(keys=True, data=True):
        edges.append(
            {
                "id": attrs.get("id", str(keys)),
                "source": source,
                "target": target,
                "type": attrs.get("relation", "RELATED_TO"),
                "label": attrs.get("relation", "RELATED_TO"),
                "attributes": dict(attrs.get("attributes", {})),
                "source_name": attrs.get("source_name"),
                "target_name": attrs.get("target_name"),
            }
        )
    edges.sort(key=lambda e: (e["source"], e["target"], e["type"]))

    er_stats: Dict[str, Any] = {}
    if resolution is not None:
        er_stats = {
            "original_mention_count": resolution.stats.get("original_mentions", 0),
            "original_unique_names": resolution.stats.get("original_unique_names", 0),
            "resolved_entity_count": resolution.stats.get("resolved_entities", 0),
        }

    document: Dict[str, Any] = {
        "directed": bool(graph.is_directed()),
        "multigraph": bool(graph.is_multigraph()),
        "metadata": {
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "generated_at": graph.graph.get("created_at"),
            "source_file": graph.graph.get("source_file"),
            "entity_resolution": er_stats,
        },
        "nodes": nodes,
        "edges": edges,
    }
    if include_entity_mapping and resolution is not None:
        document["entity_mapping"] = dict(resolution.name_to_guid)
    return document


def save_artifacts(
    graph: nx.MultiDiGraph,
    data_document: Mapping[str, Any],
    output_dir: str | os.PathLike[str],
) -> Tuple[Path, Path]:
    """Persist ``graph.pkl`` and ``graph_data.json`` into ``output_dir``.

    Returns the ``(pkl_path, json_path)`` pair.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    pkl_path = out / GRAPH_PKL_NAME
    with pkl_path.open("wb") as fh:
        pickle.dump(graph, fh, protocol=pickle.HIGHEST_PROTOCOL)

    json_path = out / GRAPH_DATA_NAME
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(data_document, fh, indent=2, ensure_ascii=False)

    logger.info("Saved %s and %s", pkl_path, json_path)
    return pkl_path, json_path


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Paths and summary statistics of a full pipeline run."""

    graph_path: Path
    data_path: Path
    metrics_path: Optional[Path]
    load_report: LoadReport
    resolution: ResolutionResult
    metadata: Dict[str, Any] = field(default_factory=dict)


def run_pipeline(
    input_path: str | os.PathLike[str] | None = None,
    output_dir: str | os.PathLike[str] | None = None,
    *,
    match_config: Optional[MatchConfig] = None,
    run_analytics: bool = True,
    graph_name: str = "resolved_knowledge_graph",
) -> PipelineResult:
    """End-to-end pipeline: load -> resolve -> build -> (analytics) -> save.

    Args:
        input_path: Path to ``graph_triplets.json``. Defaults to
            ``<module>/data/graph_triplets.json`` when present, otherwise
            ``./graph_triplets.json``.
        output_dir: Where artifacts are written. Defaults to
            ``$GRAPH_PIPELINE_DIR`` or ``<module>/output``.
        match_config: Optional :class:`MatchConfig` overrides.
        run_analytics: When True (default), also computes metrics via
            :mod:`analytics` and writes ``graph_metrics.json``.
        graph_name: Name stored in the graph metadata.

    Returns:
        A :class:`PipelineResult` with artifact paths and statistics.
    """
    # Imported lazily to keep module import graphs acyclic.
    from src.graph import analytics

    resolved_input = _default_input_path() if input_path is None else Path(input_path)
    resolved_output = (
        Path(os.environ.get(ARTIFACT_DIR_ENV, _MODULE_DIR / "output"))
        if output_dir is None
        else Path(output_dir)
    )

    records, report = load_triplets(resolved_input)
    resolution = resolve_entities(records, match_config)
    graph = build_graph(records, resolution, graph_name=graph_name, source_file=str(resolved_input))

    metrics_path: Optional[Path] = None
    if run_analytics and graph.number_of_nodes() > 0:
        er_summary = resolution.to_er_summary()
        analytics.attach_metrics(graph, er_summary=er_summary)

    data_document = graph_to_fastapi_json(graph, resolution)
    pkl_path, json_path = save_artifacts(graph, data_document, resolved_output)

    if run_analytics and graph.number_of_nodes() > 0:
        metrics_doc = analytics.build_metrics_document(
            graph, er_summary=resolution.to_er_summary()
        )
        metrics_path = analytics.write_graph_metrics(metrics_doc, resolved_output)

    return PipelineResult(
        graph_path=pkl_path,
        data_path=json_path,
        metrics_path=metrics_path,
        load_report=report,
        resolution=resolution,
        metadata=dict(data_document["metadata"]),
    )


def _default_input_path() -> Path:
    """Default triplet input location (project ``data/`` first, then CWD)."""
    candidate = _MODULE_DIR.parent / "data" / "graph_triplets.json"
    if candidate.exists():
        return candidate
    candidate = _MODULE_DIR / "data" / "graph_triplets.json"
    if candidate.exists():
        return candidate
    return Path("graph_triplets.json")


# --------------------------------------------------------------------------
# Reusable loaders for FastAPI (no pipeline execution)
# --------------------------------------------------------------------------

def _artifact_candidates(name: str) -> List[Path]:
    """Search order for an artifact: env dir, module/output, module dir, CWD."""
    candidates: List[Path] = []
    env_dir = os.environ.get(ARTIFACT_DIR_ENV)
    if env_dir:
        candidates.append(Path(env_dir) / name)
    candidates.append(_MODULE_DIR / "output" / name)
    candidates.append(_MODULE_DIR / name)
    candidates.append(Path.cwd() / name)
    return candidates


def find_artifact(name: str, base_dir: str | os.PathLike[str] | None = None) -> Path:
    """Locate an artifact file, searching sensible default locations.

    Raises:
        ArtifactNotFoundError: If the file exists nowhere in the search path.
    """
    if base_dir is not None:
        candidate = Path(base_dir) / name
        if candidate.exists():
            return candidate
        raise ArtifactNotFoundError(f"Artifact {name!r} not found in {base_dir}")
    for candidate in _artifact_candidates(name):
        if candidate.exists():
            return candidate
    raise ArtifactNotFoundError(
        f"Artifact {name!r} not found. Searched: "
        + ", ".join(str(c) for c in _artifact_candidates(name))
        + f". Run the pipeline first or set ${ARTIFACT_DIR_ENV}."
    )


def load_graph(path: str | os.PathLike[str] | None = None) -> nx.MultiDiGraph:
    """Load (and cache) the pickled NetworkX graph.

    Safe to import and call from FastAPI at request time — it never runs the
    pipeline, it only reads ``graph.pkl`` from disk.
    """
    target = Path(path) if path is not None else find_artifact(GRAPH_PKL_NAME)
    return _load_graph_cached(str(target.resolve()))


def get_graph_data(path: str | os.PathLike[str] | None = None) -> Dict[str, Any]:
    """Load (and cache) the FastAPI-ready JSON document."""
    target = Path(path) if path is not None else find_artifact(GRAPH_DATA_NAME)
    return _load_data_cached(str(target.resolve()))


def get_node(guid: str, path: str | os.PathLike[str] | None = None) -> Optional[Dict[str, Any]]:
    """Return one node document by GUID, or ``None`` if unknown."""
    document = get_graph_data(path)
    for node in document.get("nodes", []):
        if node.get("id") == guid:
            return node
    return None


def get_edges(
    path: str | os.PathLike[str] | None = None,
) -> List[Dict[str, Any]]:
    """Return all edge documents."""
    return list(get_graph_data(path).get("edges", []))


def get_neighbors(guid: str, path: str | os.PathLike[str] | None = None) -> List[Dict[str, Any]]:
    """Return the neighborhood of a node (guid, direction and edge type)."""
    graph = load_graph(path)
    if guid not in graph:
        return []
    neighbors: List[Dict[str, Any]] = []
    for _, target, attrs in graph.out_edges(guid, data=True):
        neighbors.append({"guid": target, "direction": "out", "type": attrs.get("relation")})
    for source, _, attrs in graph.in_edges(guid, data=True):
        neighbors.append({"guid": source, "direction": "in", "type": attrs.get("relation")})
    return neighbors


def get_entity_mapping(path: str | os.PathLike[str] | None = None) -> Dict[str, str]:
    """Return the original-name -> GUID mapping from ``graph_data.json``."""
    return dict(get_graph_data(path).get("entity_mapping", {}))


# Cached internals (keyed by resolved absolute path).

try:
    from functools import lru_cache
except ImportError:  # pragma: no cover
    lru_cache = None

if lru_cache is not None:

    @lru_cache(maxsize=4)
    def _load_graph_cached(resolved_path: str) -> nx.MultiDiGraph:
        with Path(resolved_path).open("rb") as fh:
            graph = pickle.load(fh)
        logger.info("Loaded graph from %s", resolved_path)
        return graph

    @lru_cache(maxsize=4)
    def _load_data_cached(resolved_path: str) -> Dict[str, Any]:
        with Path(resolved_path).open("r", encoding="utf-8") as fh:
            document = json.load(fh)
        logger.info("Loaded graph data from %s", resolved_path)
        return document

else:  # pragma: no cover - Python without functools.lru_cache (very unlikely)
    def _load_graph_cached(resolved_path: str) -> nx.MultiDiGraph:
        with Path(resolved_path).open("rb") as fh:
            return pickle.load(fh)

    def _load_data_cached(resolved_path: str) -> Dict[str, Any]:
        with Path(resolved_path).open("r", encoding="utf-8") as fh:
            return json.load(fh)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _cli() -> int:  # pragma: no cover - manual invocation helper
    import argparse

    parser = argparse.ArgumentParser(
        description="Build a resolved knowledge graph from graph_triplets.json"
    )
    parser.add_argument("--input", "-i", default=None, help="Path to graph_triplets.json")
    parser.add_argument("--output-dir", "-o", default=None, help="Artifact output directory")
    parser.add_argument("--no-analytics", action="store_true", help="Skip metrics computation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    result = run_pipeline(
        input_path=args.input,
        output_dir=args.output_dir,
        run_analytics=not args.no_analytics,
    )
    print("Pipeline finished.")
    print(f"  loaded triplets : {result.load_report.loaded} (skipped {result.load_report.skipped})")
    print(f"  resolved entities: {result.resolution.stats.get('resolved_entities')}"
          f" from {result.resolution.stats.get('original_unique_names')} names")
    print(f"  graph           : {result.metadata['node_count']} nodes / {result.metadata['edge_count']} edges")
    print(f"  graph.pkl       : {result.graph_path}")
    print(f"  graph_data.json : {result.data_path}")
    if result.metrics_path:
        print(f"  graph_metrics.json: {result.metrics_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
