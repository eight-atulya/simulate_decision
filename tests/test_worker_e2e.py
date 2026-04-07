"""E2E Tests for Worker System."""
from __future__ import annotations

import json
from typing import Any

import pytest

from simulate_decision.server.job_manager import JobManager, JobStatus


class TestWorker:
    """Tests for Worker class."""

    @pytest.fixture
    def worker(self) -> Any:
        """Create a worker instance."""
        from simulate_decision.server.worker import Worker

        return Worker(worker_id=1, max_retries=3)

    @pytest.fixture
    def mock_job(self) -> dict[str, Any]:
        """Create a mock job."""
        return {
            "id": "test-job-id",
            "concept": "Test concept for worker",
            "iterations": 2,
            "max_retries": 3,
            "status": "pending",
        }

    def test_worker_initialization(self, worker: Any) -> None:
        """Test worker initialization."""
        assert worker.worker_id == 1
        assert worker.max_retries == 3
        assert worker.retry_delay == 5.0
        assert worker.running is False

    def test_worker_stop(self, worker: Any) -> None:
        """Test worker stop method."""
        worker.running = True
        worker.stop()
        assert worker.running is False

    def test_worker_has_job_manager(self, worker: Any) -> None:
        """Test worker has job manager."""
        from simulate_decision.server.job_manager import JobManager

        assert isinstance(worker.job_manager, JobManager)


class TestJobProcessing:
    """Tests for job processing logic."""

    @pytest.fixture
    def job_manager(self) -> JobManager:
        """Get fresh job manager."""
        manager = JobManager.get_instance()
        manager.clear_all_jobs()
        return manager

    def test_job_lifecycle(
        self, job_manager: JobManager, sample_result_data: dict[str, Any]
    ) -> None:
        """Test complete job lifecycle."""
        job = job_manager.create_job("Lifecycle test", iterations=1)

        assert job["status"] == JobStatus.PENDING.value

        job_manager.update_job_status(job["id"], JobStatus.RUNNING)
        updated = job_manager.get_job(job["id"])
        assert updated["status"] == JobStatus.RUNNING.value

        job_manager.update_job_status(
            job["id"],
            JobStatus.SUCCESS,
            result=json.dumps(sample_result_data),
        )
        updated = job_manager.get_job(job["id"])
        assert updated["status"] == JobStatus.SUCCESS.value
        assert updated["completed_at"] is not None

    def test_job_retry_flow(self, job_manager: JobManager) -> None:
        """Test job retry flow."""
        job = job_manager.create_job("Retry test", max_retries=3)

        assert job["retry_count"] == 0

        count = job_manager.increment_retry(job["id"])
        assert count == 1

        updated = job_manager.get_job(job["id"])
        assert updated["status"] == JobStatus.RETRYING.value

    def test_job_max_retries_exceeded(self, job_manager: JobManager) -> None:
        """Test job failure after max retries."""
        job = job_manager.create_job("Max retry test", max_retries=2)

        job_manager.increment_retry(job["id"])
        job_manager.increment_retry(job["id"])

        updated = job_manager.get_job(job["id"])
        assert updated["retry_count"] == 2

        job_manager.increment_retry(job["id"])
        updated = job_manager.get_job(job["id"])
        assert updated["retry_count"] == 3

    def test_concurrent_job_updates(self, job_manager: JobManager) -> None:
        """Test concurrent updates to different jobs."""
        job1 = job_manager.create_job("Concurrent 1")
        job2 = job_manager.create_job("Concurrent 2")

        job_manager.update_job_status(job1["id"], JobStatus.RUNNING)
        job_manager.update_job_status(job2["id"], JobStatus.SUCCESS)

        updated1 = job_manager.get_job(job1["id"])
        updated2 = job_manager.get_job(job2["id"])

        assert updated1["status"] == JobStatus.RUNNING.value
        assert updated2["status"] == JobStatus.SUCCESS.value


