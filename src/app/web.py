"""Local todo web page for ``python -m app.web [--port N]``.

Serves one HTML page (no JavaScript) from a standard-library
``http.server`` bound to ``127.0.0.1`` only. The page lists the todos stored
in ``~/.todo.json`` and lets you add new ones and mark them done. It uses the
storage functions from ``app.todo``, so the CLI and the web page always share
the same list.

Routes: ``GET /`` (and ``HEAD /``) renders the page; ``POST /add`` (field
``text``) and ``POST /done`` (field ``number``) change the list and redirect
back with ``303 See Other`` (Post/Redirect/Get).

Because it is meant for a personal machine, every request is checked for a
loopback ``Host`` header (DNS-rebinding defence), POSTs with a foreign
``Origin`` are refused (CSRF defence), request bodies are capped at
``MAX_BODY`` bytes, all text is HTML-escaped and every response carries a
strict Content-Security-Policy.
"""

from __future__ import annotations

import argparse
import html
import http.server
import re
import sys
import urllib.parse
from pathlib import Path

from app.todo import TodoError, add_item, complete_item, load_items

DEFAULT_PORT = 8000
MAX_BODY = 10_000  # bytes

FORM_TYPE = "application/x-www-form-urlencoded"
EMPTY_TEXT_ERROR = "todo text must not be empty"
BAD_NUMBER_ERROR = "todo number must be a whole number"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
        "frame-ancestors 'none'; base-uri 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}

_NUMBER_RE = re.compile(r"[0-9]{1,18}")

_STYLE = """\
body { font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto;
       padding: 0 1rem; line-height: 1.5; }
.error { color: #a40000; font-weight: bold; }
form.add { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 1.5rem; }
form.add input { flex: 1; padding: 0.3rem; font-size: 1rem; }
li { margin: 0.4rem 0; }
li form { display: inline; margin-left: 0.5rem; }
li.done s { color: #555; }
.tag { color: #555; font-size: 0.9em; }
"""


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _document(title: str, body: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_esc(title)}</title>\n"
        f"<style>\n{_STYLE}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}"
        "</body>\n"
        "</html>\n"
    )


def _render_item(number: int, item: dict) -> str:
    text = _esc(item["text"])
    if item["done"]:
        return f'<li class="done"><s>{text}</s> <span class="tag">(done)</span></li>\n'
    return (
        f"<li>{text}"
        '<form method="post" action="/done">'
        f'<input type="hidden" name="number" value="{number}">'
        f'<button type="submit" aria-label="Mark #{number} done: {text}">Done</button>'
        "</form></li>\n"
    )


def render_page(items: list[dict], error: str | None = None) -> str:
    """Full HTML document for the todo list (pure; no I/O)."""
    parts = ["<h1>Todos</h1>\n"]
    if error is not None:
        parts.append(f'<p role="alert" class="error">{_esc(error)}</p>\n')
    parts.append(
        '<form class="add" method="post" action="/add">'
        '<label for="new-todo">New todo</label> '
        '<input id="new-todo" name="text" required autofocus autocomplete="off"> '
        '<button type="submit">Add</button>'
        "</form>\n"
    )
    if items:
        parts.append("<ol>\n")
        parts.extend(_render_item(n, it) for n, it in enumerate(items, start=1))
        parts.append("</ol>\n")
    else:
        parts.append("<p>No todos yet.</p>\n")
    return _document("Todos", "".join(parts))


def _render_message(title: str, message: str) -> str:
    """Small standalone page for errors that do not show the list."""
    body = (
        f"<h1>{_esc(title)}</h1>\n"
        f'<p role="alert" class="error">{_esc(message)}</p>\n'
        '<p><a href="/">Back to the todo list</a></p>\n'
    )
    return _document(title, body)


