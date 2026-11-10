# Build — 002-todo-cli

## Round 1
### What changed
- `src/app/todo.py` — new module. Storage functions `default_path`, `load_items`, `save_items`, `add_item`, `complete_item` plus `TodoError`, and an argparse CLI `main(argv)` with the `add`/`list`/`done` subcommands.
  - `load_items`: a missing file gives `[]`. Strict validation: the top level must be an object with an `items` list, and each item needs a `str` `text` and a real `bool` `done` (so `0`/`1` are rejected). Bad JSON, a wrong shape, bad UTF-8, or a read OSError raise `TodoError` naming the file. It never writes.
  - `save_items`: `mkstemp(dir=path.parent)`, `fchmod 0o600`, write, flush, fsync, then `os.replace`. On any failure the temp file is unlinked. An OSError is re-raised as `TodoError` so the CLI exits 1.
  - `add_item` / `complete_item` return `{"number", "text", "done"}`. Completing an item that is already done does not rewrite the file.
  - The CLI prints `error: <msg>` to stderr and exits 1 on `TodoError`. argparse usage errors exit 2. `list` never creates the file.
- `tests/test_todo.py` — 54 tests covering AC1–AC12 (HOME is isolated through a monkeypatch fixture and the subprocess env).
- `README.md` — new "Todo CLI" section (usage, output format, `~/.todo.json` location/format, errors, storage API). Also added `todo.py` to the layout listing.
- `CLAUDE.md` — Stack "Run" line now includes `cd src && python3 -m app.todo add <text...>|list|done <n>`. The test command is unchanged.

### How to run / test
`make test` — or try it by hand: `cd src && python3 -m app.todo list`

### Acceptance criteria
- [x] AC1 — `test_add_creates_file`
- [x] AC2 — `test_list_in_insertion_order`
- [x] AC3 — `test_list_empty_does_not_create_file`
- [x] AC4 — `test_done_marks_item`, `test_done_already_done_succeeds_without_write`
- [x] AC5 — `test_done_out_of_range[0|99|-1]`, `test_done_on_empty_list`
- [x] AC6 — `test_usage_errors_exit_2` (`done abc`, `[]`, `bogus`, `done`, `add`)
- [x] AC7 — `test_add_empty_text[...]`, `test_add_empty_text_no_file`
- [x] AC8 — `test_corrupt_file_untouched` (9 bad contents × add/list/done; checks that the error names the file, the bytes are unchanged, and no temp files are left), `test_invalid_utf8_is_error`
- [x] AC9 — `test_persists_across_processes` (subprocess add/add/done/list, plus exit codes 1 and 2)
- [x] AC10 — `test_file_mode_and_no_temp_files`, `test_save_resets_loose_mode`, `test_save_uses_os_replace`, `test_failed_save_removes_temp_and_keeps_original`
- [x] AC11 — `test_unicode_round_trip`; also checked by hand from `src/` with a temp HOME
- [x] AC12 — `test_storage_api_with_explicit_path`
- [x] AC13 — README and CLAUDE.md updated. `git diff --name-only main..HEAD` → `CLAUDE.md README.md src/app/todo.py tests/test_todo.py` (no `factory/` paths)
- [x] AC14 — `make test`: 57 passed

### Test output
```
tests/test_smoke.py ...                                                  [  5%]
tests/test_todo.py ..................................................... [ 98%]
.                                                                        [100%]

============================== 57 passed in 0.31s ==============================
```

### Commits
```
b58b1e1 Document todo CLI in README and CLAUDE.md Stack
fd397fe Add todo CLI (python -m app.todo) with reusable JSON storage
```
