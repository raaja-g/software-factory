"""Tests for the todo CLI and storage functions (``app.todo``)."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from app import todo
from app.todo import (
    TodoError,
    add_item,
    complete_item,
    default_path,
    load_items,
    main,
    save_items,
)

SRC_DIR = Path(__file__).resolve().parent.parent / "src"


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Point HOME at an empty temp dir so no test touches the real home."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def store(home):
    return home / ".todo.json"


def run(argv, capsys):
    code = main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_default_path_follows_home(home):
    assert default_path() == home / ".todo.json"


# AC1
def test_add_creates_file(store, capsys):
    code, out, err = run(["add", "buy", "milk"], capsys)
    assert code == 0
    assert out == "Added #1: buy milk\n"
    assert err == ""
    assert read_json(store) == {"items": [{"text": "buy milk", "done": False}]}
    raw = store.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert raw == json.dumps(read_json(store), indent=2) + "\n"


# AC2
def test_list_in_insertion_order(store, capsys):
    run(["add", "buy milk"], capsys)
    run(["add", "call bob"], capsys)
    run(["add", "walk dog"], capsys)
    run(["done", "2"], capsys)
    code, out, err = run(["list"], capsys)
    assert code == 0
    assert out.splitlines() == [
        "1. [ ] buy milk",
        "2. [x] call bob",
        "3. [ ] walk dog",
    ]


# AC3
def test_list_empty_does_not_create_file(store, capsys):
    code, out, err = run(["list"], capsys)
    assert code == 0
    assert out == "No todos.\n"
    assert not store.exists()


# AC4
def test_done_marks_item(store, capsys):
    run(["add", "a"], capsys)
    run(["add", "b"], capsys)
    run(["add", "c"], capsys)
    code, out, err = run(["done", "2"], capsys)
    assert code == 0
    assert out == "Done #2: b\n"
    assert read_json(store)["items"][1] == {"text": "b", "done": True}
    _, out, _ = run(["list"], capsys)
    assert out.splitlines() == ["1. [ ] a", "2. [x] b", "3. [ ] c"]


def test_done_already_done_succeeds_without_write(store, capsys):
    run(["add", "a"], capsys)
    run(["done", "1"], capsys)
    before = store.read_bytes()
    mtime = store.stat().st_mtime_ns
    code, out, _ = run(["done", "1"], capsys)
    assert code == 0
    assert out == "Done #1: a\n"
    assert store.read_bytes() == before
    assert store.stat().st_mtime_ns == mtime


# AC5
@pytest.mark.parametrize("n", ["0", "99", "-1"])
def test_done_out_of_range(store, capsys, n):
    run(["add", "a"], capsys)
    run(["add", "b"], capsys)
    before = store.read_bytes()
    code, out, err = run(["done", n], capsys)
    assert code == 1
    assert out == ""
    assert err.startswith("error:")
    assert "(have 2)" in err
    assert store.read_bytes() == before


def test_done_on_empty_list(store, capsys):
    code, out, err = run(["done", "1"], capsys)
    assert code == 1
    assert out == ""
    assert err.startswith("error:")
    assert not store.exists()


# AC6
@pytest.mark.parametrize("argv", [["done", "abc"], [], ["bogus"], ["done"], ["add"]])
def test_usage_errors_exit_2(home, capsys, argv):
    with pytest.raises(SystemExit) as excinfo:
        main(argv)
    assert excinfo.value.code == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert "usage:" in err


# AC7
@pytest.mark.parametrize("argv", [["add", "   "], ["add", ""], ["add", " ", "\t"]])
def test_add_empty_text(store, capsys, argv):
    run(["add", "existing"], capsys)
    before = store.read_bytes()
    code, out, err = run(argv, capsys)
    assert code == 1
    assert out == ""
    assert err == "error: todo text must not be empty\n"
    assert store.read_bytes() == before


def test_add_empty_text_no_file(store, capsys):
    code, _, err = run(["add", "   "], capsys)
    assert code == 1
    assert err.startswith("error:")
    assert not store.exists()


# AC8
BAD_CONTENTS = [
    "{not json",
    '{"items": 5}',
    "[]",
    '{"other": []}',
    '{"items": ["x"]}',
    '{"items": [{"text": "a"}]}',
    '{"items": [{"text": 1, "done": false}]}',
    '{"items": [{"text": "a", "done": 0}]}',
    '{"items": [{"text": "a", "done": "yes"}]}',
]


@pytest.mark.parametrize("content", BAD_CONTENTS)
@pytest.mark.parametrize("argv", [["add", "x"], ["list"], ["done", "1"]])
def test_corrupt_file_untouched(store, capsys, content, argv):
    store.write_text(content, encoding="utf-8")
    before = store.read_bytes()
    code, out, err = run(argv, capsys)
    assert code == 1
    assert out == ""
    assert err.startswith("error:")
    assert str(store) in err
    assert store.read_bytes() == before
    assert sorted(p.name for p in store.parent.iterdir()) == [".todo.json"]


def test_invalid_utf8_is_error(store, capsys):
    store.write_bytes(b"\xff\xfe\x00garbage")
    before = store.read_bytes()
    code, _, err = run(["list"], capsys)
    assert code == 1
    assert str(store) in err
    assert store.read_bytes() == before


# AC9
def test_persists_across_processes(home):
    env = {**os.environ, "HOME": str(home), "PYTHONIOENCODING": "utf-8"}

    def cli(*args):
        return subprocess.run(
            [sys.executable, "-m", "app.todo", *args],
            cwd=SRC_DIR,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    r = cli("add", "buy", "milk")
    assert r.returncode == 0, r.stderr
    assert r.stdout == "Added #1: buy milk\n"
    r = cli("add", "call bob")
    assert r.returncode == 0, r.stderr
    assert r.stdout == "Added #2: call bob\n"
    r = cli("done", "1")
    assert r.returncode == 0, r.stderr
    assert r.stdout == "Done #1: buy milk\n"
    r = cli("list")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == ["1. [x] buy milk", "2. [ ] call bob"]
    r = cli("done", "7")
    assert r.returncode == 1
    assert r.stdout == ""
    assert r.stderr.startswith("error:")
    r = cli("done", "abc")
    assert r.returncode == 2
    assert "usage:" in r.stderr


# AC10
def test_file_mode_and_no_temp_files(store, capsys):
    run(["add", "a"], capsys)
    assert stat.S_IMODE(store.stat().st_mode) == 0o600
    run(["add", "b"], capsys)
    run(["done", "1"], capsys)
    assert stat.S_IMODE(store.stat().st_mode) == 0o600
    assert sorted(p.name for p in store.parent.iterdir()) == [".todo.json"]


def test_save_resets_loose_mode(store):
    store.write_text('{"items": []}\n', encoding="utf-8")
    store.chmod(0o644)
    save_items([{"text": "a", "done": False}], store)
    assert stat.S_IMODE(store.stat().st_mode) == 0o600


def test_save_uses_os_replace(store, monkeypatch):
    calls = []
    real_replace = os.replace

    def spy(src, dst):
        calls.append((Path(src), Path(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(todo.os, "replace", spy)
    save_items([{"text": "a", "done": False}], store)
    assert len(calls) == 1
    src, dst = calls[0]
    assert dst == store
    assert src.parent == store.parent
    assert not src.exists()


def test_failed_save_removes_temp_and_keeps_original(store, monkeypatch):
    save_items([{"text": "orig", "done": False}], store)
    before = store.read_bytes()

    def boom(src, dst):
        raise OSError("disk on fire")

    monkeypatch.setattr(todo.os, "replace", boom)
    with pytest.raises(TodoError):
        save_items([{"text": "new", "done": False}], store)
    assert store.read_bytes() == before
    assert sorted(p.name for p in store.parent.iterdir()) == [".todo.json"]


# AC11
def test_unicode_round_trip(store, capsys):
    code, out, _ = run(["add", "café", "☕"], capsys)
    assert code == 0
    assert out == "Added #1: café ☕\n"
    _, out, _ = run(["list"], capsys)
    assert out == "1. [ ] café ☕\n"
    assert read_json(store)["items"][0]["text"] == "café ☕"
    assert "café ☕" in store.read_text(encoding="utf-8")


# AC12
def test_storage_api_with_explicit_path(home, tmp_path):
    path = tmp_path / "x.json"
    assert load_items(path) == []
    assert not path.exists()
    first = add_item("  one  ", path=path)
    assert first == {"number": 1, "text": "one", "done": False}
    second = add_item("two", path=path)
    assert second["number"] == 2
    done = complete_item(2, path=path)
    assert done == {"number": 2, "text": "two", "done": True}
    assert load_items(path) == [
        {"text": "one", "done": False},
        {"text": "two", "done": True},
    ]
    with pytest.raises(TodoError):
        complete_item(3, path=path)
    with pytest.raises(TodoError, match="must not be empty"):
        add_item("   ", path=path)
    assert not (home / ".todo.json").exists()
