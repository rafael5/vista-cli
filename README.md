# vista-cli

**A comprehensive, deterministic knowledge base of the entire VistA
architecture** — every routine, every FileMan file, every RPC and
option, every KIDS patch, every documentation manual, and every
interlinkage between them — exposed through one fast offline
command-line interface.

For developers writing or enhancing VistA code, vista-cli is the
*"answer this question right now"* tool. While you're working on a
routine you need to know — continuously — what calls into it, what
FileMan files it touches, what manual sections describe it, what
patches have revised it, what other routines write the same globals,
what RPCs it backs, what menu options expose it, and what XINDEX
findings it carries. **vista-cli answers each in under a second, in
your terminal, without leaving your editor and without an internet
connection.**

```bash
vista routine PRCA45PT     # code facts + every doc that mentions it
vista doc "agent cashier"  # doc hits + every routine each section names
vista links PRCA45PT       # every interlink for one routine, dense
vista neighbors ORWPCE     # graph walk: callees, siblings, same-data routines
vista risk ORM             # composite 0–100 risk score for a routine
vista tree                 # hierarchical browser over the entire corpus
vista list packages        # the catalog: ~150 packages, rolled-up counts
```

## Deterministic, not generative

**vista-cli does not run an LLM. It does not guess, summarise, or
approximate.** Same query, same bytes out, every time. Every answer
comes from indexed TSV files and a SQLite database — that's the
whole runtime path. No API calls. No tokens. No hallucinations. No
chat round-trips.

