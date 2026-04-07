# SimulateDecision Makefile
# Cross-platform: Windows + macOS + Linux
# Requires: make, python, uv, npm, curl

.DEFAULT_GOAL := help

# -----------------------------
# OS detection
# -----------------------------
ifeq ($(OS),Windows_NT)
    DETECTED_OS := windows
    PYTHON := python
    NULL := NUL
    MKDIR_P = if not exist "$(1)" mkdir "$(1)"
    OPEN_URL = start "" "$(1)"
else
    DETECTED_OS := unix
    PYTHON := python3
    NULL := /dev/null
    MKDIR_P = mkdir -p "$(1)"
    UNAME_S := $(shell uname -s 2>/dev/null || echo unknown)
    ifeq ($(UNAME_S),Darwin)
        OPEN_URL = open "$(1)"
    else
        OPEN_URL = xdg-open "$(1)"
    endif
endif

# -----------------------------
# Project paths
# -----------------------------
ROOT := $(CURDIR)
WEB_DIR := $(ROOT)/web
TMP_DIR := $(ROOT)/.make
BACKEND_PID := $(TMP_DIR)/backend.pid
FRONTEND_PID := $(TMP_DIR)/frontend.pid

# -----------------------------
# Service config
# -----------------------------
BACKEND_HEALTH_URL := http://localhost:8000/health
UI_URL := http://localhost:8501

# -----------------------------
# Helpers
# -----------------------------
.PHONY: help
help:
	@echo SimulateDecision Makefile
	@echo
	@echo OS detected: $(DETECTED_OS)
	@echo
	@echo "Core"
	@echo "  make dev            - start backend and frontend in separate windows/processes"
	@echo "  make run            - alias for dev"
	@echo "  make start          - start backend in current shell"
	@echo "  make start-frontend - start frontend in current shell"
	@echo "  make stop           - stop services started by this Makefile"
	@echo "  make restart        - stop then start both services"
	@echo
	@echo "Checks"
	@echo "  make health         - check backend health"
	@echo "  make status         - alias for health"
	@echo "  make test           - run all tests"
	@echo "  make test-core      - run core tests only"
	@echo "  make lint           - run ruff checks"
	@echo "  make typecheck      - run pyright"
	@echo "  make format         - auto-fix and format"
	@echo "  make check          - lint + typecheck + test"
	@echo
	@echo "Frontend"
	@echo "  make build-frontend - build frontend"
	@echo "  make ui             - open UI in browser"
	@echo
	@echo "Cleanup"
	@echo "  make clean          - remove build/cache artifacts"
	@echo "  make deep-clean     - remove caches + deps + local results"
	@echo "  make install        - install/sync dependencies"

.PHONY: ensure-tmp
ensure-tmp:
ifeq ($(DETECTED_OS),windows)
	@if not exist "$(TMP_DIR)" mkdir "$(TMP_DIR)"
else
	@mkdir -p "$(TMP_DIR)"
endif

# -----------------------------
# Start services
# -----------------------------
.PHONY: dev run
dev run: ensure-tmp
ifeq ($(DETECTED_OS),windows)
	@echo Starting backend and frontend on Windows...
	@start "SimulateDecision Backend" cmd /c "cd /d $(ROOT) && uv run simulate-decision-server"
	@powershell -NoProfile -Command "Start-Sleep -Seconds 3"
	@start "SimulateDecision Frontend" cmd /c "cd /d $(WEB_DIR) && npm run dev"
	@echo Started. Note: detached Windows terminals are not PID-tracked in this mode.
else
	@echo Starting backend and frontend on Unix-like OS...
	@sh -c 'cd "$(ROOT)" && nohup uv run simulate-decision-server > "$(TMP_DIR)/backend.log" 2>&1 & echo $$! > "$(BACKEND_PID)"'
	@sleep 3
	@sh -c 'cd "$(WEB_DIR)" && nohup npm run dev > "$(TMP_DIR)/frontend.log" 2>&1 & echo $$! > "$(FRONTEND_PID)"'
	@echo Backend PID: $$(cat "$(BACKEND_PID)" 2>/dev/null || echo unknown)
	@echo Frontend PID: $$(cat "$(FRONTEND_PID)" 2>/dev/null || echo unknown)
	@echo Logs: $(TMP_DIR)/backend.log , $(TMP_DIR)/frontend.log