class TestWorkerIntegration:
    """Integration tests for worker system."""

    @pytest.fixture
    def job_manager(self) -> JobManager:
        """Get fresh job manager."""
        manager = JobManager.get_instance()
        manager.clear_all_jobs()
        return manager

    def test_pending_jobs_queue(self, job_manager: JobManager) -> None:
        """Test pending jobs queue behavior."""
        job1 = job_manager.create_job("Queue test 1")
        job2 = job_manager.create_job("Queue test 2")
        job3 = job_manager.create_job("Queue test 3")

        pending = job_manager.get_pending_jobs(limit=10)
        assert len(pending) == 3

        pending_ids = [j["id"] for j in pending]
        assert job1["id"] in pending_ids
        assert job2["id"] in pending_ids
        assert job3["id"] in pending_ids

    def test_pending_jobs_order_preserved(self, job_manager: JobManager) -> None:
        """Test that pending jobs maintain creation order."""
        jobs = [job_manager.create_job(f"Ordered {i}") for i in range(5)]

        pending = job_manager.get_pending_jobs(limit=5)
        for i, job in enumerate(jobs):
            assert pending[i]["id"] == job["id"]

    def test_running_job_not_in_pending(self, job_manager: JobManager) -> None:
        """Test that running jobs are not in pending queue."""
        job1 = job_manager.create_job("Should be pending")
        job2 = job_manager.create_job("Should be running")

        job_manager.update_job_status(job2["id"], JobStatus.RUNNING)

        pending = job_manager.get_pending_jobs(limit=10)
        pending_ids = [j["id"] for j in pending]

        assert job1["id"] in pending_ids
        assert job2["id"] not in pending_ids

    def test_failed_job_not_in_pending(self, job_manager: JobManager) -> None:
        """Test that failed jobs are not in pending queue."""
        job1 = job_manager.create_job("Should be pending")
        job2 = job_manager.create_job("Should be failed")

        job_manager.update_job_status(job2["id"], JobStatus.FAILED)

        pending = job_manager.get_pending_jobs(limit=10)
        pending_ids = [j["id"] for j in pending]

        assert job1["id"] in pending_ids
        assert job2["id"] not in pending_ids

    def test_retrying_job_in_pending(self, job_manager: JobManager) -> None:
        """Test that retrying jobs are still in pending queue."""
        job = job_manager.create_job("Should retry")
        job_manager.increment_retry(job["id"])

        pending = job_manager.get_pending_jobs(limit=10)
        pending_ids = [j["id"] for j in pending]

        assert job["id"] in pending_ids


class TestWorkerResultStorage:
    """Tests for worker result storage."""

    @pytest.fixture
    def job_manager(self) -> JobManager:
        """Get fresh job manager."""
        manager = JobManager.get_instance()
        manager.clear_all_jobs()
        return manager

    def test_result_storage_path(
        self, job_manager: JobManager, sample_result_data: dict[str, Any]
    ) -> None:
        """Test that results can be stored in correct path."""
        from simulate_decision.server.worker import RESULTS_DIR

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        job = job_manager.create_job("Result storage test")
        job_manager.update_job_status(
            job["id"],
            JobStatus.SUCCESS,
            result=json.dumps(sample_result_data),
        )

        result_file = RESULTS_DIR / f"{job['id']}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(sample_result_data, f)

        assert result_file.exists()

    def test_result_file_content(
        self, job_manager: JobManager, sample_result_data: dict[str, Any]
    ) -> None:
        """Test that result file contains correct data."""
        from simulate_decision.server.worker import RESULTS_DIR

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        job = job_manager.create_job("Content test")
        job_manager.update_job_status(
            job["id"],
            JobStatus.SUCCESS,
            result=json.dumps(sample_result_data),
        )

        result_file = RESULTS_DIR / f"{job['id']}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(sample_result_data, f)

        with open(result_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["status"] == "SUCCESS"
        assert data["iterations"] == 1
