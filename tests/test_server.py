"""Tests for SimulateDecision Server."""

import json
import pytest
from fastapi.testclient import TestClient

from simulate_decision.server.api import app
from simulate_decision.server.job_manager import JobManager

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_jobs():
    manager = JobManager.get_instance()
    manager.clear_all_jobs()
    yield
    manager.clear_all_jobs()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_create_job():
    response = client.post(
        "/analyze",
        json={"concept": "Test concept", "iterations": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["concept"] == "Test concept"
    assert data["status"] == "pending"
    assert data["iterations"] == 2


def test_list_jobs():
    client.post("/analyze", json={"concept": "Job 1"})
    client.post("/analyze", json={"concept": "Job 2"})

    response = client.get("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_job():
    create_response = client.post(
        "/analyze",
        json={"concept": "Get test"},
    )
    job_id = create_response.json()["id"]

    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["concept"] == "Get test"


def test_get_failed_job_details_exposes_result_when_available():
    from simulate_decision.server.job_manager import JobManager, JobStatus
    from simulate_decision.server.worker import RESULTS_DIR

    manager = JobManager.get_instance()
    job = manager.create_job("Failed job detail test case")
    # First set to RUNNING, then to FAILED
    manager.update_job_status(job["id"], JobStatus.RUNNING)
    manager.update_job_status(
        job["id"],
        JobStatus.FAILED,
        result=json.dumps({
            "status": "FAILURE",
            "iterations": 2,
            "blueprint": None,
            "purified_atoms": None,
            "strategy_history": [],
            "metadata": {
                "concept": job["concept"],
                "converged": False,
                "total_iterations": 2,
                "pipeline_name": "standard",
                "stages_executed": ["deconstruct", "verify"],
            },
            "error": "Policy could not converge on stable axioms.",
        }),
        error="Policy could not converge on stable axioms.",
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_file = RESULTS_DIR / f"{job['id']}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "status": "FAILURE",
            "iterations": 2,
            "blueprint": None,
            "purified_atoms": None,
            "strategy_history": [],
            "metadata": {
                "concept": job["concept"],
                "converged": False,
                "total_iterations": 2,
                "pipeline_name": "standard",
                "stages_executed": ["deconstruct", "verify"],
            },
            "error": "Policy could not converge on stable axioms.",
        }, f)

    response = client.get(f"/jobs/{job['id']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error"] == "Policy could not converge on stable axioms."
    assert payload["result"]["status"] == "FAILURE"
    assert payload["result"]["metadata"]["converged"] is False


def test_load_result_falls_back_to_job_record():
    from simulate_decision.server.analysis import load_result
    from simulate_decision.server.job_manager import JobManager, JobStatus

    manager = JobManager.get_instance()
    job = manager.create_job("Fallback result record test")
    # First set to RUNNING, then to FAILED
    manager.update_job_status(job["id"], JobStatus.RUNNING)
    manager.update_job_status(
        job["id"],
        JobStatus.FAILED,
        result=json.dumps({
            "status": "FAILURE",
            "iterations": 1,
            "purified_atoms": None,
            "blueprint": None,
            "strategy_history": [],
            "metadata": {
                "concept": job["concept"],
                "converged": False,
                "total_iterations": 1,
                "pipeline_name": "standard",
                "stages_executed": ["deconstruct", "verify"],
            },
            "error": "No file present, fallback to job record.",
        }),
        error="No file present, fallback to job record.",
    )

    result = load_result(job["id"])
    assert result is not None
    assert result["status"] == "FAILURE"
    assert result["metadata"]["converged"] is False


def test_get_job_not_found():
    response = client.get("/jobs/nonexistent-id")
    assert response.status_code == 404


def test_delete_job():
    create_response = client.post(
        "/analyze",
        json={"concept": "Delete test"},
    )
    job_id = create_response.json()["id"]

    response = client.delete(f"/jobs/{job_id}")
    assert response.status_code == 200

    get_response = client.get(f"/jobs/{job_id}")
    assert get_response.status_code == 404


def test_clear_all_jobs():
    client.post("/analyze", json={"concept": "Job 1"})
    client.post("/analyze", json={"concept": "Job 2"})

    response = client.delete("/jobs")
    assert response.status_code == 200

    list_response = client.get("/jobs")
    assert list_response.json() == []


def test_get_stats():
    client.post("/analyze", json={"concept": "Stats test 1"})
    client.post("/analyze", json={"concept": "Stats test 2"})

    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["pending"] == 2
