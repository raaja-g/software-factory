VERDICT: PASS

## Summary
`src/app/web.py` follows the spec closely and is clean and well structured. `make test` passes with 128 passed, and `tests/test_web.py` covers AC1-AC15 with request-level, unit and subprocess tests.

## Notes
- `_post_done` loads the items and then `complete_item` loads them again. The server is single-threaded, so this is not a race. It is only one extra read, and the 500-versus-400 split it allows is sensible.
- Host and Origin matching is strict: exactly one header, lowercased. This is stricter than the spec, which is fine.
- `send_error` is overridden so that http.server's own errors also carry the security headers. Good.
