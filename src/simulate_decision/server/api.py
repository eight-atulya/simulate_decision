from __future__ import annotations

import json
import time
import logging
from pathlib import Path
from typing import Any
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from simulate_decision.server.job_manager import JobManager, JobStatus
from simulate_decision.server.analysis import (
    get_hyper_details,
    get_token_efficiency,
    get_lm_interactions,
    get_reasoning_traces,
    get_stage_analysis,
    compare_templates,
    get_lm_call_details,
    load_result,
)

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
    allow_origins=["http://localhost:8501", "http://localhost:3000"],  # Production: specify allowed origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Simple in-memory rate limiting (production: use Redis/external service)
rate_limit_store = {}

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple rate limiting middleware - 100 requests per minute per IP"""
    client_ip = request.client.host
    current_time = time.time()
    window_start = current_time - 60  # 1 minute window

    if client_ip not in rate_limit_store:
        rate_limit_store[client_ip] = []

    # Clean old requests
    rate_limit_store[client_ip] = [
        timestamp for timestamp in rate_limit_store[client_ip]
        if timestamp > window_start
    ]

    if len(rate_limit_store[client_ip]) >= 100:
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded. Try again later."}
        )

    rate_limit_store[client_ip].append(current_time)
    response = await call_next(request)
    return response

@app.get(
    "/metrics",
    tags=["Monitoring"],
    summary="Application Metrics",
    description="Get application performance and usage metrics.",
)
async def get_metrics() -> dict[str, Any]:
    """Get application metrics for monitoring"""
    manager = JobManager.get_instance()
    stats = manager.get_stats()

    # Calculate additional metrics
    total_jobs = stats.get("total_jobs", 0)
    completed_jobs = stats.get("completed_jobs", 0)
    failed_jobs = stats.get("failed_jobs", 0)

    success_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
    failure_rate = (failed_jobs / total_jobs * 100) if total_jobs > 0 else 0

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "jobs": {
            "total": total_jobs,
            "pending": stats.get("pending_jobs", 0),
            "running": stats.get("running_jobs", 0),
            "completed": completed_jobs,
            "failed": failed_jobs,
            "success_rate_percent": round(success_rate, 2),
            "failure_rate_percent": round(failure_rate, 2),
        },
        "performance": {
            "rate_limited_requests": len(rate_limit_store),  # Number of IPs being rate limited
        }
    }

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR = DATA_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


class AnalyzeRequest(BaseModel):
    concept: str = Field(..., min_length=10, max_length=10000, description="The concept to analyze")
    iterations: int = Field(3, ge=1, le=10, description="Number of processing iterations")
    max_retries: int = Field(3, ge=0, le=5, description="Maximum retry attempts")
    pipeline: str = Field("standard", pattern="^(standard|creative|analytical)$", description="Processing pipeline to use")


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
    # Enhanced hyper-details fields
    execution_summary: dict[str, Any] | None = None
    token_efficiency: dict[str, Any] | None = None
    lm_interactions_summary: dict[str, Any] | None = None
    reasoning_analysis: dict[str, Any] | None = None
    stage_analysis: dict[str, Any] | None = None
    pipeline_name: str | None = None
    total_tokens_used: int | None = None
    lm_calls_count: int | None = None
    converged: bool | None = None


class TokenEfficiencyResponse(BaseModel):
    total_tokens: int
    lm_calls_count: int
    iterations: int
    avg_tokens_per_call: float
    tokens_per_iteration: float
    prompt_tokens_total: int
    completion_tokens_total: int
    prompt_percentage: float
    completion_percentage: float
    cost_total: float
    cost_per_call: float
    error: str | None = None


class LMInteractionSummary(BaseModel):
    total_calls: int
    summary: dict[str, Any]
    interactions: list[dict[str, Any]]


class ReasoningAnalysis(BaseModel):
    strategy_evolution: list[dict[str, Any]]
    stage_outputs: dict[str, Any]
    total_iterations: int
    final_output_summary: dict[str, Any]
    error: str | None = None


class StageAnalysisResponse(BaseModel):
    stages: dict[str, Any]
    stage_order: list[str]
    error: str | None = None


class HyperDetailsResponse(BaseModel):
    job_metadata: dict[str, Any]
    execution_summary: dict[str, Any]
    token_efficiency: dict[str, Any]
    lm_interactions: dict[str, Any]
    reasoning_analysis: dict[str, Any]
    outputs: dict[str, Any]
    error: str | None = None


class TemplateComparisonResponse(BaseModel):
    templates: dict[str, Any]
    summary: dict[str, Any]
    error: str | None = None



@app.get(
    "/health",
    tags=["Health"],
    summary="Health Check",
    description="Check if the API server is running and healthy.",
)
async def health_check() -> dict[str, Any]:
    """Enhanced health check with system status"""
    try:
        # Check if we can access job storage
        manager = JobManager.get_instance()
        stats = manager.get_stats()

        # Basic system info (optional psutil)
        system_info = {}
        try:
            import psutil
            system_info = {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent,
            }
        except ImportError:
            system_info = {"note": "psutil not available - install for system metrics"}

        health_data = {
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "version": "1.0.0",
            "system": system_info,
            "jobs": {
                "total": stats.get("total_jobs", 0),
                "pending": stats.get("pending_jobs", 0),
                "running": stats.get("running_jobs", 0),
                "completed": stats.get("completed_jobs", 0),
                "failed": stats.get("failed_jobs", 0),
            }
        }

        return health_data
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(UTC).isoformat()
        }


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
    summary="Get Job Hyper Details",
    description="""Get comprehensive hyper-detailed information about a specific job.
    