class _Reject(Exception):
    """Abort request handling with an HTML error response."""

    def __init__(self, status: int, message: str, headers: dict | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.headers = headers or {}


class TodoHandler(http.server.BaseHTTPRequestHandler):
    """Request handler for the todo page. ``store_path`` is set per server."""

    store_path: Path | None = None
    server_version = "todo-web"
    sys_version = ""

    # -- response helpers -------------------------------------------------

    def _send_html(
        self, status: int, page: str, headers: dict | None = None
    ) -> None:
        data = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_error(
        self, code: int, message: str | None = None, explain: str | None = None
    ) -> None:
        """Error responses from ``http.server`` itself, with our headers."""
        try:
            short, _long = self.responses[code]
        except KeyError:
            short = "Error"
        self.close_connection = True
        self._send_html(code, _render_message(f"{code} {short}", message or short))

    def _reject(self, exc: _Reject) -> None:
        short = self.responses.get(exc.status, ("Error",))[0]
        self.close_connection = True
        self._send_html(
            exc.status,
            _render_message(f"{exc.status} {short}", exc.message),
            exc.headers,
        )

    def _redirect_home(self) -> None:
        self._send_html(
            303,
            _render_message("303 See Other", "Done. Returning to the list."),
            {"Location": "/"},
        )

    def _page_with_error(self, status: int, error: str) -> None:
        """Re-render the full page with ``error`` (500 if the store is bad)."""
        try:
            items = load_items(self.store_path)
        except TodoError as exc:
            raise _Reject(500, str(exc)) from exc
        self._send_html(status, render_page(items, error))

    # -- request checks ---------------------------------------------------

    def _allowed_hosts(self) -> tuple[str, ...]:
        port = self.server.server_address[1]
        return (f"127.0.0.1:{port}", f"localhost:{port}")

    def _check_host(self) -> None:
        hosts = self.headers.get_all("Host") or []
        if len(hosts) != 1 or hosts[0].strip().lower() not in self._allowed_hosts():
            raise _Reject(400, "invalid Host header")

    def _check_origin(self) -> None:
        origins = self.headers.get_all("Origin") or []
        if not origins:
            return
        allowed = tuple(f"http://{h}" for h in self._allowed_hosts())
        if len(origins) != 1 or origins[0].strip().lower() not in allowed:
            raise _Reject(403, "cross-origin request refused")

    def _read_form(self) -> dict[str, str]:
        ctype = self.headers.get("Content-Type", "")
        if ctype.split(";", 1)[0].strip().lower() != FORM_TYPE:
            raise _Reject(415, f"expected Content-Type {FORM_TYPE}")
        if self.headers.get("Transfer-Encoding"):
            raise _Reject(411, "Content-Length required")
        lengths = self.headers.get_all("Content-Length") or []
        if not lengths:
            raise _Reject(411, "Content-Length required")
        if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,18}", lengths[0].strip()):
            raise _Reject(400, "invalid Content-Length")
        length = int(lengths[0].strip())
        if length > MAX_BODY:
            raise _Reject(413, f"request body larger than {MAX_BODY} bytes")
        body = self.rfile.read(length)
        if len(body) != length:
            raise _Reject(400, "incomplete request body")
        try:
            fields = urllib.parse.parse_qs(
                body.decode("utf-8"),
                keep_blank_values=True,
                encoding="utf-8",
                errors="strict",
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise _Reject(400, "request body is not valid UTF-8 form data") from exc
        return {name: values[0] for name, values in fields.items()}

    # -- routes -----------------------------------------------------------

    def _handle(self, method: str) -> None:
        try:
            self._check_host()
            path = self.path.split("?", 1)[0]
            if method in ("GET", "HEAD"):
                self._route_get(path)
            else:
                self._route_post(path)
        except _Reject as exc:
            self._reject(exc)

    def _route_get(self, path: str) -> None:
        if path in ("/add", "/done"):
            raise _Reject(405, "use POST", {"Allow": "POST"})
        if path != "/":
            raise _Reject(404, "page not found")
        try:
            items = load_items(self.store_path)
        except TodoError as exc:
            raise _Reject(500, str(exc)) from exc
        self._send_html(200, render_page(items))

    def _route_post(self, path: str) -> None:
        if path == "/":
            raise _Reject(405, "use GET", {"Allow": "GET, HEAD"})
        if path not in ("/add", "/done"):
            raise _Reject(404, "page not found")
        self._check_origin()
        form = self._read_form()
        if path == "/add":
            self._post_add(form)
        else:
            self._post_done(form)

    def _post_add(self, form: dict[str, str]) -> None:
        text = form.get("text", "")
        if not text.strip():
            self._page_with_error(400, EMPTY_TEXT_ERROR)
            return
        try:
            add_item(text, self.store_path)
        except TodoError as exc:
            # Text is non-empty, so this is a storage (read/write) failure.
            raise _Reject(500, str(exc)) from exc
        self._redirect_home()

    def _post_done(self, form: dict[str, str]) -> None:
        raw = form.get("number", "").strip()
        if not _NUMBER_RE.fullmatch(raw):
            self._page_with_error(400, BAD_NUMBER_ERROR)
            return
        number = int(raw)
        try:
            items = load_items(self.store_path)
        except TodoError as exc:
            raise _Reject(500, str(exc)) from exc
        try:
            complete_item(number, self.store_path)
        except TodoError as exc:
            if 1 <= number <= len(items):
                raise _Reject(500, str(exc)) from exc  # storage failure
            self._send_html(400, render_page(items, str(exc)))
            return
        self._redirect_home()

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        self._handle("GET")

    def do_HEAD(self) -> None:  # noqa: N802
        self._handle("HEAD")

    def do_POST(self) -> None:  # noqa: N802
        self._handle("POST")


def make_server(
    port: int = DEFAULT_PORT, path: Path | None = None
) -> http.server.HTTPServer:
    """HTTPServer bound to ("127.0.0.1", port) whose handler reads/writes `path`
    (None -> app.todo.default_path(), resolved per request)."""
    handler = type(
        "BoundTodoHandler",
        (TodoHandler,),
        {"store_path": None if path is None else Path(path)},
    )
    return http.server.HTTPServer(("127.0.0.1", port), handler)


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid port: {value!r}") from None
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"port must be 0-65535, got {port}")
    return port


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.web",
        description="Serve the todo list as a local web page on 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        type=_port,
        default=DEFAULT_PORT,
        metavar="N",
        help=f"port to listen on (default {DEFAULT_PORT}; 0 picks a free port)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the web server until Ctrl+C; return 0, or 1 if the bind fails."""
    args = _build_parser().parse_args(argv)
    try:
        server = make_server(args.port)
    except OSError as exc:
        print(f"error: cannot listen on 127.0.0.1:{args.port}: {exc}", file=sys.stderr)
        return 1
    port = server.server_address[1]
    print(f"Serving todos at http://127.0.0.1:{port}/ (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
