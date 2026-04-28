# vista-cli

A unified command-line tool for querying VistA — its code, its data
dictionary, and 40 years of accumulated documentation — through one
interface.

## What is VistA?

**VistA** (Veterans Health Information Systems and Technology
Architecture) is the U.S. Department of Veterans Affairs' electronic
health record system: a hospital information system written in MUMPS
that has been in continuous production use for over forty years.

Concretely, the open-source release looks like this:

| Surface | Scale |
|---|---|
| Routines (`.m` source files) | ~39,500 |
| Packages (Pharmacy, Lab, Order Entry, …) | ~150 |
| FileMan files (the data dictionary) | ~8,000 |
| Tags (function entry-points) | ~290,000 |
| Manuals on the VA Document Library | ~2,800 |
| Indexed manual sections | ~138,700 |
| Routine references inside manuals | ~23,700 |

Code lives in 8-character `.m` files with no module system; behavior
is documented in DOCX/PDF manuals organized by audience. There is
no native bidirectional index — a routine doesn't know which manual
documents it; a manual section doesn't link to the routines that
implement it.

`vista` closes that loop:

```bash
vista routine PRCA45PT     # code facts + every doc that mentions it
vista doc "agent cashier"  # doc hits + every routine each section names
vista links PSO            # all interlinks for a reference, dense
vista neighbors ORWPCE     # graph walk: callees, siblings, same-data routines
vista risk ORM             # composite 0–100 risk score for a routine
```

## Where the data comes from

vista-cli is the integrator. The data preparation — downloading,
parsing, classifying, indexing — lives in two upstream projects, each
with its own pipeline and release cadence:

