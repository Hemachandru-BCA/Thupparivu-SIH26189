"""
jobs.py
-------
Minimal in-memory job tracker so the React frontend can kick off a
pipeline stage, get a job_id back immediately, and poll for status
instead of holding an HTTP connection open for 10-30+ seconds.

Not meant to survive a server restart or scale across multiple worker
processes -- for that, swap this for Celery/RQ + Redis. For a single
`uvicorn` process (the common case for this kind of demo/hackathon
project) this is enough and adds zero infra dependencies.
"""

from __future__ import annotations

import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    kind: str
    status: JobStatus = JobStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.id,
            "kind": self.kind,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
        }


class JobManager:
    def __init__(self, max_workers: int = 2):
        self._jobs: Dict[str, Job] = {}
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, kind: str, fn: Callable[[], Dict[str, Any]]) -> Job:
        job = Job(id=str(uuid.uuid4()), kind=kind)
        with self._lock:
            self._jobs[job.id] = job
        self._executor.submit(self._run, job.id, fn)
        return job

    def _run(self, job_id: str, fn: Callable[[], Dict[str, Any]]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc).isoformat()
        try:
            result = fn()
            with self._lock:
                job.result = result
                job.status = JobStatus.SUCCESS
        except Exception:  # noqa: BLE001 - surface any failure to the client
            with self._lock:
                job.error = traceback.format_exc()
                job.status = JobStatus.FAILED
        finally:
            with self._lock:
                job.finished_at = datetime.now(timezone.utc).isoformat()

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> Dict[str, Job]:
        with self._lock:
            return dict(self._jobs)


job_manager = JobManager()
