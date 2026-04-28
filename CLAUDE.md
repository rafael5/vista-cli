# Claude Project Context — vista-cli

## What this project is

`vista-cli` is the unified CLI that joins **vista-meta** (code model
TSVs at `~/vista-meta/vista/export/code-model/`) with **vista-docs**
(documentation frontmatter SQLite at
`~/data/vista-docs/state/frontmatter.db`) into one queryable surface.

Single binary `vista`. VistA-specific. Orthogonal to:
- `vista-meta` — code-model bake + KIDS workflow + VSCode extension
  ([github.com/rafael5/vista-meta](https://github.com/rafael5/vista-meta))
- `vista-docs` — VDL crawler + ingest + frontmatter pipeline
  ([github.com/rafael5/vista-docs](https://github.com/rafael5/vista-docs))
- `m-cli` — language layer (`m fmt`, `m lint`, `m test`)

`vista` is the **integrator**: it reads from both, writes to neither,
and surfaces cross-artifact joins (routine ↔ docs, RPC ↔ section,
file ↔ patch, etc.).

Design rationale and roadmap: [docs/vista-cli-planning.md](docs/vista-cli-planning.md).
User guide: [docs/vista-cli-guide.md](docs/vista-cli-guide.md).
Distribution: [docs/vista-cli-packaging.md](docs/vista-cli-packaging.md).

## Status

Phases 1–4 of the planning doc are implemented. v0.1.0 tagged
2026-04-28. 217 tests, ruff + mypy clean.

- **Phase 1 — MVP**: routine, package, file, rpc, option, patch,
  global, where, search, doc, doctor.
- **Phase 2 — joins and graph**: links, neighbors, coverage,
  timeline, context, ask + canonical package-id layer.
- **Phase 3 — cache and polish**: build-cache materialises
  `joined.db`; `CodeModelView` transparent cache-aware proxy;
  `--no-cache` top-level flag; risk, layers, matrix.
- **Phase 4 — portable distribution**: snapshot create / verify /
  info / install (tar.xz + SHA-256 manifest), fetch (file:// or
  HTTPS + atomic swap), init (idempotent bootstrap), doctor reports
  snapshot version. PyInstaller `--onedir` Linux tarball + Homebrew
  formula. Distribution intentionally limited to Homebrew on macOS
  and PyInstaller tarball on Linux — no PyPI.

## Project structure

```
src/vista_cli/
  __main__.py           # python -m vista_cli
  cli.py                # Click subcommand wiring (24 commands)
  config.py             # path resolution (env vars + defaults)
  canonical.py          # package id: directory ↔ ns ↔ app_code
  snapshot.py           # bundle create / verify / info / install
  fetch.py              # download + atomic install of snapshot bundles
  data/
    packages.csv        # canonical map shipped in the wheel
  stores/
    code_model.py       # TSV reader (vista-meta side)
    data_model.py       # FileMan files / PIKS reader
    doc_model.py        # SQLite reader (vista-docs side)
    cache.py            # joined.db builder + reader
    code_view.py        # cache-aware proxy in front of code_model
    joined.py           # cross-store joins
  commands/             # one Click command per file
  format/
    markdown.py
    json_out.py
    tsv_out.py

tests/
  unit/                 # pure functions + Click CliRunner against fixtures
  fixtures/             # tiny TSV + SQLite fixtures, build_fixture_db.py
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
- `VISTA_CACHE_DB` → joined.db cache path

End users get the data via `vista init`, which fetches a snapshot
bundle from a GitHub release and installs it into
`~/data/vista/snapshot/`.

## Dev workflow

```bash
make install     # uv sync --extra dev + pre-commit hooks + fixtures
make test        # pytest (unit only by default)
make test-int    # integration tests (need real data on disk)
make test-lf     # rerun last failed
make watch       # TDD mode (auto-rerun on save)
make cov         # pytest with coverage
make check       # lint + mypy + cov (CI gate)
make format      # ruff format

make package           # PyInstaller --onedir → dist/vista/ + dist/vista-linux-${arch}.tar.xz
make package-smoke     # build + run --version + --help
make clean-package     # rm -rf build dist
```

## TDD — hard rule

Test first. Always. Particularly:

- Pure functions (`canonical.py`, formatters, ref-shape) — full unit
  coverage, no fixtures.
- Stores — fixture TSV + tiny SQLite at `tests/fixtures/`, exercised
  in integration tests, marked `@pytest.mark.integration`.
- Commands — invoke through Click's `CliRunner` against fixtures.
- Snapshot / fetch — round-trip a real bundle through the full
  create → verify → install pipeline; use `file://` URLs in tests
  to exercise `fetch` without network.

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
- Every command module exports a single Click command
  (`@click.command`) or group (`@click.group`). `cli.py` only wires
  them together.
- Output is deterministic — same inputs, same bytes out.
- The `CodeModelView` transparent proxy means commands consume one
  abstraction whether the cache is hot or cold. Adding a new
  cache-backed lookup means: add the SQL to `stores/cache.py`, add
  the cached method to `stores/code_view.py`, write parity tests in
  `tests/unit/test_code_view.py`.
- Distribution surface is intentionally tight: Homebrew (macOS) and
  PyInstaller tarball (Linux). No PyPI / pipx / uv-tool path.
