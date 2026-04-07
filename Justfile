# SimulateDecision Justfile
# Install: https://just.systems/install.sh
# Usage: just <target>

# Configuration
BACKEND_HOST := "localhost"
BACKEND_PORT := "8000"
FRONTEND_PORT := "8501"
WORKERS := "2"

# ============================================
# INSTALLATION
# ============================================

[doc("Install all dependencies")]
install:
    @cd web && npm install

[doc("Install Python dependencies")]
pip-install:
    @uv sync

# ============================================
# DEVELOPMENT
# ============================================

[doc("Start both backend and frontend in development")]
dev:
    @echo "Starting SimulateDecision (Backend + Frontend)..."
    @echo "  Backend:  http://{{BACKEND_HOST}}:{{BACKEND_PORT}}"
    @echo "  Frontend: http://localhost:{{FRONTEND_PORT}}"
    @python -m simulate_decision.server.main --host {{BACKEND_HOST}} --port {{BACKEND_PORT}} --workers {{WORKERS}} &
    @sleep 3
    @cd web && npm run dev

[doc("Start backend server only")]
start:
    @echo "Starting SimulateDecision backend..."
    @python -m simulate_decision.server.main --host {{BACKEND_HOST}} --port {{BACKEND_PORT}} --workers {{WORKERS}}

[doc("Start frontend dev server only")]
start-frontend:
    @echo "Starting SimulateDecision frontend..."
    @cd web && npm run dev

# ============================================
# CONTROL
# ============================================

[doc("Stop all running services")]
stop:
    @taskkill /F /IM python.exe 2>nul || true
    @taskkill /F /IM node.exe 2>nul || true

[doc("Restart all services (stop + dev)")]
restart: stop dev

[doc("Check if services are healthy")]
health:
    @curl -s -f http://{{BACKEND_HOST}}:{{BACKEND_PORT}}/health && echo " - Backend OK" || echo " - Backend FAILED"
    @curl -s -o /dev/null -w "%{http_code}" http://localhost:{{FRONTEND_PORT}} | grep -q "200" && echo " - Frontend OK" || echo " - Frontend Stopped"

# ============================================
# TESTING
# ============================================

[doc("Run all tests")]
test:
    @pytest tests/ -v

[doc("Run core engine tests")]
test-core:
    @pytest tests/test_core.py -v

[doc("Run CLI tests")]
test-cli:
    @pytest tests/test_cli.py -v

[doc("Run API tests")]
test-api:
    @pytest tests/test_api_e2e.py -v

[doc("Run signature tests")]
test-signatures:
    @pytest tests/test_signatures.py -v

# ============================================
# CODE QUALITY
# ============================================

[doc("Run ruff linter")]
lint:
    @ruff check .

[doc("Run pyright type checker")]
typecheck:
    @pyright

[doc("Format code with ruff")]
format:
    @ruff check . --fix
    @ruff format .

[doc("Run all code quality checks")]
check: lint typecheck

# ============================================
# BUILD
# ============================================

[doc("Build frontend for production")]
build-frontend:
    @cd web && npm run build

# ============================================
# CLEANUP
# ============================================

[doc("Clean build artifacts and caches")]
clean:
    @rm -rf .pytest_cache .ruff_cache __pycache__
    @rm -rf src/**/__pycache__ tests/__pycache__
    @rm -rf web/.next web/out

[doc("Clean everything including data")]
clean-all: clean
    @rm -rf .simulatedecision data/results

# ============================================
# OTHER
# ============================================

[doc("Open frontend in browser")]
ui:
    @start http://localhost:{{FRONTEND_PORT}}

[doc("Show this help message")]
help:
    @just --list

# Default target
default: help