LLMs **were** used to build the upstream pipelines that produce the
data: extracting tags from MUMPS source, detecting feature shapes,
classifying every FileMan file under the PIKS taxonomy, parsing 40
years of DOCX/PDF manuals into structured sections, recognising
entity references inside that prose, and cross-linking routines
with the manual sections that describe them. That work already
happened, in the [vista-meta](https://github.com/rafael5/vista-meta)
and [vista-docs](https://github.com/rafael5/vista-docs) projects.

**Its output — 19 deterministic TSVs (~1.0 M rows), 5 data-model
TSVs, and a SQLite frontmatter database with 138,711 FTS5-indexed
manual sections — is the only thing vista-cli reads at query time.**
The reasoning is frozen. The artifacts are content-addressed,
SHA-256-verified, regenerable, and version-stamped to the upstream
commit they came from. Sub-100 ms cache-warm queries against the
entire 40-year VistA corpus, completely offline.

## The VistA developer experience

Three tools, three layers, one workflow:

| Tool | Layer | Scope |
|---|---|---|
| **m-cli** | M-language formatter / linter / test runner | One MUMPS file at a time — knows the language, nothing else |
| **vista-meta VSCode extension** | In-editor routine browser | One routine at a time — sidebar with tags, callers, callees, cross-package call edges |
| **vista-cli** *(this project)* | Cross-product knowledge base | The entire corpus — joins code, data dictionary, and 40 years of manuals |

These compose. `m fmt` formats the file you just edited; the VSCode
extension shows you what calls into it as you read it; vista-cli
answers "…and which user-manual section talks about this routine,
what files it writes, what patches have touched it, what RPCs back
it, what other routines share its globals."

**vista-cli is the integration point of the three.** It reads from
the same data sources that vista-meta produces and the VSCode
extension consumes, adds the documentation half (vista-docs), and
exposes the joins neither of the others can. When a question
requires looking across more than one of those layers — which is
*continuously*, in real development — vista-cli is where you go.

## What's in the knowledge base

Every entity vista-meta and vista-docs have ever extracted from
VistA, and every relationship they've inferred, indexed and joined:

| Surface | Scale |
|---|---:|
| Routines (`.m` source files) | ~39,500 |
| Tags (function entry-points) | ~290,000 |
| Call edges (caller → callee) | ~241,000 |
| Global usages (routine → `^GLOBAL`) | ~78,000 |
| FileMan files (the data dictionary) | ~8,000 |
| Field-to-PIKS pointer rows | ~70,000 |
| Packages (Pharmacy, Lab, Order Entry, …) | ~150 |
| RPCs | ~4,500 |
| Menu options | ~13,000 |
| Protocols | ~6,500 |
| KIDS patches (line-2 patch lists per routine) | ~30,000 distinct |
| XINDEX findings (Style/Practice/Errors) | ~7,000 |
| Manuals on the VA Document Library | ~2,800 |
| Indexed manual sections (FTS5) | ~138,700 |
| Routine references inside manuals | ~23,700 |
| RPC references inside manuals | ~600 |
| Option references inside manuals | ~23,200 |

**Plus every interlinkage** — routine ↔ docs that mention it,
FileMan file ↔ routines that touch its global, RPC ↔ doc section ↔
backing routine, patch ↔ every routine it revised, option ↔ entry
routine ↔ user-manual section that describes the menu, global ↔
FileMan file the global is the storage of, package ↔ canonical
namespace ↔ VDL app-code.

**Total live query surface: ~338 MB**, packed and shipped as a
single ~60 MB `.tar.xz` snapshot bundle. The bundle includes a
`snapshot.json` manifest with SHA-256s and provenance back to the
upstream commits, so any installed copy of vista-cli can prove
which VistA-M release and which VDL snapshot it's serving. `vista
doctor` reports the version; `vista fetch` rolls a new one in
atomically with `.bak/` rollback.

## Where the data comes from

vista-cli is the integrator. The data preparation — downloading,
parsing, classifying, cross-linking — lives in two upstream
projects, each with its own pipeline and release cadence. **Both
projects produce deterministic, regenerable, content-addressed
artifacts** — same VistA-M release in, same byte-identical TSVs out;
same VDL snapshot in, same SQLite schema out.

| Project | Repo | What it produces |
|---|---|---|
| **vista-meta** | [github.com/rafael5/vista-meta](https://github.com/rafael5/vista-meta) | Bakes a running VistA-on-YottaDB into 19 code-model TSVs + 5 data-model TSVs: routines, calls, globals, FileMan files, RPCs, options, protocols, XINDEX findings, KIDS patches, and the PIKS classification of every global. |
| **vista-docs** | [github.com/rafael5/vista-docs](https://github.com/rafael5/vista-docs) | Crawls the VA Document Library, downloads DOCX/PDF, parses heading trees, extracts entities (routines, RPCs, options, file numbers, security keys), and lands everything in `frontmatter.db` with FTS5 over section bodies. |

Adjacent in the ecosystem (not data sources for vista-cli, but
co-evolving with it):

- **[tree-sitter-m](https://github.com/rafael5/tree-sitter-m)** —
  M-language tree-sitter parser; underpins the VSCode extensions
  and the planned `m fmt` / `m lint` / `m test` workflow.
- **[m-standard](https://github.com/rafael5/m-standard)** —
  M-language reference reconciling AnnoStd / YottaDB / IRIS dialects.
- **[vista-docs-api](https://github.com/rafael5/vista-docs-api)** —
  FastAPI read-only HTTP server over the same `frontmatter.db`.

For background, the full feature list, per-command reference, and
worked-example workflows, see the
**[vista-cli guide](docs/vista-cli-guide.md)**. New users should
start with the
**[getting-started tour](docs/vista-cli-getting-started.md)**.

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
make check        # lint + mypy + tests
ln -sf "$PWD/.venv/bin/vista" ~/.local/bin/vista   # optional — put on $PATH

# uninstall
rm -f ~/.local/bin/vista
rm -rf ~/projects/vista-cli          # or wherever the clone lives
```

### Shell completion (optional, applies to all install paths)

`vista routine PRC<TAB>` expands against the live code-model;
`vista package <TAB>`, `vista rpc <TAB>`, `vista option <TAB>`, and
`vista file <TAB>` work the same way. Pick your shell and run the
matching one-liner once:

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

Reload your shell. Completion reads from the same data sources as
the queries themselves and silently returns nothing if the data
isn't installed yet — never crashes the shell.

To remove: delete the generated file and the matching `source` line
from your shell rc.

## Documentation

- **[getting-started tour](docs/vista-cli-getting-started.md)** —
  command-by-command walk-through with real captured input/output.
  Start here.
- **[vista-cli guide](docs/vista-cli-guide.md)** — comprehensive
  user/operator guide: every command, every flag, worked workflow
  recipes, troubleshooting matrix.
- **[planning + design](docs/vista-cli-planning.md)** —
  authoritative for scope, phasing, and the interlinkage taxonomy.
- **[snapshot bundle spec](docs/vista-cli-portable-distribution.md)** —
  the `vista init / fetch / snapshot` machinery and bundle format.
- **[packaging](docs/vista-cli-packaging.md)** — Homebrew formula,
  PyInstaller build, release CI.

## Status

Phases 1–4 of the planning doc are implemented, plus v0.2.0-bound
polish (typo suggestions, shell completion, `vista list`, `vista
tree`). Latest release tagged
[v0.1.1](https://github.com/rafael5/vista-cli/releases/tag/v0.1.1).
ruff + mypy clean.
