"""
routers/pipeline.py
---------------------
POST endpoints that kick off each pipeline stage as a background job, plus
GET /jobs/{job_id} to poll for completion. Every trigger endpoint returns
immediately with a job_id -- the React frontend should poll the jobs
endpoint (e.g. every 1-2s) until status is "success" or "failed".
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.api import pipeline_steps
from src.api.jobs import job_manager
from src.api.schemas import (
    ExtractRequest,
    GenerateRequest,
    GhostDetectRequest,
    GraphBuildRequest,
    PreprocessRequest,
    RunAllRequest,
)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


def _overrides(model) -> Dict[str, Any]:
    """Drop unset/None fields so each stage's own dataclass defaults apply."""
    return model.model_dump(exclude_none=True) if model else {}


@router.post("/generate")
def trigger_generate(body: GenerateRequest = GenerateRequest()):
    overrides = _overrides(body)
    job = job_manager.submit("generate", lambda: pipeline_steps.run_generate(overrides))
    return job.to_dict()


@router.post("/preprocess")
def trigger_preprocess(body: PreprocessRequest = PreprocessRequest()):
    overrides = _overrides(body)
    job = job_manager.submit("preprocess", lambda: pipeline_steps.run_preprocess(overrides))
    return job.to_dict()


@router.post("/extract")
def trigger_extract(body: ExtractRequest = ExtractRequest()):
    overrides = _overrides(body)
    job = job_manager.submit("extract", lambda: pipeline_steps.run_extract(overrides))
    return job.to_dict()


@router.post("/graph/build")
def trigger_graph_build(body: GraphBuildRequest = GraphBuildRequest()):
    overrides = _overrides(body)
    job = job_manager.submit("graph_build", lambda: pipeline_steps.run_graph_build(overrides))
    return job.to_dict()


@router.post("/ghosts")
def trigger_ghosts(body: GhostDetectRequest = GhostDetectRequest()):
    overrides = _overrides(body)
    job = job_manager.submit("ghosts", lambda: pipeline_steps.run_ghosts(overrides))
    return job.to_dict()


@router.post("/run-all")
def trigger_run_all(body: RunAllRequest = RunAllRequest()):
    def _run():
        return pipeline_steps.run_full_pipeline(
            generate_overrides=_overrides(body.generate),
            preprocess_overrides=_overrides(body.preprocess),
            extract_overrides=_overrides(body.extract),
            graph_overrides=_overrides(body.graph),
            ghost_overrides=_overrides(body.ghosts),
            run_ghost_detection=body.run_ghost_detection,
        )

    job = job_manager.submit("run_all", _run)
    return job.to_dict()


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    return job.to_dict()


@router.get("/jobs")
def list_jobs():
    return [job.to_dict() for job in job_manager.list().values()]
