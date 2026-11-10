"""Optional real-browser test of the todo web page (``make test-browser``).

Skipped when Playwright or a Chromium/Chrome browser is not available, so
``make test`` never needs it.
"""

from __future__ import annotations

import json
import threading

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from app.web import make_server  # noqa: E402


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    home = tmp_path_factory.mktemp("home")
    mp = pytest.MonkeyPatch()
    mp.setenv("HOME", str(home))
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
        mp.undo()


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            try:
                b = p.chromium.launch(channel="chrome")
            except Exception as exc:
                pytest.skip(f"no Chromium/Chrome available for Playwright: {exc}")
        try:
            yield b
        finally:
            b.close()


def test_browser_add_and_done(live_server, browser):
    port, store = live_server
    base = f"http://127.0.0.1:{port}"
    page = browser.new_page()
    posts = []
    page.on(
        "request",
        lambda req: posts.append(req.all_headers()) if req.method == "POST" else None,
    )
    try:
        page.goto(base + "/")
        page.fill("#new-todo", "buy milk")
        with page.expect_navigation():
            page.click("button:has-text('Add')")
        assert page.url == base + "/"
        content = page.content()
        assert "buy milk" in content
        assert "cross-origin request refused" not in content
        items = json.loads(store.read_text(encoding="utf-8"))["items"]
        assert items == [{"text": "buy milk", "done": False}]

        with page.expect_navigation():
            page.click("button:has-text('Done')")
        assert page.url == base + "/"
        content = page.content()
        assert "cross-origin request refused" not in content
        assert "<s>buy milk</s>" in content
        assert "(done)" in content
        items = json.loads(store.read_text(encoding="utf-8"))["items"]
        assert items == [{"text": "buy milk", "done": True}]
    finally:
        page.close()

    assert len(posts) == 2
    for headers in posts:
        assert headers.get("origin") == base
