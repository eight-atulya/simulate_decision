"""Root conftest - Shared fixtures for all tests."""
from __future__ import annotations

import json
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

DATA_DIR = ROOT_DIR / "data"
JOBS_FILE = DATA_DIR / "jobs.json"
RESULTS_DIR = DATA_DIR / "results"


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment() -> None:
    """Setup test environment before any tests run."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True)
def clean_data_files() -> Generator[None, None, None]:
    """Clean data files before each test."""
    if JOBS_FILE.exists():
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

    if RESULTS_DIR.exists():
        for file in RESULTS_DIR.glob("*.json"):
            file.unlink()

    yield

    if JOBS_FILE.exists():
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

    if RESULTS_DIR.exists():
        for file in RESULTS_DIR.glob("*.json"):
            file.unlink()


@pytest.fixture
def sample_concept() -> str:
    """Sample concept for testing."""
    return "The concept of Justice"


@pytest.fixture
def sample_job_data() -> dict:
    """Sample job data for testing."""
    return {
        "concept": "What is consciousness?",
        "iterations": 2,
        "max_retries": 2,
    }


@pytest.fixture
def sample_result_data() -> dict:
    """Sample result data for testing."""
    return {
        "status": "SUCCESS",
        "iterations": 1,
        "purified_atoms": "1. Fairness\n2. Impartiality\n3. Law application",
        "blueprint": "A just system applies rules equally to all parties.",
        "strategy_history": [
            {
                "iteration": 1,
                "strategy": "Initial strategy",
                "atoms_count": 5,
                "axioms_count": 3,
            }
        ],
    }
