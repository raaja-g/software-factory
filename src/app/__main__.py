"""Entry point for ``python -m app``: prints the package version."""

from __future__ import annotations

from app import __version__


def main(argv: list[str] | None = None) -> int:
    """Print ``app <version>`` to stdout and return exit code 0."""
    print(f"app {__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