Includes basic job metadata, execution summary, token efficiency metrics, 
LM interaction summaries, reasoning analysis, stage analysis, and full results.
This is the primary endpoint for getting complete job information with all analysis data.""",
)
async def get_job(job_id: str) -> JobDetailResponse:
    manager = JobManager.get_instance()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result_data = None
    execution_summary = None
    token_efficiency = None
    lm_interactions_summary = None
    reasoning_analysis = None
    stage_analysis = None
    pipeline_name = None
    total_tokens_used = None
    lm_calls_count = None
    converged = None

    if job.get("status") == JobStatus.SUCCESS.value:
        result_file = RESULTS_DIR / f"{job_id}.json"
        if result_file.exists():
            with open(result_file, encoding="utf-8") as f:
                result_data = json.load(f)
            
            # Extract hyper-details from result
            metadata = result_data.get("metadata", {})
            execution_summary = {
                "converged": metadata.get("converged", False),
                "total_iterations": metadata.get("total_iterations"),
                "pipeline_name": metadata.get("pipeline_name"),
                "stages_executed": metadata.get("stages_executed", []),
                "observability_enabled": metadata.get("observability_enabled", False),
            }
            pipeline_name = metadata.get("pipeline_name")
            total_tokens_used = metadata.get("total_tokens_used")
            lm_calls_count = metadata.get("lm_calls_count")
            converged = metadata.get("converged", False)
            
            # Get token efficiency
            token_efficiency = get_token_efficiency(job_id)
            if "error" in token_efficiency:
                token_efficiency = None
            
            # Get LM interactions summary
            lm_data = get_lm_interactions(job_id)
            if "error" not in lm_data:
                lm_interactions_summary = {
                    "total_calls": lm_data.get("total_calls"),
                    "summary": lm_data.get("summary"),
                }
            
            # Get reasoning analysis
            reasoning_analysis = get_reasoning_traces(job_id)
            if "error" in reasoning_analysis:
                reasoning_analysis = None
            
            # Get stage analysis
            stage_analysis = get_stage_analysis(job_id)
            if "error" in stage_analysis:
                stage_analysis = None

    return JobDetailResponse(
        id=job["id"],
        concept=job["concept"],
        status=job["status"],
        iterations=job["iterations"],
        retry_count=job["retry_count"],
        max_retries=job["max_retries"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        completed_at=job["completed_at"],
        error=job.get("error"),
        progress=job.get("progress"),
        result=result_data,
        execution_summary=execution_summary,
        token_efficiency=token_efficiency,
        lm_interactions_summary=lm_interactions_summary,
        reasoning_analysis=reasoning_analysis,
        stage_analysis=stage_analysis,
        pipeline_name=pipeline_name,
        total_tokens_used=total_tokens_used,
        lm_calls_count=lm_calls_count,
        converged=converged,
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


@app.post(
    "/jobs/{job_id}/rerun",
    response_model=JobResponse,
    tags=["Jobs"],
    summary="Rerun Failed Job",
    description="Create a new job with the same parameters as a failed job.",
)
async def rerun_job(job_id: str) -> JobResponse:
    manager = JobManager.get_instance()
    new_job = manager.rerun_job(job_id)

    if not new_job:
        raise HTTPException(status_code=404, detail="Job not found or not in failed state")

    return JobResponse(**new_job)


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


# ==================== ENHANCED ANALYSIS ENDPOINTS ====================


@app.get(
    "/jobs/{job_id}/hyper-details",
    response_model=HyperDetailsResponse,
    tags=["Analysis"],
    summary="Get Job Hyper Details",
    description="""Get comprehensive hyper-detailed information about a job.
    
