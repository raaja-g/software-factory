# Todo CLI (`python -m app.todo`)

## Goal
Add a small command-line todo manager, run as `python -m app.todo add|list|done <n>`,
that keeps its items in a JSON file in the user's home directory so they persist
between runs. The storage logic is kept in plain functions apart from the
argument parsing, because the next backlog job (a stdlib `http.server` web page
that lists, adds, and completes todos) will reuse the same storage code and file.

## Stack & conventions
Already set up by job 001 (see `CLAUDE.md`):
- Python 3 (>= 3.10). Runtime code uses the standard library only (`argparse`,
  `json`, `pathlib`, `os`, `tempfile`).
- Code goes in `src/app/`. Tests go in `tests/test_*.py` and import `app` via
  pytest's `pythonpath = ["src"]`.
- **Test command:** `make test`.
- Run: `cd src && python3 -m app.todo <command>`.
- Follow the existing style: module docstrings, `from __future__ import annotations`,
  `main(argv: list[str] | None = None) -> int`, and
  `if __name__ == "__main__": raise SystemExit(main())`.

## Scope
- In scope:
  - New module `src/app/todo.py`: storage functions plus the CLI.
  - Subcommands `add <text...>`, `list`, `done <n>`.
  - JSON storage at `~/.todo.json`.
  - Tests in `tests/test_todo.py`.
  - A short "Todo CLI" section in `README.md`. Add the todo run command to the
    `CLAUDE.md` Stack "Run" line.
- Out of scope:
  - The web page (next backlog job).
  - Delete/edit/undo/clear commands, priorities, due dates, colours.
  - An environment variable or flag that overrides the storage path. Tests
    isolate storage by pointing `HOME` at a temp dir.
  - File locking for concurrent writers.
  - Anything under `factory/`.

## Design

### File: `src/app/todo.py`

**Storage location**
- `def default_path() -> Path:` returns `Path.home() / ".todo.json"`. It is
  evaluated at call time, not import time, so tests that change `HOME` work.

**Data shape** (UTF-8 JSON, pretty-printed with `indent=2`, newline at end):
```json
{
  "items": [
    {"text": "buy milk", "done": false},
    {"text": "call bob", "done": true}
  ]
}
```
- Items keep insertion order. The item number shown to users is the 1-based
  position in `items`. Completed items stay in the list, so numbers do not change.

**Storage API** (pure functions that the web page job can reuse; each takes an
optional `path: Path | None = None`, and `None` means `default_path()`):
- `class TodoError(Exception)` — a user-facing error. Its message is printed to
  stderr by the CLI.
- `def load_items(path=None) -> list[dict]`:
  - If the file is missing, return `[]` and do not create the file.
  - If the file has invalid JSON, or its top level is not an object with an
    `items` list, or any item is not an object with a `str` `text` and a `bool`
    `done`, raise `TodoError` with a message naming the file. **Never overwrite
    or delete a corrupt file.**
- `def save_items(items, path=None) -> None`: atomic write. Write to a temp file
  in the same directory (`tempfile.mkstemp(dir=path.parent)`), flush, then
  `os.replace` it onto the target. The file mode is `0o600`, because todos are
  personal data. If anything fails, remove the temp file.
- `def add_item(text: str, path=None) -> dict`: strips `text`. If the result is
  empty, raise `TodoError("todo text must not be empty")`. Otherwise append
  `{"text": text, "done": False}`, save, and return the new item along with its
  number (for example `{"number": n, "text": ..., "done": False}`; the builder
  may pick an equivalent return).
- `def complete_item(number: int, path=None) -> dict`: if `number` is outside
  `1..len(items)`, raise `TodoError` (for example `"no todo #5 (have 3)"`).
  Otherwise set `done = True`, save, and return the item. Completing an item
  that is already done is allowed: it saves nothing and succeeds.

**CLI** (`argparse`, `prog="python -m app.todo"`, required subcommands):
- `def main(argv: list[str] | None = None) -> int`
- `add TEXT...`: joins the words with single spaces and calls `add_item`. Prints
  `Added #<n>: <text>`. Exits 0.
- `list`: prints one line per item, `<n>. [ ] <text>` or `<n>. [x] <text>`. If
  there are no items, prints `No todos.` Exits 0. Never creates the file.
- `done N`: `N` is parsed as `int` by argparse (non-integers give argparse's
  usage error, exit 2). Calls `complete_item`. Prints `Done #<n>: <text>`.
  Exits 0.
- A `TodoError` from any command prints `error: <message>` to **stderr** and
  exits **1**. Nothing is written to stdout.
