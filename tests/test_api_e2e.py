"""E2E Tests for FastAPI Server."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from simulate_decision.server.job_manager import JobManager, JobStatus

DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_DIR = DATA_DIR / "results"


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create test client."""
    from simulate_decision.server.api import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_all_data() -> None:
    """Clean all data before each test."""
    manager = JobManager.get_instance()
    manager.clear_all_jobs()

    if RESULTS_DIR.exists():
        for file in RESULTS_DIR.glob("*.json"):
            file.unlink()

    yield

    manager.clear_all_jobs()
    if RESULTS_DIR.exists():
        for file in RESULTS_DIR.glob("*.json"):
            file.unlink()


class TestHealthEndpoint:
    """Tests for health endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        """Test health check returns healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestAnalyzeEndpoint:
    """Tests for analyze endpoint."""

    def test_create_job_success(self, client: TestClient) -> None:
        """Test creating a job successfully."""
        response = client.post(
            "/analyze",
            json={"concept": "Test concept", "iterations": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["concept"] == "Test concept"
        assert data["status"] == "pending"
        assert data["iterations"] == 2

    def test_create_job_with_defaults(self, client: TestClient) -> None:
        """Test creating job with default values."""
        response = client.post("/analyze", json={"concept": "Default test"})
        assert response.status_code == 200
        data = response.json()
        assert data["iterations"] == 3
        assert data["max_retries"] == 3

    def test_create_job_custom_max_retries(self, client: TestClient) -> None:
        """Test creating job with custom max retries."""
        response = client.post(
            "/analyze",
            json={"concept": "Retry test", "max_retries": 5},
        )
        assert response.status_code == 200
        assert response.json()["max_retries"] == 5

    def test_create_job_empty_concept(self, client: TestClient) -> None:
        """Test creating job with empty concept."""
        response = client.post("/analyze", json={"concept": ""})
        assert response.status_code in [200, 422]

    def test_create_job_missing_concept(self, client: TestClient) -> None:
        """Test creating job without concept."""
        response = client.post("/analyze", json={})
        assert response.status_code in [200, 422]

    def test_create_job_invalid_iterations(self, client: TestClient) -> None:
        """Test creating job with invalid iterations."""
        response = client.post(
            "/analyze",
            json={"concept": "Test", "iterations": -1},
        )
        assert response.status_code in [200, 422]


class TestJobsEndpoints:
    """Tests for jobs endpoints."""

    def test_list_jobs_empty(self, client: TestClient) -> None:
        """Test listing jobs when empty."""
        response = client.get("/jobs")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_jobs(self, client: TestClient) -> None:
        """Test listing jobs."""
        client.post("/analyze", json={"concept": "Job 1"})
        client.post("/analyze", json={"concept": "Job 2"})

        response = client.get("/jobs")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_jobs_with_status_filter(self, client: TestClient) -> None:
        """Test listing jobs with status filter."""
        manager = JobManager.get_instance()
        job1 = manager.create_job("Test")
        job2 = manager.create_job("Test 2")
        manager.update_job_status(job1["id"], JobStatus.SUCCESS)

        response = client.get("/jobs", params={"status": "success"})
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["status"] == "success"

    def test_list_jobs_pagination(self, client: TestClient) -> None:
        """Test listing jobs with pagination."""
        for i in range(5):
            client.post("/analyze", json={"concept": f"Job {i}"})

        response = client.get("/jobs", params={"limit": 2, "offset": 0})
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_get_job_success(self, client: TestClient) -> None:
        """Test getting a job."""
        create_response = client.post("/analyze", json={"concept": "Get test"})
        job_id = create_response.json()["id"]

        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["concept"] == "Get test"

    def test_get_job_with_result(self, client: TestClient) -> None:
        """Test getting a job with result."""
        create_response = client.post("/analyze", json={"concept": "Result test"})
        job_id = create_response.json()["id"]

        manager = JobManager.get_instance()
        manager.update_job_status(
            job_id,
            JobStatus.SUCCESS,
            result=json.dumps({"status": "SUCCESS", "iterations": 1}),
        )

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(RESULTS_DIR / f"{job_id}.json", "w") as f:
            json.dump({"status": "SUCCESS", "iterations": 1}, f)

        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["result"] is not None

    def test_get_job_not_found(self, client: TestClient) -> None:
        """Test getting non-existent job."""
        response = client.get("/jobs/nonexistent-id")
        assert response.status_code == 404

    def test_delete_job_success(self, client: TestClient) -> None:
        """Test deleting a job."""
        create_response = client.post("/analyze", json={"concept": "Delete test"})
        job_id = create_response.json()["id"]

        response = client.delete(f"/jobs/{job_id}")
        assert response.status_code == 200

        get_response = client.get(f"/jobs/{job_id}")
        assert get_response.status_code == 404

    def test_delete_job_not_found(self, client: TestClient) -> None:
        """Test deleting non-existent job."""
        response = client.delete("/jobs/nonexistent-id")
        assert response.status_code == 404

    def test_clear_all_jobs(self, client: TestClient) -> None:
        """Test clearing all jobs."""
        client.post("/analyze", json={"concept": "Job 1"})
        client.post("/analyze", json={"concept": "Job 2"})

        response = client.delete("/jobs")
        assert response.status_code == 200

        list_response = client.get("/jobs")
        assert list_response.json() == []


class TestStatsEndpoint:
    """Tests for stats endpoint."""

    def test_get_stats_empty(self, client: TestClient) -> None:
        """Test getting stats when empty."""
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_get_stats(self, client: TestClient) -> None:
        """Test getting stats."""
        client.post("/analyze", json={"concept": "Job 1"})
        client.post("/analyze", json={"concept": "Job 2"})

        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["pending"] == 2


class TestResultsEndpoint:
    """Tests for results endpoint."""

    def test_get_result_success(self, client: TestClient) -> None:
        """Test getting a result."""
        create_response = client.post("/analyze", json={"concept": "Result test"})
        job_id = create_response.json()["id"]

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        result_data = {"status": "SUCCESS", "iterations": 1, "blueprint": "Test blueprint"}
        with open(RESULTS_DIR / f"{job_id}.json", "w") as f:
            json.dump(result_data, f)

        response = client.get(f"/results/{job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "SUCCESS"

    def test_get_result_not_found(self, client: TestClient) -> None:
        """Test getting non-existent result."""
        response = client.get("/results/nonexistent-id")
        assert response.status_code == 404
