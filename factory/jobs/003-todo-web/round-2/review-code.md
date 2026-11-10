VERDICT: PASS

## Summary
The round-2 change is a minimal, correct fix: `REQUEST_TIMEOUT = 10.0` set as `TodoHandler.timeout`. `make test` gives 132 passed.

## Notes
- The new tests cover idle, partial-headers and short-body stalls. They lower the class timeout to 0.3 s so they stay fast.
- `test_stalled_client_does_not_block_server` mutates `RequestHandlerClass.timeout`. That class is created per `make_server` call, so the change does not leak between tests.
