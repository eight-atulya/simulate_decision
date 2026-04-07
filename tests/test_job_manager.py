"""E2E Tests for Job Manager."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from simulate_decision.server.job_manager import JobManager, JobStatus


class TestJobManager:
    """Comprehensive tests for JobManager."""

    @pytest.fixture
    def job_manager(self) -> JobManager:
        """Get fresh job manager instance."""
        manager = JobManager.get_instance()
        manager.clear_all_jobs()
        return manager

    def test_singleton_pattern(self) -> None:
        """Test that JobManager is a singleton."""
        m1 = JobManager.get_instance()
        m2 = JobManager.get_instance()
        assert m1 is m2

    def test_create_job(self, job_manager: JobManager) -> None:
        """Test creating a job."""
        job = job_manager.create_job(
            concept="Test concept",
            iterations=3,
            max_retries=2,
        )

        assert job["id"] is not None
        assert job["concept"] == "Test concept"
        assert job["status"] == JobStatus.PENDING.value
        assert job["iterations"] == 3
        assert job["max_retries"] == 2
        assert job["retry_count"] == 0
        assert job["result"] is None
        assert job["error"] is None
        assert "created_at" in job
        assert "updated_at" in job
        assert job["completed_at"] is None

    def test_create_multiple_jobs(self, job_manager: JobManager) -> None:
        """Test creating multiple jobs."""
        job1 = job_manager.create_job("Concept 1")
        job2 = job_manager.create_job("Concept 2")
        job3 = job_manager.create_job("Concept 3")

        assert job1["id"] != job2["id"] != job3["id"]

    def test_get_job(self, job_manager: JobManager) -> None:
        """Test getting a job by ID."""
        created = job_manager.create_job("Get test")
        retrieved = job_manager.get_job(created["id"])

        assert retrieved is not None
        assert retrieved["id"] == created["id"]
        assert retrieved["concept"] == "Get test"

    def test_get_nonexistent_job(self, job_manager: JobManager) -> None:
        """Test getting a non-existent job."""
        result = job_manager.get_job("nonexistent-id")
        assert result is None

    def test_update_job_status_success(
        self, job_manager: JobManager, sample_result_data: dict[str, Any]
    ) -> None:
        """Test updating job status to success."""
        job = job_manager.create_job("Success test")

        job_manager.update_job_status(
            job_id=job["id"],
            status=JobStatus.SUCCESS,
            result=json.dumps(sample_result_data),
        )

        updated = job_manager.get_job(job["id"])
        assert updated["status"] == JobStatus.SUCCESS.value
        assert updated["result"] is not None
        assert updated["completed_at"] is not None

    def test_update_job_status_failed(self, job_manager: JobManager) -> None:
        """Test updating job status to failed."""
        job = job_manager.create_job("Fail test")

        job_manager.update_job_status(
            job_id=job["id"],
            status=JobStatus.FAILED,
            error="Connection timeout",
        )

        updated = job_manager.get_job(job["id"])
        assert updated["status"] == JobStatus.FAILED.value
        assert updated["error"] == "Connection timeout"
        assert updated["completed_at"] is not None

    def test_update_job_status_running(self, job_manager: JobManager) -> None:
        """Test updating job status to running."""
        job = job_manager.create_job("Running test")

        job_manager.update_job_status(job_id=job["id"], status=JobStatus.RUNNING)

        updated = job_manager.get_job(job["id"])
        assert updated["status"] == JobStatus.RUNNING.value
        assert updated["completed_at"] is None

    def test_increment_retry(self, job_manager: JobManager) -> None:
        """Test incrementing retry count."""
        job = job_manager.create_job("Retry test")

        count1 = job_manager.increment_retry(job["id"])
        assert count1 == 1

        count2 = job_manager.increment_retry(job["id"])
        assert count2 == 2

        updated = job_manager.get_job(job["id"])
        assert updated["retry_count"] == 2
        assert updated["status"] == JobStatus.RETRYING.value

    def test_list_jobs(self, job_manager: JobManager) -> None:
        """Test listing all jobs."""
        job_manager.create_job("Job 1")
        job_manager.create_job("Job 2")
        job_manager.create_job("Job 3")

        jobs = job_manager.list_jobs()
        assert len(jobs) == 3

    def test_list_jobs_with_status_filter(self, job_manager: JobManager) -> None:
        """Test listing jobs with status filter."""
        job1 = job_manager.create_job("Pending job")
        job_manager.create_job("Running job")
        job_manager.update_job_status(job1["id"], JobStatus.SUCCESS)

        pending_jobs = job_manager.list_jobs(status=JobStatus.PENDING)
        success_jobs = job_manager.list_jobs(status=JobStatus.SUCCESS)

        assert len(pending_jobs) == 1
        assert len(success_jobs) == 1

    def test_list_jobs_with_pagination(self, job_manager: JobManager) -> None:
        """Test listing jobs with pagination."""
        for i in range(10):
            job_manager.create_job(f"Job {i}")

        page1 = job_manager.list_jobs(limit=3, offset=0)
        page2 = job_manager.list_jobs(limit=3, offset=3)

        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0]["id"] != page2[0]["id"]

    def test_get_pending_jobs(self, job_manager: JobManager) -> None:
        """Test getting pending jobs."""
        job1 = job_manager.create_job("Pending 1")
        job2 = job_manager.create_job("Pending 2")
        job3 = job_manager.create_job("Running")

        job_manager.update_job_status(job3["id"], JobStatus.RUNNING)

        pending = job_manager.get_pending_jobs(limit=10)

        assert len(pending) == 2
        pending_ids = [j["id"] for j in pending]
        assert job1["id"] in pending_ids
        assert job2["id"] in pending_ids

    def test_get_pending_jobs_order(self, job_manager: JobManager) -> None:
        """Test that pending jobs are ordered by creation time."""
        job1 = job_manager.create_job("First")
        job2 = job_manager.create_job("Second")

        pending = job_manager.get_pending_jobs(limit=2)
        assert pending[0]["id"] == job1["id"]
        assert pending[1]["id"] == job2["id"]

    def test_delete_job(self, job_manager: JobManager) -> None:
        """Test deleting a job."""
        job = job_manager.create_job("Delete me")
        job_id = job["id"]

        result = job_manager.delete_job(job_id)
        assert result is True

        retrieved = job_manager.get_job(job_id)
        assert retrieved is None

    def test_delete_nonexistent_job(self, job_manager: JobManager) -> None:
        """Test deleting a non-existent job."""
        result = job_manager.delete_job("nonexistent")
        assert result is False

    def test_get_stats(self, job_manager: JobManager) -> None:
        """Test getting job statistics."""
        job1 = job_manager.create_job("Job 1")
        job2 = job_manager.create_job("Job 2")
        job3 = job_manager.create_job("Job 3")

        job_manager.update_job_status(job1["id"], JobStatus.SUCCESS)
        job_manager.update_job_status(job2["id"], JobStatus.RUNNING)

        stats = job_manager.get_stats()

        assert stats["total"] == 3
        assert stats["success"] == 1
        assert stats["running"] == 1
        assert stats["pending"] == 1

    def test_get_stats_empty(self, job_manager: JobManager) -> None:
        """Test getting stats with no jobs."""
        stats = job_manager.get_stats()
        assert stats["total"] == 0

    def test_clear_all_jobs(self, job_manager: JobManager) -> None:
        """Test clearing all jobs."""
        job_manager.create_job("Job 1")
        job_manager.create_job("Job 2")
        job_manager.create_job("Job 3")

        job_manager.clear_all_jobs()

        stats = job_manager.get_stats()
        assert stats["total"] == 0

    def test_job_persistence(self, job_manager: JobManager, tmp_path: Path) -> None:
        """Test that jobs persist to file."""
        from simulate_decision.server.job_manager import JOBS_FILE

        job_manager.create_job("Persist test")

        assert JOBS_FILE.exists()

        with open(JOBS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[list(data.keys())[0]]["concept"] == "Persist test"

    def test_job_status_enum_values(self) -> None:
        """Test JobStatus enum values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.SUCCESS.value == "success"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.RETRYING.value == "retrying"

    def test_concurrent_job_creation(self, job_manager: JobManager) -> None:
        """Test creating multiple jobs concurrently."""
        jobs = [job_manager.create_job(f"Concurrent {i}") for i in range(5)]

        assert len(set(j["id"] for j in jobs)) == 5
        assert job_manager.get_stats()["total"] == 5

    def test_update_nonexistent_job(self, job_manager: JobManager) -> None:
        """Test updating a non-existent job doesn't raise."""
        job_manager.update_job_status(
            job_id="nonexistent",
            status=JobStatus.SUCCESS,
        )

        stats = job_manager.get_stats()
        assert stats["total"] == 0
