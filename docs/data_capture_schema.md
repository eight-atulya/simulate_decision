# Data Capture Schema

This document describes the JSON schema for simulation results captured by SimulateDecision.

## Overview

Simulation results are stored as JSON files in `data/results/{job_id}.json`. Each file contains comprehensive data about the simulation run, including LLM interactions, reasoning traces, and performance metrics.

## Top-Level Structure

```json
{
  "status": "SUCCESS|FAILURE",
  "iterations": 3,
  "purified_atoms": "string",
  "blueprint": "string",
  "strategy_history": [...],
  "metadata": {...},
  "lm_history": [...],
  "dspy_traces": [...],
  "dspy_trace_count": 15
}
```

### Fields

- `status`: String indicating success ("SUCCESS") or failure ("FAILURE")
- `iterations`: Integer number of iterations performed
- `purified_atoms`: String containing the final purified atomic concepts
- `blueprint`: String containing the technical blueprint output
- `strategy_history`: Array of strategy evolution records
- `metadata`: Object containing detailed metadata
- `lm_history`: Array of LLM API call records
- `dspy_traces`: Array of DSPy framework traces (optional)
- `dspy_trace_count`: Integer count of DSPy traces (optional)

## Metadata Object

```json
{
  "concept": "string",
  "total_iterations": 3,
  "total_tokens_used": 1500,
  "converged": true,
  "initial_strategy": "string",
  "final_strategy": "string",
  "model_name": "gpt-4",
  "signal_loss_threshold": 3,
  "stages_executed": ["deconstruct", "verify", "reconstruct"],
  "all_reasonings": [...],
  "atoms_before_verification": "string",
  "atoms_after_verification": "string",
  "noise_filtered": "string",
  "final_output": {...},
  "lm_calls_count": 12,
  "observability_enabled": true,
  "pipeline_name": "standard"
}
```

### Metadata Fields

- `concept`: The input concept being analyzed
- `total_iterations`: Total iterations run
- `total_tokens_used`: Total tokens consumed across all API calls
- `converged`: Boolean indicating if the simulation converged
- `initial_strategy`: Initial instruction strategy
- `final_strategy`: Final instruction strategy after optimization
- `model_name`: Name of the LLM model used
- `signal_loss_threshold`: Minimum axioms required to avoid signal loss
- `stages_executed`: Array of pipeline stage names executed
- `all_reasonings`: Array of all reasoning outputs
- `atoms_before_verification`: Raw atoms before verification
- `atoms_after_verification`: Verified atoms after filtering
- `noise_filtered`: Detected noise/metaphors removed
- `final_output`: Dictionary of final outputs from each stage
- `lm_calls_count`: Total number of LLM API calls
- `observability_enabled`: Boolean indicating if full observability was enabled
- `pipeline_name`: Name of the pipeline template used

## Strategy History Array

Each item in `strategy_history` represents one iteration's strategy state:

```json
{
  "iteration": 1,
  "stage": "deconstruct+verify",
  "strategy": "string",
  "atoms_count": 10,
  "axioms_count": 5,
  "error_signal": "string or null",
  "reasoning": "string",
  "tokens_used": 200,
  "model_name": "gpt-4",
  "raw_atoms": "string",
  "noise_detected": "string",
  "verified_atoms": "string",
  "rejection_reason": "string"
}
```

### Strategy History Fields

- `iteration`: Iteration number
- `stage`: Pipeline stage(s) executed
- `strategy`: Current instruction strategy
- `atoms_count`: Number of raw atoms extracted
- `axioms_count`: Number of axioms after verification
- `error_signal`: Error message if verification failed
- `reasoning`: LLM reasoning for this step
- `tokens_used`: Tokens used in this iteration
- `model_name`: Model used for this call
- `raw_atoms`: Raw atomic concepts
- `noise_detected`: Detected noise/metaphors
- `verified_atoms`: Verified axioms
- `rejection_reason`: Reason for axiom rejection

## LM History Array

Each item in `lm_history` represents one LLM API call:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "model": "gpt-4",
  "usage": {
    "total_tokens": 150,
    "prompt_tokens": 100,
    "completion_tokens": 50
  },
  "cost": 0.0003,
  "uuid": "12345678-1234-1234-1234-123456789abc",
  "prompt": "string",
  "response": "string"
}
```

### LM History Fields

- `timestamp`: ISO timestamp of the API call
- `model`: Model name used
- `usage`: Token usage statistics
  - `total_tokens`: Total tokens (prompt + completion)
  - `prompt_tokens`: Input tokens
  - `completion_tokens`: Output tokens
- `cost`: Estimated cost in USD
- `uuid`: Unique identifier for the call
- `prompt`: Full prompt sent to the model
- `response`: Full response from the model

## DSPy Traces

The `dspy_traces` array contains DSPy framework execution traces for debugging and analysis. The format depends on DSPy's internal tracing structure.

## Usage Examples

See `analyze_results.py` for examples of how to access and analyze this data programmatically.

## Notes

- All string fields may contain multi-line text
- Token counts are approximate and based on model tokenizer
- Cost estimates require proper pricing configuration
- Optional fields may not be present in all results