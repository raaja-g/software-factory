VERDICT: CHANGES

## Summary
The hardening is solid. The server binds only to loopback, checks Host and Origin, escapes all output, sends a strict CSP and security headers, rejects bad Content-Length and Transfer-Encoding, and caps the body before reading it. One real DoS gap remains: the handler has no socket timeout, so one idle or slow connection blocks the single-threaded server forever.

## Required changes
1. `src/app/web.py:139-144` (`TodoHandler`): set a socket timeout on the handler, for example the class attribute `timeout = 10`. `StreamRequestHandler` applies it with `settimeout`. Right now `timeout` is `None`. The spec requires a single-threaded `HTTPServer`, so any connection that never finishes its request blocks every other request indefinitely. This covers a connection that sends nothing, a partial request line or headers, or a `Content-Length` <= `MAX_BODY` followed by a short body, which hangs in `self.rfile.read(length)` at line 231.
   - I reproduced this on the branch. With one idle `socket.create_connection` open, a normal `GET /` from a second client times out (3 s client timeout, no response).
   - This happens in normal use, not only under attack. Chrome opens speculative preconnect sockets that send nothing. A local process or a web page that makes the browser preconnect to `127.0.0.1:<port>` can also cause it.
   - With a timeout, `handle_one_request` catches the `TimeoutError`, logs "Request timed out" and closes the connection. A timeout raised during the body read in `_read_form` also ends that request without touching the store.
   - Please add a test: open an idle raw socket, then check that a `GET /` from a second client succeeds within a bounded time. Set the timeout small in the test, for example on the bound handler class.

## Notes
- XSS: all item text, error messages and `TodoError` text go through `html.escape(quote=True)`. This includes the `aria-label` attribute and http.server's own `send_error` messages, which can echo request-line content. There is no `<script>`, and the CSP `default-src 'none'` is a second layer of protection. OK.
- CSRF and DNS rebinding: an exact match on a single Host and a single Origin is correct. A `null` Origin (sandboxed iframes, `file://`) is rejected. A missing Origin is allowed, as the spec says. A possible later hardening step is to also reject `Sec-Fetch-Site: cross-site` when it is present, as a backup for clients that omit Origin. This is not required.
- Clickjacking: `frame-ancestors 'none'` covers it. `form-action 'self'` and `base-uri 'none'` are good.
- Request smuggling and body parsing: rejecting `Transfer-Encoding`, duplicate or non-numeric `Content-Length`, and lengths over `MAX_BODY` before reading the body is correct. `parse_qs` uses strict UTF-8. The 10 KB cap bounds the field count.
- No path traversal surface: the server serves no files, and routes are exact string matches. The storage path comes only from `make_server` or `default_path()`.
- No secrets, no new dependencies, and `Server: todo-web` hides the Python version. The 500 page can show the store path inside the `TodoError` message. That is acceptable for a loopback-only personal tool.
- Each POST can add an item of up to about 10 KB with no total cap. Only same-origin clients can do this, so it is acceptable for this scope.
