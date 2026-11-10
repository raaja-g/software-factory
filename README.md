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
  todo.py             todo CLI + reusable storage functions (`python -m app.todo`)
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

## Todo CLI

A small todo manager. Run it from `src/`:

```sh
cd src
python3 -m app.todo add buy milk     # Added #1: buy milk
python3 -m app.todo add call bob     # Added #2: call bob
python3 -m app.todo done 2           # Done #2: call bob
python3 -m app.todo list
# 1. [ ] buy milk
# 2. [x] call bob
```

- `add TEXT...` — words are joined with single spaces; empty text is an error.
- `list` — one line per item, `<n>. [ ] <text>` (open) or `<n>. [x] <text>`
  (done); prints `No todos.` when there are none.
- `done N` — marks item `N` done. Completed items stay in the list, so numbers
  never change.

Todos are stored in **`~/.todo.json`** (UTF-8 JSON, file mode `0600`, written
atomically):

```json
{
  "items": [
    {"text": "buy milk", "done": false},
    {"text": "call bob", "done": true}
  ]
}
```

Errors (unknown item number, empty text, a corrupt or malformed storage file)
print `error: <message>` to stderr and exit 1; a corrupt file is never
overwritten. Usage errors (bad or missing subcommand, non-integer `N`) exit 2.

The storage functions `load_items`, `save_items`, `add_item`, `complete_item`
and `default_path` live in `app.todo` and each accept an optional `path`.