Includes metadata, execution summary, token efficiency, LM interactions, reasoning analysis, and outputs.
This is the primary endpoint for getting complete job information with all analysis data.""",
)
async def get_job_hyper_details(job_id: str) -> HyperDetailsResponse:
    details = get_hyper_details(job_id)
    if "error" in details:
        raise HTTPException(status_code=404, detail=details["error"])
    return HyperDetailsResponse(**details)


@app.get(
    "/jobs/{job_id}/token-efficiency",
    response_model=TokenEfficiencyResponse,
    tags=["Analysis"],
    summary="Get Token Efficiency Metrics",
    description="""Analyze token usage efficiency for a job.
    
Provides detailed metrics including:
- Total tokens used and per-call averages
- Prompt vs completion token breakdown
- Cost analysis
- Tokens per iteration metrics""",
)
async def get_job_token_efficiency(job_id: str) -> TokenEfficiencyResponse:
    efficiency = get_token_efficiency(job_id)
    if "error" in efficiency:
        raise HTTPException(status_code=404, detail=efficiency["error"])
    return TokenEfficiencyResponse(**efficiency)


@app.get(
    "/jobs/{job_id}/lm-interactions",
    response_model=LMInteractionSummary,
    tags=["Analysis"],
    summary="Get LM Interaction History",
    description="""Get detailed history of all LLM API calls made during job execution.
    
Includes call order, model, tokens, costs, and timestamps for each interaction.""",
)
async def get_job_lm_interactions(job_id: str) -> LMInteractionSummary:
    interactions = get_lm_interactions(job_id)
    if "error" in interactions:
        raise HTTPException(status_code=404, detail=interactions["error"])
    return LMInteractionSummary(**interactions)


@app.get(
    "/jobs/{job_id}/lm-history",
    tags=["Analysis"],
    summary="Get Full LM Call History",
    description="""Get the complete history of all LLM API calls made during job execution.
    
Includes full prompts, responses, token usage, costs, and timestamps for each call.
This provides the most detailed view of the LLM interactions.""",
)
async def get_job_lm_history(job_id: str) -> dict[str, Any]:
    """Get complete LM call history with full details."""
    result = load_result(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    
    lm_history = result.get("lm_history", [])
    
    # Return full history with all details
    return {
        "job_id": job_id,
        "total_calls": len(lm_history),
        "lm_history": lm_history,
    }


@app.get(
    "/jobs/{job_id}/reasoning",
    response_model=ReasoningAnalysis,
    tags=["Analysis"],
    summary="Get Reasoning Analysis",
    description="""Get detailed reasoning traces including strategy evolution.
    
Shows how the reasoning strategy evolved across iterations, atoms extracted, 
axioms verified, and outputs from each stage.""",
)
async def get_job_reasoning(job_id: str) -> ReasoningAnalysis:
    reasoning = get_reasoning_traces(job_id)
    if "error" in reasoning:
        raise HTTPException(status_code=404, detail=reasoning["error"])
    return ReasoningAnalysis(**reasoning)


@app.get(
    "/jobs/{job_id}/stages",
    response_model=StageAnalysisResponse,
    tags=["Analysis"],
    summary="Get Stage-by-Stage Analysis",
    description="""Analyze outputs and metrics for each pipeline stage.
    
Provides per-stage information including:
- Iterations executed per stage
- Tokens consumed per stage
- Atoms extracted and axioms verified
- Final outputs from each stage""",
)
async def get_job_stages(job_id: str) -> StageAnalysisResponse:
    stages = get_stage_analysis(job_id)
    if "error" in stages:
        raise HTTPException(status_code=404, detail=stages["error"])
    return StageAnalysisResponse(**stages)


@app.get(
    "/analysis/compare-templates",
    response_model=TemplateComparisonResponse,
    tags=["Analysis"],
    summary="Compare Pipeline Template Efficiency",
    description="""Compare token usage, API call counts, and convergence rates across pipeline templates.
    
Analyzes all completed jobs to provide aggregate metrics per template.""",
)
async def analyze_template_comparison() -> TemplateComparisonResponse:
    comparison = compare_templates()
    if "error" in comparison:
        raise HTTPException(status_code=500, detail=comparison["error"])
    return TemplateComparisonResponse(**comparison)

