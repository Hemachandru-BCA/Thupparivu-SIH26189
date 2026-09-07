"""
sentinelgraph_pipeline.py
-------------------------
Example Airflow DAG wiring the SentinelGraph pipeline stages (Phase V).

Architecture adapter only: this file is intentionally NOT imported by the
demo/API.  Deploy it to an Airflow DAGs folder with worker access to the
pipeline artifacts and dependencies (``pip install apache-airflow``), e.g.:

    AIRFLOW_HOME=~/airflow
    cp src/adapters/airflow_dags/sentinelgraph_pipeline.py $AIRFLOW_HOME/dags/

Task graph:

    ingest -> preprocess -> extract -> resolve_and_build_graph
           -> ghost_inference -> build_evidence_index

Each task shells out to the same stage runner the local demo uses
(``run_stage.py``) so the DAG executes the identical code path.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_ROOT = os.environ.get("SENTINELGRAPH_ROOT", "/opt/sentinelgraph-ai")
PYTHON = os.environ.get("SENTINELGRAPH_PYTHON", "python3")

DEFAULT_ARGS = {
    "owner": "sentinelgraph",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="sentinelgraph_pipeline",
    description="SentinelGraph AI end-to-end pipeline (demo stages)",
    default_args=DEFAULT_ARGS,
    schedule=None,                   # trigger manually / via API
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["sentinelgraph", "demo"],
) as dag:

    def stage(task_id: str, script: str) -> BashOperator:
        return BashOperator(
            task_id=task_id,
            bash_command=f"cd {PROJECT_ROOT} && {PYTHON} run_stage.py {script}",
        )

    ingest = stage("ingest", "generate")
    preprocess = stage("preprocess", "preprocess")
    extract = stage("extract", "extract")
    graph = stage("resolve_and_build_graph", "graph")
    ghosts = stage("ghost_inference", "ghosts")

    build_evidence = BashOperator(
        task_id="build_evidence_index",
        bash_command=(
            f"cd {PROJECT_ROOT} && {PYTHON} -m src.xai.build_evidence"
        ),
    )

    ingest >> preprocess >> extract >> graph >> ghosts >> build_evidence
