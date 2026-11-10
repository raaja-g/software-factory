"""Smoke tests for the app package skeleton."""

import subprocess
import sys
from pathlib import Path

import app
import app.__main__

SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def test_package_importable():
    assert isinstance(app.__version__, str)
    assert app.__version__


def test_main_prints_version(capsys):
    assert app.__main__.main([]) == 0
    out = capsys.readouterr().out
    assert app.__version__ in out
    assert out.strip() == f"app {app.__version__}"


def test_python_m_app():
    result = subprocess.run(
        [sys.executable, "-m", "app"],
        cwd=SRC_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"app {app.__version__}"
