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

    def _log_heartbeat(self, state: str = "idle", details: str = "") -> None:
        # Reduced frequency and verbosity for production
        pass  # Remove noisy heartbeats

    def _log_section(self, message: str, indent: int = 2) -> None:
        # Only log important events
        if "JOB STARTED" in message or "JOB COMPLETED" in message or "JOB FAILED" in message:
            logger.info(f"[Worker-{self.worker_id:02d}] {' '*indent}{message}")
        else:
            logger.debug(f"[Worker-{self.worker_id:02d}] {' '*indent}{message}")

    def _log_job_start(self, job_id: str, concept: str, pipeline: str) -> None:
        logger.info(f"[Worker-{self.worker_id:02d}] Starting job {job_id} - Pipeline: {pipeline} - Concept: {concept[:50]}...")

    def _log_job_progress(self, stage: str, status: str, elapsed: int) -> None:
        # Log progress less frequently or only on significant changes
        pass  # Remove noisy progress logs

    def _log_job_success(self, job_id: str, iterations: int, duration: float) -> None:
        logger.info(f"[Worker-{self.worker_id:02d}] Job {job_id} completed successfully - Iterations: {iterations} - Duration: {duration:.2f}s")

    def _log_job_failed(self, job_id: str, error: str, is_permanent: bool = False, duration: float = 0.0) -> None:
        logger.info(f"[Worker-{self.worker_id:02d}] Job {job_id} failed - Duration: {duration:.2f}s - Error: {error[:100]}...")

    def _persist_job_result(self, job_id: str, result_data: dict[str, Any]) -> None:
        try:
            result_file = RESULTS_DIR / f"{job_id}.json"
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning(f"[Worker-{self.worker_id:02d}] Failed to persist result for {job_id}: {exc}")

    def _log_job_retry(self, job_id: str, retry_count: int, max_retries: int) -> None:
        logger.info(f"[Worker-{self.worker_id:02d}] Job {job_id} retry {retry_count}/{max_retries}")

    def _log_job_cancelled(self, job_id: str) -> None:
        logger.info(f"[Worker-{self.worker_id:02d}] Job {job_id} cancelled")

    def _is_job_cancelled(self, job_id: str) -> bool:
        job = self.job_manager.get_job(job_id)
        if job and job.get("status") == JobStatus.CANCELLED.value:
            return True
        return False

    def _execute_pipeline(self, config: Any, pipeline_config: Any, concept: str) -> dict[str, Any]:
        config.configure_dspy()
        from simulate_decision.core import SimulateDecision

        engine = SimulateDecision(config=config, pipeline_config=pipeline_config)
        return engine(concept)

    async def process_job(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = job["id"]
        concept = job["concept"]
        iterations = job.get("iterations", 3)
        pipeline = job.get("pipeline", "standard")

        start_time = datetime.now(UTC)

        if self._is_job_cancelled(job_id):
            self._log_job_cancelled(job_id)
            self.current_job_id = None
            return {"job_id": job_id, "status": "cancelled"}

        self._log_job_start(job_id, concept, pipeline)

        try:
            from simulate_decision.core import (
                PipelineTemplates,
                StoryPipelineTemplates,
                get_config,
            )

            config = get_config()

            template = PipelineTemplates.get(pipeline)
            if template:
                pipeline_config = PipelineTemplates.create_config(pipeline, max_iterations=iterations)
            else:
                template = StoryPipelineTemplates.get(pipeline)
                if template:
                    pipeline_config = StoryPipelineTemplates.create_config(pipeline, max_iterations=iterations)
                else:
                    raise ValueError(f"Unknown template: {pipeline}")

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._execute_pipeline,
                config,
                pipeline_config,
                concept,
            )

            duration = (datetime.now(UTC) - start_time).total_seconds()

            result_data = {
                "status": result.get("status"),
                "iterations": result.get("iterations"),
                "purified_atoms": result.get("purified_atoms"),
                "blueprint": result.get("blueprint"),
                "strategy_history": result.get("strategy_history", []),
                "metadata": result.get("metadata", {}),
                "pipeline": pipeline,
                "completed_at": _utcnow_iso(),
                "duration_seconds": duration,
                "error": result.get("error"),
            }

            converged = result.get("metadata", {}).get("converged", False)
            job_status = JobStatus.SUCCESS if result.get("status") == "SUCCESS" else JobStatus.FAILED
            failure_reason = None
            if job_status == JobStatus.FAILED:
                if not converged:
                    failure_reason = f"Not converged after {result.get('iterations', iterations)} iterations"
                else:
                    failure_reason = result.get("error") or "Pipeline failed without a specific error"

                result_data["error"] = failure_reason

            self.job_manager.update_job_status(
                job_id,
                job_status,
                result=json.dumps(result_data),
                error=failure_reason if job_status == JobStatus.FAILED else None,
            )
            self._persist_job_result(job_id, result_data)

            if job_status == JobStatus.SUCCESS:
                self._log_job_success(job_id, iterations, duration)
            else:
                self._log_job_failed(job_id, failure_reason or "Pipeline failed", duration=duration)

            return {"job_id": job_id, "status": result_data["status"], "result": result_data}

        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error(f"[Worker-{self.worker_id:02d}] Exception in job {job_id}: {e}")

            retry_count = self.job_manager.increment_retry(job_id)
            max_retries = job.get("max_retries", self.max_retries)

            if retry_count >= max_retries:
                self.job_manager.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error=str(e),
                )
                self._log_job_failed(job_id, str(e), is_permanent=True, duration=duration)
                return {"job_id": job_id, "status": "failed", "error": str(e)}

            self._log_job_retry(job_id, retry_count, max_retries)
            return {"job_id": job_id, "status": "retrying", "retry_count": retry_count}

    async def run(self) -> None:
        logger.info(f"[Worker-{self.worker_id:02d}] Started")
        self.running = True

        while self.running:
            try:
                pending_jobs = self.job_manager.get_pending_jobs(limit=1)

                if not pending_jobs:
                    await asyncio.sleep(1)
                    continue

                job = pending_jobs[0]
                job_id = job["id"]

                if self._is_job_cancelled(job_id):
                    logger.debug(f"[Worker-{self.worker_id:02d}] Skipping cancelled job {job_id}")
                    continue

                if not self.job_manager.try_claim_job(job_id, self.worker_id):
                    logger.debug(f"[Worker-{self.worker_id:02d}] Failed to claim job {job_id}")
                    await asyncio.sleep(1)
                    continue

                self.current_job_id = job_id
                logger.info(f"[Worker-{self.worker_id:02d}] Claimed job {job_id}")

                await self.process_job(job)

                self.current_job_id = None
                logger.debug(f"[Worker-{self.worker_id:02d}] Freed after job {job_id}")

            except Exception as e:
                logger.error(f"[Worker-{self.worker_id:02d}] Error in worker loop: {e}")
                # Reset current job if there was an error
                if self.current_job_id:
                    # Mark job as failed if it was running
                    try:
                        job = self.job_manager.get_job(self.current_job_id)
                        if job and job.get("status") == JobStatus.RUNNING.value:
                            self.job_manager.update_job_status(
                                self.current_job_id,
                                JobStatus.FAILED,
                                error=f"Worker crashed: {str(e)}",
                            )
                    except Exception as inner_e:
                        logger.error(f"[Worker-{self.worker_id:02d}] Failed to mark job as failed: {inner_e}")
                self.current_job_id = None
                await asyncio.sleep(5)

        logger.info(f"[Worker-{self.worker_id:02d}] Stopped")

    def stop(self) -> None:
        self.running = False


async def run_workers(num_workers: int = 2, max_retries: int = 3) -> None:
    workers = [
        Worker(worker_id=i, max_retries=max_retries)
        for i in range(num_workers)
    ]

    logger.info(f"Starting worker pool with {num_workers} workers, max_retries={max_retries}")

    tasks = [asyncio.create_task(worker.run()) for worker in workers]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Shutting down workers")
        for worker in workers:
            worker.stop()
        await asyncio.gather(*tasks, return_exceptions=True)
