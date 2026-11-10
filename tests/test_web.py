"""Tests for the local todo web page (``app.web``)."""

from __future__ import annotations

import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path

import pytest

from app import web
from app.todo import add_item, load_items, save_items
from app.web import MAX_BODY, make_server, render_page

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
FORM = "application/x-www-form-urlencoded"
CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
    "frame-ancestors 'none'; base-uri 'none'"
)


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Point HOME at an empty temp dir so no test touches the real home."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def server(home):
    path = home / ".todo.json"
    srv = make_server(port=0, path=path)
    thread = threading.Thread(target=srv.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    try:
        yield srv.server_address[1], path
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


@pytest.fixture
def port(server):
    return server[0]


@pytest.fixture
def store(server):
    return server[1]


def request(port, method, path, body=None, headers=None):
    """Send one request; return ``(status, headers, text)``."""
    headers = dict(headers or {})
    if isinstance(body, str):
        body = body.encode("utf-8")
    if method == "POST":
        headers.setdefault("Content-Type", FORM)
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, resp.headers, data.decode("utf-8")
    finally:
        conn.close()


def raw_request(port, lines, body=b""):
    """Send hand-built header lines (for odd Host / Content-Length cases)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        method, path = lines[0]
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for name, value in lines[1:]:
            conn.putheader(name, value)
        conn.endheaders(body or None)
        resp = conn.getresponse()
        return resp.status, resp.headers, resp.read().decode("utf-8")
    finally:
        conn.close()


def form(**fields):
    return urllib.parse.urlencode(fields)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def seed(path, *items):
    save_items([{"text": t, "done": d} for t, d in items], path)


# AC1
def test_get_empty_store(port, store):
    status, headers, text = request(port, "GET", "/")
    assert status == 200
    assert headers["Content-Type"] == "text/html; charset=utf-8"
    assert int(headers["Content-Length"]) == len(text.encode("utf-8"))
    assert "No todos yet." in text
    assert 'action="/add"' in text
    assert 'name="text"' in text
    assert "<ol>" not in text
    assert not store.exists()


def test_head_root(port, store):
    status, headers, text = request(port, "HEAD", "/")
    assert status == 200
    assert text == ""
    assert headers["Content-Type"] == "text/html; charset=utf-8"


# AC2
def test_get_lists_items_in_order(port, store):
    seed(store, ("first", False), ("second", True), ("third", False))
    status, _, text = request(port, "GET", "/")
    assert status == 200
    assert text.index("first") < text.index("second") < text.index("third")
    assert text.count("<li") == 3
    assert 'name="number" value="1"' in text
    assert 'name="number" value="3"' in text
    assert 'value="2"' not in text
    assert "<s>second</s>" in text
    assert "(done)" in text
    assert text.count(">Done</button>") == 2
    assert 'aria-label="Mark #3 done: third"' in text


# AC3
def test_post_add(port, store):
    seed(store, ("old", False))
    status, headers, _ = request(port, "POST", "/add", form(text="  buy milk "))
    assert status == 303
    assert headers["Location"] == "/"
    assert read_json(store)["items"][-1] == {"text": "buy milk", "done": False}
    _, _, text = request(port, "GET", "/")
    assert "buy milk" in text
    assert 'name="number" value="2"' in text


def test_post_add_creates_store(port, store):
    status, _, _ = request(port, "POST", "/add", form(text="x"))
    assert status == 303
    assert read_json(store) == {"items": [{"text": "x", "done": False}]}


# AC4
@pytest.mark.parametrize("body", [form(text=""), form(text="   \t "), "", "other=1"])
def test_post_add_empty_text(port, store, body):
    status, _, text = request(port, "POST", "/add", body)
    assert status == 400
    assert '<p role="alert" class="error">todo text must not be empty</p>' in text
    assert "<h1>Todos</h1>" in text
    assert not store.exists()


def test_post_add_empty_text_keeps_file(port, store):
    seed(store, ("keep", False))
    before = store.read_bytes()
    status, _, text = request(port, "POST", "/add", form(text=" "))
    assert status == 400
    assert "keep" in text  # list still shown
    assert store.read_bytes() == before


# AC5
def test_post_done(port, store):
    seed(store, ("a", False), ("b", False))
    status, headers, _ = request(port, "POST", "/done", form(number="2"))
    assert status == 303
    assert headers["Location"] == "/"
    assert read_json(store)["items"] == [
        {"text": "a", "done": False},
        {"text": "b", "done": True},
    ]


def test_post_done_already_done_unchanged(port, store):
    seed(store, ("a", False), ("b", True))
    before = store.read_bytes()
    mtime = store.stat().st_mtime_ns
    status, headers, _ = request(port, "POST", "/done", form(number="2"))
    assert status == 303
    assert headers["Location"] == "/"
    assert store.read_bytes() == before
    assert store.stat().st_mtime_ns == mtime


# AC6
@pytest.mark.parametrize(
    "body", [form(number="0"), form(number="99"), form(number="abc"),
             form(number=""), "", form(number="-1"), form(number="1.0")]
)
def test_post_done_invalid(port, store, body):
    seed(store, ("a", False), ("b", False))
    before = store.read_bytes()
    status, _, text = request(port, "POST", "/done", body)
    assert status == 400
    assert 'role="alert"' in text
    assert store.read_bytes() == before


@pytest.mark.parametrize("n", ["0", "99"])
def test_post_done_out_of_range_message(port, store, n):
    seed(store, ("a", False), ("b", False))
    status, _, text = request(port, "POST", "/done", form(number=n))
    assert status == 400
    assert f'<p role="alert" class="error">no todo #{n} (have 2)</p>' in text
    assert "<h1>Todos</h1>" in text


def test_post_done_huge_number(port, store):
    seed(store, ("a", False))
    before = store.read_bytes()
    status, _, _ = request(port, "POST", "/done", form(number="9" * 5000))
    assert status == 400
    assert store.read_bytes() == before


# AC7
NASTY = 'x <script>alert(1)</script> "q" & y'


def test_render_page_escapes():
    page = render_page([{"text": NASTY, "done": False}, {"text": NASTY, "done": True}],
                       error=NASTY)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "&quot;q&quot;" in page
    assert "&amp; y" in page
    assert "<script" not in page.lower()


def test_render_page_structure():
    page = render_page([])
    assert page.startswith("<!doctype html>")
    assert '<html lang="en">' in page
    assert '<meta charset="utf-8">' in page
    assert "<title>Todos</title>" in page
    assert "<h1>Todos</h1>" in page
    assert '<label for="new-todo">New todo</label>' in page
    assert ('<input id="new-todo" name="text" required autofocus '
            'autocomplete="off">') in page
    assert 'role="alert"' not in page


def test_post_add_nasty_text_escaped(port, store):
    status, _, _ = request(port, "POST", "/add", form(text=NASTY))
    assert status == 303
    _, _, text = request(port, "GET", "/")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert "&quot;q&quot;" in text
    assert "&amp; y" in text
    assert "<script" not in text.lower()


# AC8
@pytest.mark.parametrize(
    "method,path,body",
    [("GET", "/", None), ("POST", "/add", form(text="x")),
     ("POST", "/done", form(number="1")), ("POST", "/add", form(text="")),
     ("POST", "/done", form(number="abc"))],
)
def test_corrupt_store_500(port, store, method, path, body):
    store.write_text("{not json <b>", encoding="utf-8")
    before = store.read_bytes()
    status, headers, text = request(port, method, path, body)
    assert status == 500
    assert headers["Content-Type"] == "text/html; charset=utf-8"
    assert "is not valid JSON" in text
    assert "<b>" not in text
    assert store.read_bytes() == before


def test_corrupt_store_message_escaped(home):
    # File name containing markup ends up in the TodoError message.
    path = home / "<b>.json"
    path.write_text("{not json", encoding="utf-8")
    srv = make_server(port=0, path=path)
    thread = threading.Thread(target=srv.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    try:
        status, _, text = request(srv.server_address[1], "GET", "/")
    finally:
        srv.shutdown()
        srv.server_close()
    assert status == 500
    assert "&lt;b&gt;.json" in text
    assert "<b>" not in text


# AC9
def test_post_foreign_origin_403(port, store):
    seed(store, ("a", False))
    before = store.read_bytes()
    for path, body in (("/add", form(text="evil")), ("/done", form(number="1"))):
        status, _, _ = request(port, "POST", path, body,
                               {"Origin": "http://evil.example"})
        assert status == 403
    status, _, _ = request(port, "POST", "/add", form(text="evil"),
                           {"Origin": "null"})
    assert status == 403
    status, _, _ = request(port, "POST", "/add", form(text="evil"),
                           {"Origin": "http://127.0.0.1:1"})
    assert status == 403
    assert store.read_bytes() == before


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_post_correct_origin_ok(port, store, host):
    status, _, _ = request(port, "POST", "/add", form(text="ok"),
                           {"Origin": f"http://{host}:{port}"})
    assert status == 303
    assert read_json(store)["items"] == [{"text": "ok", "done": False}]


@pytest.mark.parametrize("host", ["evil.example", "127.0.0.1", "localhost:1",
                                  "evil.example:{port}"])
def test_bad_host_rejected(port, store, host):
    host = host.format(port=port)
    status, _, _ = raw_request(port, [("GET", "/"), ("Host", host)])
    assert status in (400, 403)
    body = form(text="x").encode()
    status, _, _ = raw_request(
        port,
        [("POST", "/add"), ("Host", host), ("Content-Type", FORM),
         ("Content-Length", str(len(body)))],
        body,
    )
    assert status in (400, 403)
    assert not store.exists()


def test_missing_host_rejected(port, store):
    status, _, _ = raw_request(port, [("GET", "/")])
    assert status in (400, 403)


def test_localhost_host_accepted(port, store):
    status, _, _ = raw_request(port, [("GET", "/"), ("Host", f"localhost:{port}")])
    assert status == 200


# AC10
def test_body_too_large_413(port, store):
    seed(store, ("a", False))
    before = store.read_bytes()
    # Claim a large body but do not send it: the server must not wait for it.
    status, _, _ = raw_request(
        port,
        [("POST", "/add"), ("Host", f"127.0.0.1:{port}"), ("Content-Type", FORM),
         ("Content-Length", str(MAX_BODY + 1))],
    )
    assert status == 413
    big = form(text="x" * (MAX_BODY + 10))
    status, _, _ = request(port, "POST", "/add", big)
    assert status == 413
    assert store.read_bytes() == before


def test_wrong_content_type_415(port, store):
    seed(store, ("a", False))
    before = store.read_bytes()
    status, _, _ = request(port, "POST", "/add", json.dumps({"text": "x"}),
                           {"Content-Type": "application/json"})
    assert status == 415
    status, _, _ = request(port, "POST", "/done", form(number="1"),
                           {"Content-Type": "text/plain"})
    assert status == 415
    assert store.read_bytes() == before


def test_form_content_type_with_charset(port, store):
    status, _, _ = request(port, "POST", "/add", form(text="x"),
                           {"Content-Type": f"{FORM}; charset=utf-8"})
    assert status == 303


def test_missing_and_invalid_content_length(port, store):
    status, _, _ = raw_request(
        port, [("POST", "/add"), ("Host", f"127.0.0.1:{port}"), ("Content-Type", FORM)]
    )
    assert status in (400, 411)
    status, _, _ = raw_request(
        port,
        [("POST", "/add"), ("Host", f"127.0.0.1:{port}"), ("Content-Type", FORM),
         ("Content-Length", "abc")],
    )
    assert status == 400
    assert not store.exists()


def test_invalid_utf8_400(port, store):
    status, _, _ = request(port, "POST", "/add", b"text=\xff\xfe")
    assert status == 400
    status, _, _ = request(port, "POST", "/add", "text=%FF%FE")
    assert status == 400
    assert not store.exists()


# Slow / idle clients must not block the single-threaded server.
def test_handler_has_timeout(tmp_path):
    srv = make_server(port=0, path=tmp_path / ".todo.json")
    try:
        assert srv.RequestHandlerClass.timeout == web.REQUEST_TIMEOUT
        assert web.REQUEST_TIMEOUT is not None and web.REQUEST_TIMEOUT > 0
    finally:
        srv.server_close()


@pytest.mark.parametrize(
    "stall",
    [b"", b"GET / HTTP/1.1\r\nHost: ",
     b"POST /add HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
     b"Content-Type: application/x-www-form-urlencoded\r\n"
     b"Content-Length: 100\r\n\r\ntext=partial"],
    ids=["idle", "partial-headers", "short-body"],
)
def test_stalled_client_does_not_block_server(home, stall):
    path = home / ".todo.json"
    srv = make_server(port=0, path=path)
    srv.RequestHandlerClass.timeout = 0.3
    thread = threading.Thread(target=srv.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    port = srv.server_address[1]
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as stalled:
            if stall:
                stalled.sendall(stall.replace(b"{port}", str(port).encode()))
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            try:
                conn.request("GET", "/")
                resp = conn.getresponse()
                assert resp.status == 200
                resp.read()
            finally:
                conn.close()
        assert not path.exists()  # the stalled POST never wrote anything
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


# AC11
@pytest.mark.parametrize("path", ["/nope", "/index.html", "/add/x", "/done/"])
def test_unknown_get_404(port, path):
    status, _, text = request(port, "GET", path)
    assert status == 404
    assert "<h1>404" in text


@pytest.mark.parametrize("path", ["/add", "/done"])
def test_get_post_only_405(port, store, path):
    status, headers, _ = request(port, "GET", path)
    assert status == 405
    assert headers["Allow"] == "POST"
    assert not store.exists()


@pytest.mark.parametrize("path", ["/", "/nope"])
def test_unknown_post_not_2xx(port, store, path):
    status, _, _ = request(port, "POST", path, form(text="x"))
    assert status in (404, 405)
    assert not store.exists()


def test_unsupported_method(port, store):
    status, headers, _ = request(port, "DELETE", "/")
    assert status == 501
    assert headers["Content-Security-Policy"] == CSP


# AC12
@pytest.mark.parametrize(
    "method,path,body,expected",
    [("GET", "/", None, 200), ("HEAD", "/", None, 200),
     ("POST", "/add", form(text="x"), 303), ("POST", "/add", form(text=""), 400),
     ("GET", "/nope", None, 404), ("GET", "/add", None, 405),
     ("POST", "/add", "{}", 415)],
)
def test_security_headers(port, store, method, path, body, expected):
    headers = {"Content-Type": "application/json"} if expected == 415 else None
    status, resp_headers, _ = request(port, method, path, body, headers)
    assert status == expected
    assert resp_headers["Content-Type"] == "text/html; charset=utf-8"
    assert resp_headers["Content-Length"] is not None
    assert resp_headers["Content-Security-Policy"] == CSP
    assert resp_headers["X-Content-Type-Options"] == "nosniff"
    assert resp_headers["Referrer-Policy"] == "same-origin"
    assert resp_headers["Cache-Control"] == "no-store"


def test_security_headers_on_403_and_500(port, store):
    status, h, _ = request(port, "POST", "/add", form(text="x"),
                           {"Origin": "http://evil.example"})
    assert status == 403
    assert h["Content-Security-Policy"] == CSP
    assert h["Referrer-Policy"] == "same-origin"
    store.write_text("{not json", encoding="utf-8")
    status, h, _ = request(port, "GET", "/")
    assert status == 500
    assert h["Content-Security-Policy"] == CSP
    assert h["Referrer-Policy"] == "same-origin"
    assert h["Cache-Control"] == "no-store"


# Regression: Origin: null on same-origin form POSTs (job 004)
REFERRER_POLICIES = {
    "no-referrer", "no-referrer-when-downgrade", "same-origin", "origin",
    "strict-origin", "origin-when-cross-origin",
    "strict-origin-when-cross-origin", "unsafe-url",
}
DEFAULT_REFERRER_POLICY = "strict-origin-when-cross-origin"


def effective_referrer_policy(header_value):
    """Last recognised token of a ``Referrer-Policy`` header value."""
    policy = DEFAULT_REFERRER_POLICY
    for token in (header_value or "").split(","):
        token = token.strip().lower()
        if token in REFERRER_POLICIES:
            policy = token
    return policy


def browser_post_origin(policy, page_origin, target_origin):
    """``Origin`` a browser sends for a form POST (Fetch "serialize a request
    origin"; method is not GET/HEAD and mode is ``navigate``, so not CORS).

    ``policy`` may be a raw ``Referrer-Policy`` header value; the effective
    policy (last recognised token) is used.
    """
    policy = effective_referrer_policy(policy)
    page_scheme = urllib.parse.urlsplit(page_origin).scheme
    target_scheme = urllib.parse.urlsplit(target_origin).scheme
    downgrade = page_scheme == "https" and target_scheme != "https"
    if policy == "no-referrer":
        return "null"
    if policy == "same-origin" and page_origin != target_origin:
        return "null"
    if policy in ("no-referrer-when-downgrade", "strict-origin",
                  "strict-origin-when-cross-origin") and downgrade:
        return "null"
    return page_origin


def test_browser_post_origin_model():
    page = "http://127.0.0.1:8000"
    other = "http://evil.example"
    assert browser_post_origin("no-referrer", page, page) == "null"
    assert browser_post_origin("same-origin", page, page) == page
    assert browser_post_origin("same-origin", page, other) == "null"
    assert browser_post_origin("strict-origin-when-cross-origin", page, page) == page
    assert browser_post_origin("no-referrer, same-origin", page, page) == page
    assert browser_post_origin("same-origin, bogus", page, page) == page
    assert browser_post_origin("bogus", page, page) == page  # default policy
    assert browser_post_origin("", page, page) == page
    assert browser_post_origin(
        "strict-origin", "https://a.example", "http://a.example") == "null"
    assert browser_post_origin(
        "origin", "https://a.example", "http://a.example") == "https://a.example"


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_referrer_policy_does_not_null_same_origin_post(port, store, host):
    same = f"http://{host}:{port}"
    status, headers, _ = request(port, "GET", "/", headers={"Host": f"{host}:{port}"})
    assert status == 200
    policy = headers["Referrer-Policy"]
    origin = browser_post_origin(policy, same, same)
    assert origin != "null", f"Referrer-Policy {policy!r} nulls same-origin Origin"
    post_headers = {"Host": f"{host}:{port}", "Origin": origin}

    status, resp, _ = request(port, "POST", "/add", form(text="buy milk"), post_headers)
    assert status == 303
    assert resp["Location"] == "/"
    assert read_json(store)["items"] == [{"text": "buy milk", "done": False}]

    status, resp, _ = request(port, "POST", "/done", form(number="1"), post_headers)
    assert status == 303
    assert read_json(store)["items"] == [{"text": "buy milk", "done": True}]


def test_page_has_no_referrer_override(port, store):
    seed(store, ("a", False), ("b", True))
    status, _, text = request(port, "GET", "/")
    assert status == 200
    lowered = text.lower()
    assert 'name="referrer"' not in lowered
    assert "referrerpolicy" not in lowered


# AC13
def test_make_server_binds_loopback(tmp_path):
    srv = make_server(port=0, path=tmp_path / ".todo.json")
    try:
        assert srv.server_address[0] == "127.0.0.1"
        assert srv.server_address[1] != 0
    finally:
        srv.server_close()


def test_make_server_default_path_resolved_per_request(home, monkeypatch):
    srv = make_server(port=0)
    thread = threading.Thread(target=srv.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    try:
        port = srv.server_address[1]
        add_item("from home one")
        _, _, text = request(port, "GET", "/")
        assert "from home one" in text
        other = home / "other"
        other.mkdir()
        monkeypatch.setenv("HOME", str(other))
        _, _, text = request(port, "GET", "/")
        assert "No todos yet." in text
    finally:
        srv.shutdown()
        srv.server_close()


# AC14
def test_shared_with_cli(port, store):
    add_item("from cli", path=store)
    _, _, text = request(port, "GET", "/")
    assert "from cli" in text
    request(port, "POST", "/add", form(text="from web"))
    assert [it["text"] for it in load_items(store)] == ["from cli", "from web"]


def test_shared_with_cli_subprocess(port, store):
    env = {**os.environ, "HOME": str(store.parent)}
    subprocess.run([sys.executable, "-m", "app.todo", "add", "via", "cli"],
                   cwd=SRC_DIR, env=env, check=True, capture_output=True)
    _, _, text = request(port, "GET", "/")
    assert "via cli" in text


def test_unicode_round_trip(port, store):
    status, _, _ = request(port, "POST", "/add", "text=caf%C3%A9+%E2%98%95")
    assert status == 303
    assert load_items(store) == [{"text": "café ☕", "done": False}]
    _, _, text = request(port, "GET", "/")
    assert "café ☕" in text


# AC15
def _env(home):
    return {**os.environ, "HOME": str(home), "PYTHONUNBUFFERED": "1"}


def test_cli_serves_and_stops_on_sigint(tmp_path):
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.web", "--port", "0"],
        cwd=SRC_DIR, env=_env(tmp_path),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        line = proc.stdout.readline()
        assert line.startswith("Serving todos at http://127.0.0.1:")
        assert line.rstrip().endswith("/ (Ctrl+C to stop)")
        port = int(line.split("127.0.0.1:")[1].split("/")[0])
        status, _, text = request(port, "GET", "/")
        assert status == 200
        assert "No todos yet." in text
        proc.send_signal(signal.SIGINT)
        assert proc.wait(timeout=10) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()
        proc.stderr.close()
    assert not (tmp_path / ".todo.json").exists()


def test_cli_bad_port_exits_2(tmp_path):
    for value in ("abc", "70000", "-1"):
        result = subprocess.run(
            [sys.executable, "-m", "app.web", "--port", value],
            cwd=SRC_DIR, env=_env(tmp_path), capture_output=True, text=True,
            timeout=10,
        )
        assert result.returncode == 2, value


def test_cli_port_in_use_exits_1(tmp_path):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        busy = sock.getsockname()[1]
        result = subprocess.run(
            [sys.executable, "-m", "app.web", "--port", str(busy)],
            cwd=SRC_DIR, env=_env(tmp_path), capture_output=True, text=True,
            timeout=10,
        )
    assert result.returncode == 1
    assert result.stderr.startswith("error:")
    assert result.stdout == ""


def test_main_port_in_use_returns_1(capsys):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        assert web.main(["--port", str(sock.getsockname()[1])]) == 1
    assert capsys.readouterr().err.startswith("error:")
