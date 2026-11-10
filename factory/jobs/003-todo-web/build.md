# Build — 003-todo-web

## Round 1
### What changed
- `src/app/web.py` (new): the stdlib `http.server` todo page.
  - `render_page` is pure and escapes every string with `html.escape(..., quote=True)`. It has no `<script>`.
  - `TodoHandler` handles `GET`/`HEAD /`, `POST /add` and `POST /done` using Post/Redirect/Get (303 to `/`).
  - `make_server` builds a handler subclass that carries `store_path` (no module globals). It binds `("127.0.0.1", port)` with a single-threaded `HTTPServer`.
  - `main` provides `--port N` (0-65535, argparse exit 2 otherwise), prints the "Serving todos at ..." line with a flush, returns 0 on Ctrl+C, and on bind `OSError` prints `error: ...` and returns 1.
  - Hardening:
    - Every request needs a single `Host` of `127.0.0.1:<port>` or `localhost:<port>`, otherwise 400.
    - On POST, an `Origin` that is present but foreign returns 403.
    - Only `application/x-www-form-urlencoded` is accepted, otherwise 415.
    - A missing `Content-Length` (or chunked `Transfer-Encoding`) returns 411. An invalid one returns 400. More than `MAX_BODY` returns 413 without reading the body.
    - Invalid UTF-8, in the raw body or percent-encoded, returns 400 (`parse_qs(..., errors="strict")`).
    - A `TodoError` from storage returns 500 with the escaped message, and the file is never written.
    - Every response carries the CSP, nosniff, no-referrer and no-store headers. This includes http.server's own errors such as 501, through an overridden `send_error`. `Server` is set to `todo-web`, so the Python version is not shown.
  - `/done` accepts only 1-18 ASCII digits. Anything else (including `-1`, `1.0` and huge numbers) returns 400 with the page re-rendered and the error "todo number must be a whole number".
  - An out-of-range number returns 400 with the `no todo #N (have M)` message from `complete_item`.
  - `POST /` returns 405 (`Allow: GET, HEAD`). Other unknown paths return 404.
- `tests/test_web.py` (new): 71 tests covering AC1–AC15. They use a threaded `make_server(port=0)` fixture, an `http.client` request helper, raw `putrequest` for Host and Content-Length edge cases, and subprocess tests for the CLI.
- `README.md`: adds a "Todo web page" section and a `web.py` entry in the layout listing.
- `CLAUDE.md`: adds the web page run command to the Stack section.
- `src/app/todo.py` is unchanged.

Note: on Python 3.14, `http.server` collapses a leading `//` in the request path to `/`, so `GET //` serves the page. That is harmless. Route matching splits the path on `?` and does not use `urlsplit`, because `urlsplit` would read `//x` as a host.

### How to run / test
`make test`. To run the server: `cd src && python3 -m app.web [--port N]`.

### Acceptance criteria
- [x] AC1: verified by `test_get_empty_store` and `test_head_root`.
- [x] AC2: verified by `test_get_lists_items_in_order`.
- [x] AC3: verified by `test_post_add` and `test_post_add_creates_store`.
- [x] AC4: verified by `test_post_add_empty_text[*]` (empty, whitespace, empty body, missing field) and `test_post_add_empty_text_keeps_file`.
- [x] AC5: verified by `test_post_done` and `test_post_done_already_done_unchanged` (same bytes and same mtime).
- [x] AC6: verified by `test_post_done_invalid[*]` (0, 99, abc, empty, missing, -1, 1.0), `test_post_done_out_of_range_message[*]` and `test_post_done_huge_number`.
- [x] AC7: verified by `test_render_page_escapes`, `test_render_page_structure` and `test_post_add_nasty_text_escaped`.
- [x] AC8: verified by `test_corrupt_store_500[*]` (GET /, POST /add, POST /done, including the empty-text and bad-number paths) and `test_corrupt_store_message_escaped`.
- [x] AC9: verified by `test_post_foreign_origin_403`, `test_post_correct_origin_ok[*]`, `test_bad_host_rejected[*]`, `test_missing_host_rejected` and `test_localhost_host_accepted`.
- [x] AC10: verified by `test_body_too_large_413` (also with a body that is declared but never sent), `test_wrong_content_type_415`, `test_missing_and_invalid_content_length`, `test_invalid_utf8_400` and `test_form_content_type_with_charset`.
- [x] AC11: verified by `test_unknown_get_404[*]`, `test_get_post_only_405[*]`, `test_unknown_post_not_2xx[*]` and `test_unsupported_method`.
- [x] AC12: verified by `test_security_headers[*]` (200 GET and HEAD, 303, 400, 404, 405, 415) and `test_security_headers_on_403_and_500`.
- [x] AC13: verified by `test_make_server_binds_loopback` and `test_make_server_default_path_resolved_per_request`.
- [x] AC14: verified by `test_shared_with_cli`, `test_shared_with_cli_subprocess` and `test_unicode_round_trip`.
- [x] AC15: verified by `test_cli_serves_and_stops_on_sigint`, `test_cli_bad_port_exits_2` (abc, 70000, -1), `test_cli_port_in_use_exits_1` and `test_main_port_in_use_returns_1`.
- [x] AC16: `make test` passes 128 tests, and the 57 existing tests are unchanged. The README section covers the run command, the URL, binding to localhost only and sharing `~/.todo.json`.

### Test output
```
tests/test_web.py ...................................................... [ 86%]
.................                                                        [100%]

============================= 128 passed in 1.70s ==============================
```

### Commits
```
d1fa5c2 Add local todo web page (python -m app.web)
```

## Round 2
Reviews in `round-1/`: code PASS, ui PASS, ux PASS, security CHANGES (1 required item).

### Requested changes
1. **Security: no socket timeout, so a stalled client blocks the single-threaded server.** Done.
   - Added `REQUEST_TIMEOUT = 10.0` in `src/app/web.py` and set `TodoHandler.timeout = REQUEST_TIMEOUT`. `StreamRequestHandler` applies it with `settimeout()`.
   - On Python 3.14, the `except TimeoutError` in `handle_one_request` wraps the whole handler call, including `method()`. So a timeout during the request line, the headers or the body read in `_read_form` logs "Request timed out", closes the connection and never touches the store.
   - New tests in `tests/test_web.py`:
     - `test_handler_has_timeout` checks that the bound handler has a positive timeout.
     - `test_stalled_client_does_not_block_server[idle|partial-headers|short-body]` sets the handler timeout to 0.3 s and opens a stalled raw socket: one idle, one with partial headers, and one POST that claims `Content-Length: 100` but sends only part of the body. A `GET /` from a second client must then return 200. The store must still be absent afterwards.
   - I checked the tests against the bug. With the timeout set to `None`, all 4 tests fail (a client timeout or the assert). With the fix they pass.

### Not done (optional notes from the security review)
- Rejecting `Sec-Fetch-Site: cross-site` is not done. The review marked it "not required". The spec only asks for the Origin check, and a missing Origin stays allowed as the spec says.

### How to run / test
`make test`

### Test output
```
============================= 132 passed in 2.91s ==============================
```

### Commits
```
7b3ec1a Add request socket timeout so stalled clients cannot block the server
d1fa5c2 Add local todo web page (python -m app.web)
```
