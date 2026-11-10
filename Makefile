PYTHON ?= python3
VENV := .venv
STAMP := $(VENV)/.installed

.DEFAULT_GOAL := test
.PHONY: help venv test clean

help:
	@echo "make test   - create .venv (first run), install dev deps, run pytest"
	@echo "make venv   - create .venv and install requirements-dev.txt"
	@echo "make clean  - remove .venv, .pytest_cache and __pycache__ dirs"

venv: $(STAMP)

$(STAMP): requirements-dev.txt
	test -x $(VENV)/bin/python || $(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --quiet -r requirements-dev.txt
	touch $(STAMP)

test: $(STAMP)
	$(VENV)/bin/python -m pytest

clean:
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -not -path "./.git/*" -prune -exec rm -rf {} +
