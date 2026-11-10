# Todo web page (stdlib http.server)

## Goal
Add a tiny local web front end for the existing todo list. Running
`python -m app.web` starts a standard-library `http.server` on the loopback
interface that serves one HTML page. The page lists all todos and lets you add new
ones and mark them done. It uses the same `~/.todo.json` file and the same storage
functions as the CLI (`app.todo`), so the CLI and the web page always show the same
list. The point is a zero-dependency, no-JavaScript browser view of the todos that
is safe to run on a personal machine.

## Stack & conventions
- Python 3.10+, standard library only at runtime (`http.server`, `html`,
  `urllib.parse`, `argparse`). No new runtime dependencies. pytest stays dev-only.
- Code lives in `src/app/` (importable as `app`); tests in `tests/test_*.py`.
- Test command: `make test` (creates `.venv`, runs pytest; `pythonpath = ["src"]`).
- Run from `src/`: `cd src && python3 -m app.web`.
- Reuse `app.todo` (`load_items`, `add_item`, `complete_item`, `default_path`,
  `TodoError`). Do not duplicate storage logic and do not change the storage format.
- Style follows `app.todo`: module docstring, type hints,
  `from __future__ import annotations`, `main(argv) -> int`, `error: <msg>` on
  stderr for user-facing errors.

## Scope
- In scope
  - New module `src/app/web.py` with a request handler, a server factory and a
    `main()` CLI entry point (`python -m app.web [--port N]`).
  - One HTML page at `GET /` that lists todos, has an add form and has a "Done"
    button on each open item.
  - `POST /add` and `POST /done` form endpoints that use Post/Redirect/Get.
  - Basic local-server hardening: bind only to 127.0.0.1, escape all HTML,
    check Host and Origin, cap request bodies, and send security headers.
  - Tests in `tests/test_web.py`.
  - Docs: a "Todo web page" section in `README.md`, `web.py` added to the README
    layout listing, and the run command added to the `CLAUDE.md` Stack section.
- Out of scope
  - JavaScript, external CSS/fonts/assets, or a JSON API.
  - Deleting, editing, un-completing or reordering todos.
  - Binding to non-loopback interfaces (no `--host` option), TLS, auth, sessions
    and CSRF tokens.
  - Live updates or polling. The page shows the file state at request time.
  - Any change to the CLI's behaviour or output, or to the storage format.

## Design

### Files
- **Add** `src/app/web.py`
- **Add** `tests/test_web.py`
- **Change** `README.md` (new section and layout entry) and `CLAUDE.md` (Stack: how
  to run the web page).
- No changes to `src/app/todo.py`, except an optional purely additive helper if
  the builder needs one. All existing tests must still pass unchanged.

### Public API of `app.web`
```python
DEFAULT_PORT = 8000
MAX_BODY = 10_000  # bytes

def render_page(items: list[dict], error: str | None = None) -> str
    """Full HTML document for the todo list (pure; no I/O)."""

def make_server(port: int = DEFAULT_PORT, path: Path | None = None) -> http.server.HTTPServer
    """HTTPServer bound to ("127.0.0.1", port) whose handler reads/writes `path`
    (None -> app.todo.default_path(), resolved per request)."""

def main(argv: list[str] | None = None) -> int
```
- Use a single-threaded `http.server.HTTPServer`, not `ThreadingHTTPServer`. That
  serialises the file read-modify-write per request.
- Give the handler the storage path through a handler subclass or attribute that
  `make_server` creates. Do not use module globals, so tests can pass a temp path.
- `port=0` must work (the OS picks a free port), because tests use it.

### Routes
| Method + path | Behaviour |
|---|---|
| `GET /` (and `HEAD /`) | 200, `render_page(load_items(path))`. |
| `POST /add` | Form field `text`. Calls `add_item(text, path)`, then **303** `Location: /`. Empty or whitespace-only text (or a missing field) returns **400** with the page re-rendered, showing the current list and the error "todo text must not be empty". The file is not changed. |
| `POST /done` | Form field `number`. A decimal integer calls `complete_item(n, path)`, then **303** `Location: /`. A non-integer or missing value returns **400**. An out-of-range number returns **400** with the page re-rendered and the `TodoError` message (e.g. `no todo #9 (have 2)`). The file is not changed. |
| any other path | **404**, small HTML body. |
| `GET /add`, `GET /done` | **405** with `Allow: POST`. |
| `POST /` or other unknown POST paths | **404** (or 405 for `/`). Either is fine, but it must not be 2xx. |

