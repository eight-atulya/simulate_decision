help:
	@echo SimulateDecision Makefile
	@echo   make dev   - start both services
	@echo   make run   - alias for dev
	@echo   make start - start backend only
	@echo   make stop  - stop all services
	@echo   make health - check backend
	@echo   make test  - run tests
	@echo   make clean - remove build artifacts
	@echo   make deep-clean - remove all caches
	@echo   make install - rebuild dependencies

dev run:
	start "SimulateDecision Backend" cmd /k "cd /d E:\opencode\simulate_decision && uv run simulate-decision-server"
	timeout /t 3 /nobreak >nul
	start "SimulateDecision Frontend" cmd /k "cd /d E:\opencode\simulate_decision\web && npm run dev"

start:
	uv run simulate-decision-server

start-frontend:
	cd web && npm run dev

stop:
	taskkill /F /IM python.exe >nul 2>&1
	taskkill /F /IM node.exe >nul 2>&1

health:
	curl -s http://localhost:8000/health

test:
	uv run pytest tests/ -v

test-core:
	uv run pytest tests/test_core.py -v

lint:
	uv run ruff check .

typecheck:
	uv run pyright

format:
	uv run ruff check . --fix
	uv run ruff format .

check: lint

build-frontend:
	cd web && npm run build

clean:
	@echo Cleaning build artifacts...
	@if exist web\.next rmdir /S /Q web\.next
	@if exist .pytest_cache rmdir /S /Q .pytest_cache
	@if exist .ruff_cache rmdir /S /Q .ruff_cache
	@if exist __pycache__ rmdir /S /Q __pycache__
	@for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /S /Q "%%d"
	@echo Done!

deep-clean: clean
	@echo Deep cleaning...
	@if exist web\node_modules rmdir /S /Q web\node_modules
	@if exist .venv rmdir /S /Q .venv
	@if exist .simulatedecision rmdir /S /Q .simulatedecision
	@if exist data\results rmdir /S /Q data\results
	@echo Done!

install:
	@cd web && npm install
	@uv sync

ui:
	start http://localhost:8501

status:
	curl -s http://localhost:8000/health