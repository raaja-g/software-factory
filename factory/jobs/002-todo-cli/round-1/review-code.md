VERDICT: PASS

## Summary
`src/app/todo.py` matches the spec: storage is separate from the CLI, validation is strict, writes are atomic with mode 0o600, and errors exit 1 or 2 as specified. I ran `make test` and got 57 passed, which covers AC1-AC12.

## Notes
- `load_items` returns only `text` and `done`, so any extra keys in a hand-edited file are dropped on the next save. This is acceptable for the current schema, but the web job should know about it.
- `save_items` calls `fchmod` on the temp file. `mkstemp` already creates it with 0o600, so the call is harmless belt-and-braces.
- Wrapping `OSError` as `TodoError` means a missing parent directory gives a clean `error:` message instead of a traceback.