| Project | Repo | What it produces |
|---|---|---|
| **vista-meta** | [github.com/rafael5/vista-meta](https://github.com/rafael5/vista-meta) | Bakes a running VistA-on-YottaDB into deterministic TSVs: routines, calls, globals, FileMan files, RPCs, options, protocols, XINDEX findings, KIDS patches, and the PIKS classification of every global. |
| **vista-docs** | [github.com/rafael5/vista-docs](https://github.com/rafael5/vista-docs) | Crawls the VA Document Library, downloads DOCX/PDF, parses heading trees, extracts entities (routines, RPCs, options, file numbers, security keys), and lands everything in a SQLite database (`frontmatter.db`) with an FTS5 index over section bodies. |

Both projects produce **deterministic, regenerable, content-addressed
artifacts** — same VistA-M release in, same byte-identical TSVs out;
same VDL snapshot in, same SQLite schema out. That determinism is
what makes vista-cli's joins reproducible.

Related projects in the broader ecosystem (not data sources for
vista-cli, but co-evolving with it):

- **[tree-sitter-m](https://github.com/rafael5/tree-sitter-m)** —
  M-language tree-sitter parser; underpins the VSCode extensions and
  any future `m fmt` / `m lint` / `m test` workflows.
- **[m-standard](https://github.com/rafael5/m-standard)** —
  M-language reference reconciling AnnoStd / YottaDB / IRIS dialects.
- **[vista-docs-api](https://github.com/rafael5/vista-docs-api)** —
  FastAPI read-only HTTP server over the same `frontmatter.db`.

## What's integrated into vista-cli

The data the CLI reads at query time:

| Source | Files | Records | Raw size |
|---|---:|---:|---:|
| code-model TSVs (vista-meta) | 19 | ~1.0 M | 42 MB |
| data-model TSVs + CSV (vista-meta) | 5 | ~88 K | 13 MB |
| `frontmatter.db` SQLite (vista-docs) | 1 | 138,711 sections + 8 entity tables | 283 MB |
| canonical package map (vista-cli) | 1 | 16 packages | <1 KB |

**Total live query surface: ~338 MB**, packed and shipped as a
single ~60 MB `.tar.xz` snapshot bundle (the FTS5 index dominates the
compressed size). The bundle includes a `snapshot.json` manifest with
SHA-256s and provenance back to the upstream commits, so any
installed copy of vista-cli can prove which VistA-M release and which
VDL snapshot it's serving. `vista doctor` reports the snapshot
version; `vista fetch` rolls a new one in atomically with `.bak/`
rollback.

The optional source mirror (39,500 `.m` files, ~7 GB) and the
published markdown tree (~2 GB) are *not* required for queries —
they're only used by `vista where` to print `path:line` and as
read-targets when the user wants to open the original docs. They
ship as separate, opt-in release artifacts.

For background, the full feature list, per-command reference, and
worked-example workflows, see the
**[vista-cli guide](docs/vista-cli-guide.md)**.

## Install

### macOS — Homebrew

```bash
# install
brew tap rafael5/vista https://github.com/rafael5/vista-cli
brew install vista
vista init        # fetches and installs the snapshot data bundle
vista doctor      # verify

# uninstall
brew uninstall vista
brew untap rafael5/vista
rm -rf ~/data/vista                  # optional — removes snapshot + cache
```

Homebrew handles the Python interpreter via its own `python@3.12`
formula — you never see pip or a venv.

### Linux — self-contained tarball

```bash
# install (per-user, no sudo)
mkdir -p ~/.local/opt
curl -LO https://github.com/rafael5/vista-cli/releases/latest/download/vista-linux-x86_64.tar.xz
tar -xJf vista-linux-x86_64.tar.xz -C ~/.local/opt/
ln -sf ~/.local/opt/vista/vista ~/.local/bin/vista
rm vista-linux-x86_64.tar.xz
vista init        # fetches and installs the snapshot data bundle
vista doctor      # verify

# uninstall
rm ~/.local/bin/vista
rm -rf ~/.local/opt/vista
rm -rf ~/data/vista                  # optional — removes snapshot + cache
```

The Linux tarball is built with PyInstaller on `ubuntu-22.04`
(glibc 2.35), so it runs on **Ubuntu 22.04+, Debian 12+, RHEL 9+**,
and any reasonably modern Linux, with **no Python required on the
target machine**. Confirm `~/.local/bin` is on your `$PATH` (most
modern distros, including Linux Mint, set this by default). For
a system-wide install instead, swap `~/.local/opt` → `/opt` and
`~/.local/bin/vista` → `/usr/local/bin/vista` (with `sudo`).
`aarch64` and a glibc-2.17 build target will land in v0.2.x.

vista-cli is **not** distributed via PyPI. The two paths above are
the only supported install routes; see
[docs/vista-cli-packaging.md](docs/vista-cli-packaging.md) for the
rationale.

### From source (contributors)

```bash
# install
git clone https://github.com/rafael5/vista-cli
cd vista-cli
make install      # uv sync --extra dev + pre-commit + test fixtures
make check        # lint + mypy + tests (217 tests, ruff + mypy clean)
ln -sf "$PWD/.venv/bin/vista" ~/.local/bin/vista   # optional — put on $PATH

# uninstall
rm -f ~/.local/bin/vista
rm -rf ~/projects/vista-cli          # or wherever the clone lives
```

## Documentation

- **[vista-cli guide](docs/vista-cli-guide.md)** — comprehensive
  user/operator guide: every command, every flag, worked workflow
  recipes.
- **[planning + design](docs/vista-cli-planning.md)** —
  authoritative for scope, phasing, and the interlinkage taxonomy.
- **[snapshot bundle spec](docs/vista-cli-portable-distribution.md)** —
  the `vista init / fetch / snapshot` machinery and bundle format.
- **[packaging](docs/vista-cli-packaging.md)** — Homebrew formula,
  PyInstaller build, release CI.

## Status

Phases 1–4 of the planning doc are implemented. 217 tests passing,
ruff + mypy clean. First public release tagged
[v0.1.0](https://github.com/rafael5/vista-cli/releases/tag/v0.1.0)
on 2026-04-28.
