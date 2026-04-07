"""Analysis service for SimulateDecision results.

Provides comprehensive analysis functions for job results including:
- Token efficiency metrics
- LLM interaction analysis
- Reasoning trace extraction
- Template comparison
- Cost analysis
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from simulate_decision.server.job_manager import JobManager


def get_result_file(job_id: str) -> Path:
    """Get the path to a job's result file."""
    data_dir = Path(__file__).parent.parent.parent.parent / "data"
    return data_dir / "results" / f"{job_id}.json"


def load_result(job_id: str) -> dict[str, Any] | None:
    """Load a job result from file or fallback to the job record."""
    result_file = get_result_file(job_id)
    if result_file.exists():
        try:
            with open(result_file, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    manager = JobManager.get_instance()
    job = manager.get_job(job_id)
    if job and job.get("result"):
        try:
            return json.loads(job["result"])
        except json.JSONDecodeError:
            return None
    return None


def get_token_efficiency(job_id: str) -> dict[str, Any]:
    """Analyze token efficiency for a job.
    
    Returns:
        Dictionary with token metrics including:
        - total_tokens
        - lm_calls_count
        - avg_tokens_per_call
        - tokens_per_iteration
        - prompt_tokens_total
        - completion_tokens_total
        - cost_total (if available)
    """
    result = load_result(job_id)
    if not result:
        return {"error": "Result not found"}
    
    lm_history = result.get("lm_history", [])
    metadata = result.get("metadata", {})
    
    total_tokens = metadata.get("total_tokens_used", 0)
    iterations = metadata.get("total_iterations", 1)
    
    prompt_tokens_total = sum(call["usage"]["prompt_tokens"] for call in lm_history)
    completion_tokens_total = sum(call["usage"]["completion_tokens"] for call in lm_history)
    total_cost = sum(call.get("cost", 0) for call in lm_history)
    
    avg_tokens_per_call = total_tokens / len(lm_history) if lm_history else 0
    tokens_per_iteration = total_tokens / iterations if iterations > 0 else 0
    
    return {
        "total_tokens": total_tokens,
        "lm_calls_count": len(lm_history),
        "iterations": iterations,
        "avg_tokens_per_call": round(avg_tokens_per_call, 1),
        "tokens_per_iteration": round(tokens_per_iteration, 1),
        "prompt_tokens_total": prompt_tokens_total,
        "completion_tokens_total": completion_tokens_total,
        "prompt_percentage": round(100 * prompt_tokens_total / total_tokens, 1) if total_tokens > 0 else 0,
        "completion_percentage": round(100 * completion_tokens_total / total_tokens, 1) if total_tokens > 0 else 0,
        "cost_total": round(total_cost, 8),
        "cost_per_call": round(total_cost / len(lm_history), 8) if lm_history else 0,
    }


def get_lm_interactions(job_id: str) -> dict[str, Any]:
    """Get detailed LLM interaction history.
    
    Returns:
        Dictionary with:
        - interactions: list of LM calls with full details
        - summary: count and stats
    """
    result = load_result(job_id)
    if not result:
        return {"error": "Result not found"}
    
    lm_history = result.get("lm_history", [])
    
    interactions = []
    for i, call in enumerate(lm_history, 1):
        interactions.append({
            "call_number": i,
            "model": call.get("model"),
            "timestamp": call.get("timestamp"),
            "tokens_prompt": call["usage"]["prompt_tokens"],
            "tokens_completion": call["usage"]["completion_tokens"],
            "tokens_total": call["usage"]["total_tokens"],
            "cost": call.get("cost", 0),
            "messages_count": len(call.get("messages", [])),
            "uuid": call.get("uuid", "")[:8] + "...",
        })
    
    return {
        "total_calls": len(lm_history),
        "summary": {
            "total_tokens": sum(i["tokens_total"] for i in interactions),
            "total_cost": sum(i["cost"] for i in interactions),
            "avg_tokens_per_call": round(sum(i["tokens_total"] for i in interactions) / len(interactions), 1) if interactions else 0,
        },
        "interactions": interactions,
    }


def get_reasoning_traces(job_id: str) -> dict[str, Any]:
    """Extract and organize all reasoning traces.
    
    Returns:
        Dictionary with:
        - strategy_evolution: strategy changes across iterations
        - stage_outputs: outputs from each pipeline stage
        - reasoning_details: detailed reasoning at each step
    """
    result = load_result(job_id)
    if not result:
        return {"error": "Result not found"}
    
    strategy_history = result.get("strategy_history", [])
    final_output = result.get("metadata", {}).get("final_output", {})
    
    strategy_evolution = []
    for entry in strategy_history:
        strategy_evolution.append({
            "iteration": entry["iteration"],
            "stage": entry["stage"],
            "strategy": entry["strategy"][:100] + "..." if len(entry["strategy"]) > 100 else entry["strategy"],
            "atoms_extracted": entry["atoms_count"],
            "axioms_verified": entry["axioms_count"],
            "tokens_used": entry["tokens_used"],
            "reasoning_preview": entry["reasoning"][:150] + "..." if entry["reasoning"] else "N/A",
        })
    
    stage_outputs = {}
    for stage_name, outputs in final_output.items():
        stage_outputs[stage_name] = {
            stage_name: {k: (v[:100] + "..." if isinstance(v, str) and len(v) > 100 else v) 
                        for k, v in outputs.items()}
        }
    
    return {
        "strategy_evolution": strategy_evolution,
        "stage_outputs": stage_outputs,
        "total_iterations": len(strategy_history),
        "final_output_summary": {k: list(v.keys()) for k, v in final_output.items()},
    }


def get_hyper_details(job_id: str) -> dict[str, Any]:
    """Get complete hyper-detailed information about a job.
    
    Returns comprehensive information including:
    - Job metadata and status
    - Full result data
    - Token efficiency analysis
    - LM interaction summary
    - Reasoning traces
    - Cost analysis
    - Performance metrics
    """
    manager = JobManager.get_instance()
    job = manager.get_job(job_id)
    
    if not job:
        return {"error": "Job not found"}
    
    result = load_result(job_id)
    
    hyper_details = {
        "job_metadata": {
            "id": job["id"],
            "concept": job["concept"][:100] + "..." if len(job["concept"]) > 100 else job["concept"],
            "status": job["status"],
            "pipeline": job.get("pipeline", "standard"),
            "iterations": job.get("iterations"),
            "retry_count": job.get("retry_count"),
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
            "completed_at": job["completed_at"],
        },
        "execution_summary": {},
        "token_efficiency": {},
        "lm_interactions": {},
        "reasoning_analysis": {},
        "outputs": {},
    }
    
    if result:
        metadata = result.get("metadata", {})
        
        # Execution summary
        hyper_details["execution_summary"] = {
            "converged": metadata.get("converged", False),
            "total_iterations": metadata.get("total_iterations"),
            "pipeline_name": metadata.get("pipeline_name"),
            "stages_executed": metadata.get("stages_executed", []),
            "observability_enabled": metadata.get("observability_enabled", False),
        }
        
        # Token efficiency
        hyper_details["token_efficiency"] = get_token_efficiency(job_id)
        
        # LM interactions summary
        lm_data = get_lm_interactions(job_id)
        hyper_details["lm_interactions"] = {
            "total_calls": lm_data.get("total_calls"),
            "summary": lm_data.get("summary"),
        }
        
        # Reasoning analysis
        hyper_details["reasoning_analysis"] = get_reasoning_traces(job_id)
        
        # Final outputs
        if result.get("purified_atoms"):
            hyper_details["outputs"]["purified_atoms"] = result["purified_atoms"][:200] + "..."
        if result.get("blueprint"):
            hyper_details["outputs"]["blueprint"] = result["blueprint"][:200] + "..."
    
    return hyper_details


def compare_templates() -> dict[str, Any]:
    """Compare efficiency across all pipeline templates.
    
    Returns:
        Dictionary with comparison data for each template including:
        - run count
        - average tokens per run
        - average API calls
        - total tokens
        - average duration
    """
    results_dir = Path(__file__).parent.parent.parent.parent / "data" / "results"
    
    if not results_dir.exists():
        return {"error": "Results directory not found"}
    
    templates = {}
    
    for result_file in results_dir.glob("*.json"):
        try:
            with open(result_file, encoding="utf-8") as f:
                result = json.load(f)
            
            template = result.get("metadata", {}).get("pipeline_name", "unknown")
            tokens = result.get("metadata", {}).get("total_tokens_used", 0)
            calls = result.get("metadata", {}).get("lm_calls_count", 0)
            converged = result.get("metadata", {}).get("converged", False)
            
            if template not in templates:
                templates[template] = {
                    "runs": 0,
                    "total_tokens": 0,
                    "total_calls": 0,
                    "converged_runs": 0,
                    "failed_runs": 0,
                }
            
            templates[template]["runs"] += 1
            templates[template]["total_tokens"] += tokens
            templates[template]["total_calls"] += calls
            
            if converged:
                templates[template]["converged_runs"] += 1
            else:
                templates[template]["failed_runs"] += 1
        
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    
    comparison = {}
    for template, data in sorted(templates.items()):
        if data["runs"] > 0:
            comparison[template] = {
                "runs": data["runs"],
                "avg_tokens_per_run": round(data["total_tokens"] / data["runs"]),
                "avg_api_calls": round(data["total_calls"] / data["runs"], 1),
                "total_tokens": data["total_tokens"],
                "convergence_rate": round(100 * data["converged_runs"] / data["runs"], 1),
                "converged_runs": data["converged_runs"],
                "failed_runs": data["failed_runs"],
            }
    
    return {
        "templates": comparison,
        "summary": {
            "total_templates": len(comparison),
            "total_runs": sum(t["runs"] for t in templates.values()),
            "overall_convergence_rate": round(
                100 * sum(templates[t]["converged_runs"] for t in templates) / 
                sum(templates[t]["runs"] for t in templates) 
                if sum(templates[t]["runs"] for t in templates) > 0 else 0,
                1
            ),
        },
    }


def get_lm_call_details(job_id: str, call_number: int | None = None) -> dict[str, Any]:
    """Get detailed information about specific LLM calls.
    
    Args:
        job_id: Job ID to analyze
        call_number: Specific call number (1-based), or None to get all
        
    Returns:
        Dictionary with call details including prompts, responses, etc.
    """
    result = load_result(job_id)
    if not result:
        return {"error": "Result not found"}
    
    lm_history = result.get("lm_history", [])
    
    if call_number is not None:
        if call_number < 1 or call_number > len(lm_history):
            return {"error": f"Call number {call_number} not found"}
        
        call = lm_history[call_number - 1]
        return {
            "call_number": call_number,
            "model": call.get("model"),
            "timestamp": call.get("timestamp"),
            "messages": call.get("messages"),
            "messages_count": len(call.get("messages", [])),
            "tokens_used": call["usage"]["total_tokens"],
            "tokens_breakdown": {
                "prompt": call["usage"]["prompt_tokens"],
                "completion": call["usage"]["completion_tokens"],
            },
            "cost": call.get("cost", 0),
            "uuid": call.get("uuid"),
            "response_summary": {
                "model": call.get("response", {}).get("model"),
                "finish_reason": call.get("response", {}).get("choices", [{}])[0].get("finish_reason"),
            },
        }
    else:
        # Return summary of all calls
        calls_summary = []
        for i, call in enumerate(lm_history, 1):
            calls_summary.append({
                "call_number": i,
                "model": call.get("model"),
                "timestamp": call.get("timestamp"),
                "tokens_total": call["usage"]["total_tokens"],
                "cost": call.get("cost", 0),
                "uuid": call.get("uuid", "")[:12],
            })
        
        return {
            "total_calls": len(lm_history),
            "calls": calls_summary,
        }


def get_stage_analysis(job_id: str) -> dict[str, Any]:
    """Analyze outputs and metrics for each pipeline stage.
    
    Returns:
        Dictionary with per-stage analysis including outputs and metrics
    """
    result = load_result(job_id)
    if not result:
        return {"error": "Result not found"}
    
    strategy_history = result.get("strategy_history", [])
    final_output = result.get("metadata", {}).get("final_output", {})
    
    stages_analysis = {}
    
    for entry in strategy_history:
        stage = entry["stage"]
        if stage not in stages_analysis:
            stages_analysis[stage] = {
                "iterations_executed": 0,
                "total_tokens": 0,
                "atoms_extracted": 0,
                "axioms_verified": 0,
                "reasoning_samples": [],
            }
        
        stages_analysis[stage]["iterations_executed"] += 1
        stages_analysis[stage]["total_tokens"] += entry["tokens_used"]
        stages_analysis[stage]["atoms_extracted"] += entry["atoms_count"]
        stages_analysis[stage]["axioms_verified"] += entry["axioms_count"]
        
        if entry["reasoning"]:
            reasoning_preview = entry["reasoning"][:200] + "..." if len(entry["reasoning"]) > 200 else entry["reasoning"]
            stages_analysis[stage]["reasoning_samples"].append(reasoning_preview)
    
    # Add final outputs for each stage
    for stage_name, outputs in final_output.items():
        if stage_name not in stages_analysis:
            stages_analysis[stage_name] = {}
        
        stages_analysis[stage_name]["final_outputs"] = {
            k: (v[:100] + "..." if isinstance(v, str) and len(v) > 100 else v)
            for k, v in outputs.items()
        }
    
    return {
        "stages": stages_analysis,
        "stage_order": list(final_output.keys()),
    }