The page is always rendered in full on errors, so the user keeps their context. The
error text sits in an element with `role="alert"`.

### Request handling rules
- **Form parsing:** POST bodies must have
  `Content-Type: application/x-www-form-urlencoded` (parameters such as
  `; charset=utf-8` are allowed). Anything else returns **415**. Parse with
  `urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True)`. Invalid
  UTF-8 returns **400**. Use only the first value of each field.
- **Body size:** a missing or invalid `Content-Length` returns **411** or **400**.
  `Content-Length > MAX_BODY` returns **413**, and the body is not read.
- **Host check (DNS-rebinding defence):** for every request, the `Host` header
  must be `127.0.0.1:<port>` or `localhost:<port>`, where `<port>` is the bound
  port. Otherwise the response is **400** (or 403) and no file I/O happens.
- **Origin check (CSRF defence):** on POST, if an `Origin` header is present, it
  must equal `http://127.0.0.1:<port>` or `http://localhost:<port>`. Otherwise the
  response is **403** and the file is not changed. A missing `Origin` is allowed.
- **Storage errors:** a corrupt or unreadable `~/.todo.json` (any `TodoError`
  from `load_items`) on any route returns **500** with an HTML page that shows the
  escaped error message. The file is never overwritten, which matches the CLI
  guarantee.
- **Response headers** on every HTML response:
  - `Content-Type: text/html; charset=utf-8`
  - `Content-Length`
  - `X-Content-Type-Options: nosniff`
  - `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`
  - `Referrer-Policy: no-referrer`
  - `Cache-Control: no-store`
- Default request logging to stderr is fine. Do not log request bodies.

### Page (`render_page`)
- `<!doctype html>`, `<html lang="en">`, `<meta charset="utf-8">`,
  `<meta name="viewport" content="width=device-width, initial-scale=1">`,
  `<title>Todos</title>`, `<h1>Todos</h1>`.
- Optional error: `<p role="alert" class="error">ESCAPED</p>`.
- Add form: `<form method="post" action="/add">` with a visible
  `<label for="new-todo">New todo</label>`, an
  `<input id="new-todo" name="text" required autofocus autocomplete="off">` and a
  `<button type="submit">Add</button>`.
- List: an `<ol>` with one `<li>` per item, in storage order. The numbers match the
  CLI (1-based).
  - Open item: the escaped text plus
    `<form method="post" action="/done"><input type="hidden" name="number" value="N"><button type="submit" aria-label="Mark #N done: ESCAPED_TEXT">Done</button></form>`.
  - Done item: escaped text inside `<s>` (or with a `done` class that adds
    line-through), plus a visually present "done" marker such as "(done)". Done
    items have no button.
- Empty list: `<p>No todos yet.</p>` instead of the `<ol>`.
- A small inline `<style>` block is fine. No `<script>` anywhere.
- Every item text and error message passes through `html.escape(..., quote=True)`.

### CLI (`main`)
- `python -m app.web [--port N]`, default `8000`, `N` an int from 0 to 65535. An
  invalid value gives argparse exit **2**.
- On start, print `Serving todos at http://127.0.0.1:<port>/ (Ctrl+C to stop)` to
  stdout (with the actual bound port) and flush.
- Ctrl+C (`KeyboardInterrupt`) closes the server and returns **0**.
- If the bind fails (e.g. the port is in use, `OSError`), print `error: <message>`
  to stderr and return **1**.
- `if __name__ == "__main__": raise SystemExit(main())`.

## Acceptance criteria
- [ ] AC1: `GET /` with an empty or missing store returns 200 and
  `text/html; charset=utf-8`, contains `No todos yet.` and the add form
  (`action="/add"`, input `name="text"`), and does **not** create the store file.
- [ ] AC2: `GET /` lists the existing items in order with CLI numbering. Open items
  have a `/done` form with `name="number" value="N"`. Done items are visibly marked
  done and have no Done button.
- [ ] AC3: `POST /add` with `text=  buy milk ` returns 303 `Location: /`, the store
  then contains `{"text": "buy milk", "done": false}` as the last item, and a
  following `GET /` shows it.
- [ ] AC4: `POST /add` with empty or whitespace-only `text` (or no `text` field)
  returns 400, the body contains `todo text must not be empty` inside a
  `role="alert"` element, and the store bytes are unchanged (or the file is still
  absent).
- [ ] AC5: `POST /done` with `number=2` returns 303 `Location: /` and item 2 is
  `done: true`. Completing an already-done item also returns 303 and leaves the
  file bytes unchanged.
