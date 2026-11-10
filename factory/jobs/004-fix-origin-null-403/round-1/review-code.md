VERDICT: PASS

## Summary
Header changed to `same-origin` with `_check_origin` untouched; regression tests, Fetch-spec model, optional Playwright test and Make target all match the spec. `make test` run by me: 137 passed.

## Notes
- The model's `no-referrer` / cross-origin `same-origin` branches are correct per spec; unit-tested edge cases (multi-token, unknown token, empty) are a good addition.
- `tests/test_browser.py` runs under `make test` whenever Playwright is installed in `.venv` (as it is now); fine, but it will be slower there.
- Makefile `-` prefix on `playwright install` ignores all failures, which is intended (Chrome fallback).
