"""Tests for SimulateDecision Server."""

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
