.PHONY: setup lint format test test-unit test-integration clean

VENV ?= .venv
PYTHON ?= python3
PIP ?= $(VENV)/bin/pip
PYTEST ?= $(VENV)/bin/pytest
RUFF ?= $(VENV)/bin/ruff

$(VENV)/bin/activate: requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

setup: $(VENV)/bin/activate

lint: setup
	$(RUFF) check .

format: setup
	$(RUFF) format .

test: setup
	$(PYTEST) --cov=.

test-unit: setup
	$(PYTEST) tests/unit -q

test-integration: setup
	$(PYTEST) tests/integration -v

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache .coverage htmlcov
