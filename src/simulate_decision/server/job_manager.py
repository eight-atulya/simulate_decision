from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
JOBS_FILE = DATA_DIR / "jobs.json"


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _log_prefix() -> str:
    return f"[JobManager] "


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class JobManager:
    _instance: JobManager | None = None

    def __init__(self) -> None:
        self.jobs_file = JOBS_FILE

    @classmethod
    def get_instance(cls) -> JobManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_jobs(self) -> dict[str, dict[str, Any]]:
        if not self.jobs_file.exists():
            return {}
        try:
            with open(self.jobs_file, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_jobs(self, jobs: dict[str, dict[str, Any]]) -> None:
        import tempfile
        import os
        
        # Atomic write: write to temp file then rename
        temp_fd, temp_path = tempfile.mkstemp(dir=self.jobs_file.parent, suffix='.tmp')
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.jobs_file)
        except Exception:
            os.unlink(temp_path)
            raise

    def create_job(
        self,
        concept: str,
        iterations: int = 3,
        max_retries: int = 3,
        pipeline: str = "standard",
    ) -> dict[str, Any]:
        job_id = str(uuid.uuid4())
        now = _utcnow_iso()

        job = {
            "id": job_id,
            "concept": concept,
            "status": JobStatus.PENDING.value,
            "iterations": iterations,
            "max_retries": max_retries,
            "pipeline": pipeline,
            "retry_count": 0,
            "result": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }

        jobs = self._load_jobs()
        jobs[job_id] = job
        self._save_jobs(jobs)

        logger.info(f"{_log_prefix()}{'─'*50}")
        logger.info(f"{_log_prefix()}  NEW JOB CREATED")
        logger.info(f"{_log_prefix()}    ├─ Job ID    : {job_id}")
        logger.info(f"{_log_prefix()}    ├─ Pipeline  : {pipeline}")
        logger.info(f"{_log_prefix()}    ├─ Iterations: {iterations}")
        logger.info(f"{_log_prefix()}    └─ Concept   : {concept[:50]}...")

        return job

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        jobs = self._load_jobs()
        return jobs.get(job_id)

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        result: str | None = None,
        error: str | None = None,
        progress: dict | None = None,
    ) -> None:
        jobs = self._load_jobs()
        if job_id not in jobs:
            return

        current_status = jobs[job_id].get("status")
        
        # Validate status transitions
        valid_transitions = {
            JobStatus.PENDING: [JobStatus.RUNNING, JobStatus.CANCELLED],
            JobStatus.RUNNING: [JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED],
            JobStatus.SUCCESS: [],  # Terminal state
            JobStatus.FAILED: [JobStatus.RETRYING],  # Can retry failed jobs
            JobStatus.RETRYING: [JobStatus.RUNNING, JobStatus.CANCELLED],
            JobStatus.CANCELLED: [],  # Terminal state
        }
        
        if current_status and status not in valid_transitions.get(JobStatus(current_status), []):
            logger.warning(f"{_log_prefix()} Invalid status transition: {current_status} -> {status.value} for job {job_id}")
            return  # Reject invalid transition

        now = _utcnow_iso()
        old_status = jobs[job_id].get("status")
        jobs[job_id]["status"] = status.value
        jobs[job_id]["updated_at"] = now

        if result is not None:
            jobs[job_id]["result"] = result
        if error is not None:
            jobs[job_id]["error"] = error
        if progress is not None:
            jobs[job_id]["progress"] = progress
        if status in (JobStatus.SUCCESS, JobStatus.FAILED):
            jobs[job_id]["completed_at"] = now

        self._save_jobs(jobs)

        logger.info(f"{_log_prefix()}  STATUS UPDATE")
        logger.info(f"{_log_prefix()}    ├─ Job ID     : {job_id}")
        logger.info(f"{_log_prefix()}    ├─ Old Status : {old_status}")
        logger.info(f"{_log_prefix()}    └─ New Status : {status.value}")

    def increment_retry(self, job_id: str) -> int:
        jobs = self._load_jobs()
        if job_id not in jobs:
            return 0

        old_count = jobs[job_id].get("retry_count", 0)
        jobs[job_id]["retry_count"] = old_count + 1
        jobs[job_id]["status"] = JobStatus.RETRYING.value
        jobs[job_id]["updated_at"] = _utcnow_iso()
        self._save_jobs(jobs)

        logger.info(f"{_log_prefix()}  RETRY INCREMENTED")
        logger.info(f"{_log_prefix()}    ├─ Job ID      : {job_id}")
        logger.info(f"{_log_prefix()}    ├─ Old Count   : {old_count}")
        logger.info(f"{_log_prefix()}    └─ New Count   : {old_count + 1}")

        return old_count + 1

    def try_claim_job(self, job_id: str, worker_id: int) -> bool:
        jobs = self._load_jobs()
        if job_id not in jobs:
            logger.warning(f"{_log_prefix()}  JOB NOT FOUND: {job_id}")
            return False

        job = jobs[job_id]
        current_status = job.get("status")

        if current_status in (JobStatus.PENDING.value, JobStatus.RETRYING.value):
            job["status"] = JobStatus.RUNNING.value
            job["worker_id"] = worker_id
            job["updated_at"] = _utcnow_iso()
            self._save_jobs(jobs)

            logger.info(f"{_log_prefix()}  JOB CLAIMED")
            logger.info(f"{_log_prefix()}    ├─ Job ID     : {job_id}")
            logger.info(f"{_log_prefix()}    ├─ Worker ID  : {worker_id}")
            logger.info(f"{_log_prefix()}    └─ Old Status: {current_status} -> running")

            return True

        logger.warning(f"{_log_prefix()}  CLAIM FAILED")
        logger.info(f"{_log_prefix()}    ├─ Job ID     : {job_id}")
        logger.info(f"{_log_prefix()}    ├─ Worker ID  : {worker_id}")
        logger.info(f"{_log_prefix()}    └─ Reason     : already in '{current_status}' state")

        return False

    def list_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        jobs = self._load_jobs()
        result = list(jobs.values())

        if status:
            result = [j for j in result if j.get("status") == status.value]

        result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return result[offset : offset + limit]

    def get_pending_jobs(self, limit: int = 10) -> list[dict[str, Any]]:
        jobs = self._load_jobs()
        total_count = len(jobs)

        status_summary = {}
        for j in jobs.values():
            s = j.get("status", "unknown")
            status_summary[s] = status_summary.get(s, 0) + 1

        logger.info(f"{_log_prefix()}  SCANNING FOR PENDING JOBS")
        logger.info(f"{_log_prefix()}    ├─ Total Jobs    : {total_count}")
        logger.info(f"{_log_prefix()}    │   Status Breakdown:")
        for s, count in sorted(status_summary.items()):
            logger.info(f"{_log_prefix()}    │     ├─ {s:12s}: {count}")
        logger.info(f"{_log_prefix()}    │   ")
        pending = [
            j
            for j in jobs.values()
            if j.get("status") in (JobStatus.PENDING.value, JobStatus.RETRYING.value)
        ]
        
        logger.info(f"{_log_prefix()}    └─ Found: {len(pending)} pending/retrying jobs")
        
        pending.sort(key=lambda x: x.get("created_at", ""))
        return pending[:limit]

    def delete_job(self, job_id: str) -> bool:
        jobs = self._load_jobs()
        if job_id in jobs:
            del jobs[job_id]
            self._save_jobs(jobs)
            logger.info(f"{_log_prefix()}  JOB DELETED: {job_id}")
            return True
        return False

    def cancel_job(self, job_id: str) -> bool:
        jobs = self._load_jobs()
        if job_id in jobs:
            job = jobs[job_id]
            old_status = job.get("status")
            if job["status"] in (JobStatus.PENDING.value, JobStatus.RUNNING.value, JobStatus.RETRYING.value):
                job["status"] = JobStatus.CANCELLED.value
                job["updated_at"] = _utcnow_iso()
                self._save_jobs(jobs)

                logger.info(f"{_log_prefix()}  JOB CANCELLED")
                logger.info(f"{_log_prefix()}    ├─ Job ID     : {job_id}")
                logger.info(f"{_log_prefix()}    └─ Old Status: {old_status} -> cancelled")

                return True
        return False

    def rerun_job(self, job_id: str) -> dict[str, Any] | None:
        """Create a new job with the same parameters as a failed job"""
        jobs = self._load_jobs()
        if job_id not in jobs:
            return None

        original_job = jobs[job_id]
        if original_job.get("status") != JobStatus.FAILED.value:
            return None  # Only allow rerunning failed jobs

        # Create new job with same parameters
        new_job = self.create_job(
            concept=original_job["concept"],
            iterations=original_job["iterations"],
            max_retries=original_job["max_retries"],
            pipeline=original_job["pipeline"],
        )

        logger.info(f"{_log_prefix()}  JOB RERUN CREATED")
        logger.info(f"{_log_prefix()}    ├─ Original Job: {job_id}")
        logger.info(f"{_log_prefix()}    └─ New Job     : {new_job['id']}")

        return new_job

    def get_stats(self) -> dict[str, Any]:
        jobs = self._load_jobs()
        stats: dict[str, Any] = {"total": len(jobs)}

        status_counts: dict[str, int] = {}
        for job in jobs.values():
            s = job.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        return {**status_counts, **stats}

    def clear_all_jobs(self) -> None:
        self._save_jobs({})
        logger.info(f"{_log_prefix()}  ALL JOBS CLEARED")
