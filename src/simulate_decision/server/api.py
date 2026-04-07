from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from simulate_decision.server.job_manager import JobManager, JobStatus

app = FastAPI(
    title="SimulateDecision API",
    description="""# SimulateDecision API

Decision Simulator - AI-Powered Decision Analysis Engine

## Features
- **Job Management**: Submit and track analysis jobs
- **Health Check**: Monitor server status
- **Statistics**: View job metrics

## Authentication
Currently no authentication required (dev mode).
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR = DATA_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


class AnalyzeRequest(BaseModel):
    concept: str
    iterations: int = 3
    max_retries: int = 3
    pipeline: str = "standard"


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []
    systemPrompt: str | None = None


@app.post(
    "/chat/stream",
    tags=["Chat"],
    summary="Chat with AI (Streaming)",
    description="Send a message and receive streaming response from the AI.",
)
async def chat_stream(request: ChatRequest):
    """Chat with AI using streaming response."""
    import requests

    from simulate_decision.core import get_config

    config = get_config()
    url = f"{config.lm_studio_url}/chat/completions"
    model_name = config.model_name.replace("lmstudio/", "")

    messages = []
    if request.systemPrompt:
        messages.append({"role": "system", "content": request.systemPrompt})
    messages.extend(request.history)
    messages.append({"role": "user", "content": request.message})

    def generate():
        try:
            response = requests.post(
                url,
                json={
                    "model": model_name,
                    "messages": messages,
                    "max_tokens": 2048,
                    "stream": True
                },
                headers={"Content-Type": "application/json"},
                timeout=120,
                stream=True
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data.strip() == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if content:
                                yield f"data: {json.dumps({'content': content})}\n\n"
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(generate(), media_type="text/event-stream")


class JobResponse(BaseModel):
    id: str
    concept: str
    status: str
    iterations: int
    retry_count: int
    max_retries: int
    created_at: str
    updated_at: str
    completed_at: str | None
    progress: dict[str, Any] | None = None


class JobDetailResponse(BaseModel):
    id: str
    concept: str
    status: str
    iterations: int
    retry_count: int
    max_retries: int
    created_at: str
    updated_at: str
    completed_at: str | None
    result: dict[str, Any] | None
    error: str | None
    progress: dict[str, Any] | None = None


@app.get(
    "/health",
    tags=["Health"],
    summary="Health Check",
    description="Check if the API server is running and healthy.",
)
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.post(
    "/analyze",
    response_model=JobResponse,
    tags=["Jobs"],
    summary="Submit Analysis Job",
    description="""Submit a new concept for analysis using the SimulateDecision cognitive processing system.

The job will be queued and processed asynchronously by workers.""",
)
async def analyze(request: AnalyzeRequest) -> JobResponse:
    manager = JobManager.get_instance()
    job = manager.create_job(
        concept=request.concept,
        iterations=request.iterations,
        max_retries=request.max_retries,
        pipeline=request.pipeline,
    )
    return JobResponse(**job)


@app.get(
    "/jobs",
    response_model=list[JobResponse],
    tags=["Jobs"],
    summary="List Jobs",
    description="List all jobs with optional filtering by status.",
)
async def list_jobs(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[JobResponse]:
    manager = JobManager.get_instance()
    job_status = JobStatus(status) if status else None
    jobs = manager.list_jobs(status=job_status, limit=limit, offset=offset)
    return [JobResponse(**job) for job in jobs]


@app.get(
    "/jobs/{job_id}",
    response_model=JobDetailResponse,
    tags=["Jobs"],
    summary="Get Job Details",
    description="Get detailed information about a specific job, including results if completed.",
)
async def get_job(job_id: str) -> JobDetailResponse:
    manager = JobManager.get_instance()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result_data = None
    if job.get("status") == JobStatus.SUCCESS.value:
        result_file = RESULTS_DIR / f"{job_id}.json"
        if result_file.exists():
            with open(result_file, encoding="utf-8") as f:
                result_data = json.load(f)

    return JobDetailResponse(
        **{**job, "result": result_data}
    )


@app.delete(
    "/jobs/{job_id}",
    tags=["Jobs"],
    summary="Delete Job",
    description="Delete a specific job and its results.",
)
async def delete_job(job_id: str) -> dict[str, str]:
    manager = JobManager.get_instance()
    deleted = manager.delete_job(job_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")

    result_file = RESULTS_DIR / f"{job_id}.json"
    if result_file.exists():
        result_file.unlink()

    return {"message": "Job deleted"}


@app.post(
    "/jobs/{job_id}/cancel",
    tags=["Jobs"],
    summary="Cancel Job",
    description="Cancel a running or pending job.",
)
async def cancel_job(job_id: str) -> dict[str, str]:
    manager = JobManager.get_instance()
    cancelled = manager.cancel_job(job_id)

    if not cancelled:
        raise HTTPException(status_code=404, detail="Job not found or cannot be cancelled")

    return {"message": "Job cancelled"}


@app.delete(
    "/jobs",
    tags=["Jobs"],
    summary="Clear All Jobs",
    description="Delete all jobs and their results. Use with caution!",
)
async def clear_all_jobs() -> dict[str, str]:
    manager = JobManager.get_instance()
    manager.clear_all_jobs()

    for result_file in RESULTS_DIR.glob("*.json"):
        result_file.unlink()

    return {"message": "All jobs cleared"}


@app.get(
    "/stats",
    tags=["Statistics"],
    summary="Get Statistics",
    description="Get job statistics including total, pending, running, success, and failed counts.",
)
async def get_stats() -> dict[str, Any]:
    manager = JobManager.get_instance()
    return manager.get_stats()


@app.get(
    "/results/{job_id}",
    tags=["Results"],
    summary="Get Job Result",
    description="Get the analysis result for a completed job.",
)
async def get_result(job_id: str) -> dict[str, Any]:
    result_file = RESULTS_DIR / f"{job_id}.json"

    if not result_file.exists():
        manager = JobManager.get_instance()
        job = manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=404, detail="Result not found")

    with open(result_file, encoding="utf-8") as f:
        return json.load(f)
