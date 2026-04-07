# SimulateDecision

Decision Simulator - AI-Powered Decision Analysis Engine built with DSPy and LM Studio.

## Quick Start

```powershell
# Install dependencies (including UI)
uv sync --extra ui
```

## Configuration

Copy `.env.example` to `.env` and configure:

```env
LM_STUDIO_URL=http://localhost:1234/v1
MODEL_NAME=google/gemma-4-26b-a4b
MAX_ITERATIONS=3
SIGNAL_LOSS_THRESHOLD=3
```

**Requirements:**
- Python 3.11+
- [LM Studio](https://lmstudio.ai) running with local server enabled on port 1234
- A text-only model loaded in LM Studio

---

## Usage

### Option 1: CLI (Terminal)

Run analysis directly from the command line:

```powershell
uv run simulate-decision "The concept of 'Justice'"
```

Custom iterations:
```powershell
uv run simulate-decision "What is consciousness?" --iterations 5
```

### Option 2: UI (Next.js Dashboard)

Start the backend server (Terminal 1):
```powershell
uv run simulate-decision-server
```

Start the UI (Terminal 2):
```powershell
cd web && npm run dev
```

Then open http://localhost:8501 in your browser.

---

## Architecture

SimulateDecision uses a **Policy-Driven RL approach** with three cognitive stages:

1. **Deconstruct** - Break concepts into atomic components
2. **Verify** - Filter via axiomatic validation (environment/reward)
3. **Reconstruct** - Build technical blueprint from verified axioms

The `FailureAnalyzer` acts as a policy optimizer, generating correction vectors when verification fails.
