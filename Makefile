.PHONY: install test coverage lint format typecheck check clean lock smoke

PYTHON ?= python
VENV ?= .venv

ifeq ($(OS),Windows_NT)
VENV_PYTHON := $(VENV)/Scripts/python.exe
else
VENV_PYTHON := $(VENV)/bin/python
endif

install:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	@if [ -f requirements-lock.txt ]; then \
		$(VENV_PYTHON) -m pip install -r requirements-lock.txt; \
	else \
		$(VENV_PYTHON) -m pip install -r requirements.txt; \
	fi
	$(VENV_PYTHON) -m pip install -e ".[dev,build]"

test:
	$(VENV_PYTHON) -m pytest

coverage:
	$(VENV_PYTHON) -m pytest --cov=autoclicker --cov-report=term --cov-report=html --cov-report=xml

lint:
	$(VENV_PYTHON) -m ruff check autoclicker autoclicker.py tests scripts
	$(VENV_PYTHON) -m ruff format --check tests scripts tools run_tests.py

format:
	$(VENV_PYTHON) -m ruff format tests scripts tools run_tests.py

typecheck:
	$(VENV_PYTHON) -m mypy autoclicker

check: lint typecheck test

clean:
	rm -rf $(VENV) build dist htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} + 2>/dev/null || true

lock:
	$(VENV_PYTHON) tools/refresh_lock.py

smoke:
	$(VENV_PYTHON) scripts/smoke_check.py
