# Fix: same-origin form POSTs refused with 403 (Origin: null)

## Goal
Submitting the **Add** or **Done** form on the local todo page (`python -m app.web`)
in a real browser fails with `403 cross-origin request refused`. The page is served
with `Referrer-Policy: no-referrer`; per the Fetch spec ("serialize a request
origin"), a non-GET/HEAD, non-CORS request whose referrer policy is `no-referrer`
gets `Origin: null`, even when it is same-origin. `_check_origin` correctly rejects
`Origin: null`, so every browser form POST is refused. Fix it by changing the
policy to `Referrer-Policy: same-origin` (which never nulls a same-origin
request's Origin and still sends no referrer cross-origin), keep rejecting
`Origin: null`, and add regression tests so a future policy change that brings
`Origin: null` back fails the suite.

## Stack & conventions
- Python 3.10+, standard library only at runtime. Code in `src/app/`, tests in
  `tests/` (pytest, `pythonpath = ["src"]`).
- Test command: `make test` (creates `.venv`, installs `requirements-dev.txt`,
  runs `python -m pytest`). This must keep needing only pytest.
- Web server is `src/app/web.py` (`http.server`, no JavaScript in the page);
  its tests are `tests/test_web.py` (real server on port 0 via the `server` /
  `port` / `store` fixtures, `request()` helper using `http.client`).
- Work on branch `factory/004-fix-origin-null-403`. Do not edit `factory/`.

## Scope
- In scope
  - `SECURITY_HEADERS["Referrer-Policy"]` changed from `no-referrer` to
    `same-origin` in `src/app/web.py` (and the module docstring if it mentions it).
  - `_check_origin` behaviour unchanged: missing Origin allowed; exactly one
    Origin equal to `http://127.0.0.1:<port>` or `http://localhost:<port>`
    (case-insensitive) allowed; anything else, **including `null`**, is 403.
  - Update the existing header assertion in `tests/test_web.py`
    (`test_security_headers` currently asserts `no-referrer`).
  - New deterministic regression test(s) that model the browser's Origin
    computation from the served `Referrer-Policy` (always run under `make test`).
  - Optional real-browser test (Playwright) for add and done, skipped cleanly
    when Playwright or a browser is not available; separate opt-in dependency
    file and Make target so `make test` stays pytest-only.
  - README: one-line note that the page sends `Referrer-Policy: same-origin`
    and that `Origin: null` POSTs are refused; document `make test-browser`.
- Out of scope
  - Accepting `Origin: null`, relaxing Host/Origin checks, adding CSRF tokens,
    adding `Sec-Fetch-Site` checks, adding JavaScript, any other header change.
  - Changing CLI/storage code.

## Design

### `src/app/web.py`
- `SECURITY_HEADERS["Referrer-Policy"] = "same-origin"`. Add a short comment:
  `no-referrer` would make browsers send `Origin: null` on same-origin form
  POSTs (Fetch spec), which `_check_origin` refuses.
- No other logic changes. The rendered HTML must not introduce a
  `<meta name="referrer">` or `referrerpolicy=` attribute.

### `tests/test_web.py`
1. Update `test_security_headers`: `Referrer-Policy == "same-origin"`.
2. Add a helper implementing the Fetch spec's origin serialization for a
   form POST (method not GET/HEAD, mode `navigate`, so not CORS):
   ```
   def browser_post_origin(policy, page_origin, target_origin) -> str
   ```
   - `policy` is the effective referrer policy: last recognised token of the
     comma-separated `Referrer-Policy` header value (unknown tokens ignored;
     no recognised token -> default `strict-origin-when-cross-origin`).
   - Returns `"null"` when:
     - `no-referrer`;
     - `same-origin` and page and target origins differ;
     - `no-referrer-when-downgrade`, `strict-origin`,
       `strict-origin-when-cross-origin` and page is `https:` but target is not.
   - Otherwise returns `page_origin`.
3. New test `test_referrer_policy_does_not_null_same_origin_post`
   (parametrize host `127.0.0.1` / `localhost`): `GET /`, read the
   `Referrer-Policy` header, compute
   `origin = browser_post_origin(policy, f"http://{host}:{port}", same)`,
   assert `origin != "null"`, then POST `/add` with `Host: {host}:{port}` and
   that `Origin`; assert 303 and the item is stored. Do the same for `/done`.
   This test fails if the header goes back to `no-referrer`.
4. New test `test_browser_post_origin_model`: unit tests of the helper itself —
   `no-referrer` -> `"null"`; `same-origin` same-origin -> page origin;
   `same-origin` cross-origin -> `"null"`; `strict-origin-when-cross-origin`
   http->http -> page origin; multi-token value `"no-referrer, same-origin"`
   -> uses `same-origin`.
5. Keep `test_post_foreign_origin_403` asserting `Origin: null` -> 403 and the
   store unchanged (already present; must still pass).
6. New test: the `GET /` HTML contains neither `name="referrer"` nor
   `referrerpolicy`.

### `tests/test_browser.py` (new, optional)
- `playwright = pytest.importorskip("playwright.sync_api")`.
- Module fixture starts `make_server(port=0, path=tmp store)` in a thread (same
  pattern as `tests/test_web.py`, with `HOME` pointed at a temp dir) and launches
  Chromium headless: try `p.chromium.launch()`, else
  `p.chromium.launch(channel="chrome")`; if both raise, `pytest.skip(...)`.
- `test_browser_add_and_done`: open `http://127.0.0.1:<port>/`, fill
  `#new-todo` with `buy milk`, click **Add**; assert final URL is `/`, the page
  shows `buy milk` and no `cross-origin request refused`, and the store has the
  item. Click the item's **Done** button; assert the item renders struck
  through with `(done)` and the store has `done: true`. Also record the request
  headers of the POSTs (`page.on("request")`) and assert `Origin` is
  `http://127.0.0.1:<port>` (not `null`).
- New `requirements-browser.txt`: `-r requirements-dev.txt` plus `playwright`.
- `Makefile`: new `test-browser` target that installs
  `requirements-browser.txt` into `.venv`, runs
  `.venv/bin/python -m playwright install chromium` (best effort; Chrome
  channel fallback covers machines with Google Chrome), then
  `.venv/bin/python -m pytest tests/test_browser.py`. Add it to `help` and
  `.PHONY`. `make test` is unchanged and must not require Playwright (the
  browser test skips there).

### `README.md`
- In the web-page bullet list: POSTs whose `Origin` is foreign or `null` are
  refused; the page sends `Referrer-Policy: same-origin` so browsers send the
  real Origin on its own forms.
- In "Running tests": `make test-browser` runs the optional real-browser test.

## Acceptance criteria
- [ ] AC1 — Every response (200, 303, 400, 403, 404, 405, 415, 500) carries
  `Referrer-Policy: same-origin`; the other security headers are unchanged.
- [ ] AC2 — A POST to `/add` or `/done` with `Origin: http://127.0.0.1:<port>`
  or `http://localhost:<port>` (matching Host) returns 303 and changes the store.
- [ ] AC3 — A POST with `Origin: null`, a foreign origin, or a wrong port still
  returns 403 and leaves the store byte-for-byte unchanged; a POST with no
  Origin is still accepted.
- [ ] AC4 — A regression test derives the browser's Origin from the served
  `Referrer-Policy` header via the Fetch-spec model and fails if that Origin
  would be `null` for a same-origin form POST (verified by temporarily setting
  the header back to `no-referrer`: the test fails).
- [ ] AC5 — The rendered page contains no `<meta name="referrer">` and no
  `referrerpolicy` attribute.
- [ ] AC6 — With Playwright and a Chromium/Chrome available,
  `make test-browser` adds a todo and marks it done through real form
  submissions, with no 403, and the POSTs carry the real page Origin.
  Without Playwright, `make test` passes and the browser test is reported as
  skipped.
- [ ] AC7 — `make test` passes with only `requirements-dev.txt` installed; all
  pre-existing tests still pass (with the header assertion updated).

## Test plan
- AC1: `test_security_headers` (updated) and `test_security_headers_on_403_and_500`
  (add a `Referrer-Policy == "same-origin"` assertion).
- AC2: existing `test_post_correct_origin_ok` plus the new
  `test_referrer_policy_does_not_null_same_origin_post` (add and done).
- AC3: existing `test_post_foreign_origin_403` (includes `Origin: null`) and
  existing no-Origin tests (`test_post_add`, `test_post_done`).
- AC4: `test_referrer_policy_does_not_null_same_origin_post` +
  `test_browser_post_origin_model`; builder confirms manually that reverting the
  header to `no-referrer` makes the former fail, then restores it.
- AC5: new HTML-content test on `GET /`.
- AC6: `tests/test_browser.py` via `make test-browser`; under `make test` it
  shows as skipped.
- AC7: `make test` (exit 0).
