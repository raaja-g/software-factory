# Bootstrap a minimal Python 3 project

## Goal
The repo has no application code yet. Set up a minimal, conventional Python 3
project skeleton (an importable `app` package under `src/`, pytest configuration,
a `make test` entry point, and a README) so later backlog jobs (the `todo` CLI at
`python -m app.todo` and a stdlib `http.server` web page) have a place to live and
a single, reliable test command that every factory agent can run.

## Stack & conventions
Chosen by this job (the repo had no stack before):
- **Language:** Python 3, minimum 3.10 (local machine has 3.14). Standard library
  only at runtime; no third-party runtime dependencies.
- **Layout:** `src/` layout. Application code lives in `src/app/`; tests live in
  `tests/` at the repo root, files named `test_*.py`.
- **Test framework:** pytest (dev-only dependency).
- **Test command:** `make test`. Note: on this machine `pytest` is present as a
  Homebrew binary but is *not* importable from the system `python3`, so the
  Makefile must not rely on a globally installed pytest. Instead it creates a
  project-local virtualenv at `.venv/` (already in `.gitignore`) and installs dev
  dependencies into it on first run.
- **Import path:** tests import `app` via pytest's `pythonpath = ["src"]` setting
  in `pyproject.toml`, so no editable install is required.
- The builder must update the **Stack** section of `CLAUDE.md` with the above
  (language, layout, how to run, test command `make test`).

## Scope
- In scope:
  - `src/app/` package with `__init__.py` (exposing `__version__`) and a
    `__main__.py` so `python -m app` works from `src/`.
  - `pyproject.toml` with project metadata and pytest config.
  - `requirements-dev.txt` listing `pytest`.
  - `Makefile` with `venv`, `test`, and `clean` targets.
  - A small smoke test suite in `tests/`.
  - `README.md` explaining setup and how to run tests.
  - Updating the Stack section of `CLAUDE.md`.
- Out of scope:
  - The `todo` CLI, any persistence, the web page (later backlog jobs).
  - Linters/formatters (ruff, black, mypy), CI configuration, packaging/publishing.
  - Anything under `factory/` (orchestrator-owned).

## Design
Files to add:

- `src/app/__init__.py`
  - Module docstring; `__version__ = "0.1.0"`.
- `src/app/__main__.py`
  - `def main(argv: list[str] | None = None) -> int:` prints
    `app <__version__>` to stdout and returns `0`.
  - `if __name__ == "__main__": raise SystemExit(main())`.
- `pyproject.toml`
  - `[project]`: `name = "app"`, `version = "0.1.0"`,
    `requires-python = ">=3.10"`, `dependencies = []`.
  - `[tool.pytest.ini_options]`: `pythonpath = ["src"]`, `testpaths = ["tests"]`.
  - A `[build-system]` table is optional; the project is not installed.
- `requirements-dev.txt` — `pytest>=7`.
- `Makefile` (tab-indented recipes; `.PHONY` declared):
  - `PYTHON ?= python3`, `VENV := .venv`.
  - `venv`: creates `$(VENV)` with `$(PYTHON) -m venv` and installs
    `requirements-dev.txt` into it. Should be idempotent — use a stamp/target file
    (e.g. `$(VENV)/.installed` depending on `requirements-dev.txt`) so repeated
    `make test` does not reinstall.
  - `test`: depends on the venv; runs `$(VENV)/bin/python -m pytest`; the make
    exit code reflects the pytest result.
  - `clean`: removes `$(VENV)`, `.pytest_cache`, and `__pycache__` dirs.
  - Default target (first target) is `test` or a `help` target — builder's choice,
    but `make test` must work.
- `tests/test_smoke.py`
  - `test_package_importable`: `import app`; `app.__version__` is a non-empty str.
  - `test_main_prints_version(capsys)`: `app.__main__.main([])` returns `0` and
    stdout contains `app.__version__`.
  - `test_python_m_app`: runs `[sys.executable, "-m", "app"]` via `subprocess`
    with `cwd` (or `PYTHONPATH`) pointing at `src/`; exit code 0 and output
    contains the version.
- `README.md`
  - Project one-liner; requirements (Python 3.10+, `make`); layout overview
    (`src/app/`, `tests/`); "Running tests" section with `make test` and a note
    that the first run creates `.venv/` and installs pytest; manual alternative
    (`python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt &&
    .venv/bin/python -m pytest`); `make clean`; how to run the app
    (`cd src && python3 -m app`).

File to change:
- `CLAUDE.md` — replace the "Not chosen yet" Stack text with the stack, layout,
  run command, and test command `make test`. Leave Conventions unchanged.

## Acceptance criteria
- [ ] AC1 — `src/app/__init__.py` exists and `app` is importable in tests;
  `app.__version__` is a non-empty string.
- [ ] AC2 — `cd src && python3 -m app` exits 0 and prints `app <version>`.
- [ ] AC3 — From a clean checkout (no `.venv/`), `make test` creates `.venv/`,
  installs pytest, runs the test suite, and exits 0 with all tests passing.
- [ ] AC4 — A second `make test` run does not reinstall dependencies and still
  exits 0.
- [ ] AC5 — `make test` exits non-zero when a test fails (verified by temporarily
  adding a failing test, then removing it — not committed).
- [ ] AC6 — `make clean` removes `.venv/` and `.pytest_cache/`.
- [ ] AC7 — `README.md` documents requirements, layout, `make test`, the manual
  venv alternative, and how to run the app.
- [ ] AC8 — `CLAUDE.md` Stack section names Python 3 / pytest / `src/` layout and
  states the test command `make test`.
- [ ] AC9 — No files under `factory/` are modified by the build; `.venv/` and
  caches are not committed.

## Test plan
- AC1, AC2: `tests/test_smoke.py` (`test_package_importable`,
  `test_main_prints_version`, `test_python_m_app`), run via `make test`. AC2 also
  checked manually: `cd src && python3 -m app`.
- AC3: `make clean && make test` — confirm `.venv/` is created and output ends
  with all tests passed, `echo $?` is 0.
- AC4: run `make test` again; confirm no pip install output and exit 0.
- AC5: temporarily add `tests/test_fail.py` with `assert False`, run `make test`,
  confirm non-zero exit; delete the file.
- AC6: `make clean && ls -a` — `.venv` and `.pytest_cache` absent.
- AC7, AC8: reviewer inspection of `README.md` and `CLAUDE.md`.
- AC9: `git diff --name-only main..HEAD` shows no `factory/` paths and no `.venv`
  / `__pycache__` / `.pytest_cache` paths. (Builder may add `.pytest_cache/` to
  `.gitignore`.)

Command: `make test`
