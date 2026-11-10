PYTHON ?= python3
VENV := .venv
STAMP := $(VENV)/.installed

.DEFAULT_GOAL := test
.PHONY: help venv test test-browser clean

help:
	@echo "make test   - create .venv (first run), install dev deps, run pytest"
	@echo "make test-browser - install Playwright + Chromium, run the real-browser test"
	@echo "make venv   - create .venv and install requirements-dev.txt"
	@echo "make clean  - remove .venv, .pytest_cache and __pycache__ dirs"

venv: $(STAMP)

$(STAMP): requirements-dev.txt
	test -x $(VENV)/bin/python || $(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --quiet -r requirements-dev.txt
	touch $(STAMP)

test: $(STAMP)
	$(VENV)/bin/python -m pytest

BROWSER_STAMP := $(VENV)/.installed-browser

$(BROWSER_STAMP): $(STAMP) requirements-browser.txt
	$(VENV)/bin/python -m pip install --quiet -r requirements-browser.txt
	touch $(BROWSER_STAMP)

# Installing Chromium is best effort: the test falls back to Google Chrome.
test-browser: $(BROWSER_STAMP)
	-$(VENV)/bin/python -m playwright install chromium
	$(VENV)/bin/python -m pytest tests/test_browser.py

clean:
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -not -path "./.git/*" -prune -exec rm -rf {} +
