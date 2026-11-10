# Build — 004-fix-origin-null-403

## Round 1
### What changed
- `src/app/web.py` — `SECURITY_HEADERS["Referrer-Policy"]` is now `same-origin` (was `no-referrer`), with a comment explaining why; the module docstring mentions it. `_check_origin` is unchanged (it still refuses `Origin: null`).
- `tests/test_web.py` — `test_security_headers` and `test_security_headers_on_403_and_500` now assert `same-origin`. New helpers `effective_referrer_policy` (last recognised token, default `strict-origin-when-cross-origin`) and `browser_post_origin(policy, page_origin, target_origin)`, which models the Fetch spec's "serialize a request origin" for a navigate-mode form POST. New tests: `test_browser_post_origin_model`, `test_referrer_policy_does_not_null_same_origin_post[127.0.0.1|localhost]` (add + done) and `test_page_has_no_referrer_override`.
- `tests/test_browser.py` (new) — optional Playwright test `test_browser_add_and_done`. It runs the server in a thread with a temp HOME, launches Chromium and falls back to `channel="chrome"`, then adds `buy milk`, marks it done, and checks the URL, page text, the store and the POST `Origin` headers. It is skipped when Playwright or a browser is missing.
- `requirements-browser.txt` (new) — `-r requirements-dev.txt` + `playwright`.
- `Makefile` — new `test-browser` target, which installs browser deps through a stamp file, runs `playwright install chromium` (best effort, error ignored) and then runs pytest on `tests/test_browser.py`. Added to `help` and `.PHONY`. `make test` is unchanged.
- `README.md` — web bullets now say that foreign or `null` Origin POSTs are refused and that the page sends `Referrer-Policy: same-origin`. "Running tests" documents `make test-browser`, and the layout lists the new file and target.
- `CLAUDE.md` — Stack section has a line for the optional `make test-browser`.

### How to run / test
`make test` (required, pytest only). Optional: `make test-browser`.

### Acceptance criteria
- [x] AC1 — `test_security_headers` (200/303/400/404/405/415) and `test_security_headers_on_403_and_500` (403, 500) assert `Referrer-Policy: same-origin`. The other header assertions are unchanged.
- [x] AC2 — `test_post_correct_origin_ok[127.0.0.1|localhost]` and `test_referrer_policy_does_not_null_same_origin_post[127.0.0.1|localhost]` (both `/add` and `/done` return 303 and change the store).
- [x] AC3 — `test_post_foreign_origin_403` (foreign origin, `null`, wrong port: 403, store bytes unchanged). `test_post_add` and `test_post_done` cover POSTs with no Origin.
- [x] AC4 — `test_referrer_policy_does_not_null_same_origin_post` and `test_browser_post_origin_model`. Checked by hand: with the header set back to `no-referrer`, both parametrizations failed (`Referrer-Policy 'no-referrer' nulls same-origin Origin`). The header was then restored.
- [x] AC5 — `test_page_has_no_referrer_override`.
- [x] AC6 — `make test-browser` on this machine: `tests/test_browser.py . 1 passed` (Playwright Chromium, real form submissions, both POSTs carried `Origin: http://127.0.0.1:<port>`). I also checked by hand that with `no-referrer` the browser test fails: the page stayed on `/add`, which is the 403. Without Playwright installed, `make test` gave `136 passed, 1 skipped` (`could not import 'playwright.sync_api'`).
- [x] AC7 — `make test` exits 0. The 1 skipped result above was before Playwright was installed. After `make test-browser` installed Playwright into `.venv`, the browser test also runs under `make test` (137 passed).

### Note
When you swap `no-referrer` and `same-origin` (both 11 chars) within one second, CPython can keep using a stale `.pyc`, because size and mtime match. Clear `__pycache__` (or `make clean`) if you repeat the AC4 revert check.

### Test output
```
============================= 137 passed in 3.78s ==============================
```
(before Playwright was installed: `136 passed, 1 skipped in 2.83s`; `make test-browser`: `1 passed in 5.48s`)

### Commits
```
f173826 Add optional Playwright browser test (make test-browser) and docs
e9b490d Send Referrer-Policy: same-origin so browser form POSTs keep their Origin
```
