.PHONY: install test test-int test-lf watch lint format mypy cov check push pull hooks fixtures

PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF   := .venv/bin/ruff
MYPY   := .venv/bin/mypy
PTW    := .venv/bin/ptw
VISTA  := .venv/bin/vista

install:
	uv sync --extra dev
	$(MAKE) hooks
	$(MAKE) fixtures

hooks:
	.venv/bin/pre-commit install --hook-type pre-commit --hook-type pre-push

fixtures:
	$(PYTHON) tests/fixtures/build_fixture_db.py

test:
	$(PYTEST)

test-int:
	$(PYTEST) -m integration

test-lf:
	$(PYTEST) --lf

watch:
	$(PTW) -- --tb=short

lint:
	$(RUFF) check src/ tests/

format:
	$(RUFF) format src/ tests/

mypy:
	$(MYPY) src/

cov:
	$(PYTEST) --cov --cov-report=term-missing

check: lint mypy cov

pull:
	git pull origin main

push: check
	git push origin main