- [ ] AC6: `POST /done` with `number` set to `0`, `99`, `abc`, an empty value or
  no field returns 400, and the store is unchanged. The out-of-range case shows
  the `no todo #N (have M)` message.
- [ ] AC7: Item text containing `<script>alert(1)</script>`, `"` and `&` is shown
  escaped (`&lt;script&gt;`, `&quot;`, `&amp;`). The raw `<script>` never appears
  in the response. The page has no `<script>` tags at all.
- [ ] AC8: A corrupt store file (e.g. `{not json`) makes `GET /`, `POST /add` and
  `POST /done` all return 500 with the escaped error message, and the file bytes
  are unchanged.
- [ ] AC9: A POST with `Origin: http://evil.example` returns 403 and the store is
  unchanged. A request with `Host: evil.example` returns 400 or 403. A POST with
  the correct `Origin` succeeds.
- [ ] AC10: A POST with `Content-Length` over 10 000 returns 413. A POST with
  `Content-Type: application/json` returns 415. Neither changes the store.
- [ ] AC11: Unknown paths return 404. `GET /add` returns 405 with `Allow: POST`.
- [ ] AC12: Every HTML response carries the CSP, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer` and `Cache-Control: no-store` headers listed in
  the Design section.
- [ ] AC13: `make_server(port=0, path=...)` binds to `127.0.0.1` only
  (`server.server_address[0] == "127.0.0.1"`).
- [ ] AC14: The CLI and the web page share data. An item added with
  `app.todo.add_item` (or `python -m app.todo add`) appears on `GET /`, and an item
  added through `POST /add` appears in `app.todo.load_items()`. Unicode text
  (`café ☕`) round-trips through the form and the page.
- [ ] AC15: `python -m app.web --port 0` (subprocess, with `HOME` set to a temp
  dir) prints `Serving todos at http://127.0.0.1:<port>/`, serves `GET /` on that
  port, and exits on SIGINT. `--port abc` exits 2. If the port is already in use,
  it prints `error:` to stderr and exits 1.
- [ ] AC16: The existing test suite passes unchanged, and `README.md` documents how
  to run the web page (`cd src && python3 -m app.web [--port N]`, the URL, that it
  binds only to localhost, and that it shares `~/.todo.json` with the CLI).

## Test plan
Run everything with `make test`. New tests go in `tests/test_web.py`.

- **Fixtures:**
  - Set `HOME` to `tmp_path` with monkeypatch, as `test_todo.py` does, so the real
    home is never touched.
  - A `server` fixture calls `make_server(port=0, path=tmp_path / ".todo.json")`,
    runs `serve_forever` in a daemon thread, and yields `(port, path)`. On teardown
    it calls `shutdown()` and `server_close()`.
- **HTTP client:**
  - Use `http.client.HTTPConnection("127.0.0.1", port)`, not `urllib`, so 303
    redirects are not followed and headers such as `Host` and `Origin` can be set.
    `HTTPConnection` sends `Host: 127.0.0.1:<port>` by default.
  - Add a small helper `request(method, path, body=None, headers=None)` that
    returns `(status, headers, text)`. It defaults to the form content type for
    POSTs.
- **How each AC is checked:**
  - AC1–AC6, AC8, AC10, AC11: request-level tests that assert the status, the
    `Location` header and the body substrings. They check file state with
    `json.loads(path.read_text())` or `path.read_bytes()` before and after the
    request, plus `path.exists()`.
  - AC7: a unit test calls `render_page([...])` directly with nasty text, and a
    request-level test adds the same text through `POST /add`.
  - AC9: set the headers explicitly. Use `conn.putrequest(..., skip_host=True)` and
    `putheader("Host", "evil.example")` for the Host case.
  - AC12: parametrize over several responses (200, 303 where HTML is returned, 400
    and 404) and assert the headers.
  - AC13: assert on `server.server_address`.
  - AC14: mix `app.todo.add_item(..., path=...)` and HTTP calls on the same path.
    Post `text=caf%C3%A9+%E2%98%95` and check that `GET /` contains `café ☕`.
  - AC15: `subprocess.Popen([sys.executable, "-m", "app.web", "--port", "0"],
    cwd=SRC_DIR, env={..., "HOME": tmp})`. Read the first stdout line, parse the
    port, `GET /`, then `send_signal(SIGINT)` and assert exit code 0 within a
    timeout. For the port-in-use case, bind a socket to `127.0.0.1:0` first, pass
    its port, and assert exit 1 with `error:` on stderr. `--port abc` should exit
    2.
  - AC16: `make test` is green. The README section is reviewed manually.
