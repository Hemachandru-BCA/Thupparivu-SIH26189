"""
pipeline_steps.py
------------------
Thin wrappers around each stage of the CriminalAnalysis / SentinelGraph AI
pipeline, returning plain JSON-serializable dicts. These are the functions
the job runner (api/jobs.py) and the routers call -- kept separate from the
FastAPI routing code so they're independently testable/importable (e.g.
from a CLI or a notebook) without pulling in FastAPI at all.

Each step reads/writes to the fixed paths in api/paths.py, so a run of
generate -> preprocess -> extract -> graph_build -> ghosts always chains
correctly with no manual path plumbing.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

from src.api import paths


def run_generate(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Stage 1: synthetic dataset generation (gangs/persons/calls/txns/meetings)."""
    from src.generator.config import SimulationConfig
    from src.generator.dataset_generator import DatasetGenerator

    config = SimulationConfig(**(overrides or {}))
    generator = DatasetGenerator(config=config, output_dir=str(paths.SYNTHETIC_DIR))
    summary = generator.run()
    return asdict(summary)


def run_preprocess(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Stage 2: standardize persons, simulate FIRs/reports, clean + dedupe text."""
    from src.preprocessing.pipeline import PipelineConfig, PreprocessingPipeline

    config = PipelineConfig(
        input_dir=str(paths.SYNTHETIC_DIR),
        output_dir=str(paths.PROCESSED_DIR),
        **(overrides or {}),
    )
    pipeline = PreprocessingPipeline(config)
    summary = pipeline.run()
    return asdict(summary)


def run_extract(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Stage 3: NER + relation extraction + event extraction -> graph_triplets.json."""
    from src.extraction.pipeline import ExtractionConfig, ExtractionPipeline

    config = ExtractionConfig(
        input_path=str(paths.CLEANED_RECORDS_PATH),
        output_path=str(paths.GRAPH_TRIPLETS_PATH),
        **(overrides or {}),
    )
    pipeline = ExtractionPipeline(config)
    summary = pipeline.run()
    return asdict(summary)


def run_graph_build(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Stage 4: entity resolution + graph construction + analytics -> graph.pkl/json."""
    from src.graph import graph_builder
    from src.graph.graph_builder import run_pipeline as build_pipeline

    result = build_pipeline(
        input_path=str(paths.GRAPH_TRIPLETS_PATH),
        output_dir=str(paths.GRAPH_OUTPUT_DIR),
        **(overrides or {}),
    )
    _invalidate_graph_caches()
    return {
        "graph_path": str(result.graph_path),
        "data_path": str(result.data_path),
        "metrics_path": str(result.metrics_path) if result.metrics_path else None,
        "load_report": result.load_report.to_dict(),
        "metadata": result.metadata,
    }


def _invalidate_graph_caches() -> None:
    """Clear the module-level lru_caches in graph_builder/analytics.

    Both modules cache loaded artifacts (graph.pkl / graph_data.json /
    graph_metrics.json) keyed only by resolved path, with no mtime check --
    so once an artifact has been read once, re-running the graph pipeline
    and writing a new file at the *same* path would otherwise keep serving
    the old in-memory copy for the lifetime of the process. We clear them
    explicitly after every write so GET requests always see fresh data.
    """
    from graph import analytics, graph_builder

    for fn_name in ("_load_graph_cached", "_load_data_cached"):
        fn = getattr(graph_builder, fn_name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()

    fn = getattr(analytics, "_load_metrics_cached", None)
    if fn is not None and hasattr(fn, "cache_clear"):
        fn.cache_clear()


def run_ghosts(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Stage 5 (optional): hidden-coordinator / ghost-node detection."""
    from src.graph.ghost_nodes import GhostConfig, _mask_nodes, detect_ghost_nodes, load_graph, write_predictions
    import csv

    graph = load_graph(str(paths.GRAPH_PKL_PATH))
    config = GhostConfig(**(overrides or {}))
    hidden_names = set()
    if paths.PERSONS_CSV.exists():
        with paths.PERSONS_CSV.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if str(row.get("is_hidden_coordinator", "")).strip().lower() == "true":
                    if row.get("full_name"):
                        hidden_names.add(row["full_name"])
    observed_graph = _mask_nodes(graph, hidden_names) if hidden_names else graph
    document = detect_ghost_nodes(observed_graph, config)
    document.setdefault("metadata", {})["synthetic_hidden_nodes_masked"] = len(hidden_names)
    output_path = write_predictions(document, str(paths.GHOST_PREDICTIONS_PATH))
    return {
        "output_path": str(output_path),
        "summary": document.get("summary", {}),
        "num_communities": len(document.get("communities", [])),
        "num_ghost_nodes": len(document.get("ghost_nodes", [])),
    }


def run_full_pipeline(
    generate_overrides: Optional[Dict[str, Any]] = None,
    preprocess_overrides: Optional[Dict[str, Any]] = None,
    extract_overrides: Optional[Dict[str, Any]] = None,
    graph_overrides: Optional[Dict[str, Any]] = None,
    ghost_overrides: Optional[Dict[str, Any]] = None,
    run_ghost_detection: bool = True,
) -> Dict[str, Any]:
    """Chain every stage end-to-end (used by the /pipeline/run-all job)."""
    results: Dict[str, Any] = {}
    results["generate"] = run_generate(generate_overrides)
    results["preprocess"] = run_preprocess(preprocess_overrides)
    results["extract"] = run_extract(extract_overrides)
    results["graph_build"] = run_graph_build(graph_overrides)
    if run_ghost_detection:
        results["ghosts"] = run_ghosts(ghost_overrides)
    return results
