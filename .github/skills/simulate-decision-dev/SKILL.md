---
name: simulate-decision-dev
description: '**DEVELOPMENT SKILL** — Commands for developing, testing, and managing the SimulateDecision application. USE FOR: starting development servers, running tests, code quality checks, building frontend, service management. DO NOT USE FOR: general coding questions; runtime debugging; production deployment. INVOKES: make commands, just commands, terminal operations for development workflow.'
---

# SimulateDecision Development Skill

## Overview

This skill provides commands for developing, testing, and managing the SimulateDecision application. SimulateDecision is a decision simulator that uses DSPy for cognitive processing.

## Project Structure

```
simulate_decision/
├── src/simulate_decision/  # Main Python package
│   ├── core/               # Core engine, state, storage
│   ├── cli/                # CLI commands
│   ├── server/             # FastAPI server & workers
│   └── signatures/         # DSPy signatures
├── web/                    # Next.js frontend
├── data/                   # Runtime data
├── tests/                  # Test suite
├── docs/                   # Documentation
├── Makefile                # Main build commands
└── Justfile                # Alternative (just command)
```

## Development Commands

### Start Development Environment

```bash
make dev
```
Start both backend API server and frontend dev server.

- Backend: http://localhost:8000
- Frontend: http://localhost:8501
- API Docs: http://localhost:8000/docs

### Start Individual Services

```bash
make start           # Backend API server only
make start-frontend # Frontend dev server only
```

## Control Commands

### Service Management

```bash
make stop            # Stop all running services
make restart         # Restart all services (stop + dev)
make health          # Check if services are healthy
```

### Monitoring

```bash
make logs            # Show backend logs (last 50 lines)
make status          # Show detailed status of all services
```

## Testing Commands

### Run Tests

```bash
make test            # Run all tests
make test-core       # Core engine tests only
make test-cli        # CLI tests only
make test-api        # API tests only
make test-signatures # Signature tests only
```

## Code Quality Commands

### Linting & Type Checking

```bash
make lint            # Run ruff linter
make typecheck       # Run pyright type checker
make format          # Format code with ruff (auto-fix)
make check           # Run all code quality checks
```

## Build Commands

### Frontend

```bash
make build-frontend  # Build frontend for production
make ui              # Open frontend in browser
```

## Installation

### Install Dependencies

```bash
make install         # Install Python + Node.js dependencies
```

## Cleanup Commands

### Clean Build Artifacts

```bash
make clean           # Remove build artifacts and caches
```
Removes:
- `web/.next` (Next.js build)
- `.pytest_cache` (pytest cache)
- `.ruff_cache` (linter cache)
- All `__pycache__` folders

### Deep Clean (Nuclear Option)

```bash
make deep-clean      # Remove ALL caches including venv & node_modules
```
Removes:
- `web/node_modules` (npm dependencies)
- `.venv` (Python virtual environment)
- `.simulatedecision` (app data)
- `data/results` (job results)

**Warning**: This will require rebuilding dependencies with `make install`

## Alternative: Using Just

If you prefer `just` over `make`:

```bash
just dev             # Start development
just start           # Start backend
just test            # Run tests
just lint            # Lint code
just help            # Show all commands
```

## Environment Variables

Create a `.env` file in the root:

```bash
# LM Studio Settings
LM_STUDIO_URL=http://localhost:1234/v1
LM_STUDIO_API_KEY=lm-studio

# Model Configuration
MODEL_NAME=google/gemma-4-26b-a4b

# Engine Settings
MAX_ITERATIONS=3
SIGNAL_LOSS_THRESHOLD=3
```

## Quick Start

1. Install dependencies:
   ```bash
   make install
   ```

2. Start development:
   ```bash
   make dev
   ```

3. Run tests:
   ```bash
   make test
   ```

4. Check code quality:
   ```bash
   make check
   ```

## Git Workflow

### Commit Message Conventions

Use structured commit messages with prefixes for better tracking:

```bash
# Bug fixes
git commit -m "[fix] ~ Brief description of the fix"

# New features or enhancements
git commit -m "[feat] ~ Brief description of the new feature"

# Upgrades or improvements
git commit -m "[upgrade] ~ Brief description of the improvement"

# Documentation updates
git commit -m "[docs] ~ Brief description of documentation changes"

# Code refactoring
git commit -m "[refactor] ~ Brief description of refactoring"
```

**Examples:**
```bash
git commit -m "[fix] ~ Add missing logger import in config.py to resolve NameError"
git commit -m "[upgrade] ~ Add rerun functionality for failed jobs (backend API + frontend UI)"
git commit -m "[feat] ~ Enhance server logging and graceful shutdown handling"
```

## Configuration

- Backend port: 8000 (configurable via BACKEND_PORT)
- Frontend port: 8501 (configurable via FRONTEND_PORT)
- Workers: 2 (configurable via WORKERS)

Example:
```bash
BACKEND_PORT=9000 make start
```

## Troubleshooting

### Port Already in Use
```bash
make stop
make start
```

### Clean Start (After Issues)
```bash
make deep-clean
make install
make dev
```

## Architecture

- **Backend**: FastAPI + DSPy for AI processing
- **Frontend**: Next.js 16 with React 19
- **Storage**: JSON file-based history (~/.simulatedecision/history.json)
- **API**: RESTful with job queue system

## See Also

- [API Documentation](http://localhost:8000/docs)
- [README.md](../../../README.md)
- [pyproject.toml](../../../pyproject.toml)
- [data_capture_schema.md](../../../docs/data_capture_schema.md)