endif

.PHONY: start
start:
	@cd "$(ROOT)" && uv run simulate-decision-server

.PHONY: start-frontend
start-frontend:
	@cd "$(WEB_DIR)" && npm run dev

# -----------------------------
# Stop services
# -----------------------------
.PHONY: stop
stop:
ifeq ($(DETECTED_OS),windows)
	@echo Stopping likely SimulateDecision processes on Windows...
	@powershell -NoProfile -Command "$$procs = Get-CimInstance Win32_Process | Where-Object { ($$_.Name -match 'python|node|uv') -and ($$_.CommandLine -match 'simulate-decision-server|npm run dev|next dev') }; if ($$procs) { $$procs | ForEach-Object { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('Stopped PID ' + $$_.ProcessId) } } else { Write-Host 'No matching SimulateDecision processes found.' }"
else
	@echo Stopping services on Unix-like OS...
	@if [ -f "$(BACKEND_PID)" ]; then kill "$$(cat "$(BACKEND_PID)")" 2>/dev/null || true; rm -f "$(BACKEND_PID)"; echo "Stopped backend"; else echo "No backend PID file"; fi
	@if [ -f "$(FRONTEND_PID)" ]; then kill "$$(cat "$(FRONTEND_PID)")" 2>/dev/null || true; rm -f "$(FRONTEND_PID)"; echo "Stopped frontend"; else echo "No frontend PID file"; fi
endif

.PHONY: restart
restart: stop dev

# -----------------------------
# Health / status
# -----------------------------
.PHONY: health status
health status:
	@curl -fsS "$(BACKEND_HEALTH_URL)" || (echo Backend health check failed && exit 1)

# -----------------------------
# Tests / quality
# -----------------------------
.PHONY: test
test:
	@uv run pytest tests/ -v

.PHONY: test-core
test-core:
	@uv run pytest tests/test_core.py -v

.PHONY: lint
lint:
	@uv run ruff check .

.PHONY: typecheck
typecheck:
	@uv run pyright

.PHONY: format
format:
	@uv run ruff check . --fix
	@uv run ruff format .

.PHONY: check
check: lint typecheck test

# -----------------------------
# Frontend
# -----------------------------
.PHONY: build-frontend
build-frontend:
	@cd "$(WEB_DIR)" && npm run build

.PHONY: ui
ui:
ifeq ($(DETECTED_OS),windows)
	@start "" "$(UI_URL)"
else
	@$(call OPEN_URL,$(UI_URL))
endif

# -----------------------------
# Dependency install
# -----------------------------
.PHONY: install
install:
	@cd "$(WEB_DIR)" && npm install
	@uv sync

# -----------------------------
# Cleanup (Python-based for portability)
# -----------------------------
.PHONY: clean
clean:
	@echo Cleaning build artifacts...
	@$(PYTHON) -c "from pathlib import Path; import shutil; root=Path(r'$(ROOT)'); targets=[root/'web'/'.next', root/'.pytest_cache', root/'.ruff_cache']; \
for p in targets: \
    shutil.rmtree(p, ignore_errors=True) if p.exists() else None; \
[shutil.rmtree(p, ignore_errors=True) for p in root.rglob('__pycache__') if p.is_dir()]; \
print('Done!')"

.PHONY: deep-clean
deep-clean: clean
	@echo Deep cleaning...
	@$(PYTHON) -c "from pathlib import Path; import shutil; root=Path(r'$(ROOT)'); targets=[root/'web'/'node_modules', root/'.venv', root/'.simulatedecision', root/'data'/'results', root/'.make']; \
for p in targets: \
    shutil.rmtree(p, ignore_errors=True) if p.exists() else None; \
print('Done!')"