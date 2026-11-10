# app

A minimal Python 3 project skeleton (standard library only at runtime), built by the software factory.

## Requirements

- Python 3.10+ (`python3` on your `PATH`)
- `make`

pytest is a dev-only dependency; `make test` installs it into a project-local virtualenv for you.

## Layout

```
src/app/              application package (importable as `app`)
  __init__.py         package metadata (`__version__`)
  __main__.py         entry point for `python -m app`
tests/                pytest test suite (`test_*.py`)
pyproject.toml        project metadata + pytest config (`pythonpath = ["src"]`)
requirements-dev.txt  dev dependencies (pytest)
Makefile              `venv`, `test`, `clean` targets
```

## Running tests

```sh
make test
```

The first run creates a virtualenv in `.venv/` and installs pytest from
`requirements-dev.txt` into it; later runs reuse it (it is only reinstalled when
`requirements-dev.txt` changes). The exit code of `make test` is pytest's.

Manual alternative (without `make`):

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest
```

To remove the virtualenv and caches:

```sh
make clean
```

## Running the app

```sh
cd src && python3 -m app
```

Prints `app <version>`, e.g. `app 0.1.0`.