- A missing or unknown subcommand gives the argparse usage error and exits 2.

### Other files
- `tests/test_todo.py`: new (see Test plan).
- `README.md`: add a "Todo CLI" section with usage examples, the storage
  location `~/.todo.json`, and the output format.
- `CLAUDE.md`: add `cd src && python3 -m app.todo list` (etc.) to the Run line
  of the Stack section.

## Acceptance criteria
- [ ] AC1 — `python -m app.todo add buy milk` (run from `src/`) exits 0, prints
  `Added #1: buy milk`, and creates `~/.todo.json` with
  `{"items": [{"text": "buy milk", "done": false}]}`.
- [ ] AC2 — `list` prints the items in insertion order as `1. [ ] buy milk`,
  `2. [x] call bob`, and so on, and exits 0.
- [ ] AC3 — `list` with no storage file prints `No todos.`, exits 0, and does
  **not** create the file.
- [ ] AC4 — `done 2` marks item 2 done, prints `Done #2: <text>`, exits 0. A
  later `list` shows `[x]` for it and the numbering is unchanged.
- [ ] AC5 — `done 0`, `done 99` (out of range), or `done` on an empty list
  prints `error: ...` to stderr, exits 1, and leaves the file unchanged.
- [ ] AC6 — `done abc` and a missing or unknown subcommand exit 2 with a usage
  message on stderr.
- [ ] AC7 — `add` with empty or whitespace-only text (for example `add "   "`)
  prints an error to stderr, exits 1, and adds nothing.
- [ ] AC8 — If `~/.todo.json` holds invalid JSON or the wrong shape, every
  command prints `error: ...` (naming the file) to stderr, exits 1, and leaves
  the file byte-for-byte unchanged.
- [ ] AC9 — Items persist across separate process invocations, so
  `add`/`add`/`done`/`list` run as separate subprocesses give consistent
  results.
- [ ] AC10 — A file created by the CLI has permissions `0o600`. Saves are
  atomic: temp file plus `os.replace`, and no stray temp files are left in the
  directory afterwards.
- [ ] AC11 — Unicode text round-trips (for example `add café ☕` then `list`
  shows it unchanged).
- [ ] AC12 — The storage functions (`load_items`, `save_items`, `add_item`,
  `complete_item`, `default_path`) can be imported from `app.todo` and accept an
  explicit `path`.
- [ ] AC13 — `README.md` documents the todo CLI and its storage location.
  `CLAUDE.md` Run line mentions it. No files under `factory/` are changed.
- [ ] AC14 — `make test` passes, including the existing smoke tests.

## Test plan
All automated, in `tests/test_todo.py`, run with **`make test`**.

- Isolation: use a fixture that does `monkeypatch.setenv("HOME", str(tmp_path))`.
  Subprocess tests pass `env={**os.environ, "HOME": str(tmp_path)}` and
  `cwd=SRC_DIR` (same pattern as `test_smoke.py`). No test touches the real home
  directory.
- AC1, AC2, AC4: call `main([...])` in-process with `capsys`, check stdout and
  the exit code, and parse the JSON file to check its contents.
- AC3: `main(["list"])` on an empty `HOME`: output `No todos.`, and the file
  does not exist.
- AC5: add 2 items, then for `done 0` / `done 99` check the return value is 1,
  stderr starts with `error:`, and the file bytes are unchanged. Also cover the
  empty-list case.
- AC6: `pytest.raises(SystemExit)` with code 2 for `["done", "abc"]`, `[]`, and
  `["bogus"]`.
- AC7: `main(["add", "   "])` returns 1, and the item count is unchanged.
- AC8: write `"{not json"` and also `'{"items": 5}'` to the file. Each of `add`,
  `list`, and `done 1` returns 1 with `error:` on stderr, and the file bytes
  equal the original.
- AC9: a subprocess sequence `[sys.executable, "-m", "app.todo", ...]`: add,
  add, done 1, list. Check the final stdout lines.
- AC10: after an `add`, `stat.S_IMODE(path.stat().st_mode) == 0o600`, and the
  directory listing of `tmp_path` contains only `.todo.json`.
- AC11: round-trip of `café ☕` through add/list, and the JSON loads back to the
  same string.
- AC12: unit tests that call `add_item`/`complete_item`/`load_items` with an
  explicit `path=tmp_path / "x.json"`.
- AC13: reviewer inspection, plus `git diff --name-only main..HEAD` shows no
  `factory/` paths.
- AC14: `make test` exits 0.
