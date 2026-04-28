# Claude Project Context — vista-cli

## What this project is

`vista-cli` is the unified CLI that joins **vista-meta** (code model
TSVs at `~/vista-meta/vista/export/code-model/`) with **vista-docs**
(documentation frontmatter SQLite at `~/data/vista-docs/state/frontmatter.db`)
into one queryable surface.

Single binary `vista`. VistA-specific. Orthogonal to:
- `m-cli` — language layer (`m fmt`, `m lint`, `m test`)
- `vista-meta` — code-model bake + KIDS workflow + VSCode extension
- `vista-docs` — VDL crawler + ingest + frontmatter pipeline

`vista` is the **integrator**: it reads from both, writes to neither,
and surfaces cross-artifact joins (routine ↔ docs, RPC ↔ section,
file ↔ patch, etc.).

Design rationale and roadmap: [docs/vista-cli-planning.md](docs/vista-cli-planning.md).

## Project structure

```
src/vista_cli/
  __main__.py           # python -m vista_cli
  cli.py                # Click subcommand wiring
  config.py             # path resolution (env vars + defaults)
  canonical.py          # package id: directory ↔ ns ↔ app_code
  stores/
    code_model.py       # TSV reader (vista-meta side)
    doc_model.py        # SQLite reader (vista-docs side)
    joined.py           # cross-store joins
  commands/
    routine.py          # vista routine RTN
    where.py            # vista where REF
    doctor.py           # vista doctor
    ...                 # one module per subcommand (phase 1+)
  format/
    markdown.py
    json_out.py
    tsv_out.py

tests/
  unit/                 # pure functions, no I/O
  integration/          # against real TSVs + SQLite (marked)
  fixtures/             # tiny TSV + SQLite fixtures
```

**Rule:** new I/O goes in `stores/`. Pure logic (formatters,
canonical mapping, ref-shape detection) is in top-level modules with
unit tests.

## Data sources (NOT in this repo)

- vista-meta TSVs: `~/vista-meta/vista/export/code-model/*.tsv`
- vista-meta data model: `~/vista-meta/vista/export/data-model/*.tsv`
- vista-meta source mirror: `~/vista-meta/vista/vista-m-host/`
- vista-docs SQLite: `~/data/vista-docs/state/frontmatter.db`
- vista-docs published markdown: `~/data/vista-docs/publish/`

Override via env vars (see `config.py`):
- `VISTA_CODE_MODEL` → code-model TSV directory
- `VISTA_DATA_MODEL` → data-model TSV directory
- `VISTA_M_HOST` → VistA-M source mirror
- `VISTA_DOC_DB` → frontmatter.db path
- `VISTA_DOC_PUBLISH` → publish/ tree

## Dev workflow

```bash
make install    # uv sync --extra dev + pre-commit hooks
make test       # pytest (unit only by default)
make test-int   # integration tests (need real data on disk)
make test-lf    # rerun last failed
make watch      # TDD mode (auto-rerun on save)
make cov        # pytest with coverage
make check      # lint + mypy + cov (CI gate)
make format     # ruff format
```

## TDD — hard rule

Test first. Always. Particularly:

- Pure functions (`canonical.py`, formatters, ref-shape) — full unit
  coverage, no fixtures.
- Stores — fixture TSV + tiny SQLite at `tests/fixtures/`, exercised
  in integration tests, marked `@pytest.mark.integration`.
- Commands — invoke through Click's `CliRunner` against fixtures.

## Code style

- ruff (line length 88)
- Rules: E, F, I
- No `print()` — use logging. Click outputs go through `click.echo`.
- No mocks unless unavoidable. Prefer real fixtures.

## Claude guidelines

- The planning doc ([docs/vista-cli-planning.md](docs/vista-cli-planning.md))
  is authoritative for scope and phasing. Do not expand beyond the
  current phase without updating the doc first.
- Keep stores narrow: parse-and-return, no business logic. Joins go
  in `stores/joined.py`; formatting goes in `format/`.
- Every command module exports a single Click command (`@click.command`).
  `cli.py` only wires them together.
- Output is deterministic — same inputs, same bytes out.
