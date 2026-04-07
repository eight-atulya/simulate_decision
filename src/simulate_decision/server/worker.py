from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from simulate_decision.server.job_manager import JobManager, JobStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR = DATA_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _log_separator(title: str = "") -> str:
    if title:
        return f"\n{'='*60}\n  {title}\n{'='*60}\n"
    return f"\n{'─'*60}\n"


class Worker:
    def __init__(
        self,
        worker_id: int = 0,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> None:
        self.worker_id = worker_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.running = False
        self.current_job_id: str | None = None
        self.job_manager = JobManager.get_instance()
        self._heartbeat_interval = 60  # seconds

    def _log_heartbeat(self, state: str = "idle", details: str = "") -> None:
        job_info = f"job_id={self.current_job_id}" if self.current_job_id else "job_id=None"
        detail_info = f" | {details}" if details else ""
        logger.info(
            f"[Worker-{self.worker_id:02d}] "
            f"HEARTBEAT | state={state:20s} | {job_info}{detail_info}"
        )

    def _log_section(self, message: str, indent: int = 2) -> None:
        logger.info(f"[Worker-{self.worker_id:02d}] {' '*indent}{message}")

    def _log_job_start(self, job_id: str, concept: str, pipeline: str) -> None:
        self._log_section(f"{_log_separator('JOB STARTED')}")
        self._log_section(f"Job ID    : {job_id}")
        self._log_section(f"Pipeline  : {pipeline}")
        self._log_section(f"Concept   : {concept[:60]}...")
        self._log_section(f"{'─'*60}")

    def _log_job_progress(self, stage: str, status: str, elapsed: int) -> None:
        self._log_section(f"  └─ Stage: {stage:15s} | Status: {status:10s} | Elapsed: {elapsed}s", indent=0)

    def _log_job_success(self, job_id: str, iterations: int) -> None:
        self._log_section(f"{'─'*60}")
        self._log_section(f"Job ID    : {job_id}")
        self._log_section(f"Status    : SUCCESS")
        self._log_section(f"Iterations: {iterations}")
        self._log_section(f"{_log_separator('JOB COMPLETED')}")

    def _log_job_failed(self, job_id: str, error: str, is_permanent: bool = False) -> None:
        self._log_section(f"{'─'*60}")
        self._log_section(f"Job ID    : {job_id}")
        self._log_section(f"Status    : {'FAILED (permanent)' if is_permanent else 'FAILED (will retry)'}")
        self._log_section(f"Error     : {error[:80]}...")
        if is_permanent:
            self._log_section(f"{_log_separator('JOB FAILED PERMANENTLY')}")

    def _log_job_retry(self, job_id: str, retry_count: int, max_retries: int) -> None:
        self._log_section(f"  └─ Retry: {retry_count}/{max_retries} for job {job_id}")

    def _log_job_cancelled(self, job_id: str) -> None:
        self._log_section(f"Job ID: {job_id} | Status: CANCELLED")
        self._log_section(f"{_log_separator('JOB CANCELLED')}")

    def _is_job_cancelled(self, job_id: str) -> bool:
        job = self.job_manager.get_job(job_id)
        if job and job.get("status") == JobStatus.CANCELLED.value:
            return True
        return False

    async def process_job(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = job["id"]
        concept = job["concept"]
        iterations = job.get("iterations", 3)
        pipeline = job.get("pipeline", "standard")

        self._log_heartbeat(state="PROCESSING", details="loading job details")

        if self._is_job_cancelled(job_id):
            self._log_job_cancelled(job_id)
            self.current_job_id = None
            self._log_heartbeat(state="CANCELLED_BEFORE_START")
            return {"job_id": job_id, "status": "cancelled"}

        self._log_job_start(job_id, concept, pipeline)
        self._log_heartbeat(state="PROCESSING", details="initializing pipeline")

        start_time = datetime.now(UTC)

        try:
            from simulate_decision.core import (
                PipelineTemplates,
                StoryPipelineTemplates,
                get_config,
            )

            config = get_config()
            config.configure_dspy()

            template = PipelineTemplates.get(pipeline)
            if template:
                pipeline_config = PipelineTemplates.create_config(pipeline, max_iterations=iterations)
            else:
                template = StoryPipelineTemplates.get(pipeline)
                if template:
                    pipeline_config = StoryPipelineTemplates.create_config(pipeline, max_iterations=iterations)
                else:
                    raise ValueError(f"Unknown template: {pipeline}")

            from simulate_decision.core import SimulateDecision
            engine = SimulateDecision(config=config, pipeline_config=pipeline_config)

            def progress_callback(stage: str, status: str):
                elapsed = (datetime.now(UTC) - start_time).total_seconds()
                self._log_job_progress(stage, status, int(elapsed))
                self.job_manager.update_job_status(
                    job_id,
                    JobStatus.RUNNING,
                    progress={"current_stage": stage, "status": status, "elapsed_seconds": int(elapsed)}
                )

            self._log_heartbeat(state="PROCESSING", details="running engine")
            result = await asyncio.get_event_loop().run_in_executor(
                None, engine, concept
            )

            result_data = {
                "status": result.get("status"),
                "iterations": result.get("iterations"),
                "purified_atoms": result.get("purified_atoms"),
                "blueprint": result.get("blueprint"),
                "strategy_history": result.get("strategy_history", []),
                "metadata": result.get("metadata", {}),
                "pipeline": pipeline,
                "completed_at": _utcnow_iso(),
            }

            result_file = RESULTS_DIR / f"{job_id}.json"
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)

            self.job_manager.update_job_status(
                job_id,
                JobStatus.SUCCESS,
                result=json.dumps(result_data),
            )

            self._log_job_success(job_id, iterations)
            self._log_heartbeat(state="FREE", details="job completed successfully")

            return {"job_id": job_id, "status": "success", "result": result_data}

        except Exception as e:
            logger.error(f"[Worker-{self.worker_id:02d}] {' '*2}Exception: {e}")

            retry_count = self.job_manager.increment_retry(job_id)
            max_retries = job.get("max_retries", self.max_retries)

            if retry_count >= max_retries:
                self.job_manager.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error=str(e),
                )
                self._log_job_failed(job_id, str(e), is_permanent=True)
                self._log_heartbeat(state="FREE", details="job failed permanently")
                return {"job_id": job_id, "status": "failed", "error": str(e)}

            self._log_job_retry(job_id, retry_count, max_retries)
            self._log_heartbeat(state="FREE", details="job failed, will retry")

            return {"job_id": job_id, "status": "retrying", "retry_count": retry_count}

    async def run(self) -> None:
        logger.info(f"[Worker-{self.worker_id:02d}] {' '*2}{_log_separator('WORKER STARTED')}")
        self.running = True
        self._log_heartbeat(state="INITIALIZING")
        last_heartbeat = datetime.now(UTC)

        while self.running:
            try:
                self._log_heartbeat(state="FREE", details="ready to take new simulation job")
                self._log_heartbeat(state="POLLING", details="looking for pending jobs")
                pending_jobs = self.job_manager.get_pending_jobs(limit=1)

                if not pending_jobs:
                    elapsed = (datetime.now(UTC) - last_heartbeat).total_seconds()
                    if elapsed >= self._heartbeat_interval:
                        self._log_heartbeat(state="IDLE", details=f"no pending jobs, heartbeat (last: {int(elapsed)}s ago)")
                        last_heartbeat = datetime.now(UTC)
                    await asyncio.sleep(1)
                    continue

                job = pending_jobs[0]
                job_id = job["id"]

                self._log_heartbeat(state="FOUND_JOB", details=f"job_id={job_id}")

                if self._is_job_cancelled(job_id):
                    logger.info(f"[Worker-{self.worker_id:02d}] Skipping cancelled job {job_id}")
                    self.current_job_id = None
                    self._log_heartbeat(state="SKIP_CANCELLED")
                    last_heartbeat = datetime.now(UTC)
                    continue

                if not self.job_manager.try_claim_job(job_id, self.worker_id):
                    self._log_heartbeat(state="CONFLICT", details=f"job already claimed by another worker")
                    await asyncio.sleep(1)
                    continue

                self.current_job_id = job_id
                self._log_heartbeat(state="CLAIMED", details=f"job_id={job_id} successfully claimed")
                last_heartbeat = datetime.now(UTC)

                await self.process_job(job)

                self.current_job_id = None
                self._log_heartbeat(state="FREE", details="job completed successfully")
                last_heartbeat = datetime.now(UTC)
            except Exception as e:
                logger.error(f"[Worker-{self.worker_id:02d}] {' '*2}Error in worker loop: {e}")
                self._log_heartbeat(state="ERROR", details=str(e)[:50])
                self.current_job_id = None
                last_heartbeat = datetime.now(UTC)
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"[Worker-{self.worker_id:02d}] {' '*2}Error in worker loop: {e}")
                self._log_heartbeat(state="ERROR", details=str(e)[:50])
                self.current_job_id = None
                last_heartbeat = datetime.now(UTC)
                await asyncio.sleep(5)

        self._log_heartbeat(state="STOPPED")
        logger.info(f"[Worker-{self.worker_id:02d}] {' '*2}{_log_separator('WORKER STOPPED')}")

    def stop(self) -> None:
        self.running = False


async def run_workers(num_workers: int = 2, max_retries: int = 3) -> None:
    workers = [
        Worker(worker_id=i, max_retries=max_retries)
        for i in range(num_workers)
    ]

    tasks = [asyncio.create_task(worker.run()) for worker in workers]

    logger.info(f"{_log_separator('WORKER POOL STARTED')}")
    logger.info(f"  Workers     : {num_workers}")
    logger.info(f"  Max Retries: {max_retries}")
    logger.info(f"{'─'*60}")

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info(f"{_log_separator('SHUTTING DOWN WORKERS')}")
        for worker in workers:
            worker.stop()
        await asyncio.gather(*tasks, return_exceptions=True)
