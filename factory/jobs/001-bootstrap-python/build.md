# Build — 001-bootstrap-python

## Round 1
### What changed
- `src/app/__init__.py` — package docstring + `__version__ = "0.1.0"`.
- `src/app/__main__.py` — `main(argv=None) -> int` prints `app <version>`, returns 0; `python -m app` entry point.
- `pyproject.toml` — project metadata (`name = "app"`, `requires-python = ">=3.10"`, no deps) and pytest config (`pythonpath = ["src"]`, `testpaths = ["tests"]`). No build-system table (project is not installed).
- `requirements-dev.txt` — `pytest>=7`.
- `Makefile` — `help`, `venv`, `test`, `clean` targets (all `.PHONY`); default goal `test`. `venv`/`test` depend on stamp file `.venv/.installed`, which depends on `requirements-dev.txt`, so deps are installed only on first run or when the requirements change. `test` runs `.venv/bin/python -m pytest` so make's exit code reflects pytest. `clean` removes `.venv`, `.pytest_cache`, and `__pycache__` dirs (excluding `.git`).
- `tests/test_smoke.py` — `test_package_importable`, `test_main_prints_version`, `test_python_m_app` (subprocess with `cwd=src/`).
- `README.md` — one-liner, requirements, layout, running tests (`make test`, first-run venv note, manual alternative, `make clean`), running the app.
- `CLAUDE.md` — Stack section now describes Python 3.10+/stdlib-only, `src/` layout, run command, pytest, and test command `make test`. Conventions unchanged.
- `.gitignore` — added `.pytest_cache/` (`.venv/`, `__pycache__/` were already present).

### How to run / test
`make test`  (app: `cd src && python3 -m app`)

### Acceptance criteria
- [x] AC1 — `test_package_importable` passes.
- [x] AC2 — `cd src && python3 -m app` printed `app 0.1.0`, exit 0; also `test_python_m_app`.
- [x] AC3 — `make clean && make test` from no `.venv/`: venv created, pytest installed, `3 passed`, exit 0.
- [x] AC4 — second `make test` ran only `.venv/bin/python -m pytest` (no pip step), `3 passed`, exit 0.
- [x] AC5 — temporary `tests/test_fail.py` (`assert False`) → `make test` exit 2; file deleted, not committed.
- [x] AC6 — `make clean` then `ls -a`: no `.venv`, no `.pytest_cache`; no `__pycache__` left.
- [x] AC7 — README sections: Requirements, Layout, Running tests (incl. manual venv alternative and `make clean`), Running the app.
- [x] AC8 — CLAUDE.md Stack names Python 3 / pytest / `src/` layout and test command `make test`.
- [x] AC9 — `git diff --name-only main..HEAD` lists only `.gitignore CLAUDE.md Makefile README.md pyproject.toml requirements-dev.txt src/app/__init__.py src/app/__main__.py tests/test_smoke.py`; nothing under `factory/`, no venv/caches.

### Test output
```
platform darwin -- Python 3.14.5, pytest-9.2.0, pluggy-1.7.0
configfile: pyproject.toml
testpaths: tests
collected 3 items

tests/test_smoke.py ...                                                  [100%]

============================== 3 passed in 0.03s ===============================
```
(First-run pip install printed harmless "Cache entry deserialization failed" warnings from the local pip cache.)

### Commits
```
eaccb30 Bootstrap minimal Python 3 project skeleton
```
