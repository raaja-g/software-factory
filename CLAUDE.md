# software-factory

This repo is driven by the **software factory**: run `/factory <feature>` or
`/factory next` in Claude Code. See `.claude/skills/factory/SKILL.md` for the loop
and `.claude/agents/` for each agent.

## Stack
- **Language:** Python 3 (>= 3.10), standard library only at runtime; no
  third-party runtime dependencies.
- **Layout:** `src/` layout — application code in `src/app/` (package `app`);
  tests in `tests/` at the repo root, named `test_*.py`. Tests import `app` via
  pytest's `pythonpath = ["src"]` in `pyproject.toml` (no install needed).
- **Run:** `cd src && python3 -m app`
- **Test framework:** pytest (dev-only, listed in `requirements-dev.txt`).
- **Test command:** `make test` — creates a project-local `.venv/` and installs
  dev deps on first run, then runs `.venv/bin/python -m pytest`. Do not rely on a
  globally installed pytest. `make clean` removes `.venv/` and caches.

Keep this section current: language, how to run, and the **test command**
(agents rely on it).

## Conventions
- Feature work happens only on `factory/<job-id>` branches; `main` only receives merges.
- `factory/` is factory bookkeeping, owned by the orchestrator — never edited by builders.
- Dashboard: `cd factory && python3 -m http.server 8765` → http://localhost:8765/dashboard.html
