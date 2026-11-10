"""Todo CLI for ``python -m app.todo add|list|done <n>``.

Todos are stored as UTF-8 JSON in ``~/.todo.json``::

    {"items": [{"text": "buy milk", "done": false}]}

The storage functions (``default_path``, ``load_items``, ``save_items``,
``add_item``, ``complete_item``) are plain functions, separate from the
argument parsing, so other front ends can reuse the same file and logic.
Each accepts an optional ``path``; ``None`` means ``default_path()``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

FILE_MODE = 0o600


class TodoError(Exception):
    """A user-facing error; the CLI prints its message to stderr."""


def default_path() -> Path:
    """Return the storage file path, ``~/.todo.json`` (evaluated at call time)."""
    return Path.home() / ".todo.json"


def _resolve(path: Path | None) -> Path:
    return default_path() if path is None else Path(path)


def _valid_item(item: object) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("text"), str)
        and type(item.get("done")) is bool
    )


def load_items(path: Path | None = None) -> list[dict]:
    """Load and validate the todo items.

    A missing file yields ``[]`` (and is not created). Unreadable, invalid or
    wrongly-shaped files raise ``TodoError`` naming the file; they are never
    modified.
    """
    path = _resolve(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError) as exc:
        raise TodoError(f"cannot read {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TodoError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise TodoError(f"{path} must contain an object with an 'items' list")
    items = data["items"]
    for index, item in enumerate(items, start=1):
        if not _valid_item(item):
            raise TodoError(
                f"{path}: item #{index} must be an object with a string "
                "'text' and a boolean 'done'"
            )
    return [{"text": item["text"], "done": item["done"]} for item in items]


def save_items(items: list[dict], path: Path | None = None) -> None:
    """Atomically write ``items`` to the storage file with mode ``0o600``.

    Writes a temp file in the same directory, then ``os.replace``s it onto the
    target. The temp file is removed if anything fails.
    """
    path = _resolve(path)
    payload = json.dumps({"items": items}, indent=2, ensure_ascii=False) + "\n"
    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
    except OSError as exc:
        raise TodoError(f"cannot write {path}: {exc}") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            os.fchmod(fh.fileno(), FILE_MODE)
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException as exc:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        if isinstance(exc, OSError):
            raise TodoError(f"cannot write {path}: {exc}") from exc
        raise


def add_item(text: str, path: Path | None = None) -> dict:
    """Append a new not-done item and return it with its 1-based ``number``."""
    text = text.strip()
    if not text:
        raise TodoError("todo text must not be empty")
    items = load_items(path)
    item = {"text": text, "done": False}
    items.append(item)
    save_items(items, path)
    return {"number": len(items), **item}


def complete_item(number: int, path: Path | None = None) -> dict:
    """Mark item ``number`` (1-based) done and return it with its ``number``.

    Completing an already-done item succeeds without rewriting the file.
    """
    items = load_items(path)
    if not 1 <= number <= len(items):
        raise TodoError(f"no todo #{number} (have {len(items)})")
    item = items[number - 1]
    if not item["done"]:
        item["done"] = True
        save_items(items, path)
    return {"number": number, **item}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.todo", description="A tiny todo list."
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True
    add = sub.add_parser("add", help="add a todo")
    add.add_argument("text", nargs="+", metavar="TEXT", help="todo text")
    sub.add_parser("list", help="list todos")
    done = sub.add_parser("done", help="mark todo N as done")
    done.add_argument("number", type=int, metavar="N", help="todo number")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the todo CLI; return 0 on success, 1 on ``TodoError``."""
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "add":
            item = add_item(" ".join(args.text))
            lines = [f"Added #{item['number']}: {item['text']}"]
        elif args.command == "list":
            items = load_items()
            lines = [
                f"{n}. [{'x' if it['done'] else ' '}] {it['text']}"
                for n, it in enumerate(items, start=1)
            ] or ["No todos."]
        else:
            item = complete_item(args.number)
            lines = [f"Done #{item['number']}: {item['text']}"]
    except TodoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
