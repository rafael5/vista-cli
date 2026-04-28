.PHONY: install test test-int test-lf watch lint format mypy cov check push pull \
        hooks fixtures package package-smoke clean-package

PYTHON      := .venv/bin/python
PYTEST      := .venv/bin/pytest
RUFF        := .venv/bin/ruff
MYPY        := .venv/bin/mypy
PTW         := .venv/bin/ptw
VISTA       := .venv/bin/vista
PYINSTALLER := .venv/bin/pyinstaller

# Detect platform/arch for the release tarball name.
UNAME_S := $(shell uname -s | tr A-Z a-z)
UNAME_M := $(shell uname -m)
TARBALL := vista-$(UNAME_S)-$(UNAME_M).tar.xz

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

# ── Packaging ────────────────────────────────────────────────────
#
# `make package` produces dist/$(TARBALL) — a self-contained tarball
# of the `vista` CLI plus its Python interpreter. Drop the contents
# on $PATH; no Python install required on the target.

package:
	uv sync --extra dev --extra package
	rm -rf build dist
	$(PYINSTALLER) --clean --noconfirm vista.spec
	tar -cJf dist/$(TARBALL) -C dist vista
	@echo
	@echo "  built: dist/$(TARBALL) ($$(du -h dist/$(TARBALL) | cut -f1))"
	@echo "  bundle: dist/vista/ ($$(du -sh dist/vista | cut -f1))"

package-smoke: package
	./dist/vista/vista --version
	./dist/vista/vista --help > /dev/null
	@echo "  smoke-test ok"

clean-package:
	rm -rf build dist *.spec.bak
