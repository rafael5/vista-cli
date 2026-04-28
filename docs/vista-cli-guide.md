# vista-cli — Comprehensive Guide

A user and operator guide for **`vista`**, the unified CLI that joins
[vista-meta](https://github.com/rafael5/vista-meta) (the VistA code
model) with [vista-docs](https://github.com/rafael5/vista-docs) (the
VA Document Library frontmatter database) into one queryable surface.

This document is for people who want to *use* vista-cli effectively.
For the design rationale and roadmap behind it, see
[vista-cli-planning.md](vista-cli-planning.md). For installation
quick-start and project context, see the
[README](../README.md). For the snapshot bundle / `init` /
`fetch` machinery, see
[vista-cli-portable-distribution.md](vista-cli-portable-distribution.md).

---

## Table of contents

- [1. Introduction](#1-introduction)
  - [1.1 The need](#11-the-need)
  - [1.2 Design](#12-design)
  - [1.3 Data inputs](#13-data-inputs)
  - [1.4 Implementation](#14-implementation)
- [2. Installing and configuring](#2-installing-and-configuring)
- [3. Command reference](#3-command-reference)
  - [3.1 Inspecting one artifact](#31-inspecting-one-artifact)
  - [3.2 Cross-references and graph walks](#32-cross-references-and-graph-walks)
  - [3.3 Search](#33-search)
  - [3.4 Reporting and analysis](#34-reporting-and-analysis)
  - [3.5 AI bundling](#35-ai-bundling)
  - [3.6 Operations](#36-operations)
- [4. Using vista-cli effectively](#4-using-vista-cli-effectively)
  - [4.1 The four output formats](#41-the-four-output-formats)
  - [4.2 Workflow recipes](#42-workflow-recipes)
  - [4.3 Tips and conventions](#43-tips-and-conventions)
- [5. Troubleshooting](#5-troubleshooting)

---

## 1. Introduction

### 1.1 The need

VistA is a ~40-year-old hospital information system: roughly 39,500
MUMPS routines, ~8,000 FileMan files, hundreds of packages, and ~2,800
manuals on the VA Document Library (VDL). Two long-standing forms of
fragmentation make day-to-day work painful:

- **Code lives in `.m` files** with 8-character names and no module
  system. Finding "everything that touches FileMan file 430" or "every
  routine called from CPRS that writes patient data" is a grep job.
- **Behavior is documented in DOCX/PDF manuals** organized by audience
  (User / Technical / Installation) and addressed by app code (CPRS,
  PRCA, PSO). The manual that explains a routine has no link to the
  routine; the routine has no field saying "documented in §4.2 of the
  User Manual."

Two upstream projects each solved one half:

- **vista-meta** bakes a running VistA into 19 code-model TSVs +
  5 data-model TSVs (~1.0 M rows) describing routines, calls, globals,
  RPCs, options, FileMan files, and PIKS classifications.
- **vista-docs** crawls the VDL into a SQLite database
  (`frontmatter.db`) with 2,842 documents, 138,711 FTS5-indexed
  sections, and extracted entity tables (23,714 routine references,
  631 RPC references, 23,199 option references, etc.).

What was missing was the join. `vista` is that join: a single binary
that reads from both stores, never writes to either, and answers
cross-artifact questions in under a second:

```bash
vista routine PRCA45PT     # code facts + every doc that mentions it
vista doc "agent cashier"  # doc hits + every routine each section names
vista links PSO            # all interlinks for a routine, in one report
vista ask "how does an order get verified?" --routine ORM   # AI-ready bundle
```

### 1.2 Design

vista-cli sits in a deliberately narrow niche. Three CLIs, three
layers, no overlap:

```
┌─────────────────────────────────────────────────────────────┐
│  vista        (this tool — VistA-specific cross-model)      │
│  - joins code, data, KIDS, and documentation                │
│  - reads vista-meta TSVs + vista-docs frontmatter.db        │
└────────────┬─────────────────────────────────┬──────────────┘
             │                                 │
             ▼                                 ▼
┌──────────────────────────┐      ┌──────────────────────────┐
│ vista-meta (code model)  │      │ vista-docs (doc model)   │
│ - bakes VistA-M → TSVs   │      │ - crawls VDL → SQLite    │
└──────────────────────────┘      └──────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  m-cli   (M-language layer — orthogonal to all of above)     │
│  - m fmt / m lint / m test                                   │
└──────────────────────────────────────────────────────────────┘
```

Boundary rules in practice:

| Concern | Owner |
|---|---|
| MUMPS parsing, AST | `m-cli` |
| Code-model TSV bake, KIDS, VSCode sidebar | `vista-meta` |
| VDL crawl, ingest, frontmatter SQLite | `vista-docs` |
| **Cross-product queries** | **`vista`** |
| Interactive navigation, AI bundling | `vista` |

`vista` is a **read-only consumer**. It never modifies the upstream
TSVs or SQLite — both stay authoritative — and it ships its own
canonical package map (`src/vista_cli/data/packages.csv`) to bridge
the namespace mismatch between vista-meta (directory names like
`Outpatient Pharmacy`) and vista-docs (VDL `app_code` and VistA
namespace `pkg_ns`, both `PSO`).

Three design principles that fall out of this:

1. **Stores are narrow.** Each store module (`code_model.py`,
   `data_model.py`, `doc_model.py`) parses-and-returns. No business
   logic. Joins live in `stores/joined.py`; formatting in `format/`.
2. **Output is deterministic.** Same inputs, same bytes out — a
   property tested with golden snapshots. Pipe-able into git, diff,
   awk, or jq without surprise.
3. **Every command supports four formats** (`md`, `json`, `tsv`,
   `table`) so the same query feeds a terminal, a script, a
   spreadsheet, or an LLM with no extra plumbing.

### 1.3 Data inputs

`vista` reads from five locations on disk. None of them are managed
by vista-cli; you point at them via env vars or a config and the CLI
respects whatever vista-meta and vista-docs have produced.

| Source | Default path | Env var | Provides |
|---|---|---|---|
| Code model | `~/vista-meta/vista/export/code-model/` | `VISTA_CODE_MODEL` | 19 TSVs: routines, calls, globals, rpcs, options, xindex, packages, etc. |
| Data model | `~/vista-meta/vista/export/data-model/` | `VISTA_DATA_MODEL` | 5 TSVs: FileMan files, fields, PIKS classifications |
| Source mirror | `~/vista-meta/vista/vista-m-host/` | `VISTA_M_HOST` | host-visible copy of VistA-M (`Packages/<Pkg>/Routines/<RTN>.m`) |
| Doc DB | `~/data/vista-docs/state/frontmatter.db` | `VISTA_DOC_DB` | SQLite with documents, doc_routines, doc_rpcs, doc_options, doc_globals, doc_file_refs, doc_sections, FTS5 index |
| Published docs | `~/data/vista-docs/publish/` | `VISTA_DOC_PUBLISH` | Consolidated markdown by section/app |
| (Cache) | `~/data/vista/joined.db` | `VISTA_CACHE_DB` | Materialized join cache (built by `vista build-cache`) |

The most heavily used inputs:

- **`routines-comprehensive.tsv`** — one row per routine, with package,
  line count, in/out-degree, RPC×/OPT×, and source path.
- **`routine-calls.tsv`** — every call edge.
- **`routine-globals.tsv`** — every global usage with ref-count.
- **`xindex-errors.tsv`** — XINDEX findings (Style, Practice, Errors).
- **`rpcs.tsv`, `options.tsv`, `protocols.tsv`, `packages.tsv`,
  `xindex-tags.tsv`** — entity tables.
- **`files.tsv`, `piks.tsv`** (data model) — FileMan files with PIKS
  class.
- **`documents`, `doc_routines`, `doc_rpcs`, `doc_options`,
  `doc_sections`, `doc_sections_fts`** (SQLite) — doc side.

The `v_*_coverage` SQL views in `frontmatter.db` (e.g.
`v_routine_coverage`, `v_rpc_coverage`) are the most underrated
asset: they pre-aggregate "for routine X, here are all the docs that
mention it." vista-cli leans on them directly.

### 1.4 Implementation

```
src/vista_cli/
  __main__.py        # python -m vista_cli  →  vista
  cli.py             # Click subcommand wiring (one add_command per cmd)
  config.py          # path resolution from env vars
  canonical.py       # package id: directory ↔ ns ↔ app_code
  snapshot.py        # bundle create / verify / info / install
  fetch.py           # snapshot download + atomic swap
  data/
    packages.csv     # ships in-tree; canonical map (16 packages)
  stores/
    code_model.py    # lazy TSV reader, per-column indexes
    data_model.py    # FileMan files / PIKS reader
    doc_model.py     # read-only SQLite handle
    joined.py        # cross-store joins (coverage, links, neighbors)
    cache.py         # materialized SQLite cache build/read
    code_view.py     # cache-aware proxy in front of CodeModelStore
  commands/          # one Click command per file (24 commands total)
  format/
    json_out.py      # deterministic JSON (sorted keys, 2-space indent)
    tsv_out.py       # tab-separated with tab/newline escaping
    markdown.py      # rich human-friendly output
```

A few implementation choices worth knowing about as a user:

- **Lazy and memoized.** `CodeModelStore` reads only the TSVs a query
  needs and caches them per-process; per-column indexes give O(1)
  lookups. Cold start is on the order of 200–400 ms; warm queries
  are sub-100 ms.
- **Cache-backed hot paths.** Once `vista build-cache` has produced
  `joined.db`, the routine / links / patch / neighbors commands
  consult it transparently via a `CodeModelView` proxy — sub-100 ms
  even on cold shells. `--no-cache` at the top level forces the
  TSV path for debugging or side-by-side comparisons; a stale cache
  is auto-detected and ignored rather than served.
- **Doc store failures are non-fatal.** If `frontmatter.db` is
  missing or unreadable, `vista routine X` still returns code facts;
  it just records `docs_error` in the JSON output. Code-only
  commands (`vista where`, `vista layers`, `vista matrix`,
  `vista risk`) work without the doc store at all.
- **`--latest` is the default.** Most commands include only docs
  from `documents.is_latest = 1`. Use `--all-versions` to include
  patch-bound and superseded doc versions.
- **Reference shapes are auto-detected.** `RTN`, `TAG^RTN`, `^GLOBAL`,
  `^RTN`, RPC name, option name, file number, patch ID — `vista`
  classifies each by shape (`canonical.classify_ref`) and routes
  accordingly.
- **Single runtime dependency.** `click >= 8.1`. No DuckDB, Polars,
  or FastAPI; just stdlib + sqlite3 for the actual query path.
- **Python 3.12+.** `make install` runs `uv sync --extra dev`;
  `make check` runs ruff + mypy + pytest. End users never see this:
  Homebrew handles Python on macOS, the PyInstaller tarball bundles
  it on Linux.

---

## 2. Installing and configuring

Three install paths, depending on how you'll use vista-cli. The
project's full distribution rationale is in
[vista-cli-packaging.md](vista-cli-packaging.md).

**macOS — Homebrew (recommended for end users):**

```bash
brew tap rafael5/vista https://github.com/rafael5/vista-cli
brew install vista
vista init        # download + install the snapshot data bundle
vista doctor      # verify
```

Homebrew installs `python@3.12` as a transitive dependency; you
never see pip or a venv.

**Linux — self-contained PyInstaller tarball:**

```bash
curl -LO https://github.com/rafael5/vista-cli/releases/latest/download/vista-linux-x86_64.tar.xz
tar -xJf vista-linux-x86_64.tar.xz
sudo ln -s "$PWD/vista/vista" /usr/local/bin/vista
vista init
vista doctor
```

The Linux tarball is built against glibc 2.17 (manylinux2014) and
bundles its own Python interpreter — no Python required on the
target. An `aarch64` build ships alongside the `x86_64` one.

**From source (contributors):**

```bash
git clone https://github.com/rafael5/vista-cli ~/projects/vista-cli
cd ~/projects/vista-cli
make install      # uv sync --extra dev + pre-commit + fixtures
vista doctor
```

**`vista doctor`** is the first command to run after install — and
the first command to run when something stops working. It checks
each of the five data inputs from §1.3 and reports `[ok]`, `[warn]`,
or `[!!]` per item. Warnings (e.g. cache missing or stale) are
non-fatal; `[!!]` on the code model or doc DB will block most
commands.

To point at non-default paths, export env vars in your shell init:

```bash
export VISTA_CODE_MODEL=/path/to/code-model
export VISTA_DOC_DB=/path/to/frontmatter.db
export VISTA_M_HOST=/path/to/VistA-M-host
```

The defaults in `config.py` match the single-user setup documented
in the project's CLAUDE.md.

### 2.1 Shell completion (optional)

`vista` ships with Click-powered tab-completion for routine, package,
RPC, option, and file-number arguments. Install once per shell:

```bash
# bash
_VISTA_COMPLETE=bash_source vista > ~/.local/share/vista-completion.bash
echo 'source ~/.local/share/vista-completion.bash' >> ~/.bashrc

# zsh
_VISTA_COMPLETE=zsh_source vista > ~/.local/share/vista-completion.zsh
echo 'source ~/.local/share/vista-completion.zsh' >> ~/.zshrc

# fish
_VISTA_COMPLETE=fish_source vista > ~/.config/fish/completions/vista.fish
```

After reloading your shell, `vista routine PRC<TAB>` expands against
the live code-model. The completer reads from the same data sources
as the queries themselves (cache when fresh, TSVs / SQLite
otherwise) and is capped at 50 candidates per <TAB> to keep the
shell responsive. If the data sources aren't set up yet (`vista
init` not run), completion silently returns nothing — it never
crashes the shell.

### 2.2 Typo tolerance

When you mistype a name, vista responds with a "Did you mean…?"
suggestion drawn from the live entity list, ranked by edit-distance:

```
$ vista routine PRCA45TP
Routine 'PRCA45TP' not found in code-model TSVs.
Did you mean: PRCA45PT?
```

Active for `vista routine`, `vista package`, `vista rpc`,
`vista option`, and `vista file`. Case-insensitive: lowercase input
still finds the upper-case routine name, mixed-case input still
finds the directory-cased package name.

---

## 3. Command reference

24 top-level commands (plus the four `vista snapshot` subcommands),
grouped by what they do. Every command supports `--help`. Every
command that produces tabular data supports `--format md|json|tsv`
(a few flat commands do `md|json` only); see §4.1 for when to use
which.

### 3.1 Inspecting one artifact

These are the "tell me about X" commands. One required argument
per command, output joins both stores by default.

#### `vista routine RTN` — the anchor command

The most-used command. Joins everything `vista-meta` knows about
the routine with every doc section that mentions it.

```
$ vista routine PRCA45PT
```

Returns: package (with ns and app_code), source path, line count,
in/out-degree, RPC×/OPT× counts, version line, callees, callers,
globals (with PIKS class), XINDEX findings, RPCs/options exposed,
and every doc that names the routine (latest-version-only by
default). Add `--no-docs` to skip the SQLite join, `--all-versions`
to include patch-bound docs, `--format json` for an LLM-ready
object.

#### `vista package PKG`

Package overview joining both stores. `PKG` accepts directory
(`Outpatient Pharmacy`), namespace (`PSO`), or VDL app code
(`PSO`). Output: routine roll-up (top 25 by in-degree), RPC list,
option list, every doc bound to the package via `app_code` /
`pkg_ns`. `--no-docs` for code-only; `--format tsv` returns a
docs-only table.

#### `vista file N`

FileMan file by number. Returns metadata (name, global root, field
count, record count, PIKS class), top 25 routines accessing the
file's global, every doc section that names file number `N`.

#### `vista global NAME`

Global usage report. `^DPT` and `DPT` both work. Returns the top
25 routines by reference count plus every doc section that names
the global.

#### `vista rpc NAME`

RPC end-to-end. RPC definition row (tag, source routine, return
type, version, availability, inactive flag, package) plus docs
that mention it.

#### `vista option NAME`

Option / menu metadata (menu text, type, entry routine + tag,
package) plus docs that mention it.

#### `vista patch PATCH_ID`

Routines whose line-2 patch list contains `PATCH_ID` plus every
doc bound to that patch. Useful for "what did this patch
actually change?"

#### `vista where REF`

Jump-to-source. Accepts `RTN`, `^RTN`, or `TAG^RTN`. Prints a
single line `path:line` to stdout — pipe to `$EDITOR` for an
"open at definition" workflow. Exit 2 if the ref shape isn't
supported (e.g. an RPC name); exit 1 if not found.

### 3.2 Cross-references and graph walks

#### `vista links REF`

Dense one-line-per-section cross-reference for a routine. Shows
package, options, RPCs, files, docs, patches in fixed-width
columns — the "everything connected to this routine in 12 lines"
view. JSON output is structured for downstream tooling.

#### `vista neighbors REF [--depth N] [--top K]`

Graph walk around a routine. Depth 1: callees. Depth 2: callees
of callees (top K by traffic). Plus same-package siblings ranked
by call cohesion, plus same-data routines that share the routine's
heaviest globals. The "what lives near this thing" view, useful
for learning a package by exploring outward from one entry point.

#### `vista timeline [REF | --pkg PKG]`

Chronological column of patches and doc events for a routine or
package. Patches come from line-2 lists across `.m` files; doc
events come from `documents.patch_id` and `pub_date`. Sorted by
date. Either `REF` or `--pkg` is required (exit 64 if neither).

### 3.3 Search

#### `vista search PATTERN [--scope all|routines|rpcs|options|files|docs]`

Unified case-insensitive substring search across code-model entity
names plus FTS5 phrase search over doc sections. Default scope is
`all`; narrow with `--scope` for a faster, less noisy result.
`--limit` (default 20) caps each scope.

#### `vista doc QUERY [--app PSO]`

FTS5-only search over doc section headings and bodies. Returns
ranked hits with snippet, doc title, heading path, and section
location. `--app` filters to a single VDL app code; `--all-versions`
includes superseded docs.

### 3.4 Reporting and analysis

#### `vista coverage --pkg PKG`

What fraction of a package's routines, RPCs, and options are
mentioned in at least one VDL doc. Plus the top 25 *un-documented*
routines, ordered by in-degree (highest-traffic untested first).
The triage report for "where should we write docs?"

#### `vista risk RTN`

Composite 0–100 risk score for one routine combining: in-degree
(blast radius), patch count (churn), XINDEX findings (debt),
P-class PIKS globals (double weight), cross-package outbound
coupling, and doc coverage (undocumented increases risk). Bucketed
as low / moderate / high. Useful for code-review triage.

#### `vista layers --pkg PKG`

Topological sort of intra-package calls. Layer 0 = leaves; layer N
depends only on layers `< N`. The natural reading order of a
package falls out — start at layer 0 to learn it from the bottom
up. Cyclic groups (mutual recursion) are listed separately.

#### `vista matrix [--kind package]`

N × N cross-package call-volume matrix. The off-diagonal cells
are the de facto package APIs (regardless of whether the VA
documented them as such). Heaviest cells call out the most-used
boundaries. Markdown caps to top `--top` cross-pkg edges; JSON and
TSV give the full edge list.

### 3.5 AI bundling

#### `vista context REF [--with-source] [--bytes N]`

Builds a self-contained markdown bundle for a routine or package,
suitable for pasting into an LLM chat. Includes routine info, doc
sections that mention it (full body text), and optionally the
routine's source. Respects a byte budget (`--bytes`, default
200 000) and truncates with `…truncated` if needed.

#### `vista ask QUESTION [--routine RTN] [--pkg PKG]`

`context` with a question header at the top. The LLM sees the
goal before the bundle.

```bash
vista ask "how does AR purge exempt bills end-to-end?" \
   --routine PRCA45PT --with-source --bytes 250000 > /tmp/q.md
```

### 3.6 Operations

#### `vista doctor`

Health check on the five data inputs from §1.3 plus the cache and
installed snapshot version. Run it after install and any time
something stops working. Warns (non-fatal) if the cache is missing
or stale.

#### `vista init [--from PATH] [--snapshot VERSION] [--data-dir PATH] [--force]`

Idempotent bootstrap. Detects whether usable data already exists
(env vars set or default paths populated); if so, prints what's
there and exits cleanly without overwriting. Otherwise it fetches
a snapshot bundle (or installs from `--from PATH` for air-gapped
machines) and runs `build-cache` against the freshly-installed
tree. The two-command "from clean machine to working query" path:
`brew install` → `vista init`.

#### `vista fetch [--from PATH] [--snapshot VERSION] [--list]`

Lower-level than `init` — just download + verify + atomically
install a snapshot bundle. `--list` queries the GitHub Releases API
and prints available snapshots. `--from PATH` skips the download
and installs from a local tarball (the air-gapped consumer path).
Old install is preserved at `<data-dir>.bak/` for one-deep rollback.

#### `vista snapshot {create | verify | info | install}`

The producer + verification side of the snapshot pipeline. Mostly
run by CI; a developer touches it only when reproducing a bundle
locally or auditing one.

- `vista snapshot create --out bundle.tar.xz [--snapshot-version vX.Y]`
  packs the configured stores into a portable bundle with an
  embedded `snapshot.json` manifest + SHA-256 sidecar.
- `vista snapshot verify PATH` validates structure, recomputes the
  embedded SHA-256s against the actual archive contents.
- `vista snapshot info PATH` prints the embedded manifest without
  extracting anything.
- `vista snapshot install PATH` is `vista fetch --from PATH` minus
  the download step.

#### `vista build-cache [--out PATH]`

Materializes the joined manifest from vista-meta + vista-docs into
a single SQLite file at `cache_db` (default
`~/data/vista/joined.db`). Pre-computes the join tables
(`routine_doc_refs`, `rpc_doc_refs`, `option_doc_refs`,
`file_doc_refs`, `patch_routine_refs`, `package_canonical`) plus
mirrors of the most-queried code-model TSVs. Run after every
vista-meta bake or vista-docs ingest — `vista init` does this for
you on snapshot install. Reports row counts per table and elapsed
time.

---

## 4. Using vista-cli effectively

### 4.1 The four output formats

The same query against the same data, in four shapes. Pick the
right one and downstream tooling becomes trivial.

| Format | Use when | Why |
|---|---|---|
| `--format md` (default) | Reading in a terminal, piping to `\| less`, pasting into a chat or editor | Human-friendly headings, paths, deterministic line breaks |
| `--format json` | Shell pipes, `jq`, scripts, MCP servers, LLM tools | Structured object, deterministic key order |
| `--format tsv` | Spreadsheets, `awk`, joining with vista-meta TSV outputs | One row per record, header on line 1 |
| `--format table` | Quick one-line views, status checks (commands that support it) | Tight columnar |

A few high-leverage shell idioms:

```bash
# every doc section about agent cashier, just titles
vista doc "agent cashier" --format json | jq '.[].title'

# every undocumented PSO routine, sorted by in-degree
vista coverage --pkg PSO --format json | jq -r '.undocumented[] | "\(.in_degree)\t\(.routine)"' | sort -rn

# build a package-level call matrix ready for a spreadsheet
vista matrix --format tsv > /tmp/pkg-matrix.tsv

# diff "this routine's neighbors" before and after a refactor
vista neighbors PRCA45PT --format json > before.json
# ...refactor + rebake...
vista neighbors PRCA45PT --format json > after.json
diff before.json after.json
```

### 4.2 Workflow recipes

These are the patterns that come up daily.

**Reading code while writing it.** Open `PRCA45PT.m`, then in
another terminal:

```bash
vista routine PRCA45PT       # facts + docs
vista neighbors PRCA45PT     # what's connected
vista timeline PRCA45PT      # how it changed over 25 years
```

**Onboarding to a new package.** Don't read routines alphabetically.
Read them in dependency order:

```bash
vista layers --pkg PSO       # layer 0 first, then up
vista coverage --pkg PSO     # which to read with docs alongside
vista matrix                 # who calls into PSO from outside
```

**Triaging a code review.** Risk-rank the routines being changed:

```bash
for rtn in $(git diff --name-only HEAD~1 | xargs -n1 basename | sed 's/\.m$//'); do
  vista risk "$rtn" --format json | jq -r '"\(.score)\t\(.routine)"'
done | sort -rn
```

**Investigating a doc-driven question.** Start with FTS5, then
follow the entity links:

```bash
vista doc "drug-drug interaction" --app PSO
# pick a section, note the routines/options it names
vista routine <RTN>          # for each named routine
vista option <NAME>          # for each named option
```

**Investigating a code-driven question.** The opposite direction:

```bash
vista routine PSOORNE                # who/what is this?
vista links PSOORNE                  # cross-refs, dense
vista neighbors PSOORNE --depth 2    # the conceptual neighborhood
vista where PSOORNE | xargs $EDITOR  # open the source
```

**Asking an AI about a hard VistA question.**

```bash
vista ask "how does AR purge exempt bills end-to-end?" \
  --routine PRCA45PT --with-source --bytes 250000 > /tmp/q.md
# paste /tmp/q.md into Claude/ChatGPT
```

**Building a coverage report for a package.**

```bash
vista coverage --pkg PRCA --format md > /tmp/prca-coverage.md
```

**Speeding up daily use.** After the first time `vista doctor`
warns about a missing cache:

```bash
vista build-cache            # 30–60s; speeds up hot queries
```

Re-run after every vista-meta bake or vista-docs ingest. `vista
doctor` warns when the cache is older than either source.

### 4.3 Tips and conventions

- **Reference shapes are permissive.** Most commands that take a
  reference will accept the variations you'd naturally type. The
  rule of thumb: if `vista <noun>` says "not found" and you typed
  the right name, try a different shape (`^DPT` vs `DPT`, `EN^RTN`
  vs `RTN`).
- **`--no-docs` for speed.** When you don't need the doc join,
  skipping the SQLite query roughly halves command latency.
- **`--all-versions` rarely.** The default of `is_latest = 1` is
  almost always what you want. Reach for `--all-versions` only when
  you're researching what a *specific patch* documented.
- **Pipe to `less -R`** if a markdown output overflows your
  terminal — the output is plain UTF-8 so paging works fine.
- **JSON is machine-stable.** Keys are sorted; numbers are numbers;
  strings are strings. Build scripts on top of `--format json` with
  confidence.
- **Exit codes are scriptable.** 0 = OK, 1 = not-found / missing
  store, 2 = ambiguous or unsupported ref shape, 64 = usage error.
- **`vista` is read-only.** It doesn't modify TSVs or
  `frontmatter.db`. Run upstream tools (vista-meta bake, vista-docs
  ingest) when you need fresher data; then run `vista build-cache`
  to refresh the join cache.

---

## 5. Troubleshooting

| Symptom | What it means | What to do |
|---|---|---|
| `vista doctor` shows `[!!] code model` | `VISTA_CODE_MODEL` doesn't point at a directory of TSVs | Run a vista-meta bake or fix the env var |
| `vista doctor` shows `[!!] doc db` | `frontmatter.db` is missing or unreadable | Run a vista-docs ingest, or unset `VISTA_DOC_DB` to use the default |
| `vista doctor` shows `[warn] cache stale` | The join cache is older than one of the sources | `vista build-cache` |
| `Routine 'X' not found in code-model TSVs` | Routine isn't in `routines-comprehensive.tsv` | Check spelling; if recently added, re-bake vista-meta |
| `vista routine X` returns code facts but no docs | Doc store unreachable; `docs_error` in JSON | Check `VISTA_DOC_DB`; fall back to `--no-docs` |
| `vista where X` exits 2 | Ref shape isn't routine-like (e.g. an RPC name) | Use `vista rpc X` / `vista option X` instead |
| Slow first query after a clean shell | Cold TSV read (200–400 ms) | Run `vista build-cache` and subsequent queries are <100 ms |
| `--format tsv` looks malformed | A field contained literal tab/newline | Tabs/newlines are replaced with spaces; switch to `--format json` for full fidelity |

For deeper architectural context — why each design decision was
made, what's planned for phases 2–4, and the open questions that
informed the canonical package map — see
[vista-cli-planning.md](vista-cli-planning.md).

For the portable-distribution design (`vista init` / `vista fetch`
/ `vista snapshot`, the ~60 MB snapshot tarball, air-gapped install
flow), see
[vista-cli-portable-distribution.md](vista-cli-portable-distribution.md).
