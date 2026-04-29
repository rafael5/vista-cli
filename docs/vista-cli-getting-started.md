# vista-cli — Getting Started

A practical, command-by-command tour of `vista`, the unified CLI that
joins the VistA code model with VA Document Library frontmatter into
one queryable surface.

This guide is for people who want to install vista-cli and start
running queries. Each command is shown with both its input (what you
type) and its output (what the tool actually prints). Outputs were
captured from a working install — they are real, not paraphrased.

For deeper background, design rationale, and workflow recipes, see
[vista-cli-guide.md](vista-cli-guide.md).

---

## Table of contents

- [1. Install](#1-install)
  - [1.1 macOS — Homebrew](#11-macos--homebrew)
  - [1.2 Linux — PyInstaller tarball](#12-linux--pyinstaller-tarball)
  - [1.3 From source](#13-from-source)
- [2. Configure](#2-configure)
- [3. Bootstrap data](#3-bootstrap-data)
- [4. Verify the install](#4-verify-the-install)
- [5. Uninstall](#5-uninstall)
- [6. Command tour](#6-command-tour)
  - [6.1 `doctor`](#61-doctor)
  - [6.2 `init`](#62-init)
  - [6.3 `fetch`](#63-fetch)
  - [6.4 `snapshot`](#64-snapshot)
  - [6.5 `build-cache`](#65-build-cache)
  - [6.6 `list`](#66-list)
  - [6.7 `tree`](#67-tree)
  - [6.8 `routine`](#68-routine)
  - [6.9 `package`](#69-package)
  - [6.10 `file`](#610-file)
  - [6.11 `global`](#611-global)
  - [6.12 `rpc`](#612-rpc)
  - [6.13 `option`](#613-option)
  - [6.14 `patch`](#614-patch)
  - [6.15 `where`](#615-where)
  - [6.16 `links`](#616-links)
  - [6.17 `neighbors`](#617-neighbors)
  - [6.18 `timeline`](#618-timeline)
  - [6.19 `search`](#619-search)
  - [6.20 `doc`](#620-doc)
  - [6.21 `coverage`](#621-coverage)
  - [6.22 `risk`](#622-risk)
  - [6.23 `layers`](#623-layers)
  - [6.24 `matrix`](#624-matrix)
  - [6.25 `context`](#625-context)
  - [6.26 `ask`](#626-ask)
- [7. Output formats](#7-output-formats)

---

## 1. Install

Pick one path. All three give you the same `vista` binary on PATH.

### 1.1 macOS — Homebrew

```text
$ brew tap rafael5/vista https://github.com/rafael5/vista-cli
$ brew install vista
$ vista --version
vista, version 0.1.1
```

Homebrew installs `python@3.12` as a transitive dependency. You never
see pip, a venv, or a Python toolchain.

### 1.2 Linux — PyInstaller tarball

A self-contained tarball that bundles its own Python interpreter.
Built against glibc 2.17 (manylinux2014). `aarch64` and `x86_64`
builds are published.

```text
$ curl -LO https://github.com/rafael5/vista-cli/releases/latest/download/vista-linux-x86_64.tar.xz
$ tar -xJf vista-linux-x86_64.tar.xz
$ sudo ln -s "$PWD/vista/vista" /usr/local/bin/vista
$ vista --version
vista, version 0.1.1
```

No system Python is required. To uninstall, remove the symlink and
the extracted `vista/` directory.

### 1.3 From source

For contributors and people who want to edit the code.

```text
$ git clone https://github.com/rafael5/vista-cli ~/projects/vista-cli
$ cd ~/projects/vista-cli
$ make install
$ .venv/bin/vista --version
vista, version 0.1.1
```

The repo's `Makefile` runs `uv sync --extra dev`, sets up pre-commit
hooks, and builds the test fixtures. Use `.venv/bin/vista` directly,
or `source .venv/bin/activate` to put it on PATH.

---

## 2. Configure

`vista` reads from up to six on-disk locations. None of them are
managed by vista-cli itself — you point at them via env vars (or
accept the defaults).

| Source           | Default path                                | Env var              |
|------------------|---------------------------------------------|----------------------|
| Code model TSVs  | `~/vista-meta/vista/export/code-model/`     | `VISTA_CODE_MODEL`   |
| Data model TSVs  | `~/vista-meta/vista/export/data-model/`     | `VISTA_DATA_MODEL`   |
| VistA-M source   | `~/vista-meta/vista/vista-m-host/`          | `VISTA_M_HOST`       |
| Doc DB (SQLite)  | `~/data/vista-docs/state/frontmatter.db`    | `VISTA_DOC_DB`       |
| Published docs   | `~/data/vista-docs/publish/`                | `VISTA_DOC_PUBLISH`  |
| Joined cache     | `~/data/vista/joined.db`                    | `VISTA_CACHE_DB`     |

Most users get all six populated automatically by [`vista
init`](#62-init), which downloads a snapshot bundle from a GitHub
release and unpacks it into the default locations.

To point at non-default paths (e.g. an external drive, or a checkout
from a colleague), export the env vars in your shell init:

```text
$ export VISTA_CODE_MODEL=/data/exports/code-model
$ export VISTA_DOC_DB=/data/exports/frontmatter.db
$ export VISTA_M_HOST=/data/exports/VistA-M-host
```

`vista doctor` (next section) reports which paths are in use.

---

## 3. Bootstrap data

After install, run `vista init` once. It downloads a ~64 MB snapshot
bundle, verifies SHA-256 hashes, atomically installs into
`~/data/vista/snapshot/`, and builds the joined query cache.

```text
$ vista init
```

Idempotent — re-running when data is already present prints what's
on disk and exits without overwriting. Use `--force` to reinstall.

Air-gapped machines can pass `--from path/to/bundle.tar.xz` to skip
the network entirely.

---

## 4. Verify the install

```text
$ vista doctor
  [ok] code-model dir: /home/rafael/vista-meta/vista/export/code-model
  [ok]   routines-comprehensive.tsv: /home/rafael/vista-meta/vista/export/code-model/routines-comprehensive.tsv
  [ok]   routine-calls.tsv: /home/rafael/vista-meta/vista/export/code-model/routine-calls.tsv
  [ok] data-model dir: /home/rafael/vista-meta/vista/export/data-model
  [ok] vista-m-host: /home/rafael/vista-meta/vista/vista-m-host
  [ok] doc DB: /home/rafael/data/vista-docs/state/frontmatter.db
  [ok] doc DB content: 616 latest docs, 23714 routine refs
  [ok] doc publish dir: /home/rafael/data/vista-docs/publish
  [ok] joined cache: /home/rafael/data/vista/joined.db (built 2026-04-29T10:40:42+00:00)

OK — all checks passed
```

If you see `[!!]` on the code model or doc DB, the corresponding env
var is unset or pointing at the wrong place. `[warn]` on the cache
just means the cache hasn't been built yet — run `vista build-cache`.

---

## 5. Uninstall

**Homebrew (macOS):**

```text
$ brew uninstall vista
$ brew untap rafael5/vista
$ rm -rf ~/data/vista          # snapshot + cache
```

**PyInstaller tarball (Linux):**

```text
$ sudo rm /usr/local/bin/vista
$ rm -rf vista/                # the extracted directory
$ rm -rf ~/data/vista          # snapshot + cache
```

**From source:**

```text
$ rm -rf ~/projects/vista-cli
$ rm -rf ~/data/vista
```

vista-cli writes only to `~/data/vista/` (snapshot + cache) and to
the cache locations under `~/data/vista/cache/`. It does not modify
the upstream code-model TSVs or `frontmatter.db`. If you want to
remove those too, delete `~/vista-meta/` and `~/data/vista-docs/`.

---

## 6. Command tour

24 top-level commands, in the order you'd typically meet them.
Every command supports `--help`. Outputs below are real, captured
from `vista 0.1.1` against the snapshot installed on the author's
machine — your numbers will differ.

### 6.1 `doctor`

Health check for the five data inputs plus the cache and the
installed snapshot version. Run it after install, after a snapshot
update, or any time something stops working.

```text
$ vista doctor
  [ok] code-model dir: /home/rafael/vista-meta/vista/export/code-model
  [ok]   routines-comprehensive.tsv: /home/rafael/vista-meta/vista/export/code-model/routines-comprehensive.tsv
  [ok]   routine-calls.tsv: /home/rafael/vista-meta/vista/export/code-model/routine-calls.tsv
  [ok] data-model dir: /home/rafael/vista-meta/vista/export/data-model
  [ok] vista-m-host: /home/rafael/vista-meta/vista/vista-m-host
  [ok] doc DB: /home/rafael/data/vista-docs/state/frontmatter.db
  [ok] doc DB content: 616 latest docs, 23714 routine refs
  [ok] doc publish dir: /home/rafael/data/vista-docs/publish
  [ok] joined cache: /home/rafael/data/vista/joined.db (built 2026-04-29T10:40:42+00:00)

OK — all checks passed
```

### 6.2 `init`

Bootstraps the data stores from a snapshot bundle. Idempotent — if
the data is already installed, it prints what's on disk and exits
cleanly.

```text
$ vista init --help
Usage: vista init [OPTIONS]

  Bootstrap vista-cli's data stores from a snapshot bundle.

Options:
  --snapshot TEXT       Snapshot version to fetch (default: latest).
  --from FILE           Install from a local bundle (air-gapped).
  --data-dir DIRECTORY  Where to install the snapshot (default:
                        ~/data/vista/snapshot).
  --force               Reinstall even when data is already present.
  --releases-api TEXT   GitHub Releases API URL (override for testing).
  --help                Show this message and exit.
```

Typical first run (downloads, verifies, installs, builds cache):

```text
$ vista init
```

Air-gapped install from a previously-downloaded bundle:

```text
$ vista init --from ~/Downloads/vista-snapshot-2026.04.29.tar.xz
```

### 6.3 `fetch`

Lower-level than `init` — just the download + verify + atomic install
step, with no cache build. Use `--list` to see what's available on
the GitHub Releases API.

```text
$ vista fetch --list
2026.04.29  2026-04-29T01:19:48Z         64.2 MB  https://github.com/rafael5/vista-cli/releases/download/snapshot-2026.04.29/vista-snapshot-2026.04.29.tar.xz
```

Old data is preserved at `<data-dir>.bak/` after a successful install,
giving you one-deep rollback.

### 6.4 `snapshot`

The producer side. Mostly run by CI; a developer touches it only when
reproducing a bundle locally or auditing one.

`vista snapshot info PATH` — print the embedded manifest:

```text
$ vista snapshot info ~/data/vista/cache/bootstrap.tar.xz
version       bootstrap.1
schema        1
built_at      2026-04-29T03:05:32+00:00
code-model    7 files, 24 rows
data-model    2 files, 6 rows
frontmatter   3 docs, 3 sections, fts5=yes
```

`vista snapshot verify PATH` — recompute SHA-256s and confirm:

```text
$ vista snapshot verify ~/data/vista/cache/bootstrap.tar.xz
ok: /home/rafael/data/vista/cache/bootstrap.tar.xz
  version  bootstrap.1
  built_at 2026-04-29T03:05:32+00:00
```

`vista snapshot create --out bundle.tar.xz` packs the configured
stores into a portable bundle. `vista snapshot install PATH` is
equivalent to `vista fetch --from PATH`.

### 6.5 `build-cache`

Materialises the cross-store join into `~/data/vista/joined.db`. Run
once after install (already done by `vista init`), and again after
every vista-meta bake or vista-docs ingest. Cold queries drop from
~300 ms to under 100 ms once the cache is hot.

```text
$ vista build-cache
Building cache → /home/rafael/data/vista/joined.db
  file_doc_refs                    22,022
  option_doc_refs                  23,199
  package_canonical                    16
  patch_routine_refs               66,371
  routine_calls_mirror            241,309
  routine_doc_refs                 23,714
  routine_globals_mirror           77,838
  routines_mirror                  39,330
  rpc_doc_refs                        631
Done in 1.3s.
```

### 6.6 `list`

Flat enumeration of a kind. Six subcommands: `packages`, `routines`,
`rpcs`, `options`, `files`, `globals`. Every subcommand supports
`--limit` (default 100–200) and `--format md|json|tsv`.

`vista list packages` — every package, ranked by routine count:

```text
$ vista list packages --limit 10
# Packages

10 entries.

- **Automated Information Collection System**  ns=? app=?  (3147 routines, 0 rpcs, 0 options)
- **Integrated Billing**  ns=IB app=IB  (2451 routines, 0 rpcs, 0 options)
- **Registration**  ns=DG app=DG  (2179 routines, 0 rpcs, 0 options)
- **Scheduling**  ns=? app=?  (1798 routines, 0 rpcs, 0 options)
- **IFCAP**  ns=? app=?  (1640 routines, 0 rpcs, 231 options)
- **Order Entry Results Reporting**  ns=OR app=OR  (1394 routines, 0 rpcs, 0 options)
- **Lab Service**  ns=LR app=LR  (1369 routines, 0 rpcs, 0 options)
- **Automated Medical Information Exchange**  ns=? app=?  (977 routines, 0 rpcs, 0 options)
- **Kernel**  ns=XU app=XU  (934 routines, 0 rpcs, 0 options)
- **Nursing Service**  ns=? app=?  (922 routines, 0 rpcs, 0 options)
```

`vista list routines --pkg PSO` — routines in one package, by
in-degree:

```text
$ vista list routines --pkg PSO --limit 5
# Routines in PSO

5 entries.

- `PSOBPSUT` [Outpatient Pharmacy]  351 lines · in=109 · out=14
- `PSOLSET` [Outpatient Pharmacy]  85 lines · in=81 · out=11
- `PSOHLSN1` [Outpatient Pharmacy]  163 lines · in=78 · out=14
- `PSOBPSU1` [Outpatient Pharmacy]  339 lines · in=76 · out=21
- `PSOUTL` [Outpatient Pharmacy]  371 lines · in=57 · out=18
```

`vista list files` — FileMan files by record count:

```text
$ vista list files --limit 5
# FileMan files

5 entries.

- **129.21** RXNORM SIMPLE CONCEPT AND ATOM ATTRIBUTES  `^ETSRXN(129.21,`  PIKS=? · 1000000 records
- **129.22** RXNORM RELATED CONCEPTS  `^ETSRXN(129.22,`  PIKS=? · 1000000 records
- **757.01** EXPRESSIONS  `^LEX(757.01,`  PIKS=? · 1000000 records
- **83.51** DRG PDX EXCLUSION GROUPS  `^ICDD(83.51,`  PIKS=? · 1000000 records
- **757.1** SEMANTIC MAP  `^LEX(757.1,`  PIKS=? · 961809 records
```

`vista list globals` (corpus-wide) and `vista list globals --routine
RTN` (one routine):

```text
$ vista list globals --limit 5
# Globals

5 entries.

- `^TMP`  129538 refs across 12002 routines
- `^XTMP`  19394 refs across 1843 routines
- `^DD`  16945 refs across 4820 routines
- `^PS`  16797 refs across 1562 routines
- `^DIC`  12847 refs across 4434 routines
```

```text
$ vista list globals --routine PSOBPSUT
# Globals touched by PSOBPSUT

3 entries.

- `^PS`  1 refs across 1 routines
- `^PSDRUG`  1 refs across 1 routines
- `^PSRX`  1 refs across 1 routines
```

### 6.7 `tree`

Hierarchical browser. With no argument: every package at depth 1.
With a package argument: that package's routines, RPCs, and options.

```text
$ vista tree
# Packages

174 packages.
Pass a package name as an argument to expand: `vista tree PSO`.

- **Automated Information Collection System**  ns=? app=?  (3147 routines, 0 rpcs, 0 options)
- **Integrated Billing**  ns=IB app=IB  (2451 routines, 0 rpcs, 0 options)
- **Registration**  ns=DG app=DG  (2179 routines, 0 rpcs, 0 options)
- **Scheduling**  ns=? app=?  (1798 routines, 0 rpcs, 0 options)
- **IFCAP**  ns=? app=?  (1640 routines, 0 rpcs, 231 options)
```

```text
$ vista tree PSO --top 3
# Outpatient Pharmacy  [ns=PSO, app=PSO]  (905 routines, 0 rpcs, 0 options)

## routines (top by in-degree)

- `PSOBPSUT` (351 lines · in=109 · out=14)
- `PSOLSET` (85 lines · in=81 · out=11)
- `PSOHLSN1` (163 lines · in=78 · out=14)
```

`--depth 2` walks one more level (each routine → its top callees);
`--kind routines|rpcs|options` filters which children appear.

### 6.8 `routine`

The anchor command. Everything `vista` knows about a routine, joined
with every doc that mentions it.

```text
$ vista routine PSOBPSUT
# PSOBPSUT  [Outpatient Pharmacy]

351 lines · in=109 · out=14

**source:** `/opt/VistA-M/Packages/Outpatient Pharmacy/Routines/PSOBPSUT.m`
**header:** `;;7.0;OUTPATIENT PHARMACY;**148,247,260,281,287,289,358,385,403,408,512,630,562,680,753**;DEC 1997;Build 53`
**namespace:** `PSO`

## Code facts

**Callees**

- `GET1^DIQ` (func) ×50
- `LSTRFL^PSOBPSU1` (func) ×16
- `NDCFMT^PSSNDCUT` (func) ×11
- ...

**Callers**

- `PSORTSUT` [Outpatient Pharmacy] ×30
- `PSOBPSU1` [Outpatient Pharmacy] ×15
- ...

**Globals**

- `^PS` ×1
- `^PSDRUG` ×1
- `^PSRX` ×1

## Documentation

_No VDL documentation references this routine._
```

Mistype the name and the tool suggests close matches:

```text
$ vista routine PSOORNE
Routine 'PSOORNE' not found in code-model TSVs.
Did you mean: PSOORNEW, PSOORNE6, PSOORNE5?
```

Add `--no-docs` to skip the SQLite join, `--all-versions` to include
patch-bound docs, `--format json` for an LLM-ready object.

### 6.9 `package`

Package overview. Accepts directory name (`Outpatient Pharmacy`),
namespace (`PSO`), or VDL app code (`PSO`) — all three resolve to the
same canonical package.

```text
$ vista package PSO
# Outpatient Pharmacy

namespace `PSO` · app_code `PSO`

905 routines · 119530 lines · 0 RPCs · 0 options

## Top routines (by in-degree)

- `PSOBPSUT` in=109 · out=14 · 351 lines
- `PSOLSET` in=81 · out=11 · 85 lines
- `PSOHLSN1` in=78 · out=14 · 163 lines
- ...

## Documentation

- **[UM]** OneVA Pharmacy User Manual (PSO*7*774)
- **[RN]** Pharmacy Ordering Enhancements (POE) Phase 2 Release Notes
- **[UG]** Pharmacy Reengineering (PRE) Inbound ePrescribing (IEP) User Guide Version 5.0 (Unit 7 Part 2) Updated PSO*7.0*770 (patch PSO*5.0*770)
- **[API]** API Manual - Pharmacy Reengineering (PRE)
- ...
```

### 6.10 `file`

FileMan file by number. Returns metadata, top routines that touch the
file's global, and every doc section that names file `N`.

```text
$ vista file 2
# File 2 — PATIENT

global `^DPT(` · 594 fields · 1811 records

## Top routines touching this global

- `DGLOCK` [Registration] ×41
- `MPIF001` [Master Patient Index VistA] ×40
- `DGRPXX12` [Registration] ×37
- ...

## Documentation

- **[TM]** CPRS Technical Manual: List Manager Version (Updated OR*3.0*636) (patch CPRS*3.0)
- **[UM]** FM 22.2 User Manual (patch DI*22.2)
- **[UM]** Laboratory Version 5.2 User Manual
- ...
```

### 6.11 `global`

Global usage report. Both `^DPT` and `DPT` work as input.

```text
$ vista global ^DPT
# Global `^DPT`

3643 routine(s) · 11396 total ref(s)

## Top routines using this global

- `DGLOCK` [Registration] ×41
- `MPIF001` [Master Patient Index VistA] ×40
- `DGRPXX12` [Registration] ×37
- ...

## Documentation

- **[TM]** Kernel Toolkit Technical Manual: Currently being absorbed by Kernel Technical Manual
- **[TM]** Ambulatory Care Reporting Technical Manual
- **[TM]** Virtual Patient Record (VPR) Technical Manual
- ...
```

### 6.12 `rpc`

RPC end-to-end: tag, source routine, return type, version, plus docs
that mention it.

```text
$ vista rpc ACKQAUD1
# RPC `ACKQAUD1`

entry: `START^ACKQAG01` · returns: 2 · availability: R

## Documentation

_No VDL documentation references this RPC._
```

### 6.13 `option`

Option / menu metadata plus docs that mention it.

```text
$ vista option "A1B2 BACKGROUND JOB"
# OPTION `A1B2 BACKGROUND JOB`

_ODS Background Job_

type: R · entry: `^A1B2BGJ` · package: OPERATION DESERT SHIELD

## Documentation

_No VDL documentation references this option._
```

### 6.14 `patch`

Routines whose line-2 patch list contains `PATCH_ID`, plus every doc
bound to that patch.

```text
$ vista patch 'PSO*7*774'
# Patch `PSO*7*774`

0 routine(s) carry this patch in line-2.

## Documentation

- **[DIBR]** PSO*7*774 Deployment, Installation, Back-Out, and Rollback Guide
  `PSO/pso-7-774-deployment-installation-back-out-and-rollback-guide.md`
```

### 6.15 `where`

Jump-to-source. Prints `path:line` for a routine, `^RTN`, or `TAG^RTN`.
Pipe to `$EDITOR` for an open-at-definition workflow.

```text
$ vista where PRCA45PT
/home/rafael/vista-meta/vista/vista-m-host/Packages/Accounts Receivable/Routines/PRCA45PT.m:1
```

```text
$ vista where EN^PRCA45PT
/home/rafael/vista-meta/vista/vista-m-host/Packages/Accounts Receivable/Routines/PRCA45PT.m:24
```

Exit codes are scriptable: `0` on hit, `1` on not-found, `2` on
unsupported ref shape (e.g. an RPC name).

### 6.16 `links`

Dense one-line-per-section cross-reference. The "everything connected
to this routine in 12 lines" view.

```text
$ vista links PSOBPSUT
routine          PSOBPSUT
package          Outpatient Pharmacy (ns=PSO, app=PSO)
opts             (none)
rpcs             (none)
files            50.073 DUE QUESTIONNAIRE, 50 DRUG, 52 PRESCRIPTION
docs             0
patches          PSOBPSUT*7.0*{148,247,260,281,287,289,358,385,403,408,512,562,630,680,753}
```

### 6.17 `neighbors`

Graph walk around a routine: callees (depth 1 or 2), same-package
siblings ranked by call cohesion, same-data routines that share the
heaviest globals.

```text
$ vista neighbors PSOBPSUT --depth 1 --top 3
# PSOBPSUT — neighbors (depth 1)

_package: Outpatient Pharmacy_

## Callees (depth 1)

- `GET1^DIQ` (func) ×50
- `LSTRFL^PSOBPSU1` (func) ×16
- `NDCFMT^PSSNDCUT` (func) ×11

## Same-package siblings (by call cohesion)

- `PSOBPSU1` shared callees: 11
- `PSOREJP3` shared callees: 10
- `PSOREJU3` shared callees: 10

## Same-data routines (touching the same globals)

- `PSOUTL` [Outpatient Pharmacy] ×153 (shares: ^PSRX, ^PS, ^PSDRUG)
- `PSOSUTL` [Outpatient Pharmacy] ×131 (shares: ^PSRX, ^PS, ^PSDRUG)
- `PSOCAN3` [Outpatient Pharmacy] ×130 (shares: ^PSRX, ^PS)
```

### 6.18 `timeline`

Chronological column of patches and doc events. Either a routine or
`--pkg PKG` is required.

```text
$ vista timeline PSOBPSUT
# timeline: PSOBPSUT

- ????-??-??  `PSOBPSUT*7.0*148`  PSOBPSUT
- ????-??-??  `PSOBPSUT*7.0*247`  PSOBPSUT
- ????-??-??  `PSOBPSUT*7.0*260`  PSOBPSUT
- ????-??-??  `PSOBPSUT*7.0*281`  PSOBPSUT
- ????-??-??  `PSOBPSUT*7.0*287`  PSOBPSUT
- ????-??-??  `PSOBPSUT*7.0*289`  PSOBPSUT
- ????-??-??  `PSOBPSUT*7.0*358`  PSOBPSUT
- ????-??-??  `PSOBPSUT*7.0*385`  PSOBPSUT
- ...
```

`????-??-??` indicates a patch with no `pub_date` in the doc store.
Patches that match a doc release get a real ISO date.

### 6.19 `search`

Unified case-insensitive substring search across code-model entity
names plus FTS5 phrase search over doc sections. Default scope is
`all`; narrow with `--scope routines|rpcs|options|files|docs`.

```text
$ vista search "purge" --limit 4
# search `purge` — 4 hit(s)

## routines

- `HLOPURGE` [Health Level Seven] — ;;1.6;HEALTH LEVEL SEVEN;**126,134,136,137,139,143**;Oct 13, 1995;Build 3
- `HLQPURGE` [Health Level Seven] — ;;1.6;HEALTH LEVEL SEVEN;**153**;Oct 13, 1995;Build 11
- `MDPURGE` [Clinical Procedures] — ;;1.0;CLINICAL PROCEDURES;**11**;Apr 01, 2004;Build 67
- `RAPURGE` [Radiology Nuclear Medicine] — ;;5.0;Radiology/Nuclear Medicine;**34,41**;Mar 16, 1998
```

### 6.20 `doc`

FTS5-only search over doc section headings and bodies. Returns ranked
hits with snippet, doc title, heading path, and section location.

```text
$ vista doc "drug interaction" --app PSO
# doc search: `drug interaction` — 20 hit(s)

## [PSO · UM] OneVA Pharmacy User Manual (PSO*7*774) — Appendix D: Glossary
> …Order Check Order checks ([drug]-allergy/ADR [interactions], [drug]-[drug], duplicate [drug]…
`PSO/oneva-pharmacy-user-manual-pso-7-774.md#appendix-d-glossary`

## [PSO · UM] OneVA Pharmacy User Manual (PSO*7*774) — OneVA Pharmacy Prescription Report
> …FEE Fee Patient Inquiry Check [Drug] [Interaction] Complete Orders from OERR Discontinue…
`PSO/oneva-pharmacy-user-manual-pso-7-774.md#oneva-pharmacy-prescription-report`

## [PSO · API] API Manual - Pharmacy Reengineering (PRE) — PSN56 API – DRUG INTERACTION file (#56)
> [↑ Table of Contents](#table-of-contents)
`PSO/api-manual-pharmacy-reengineering-pre.md#psn56-api-drug-interaction-file-56`
...
```

`--app PSO` filters to one VDL app code. `--all-versions` includes
superseded docs.

### 6.21 `coverage`

What fraction of a package's routines, RPCs, and options is mentioned
in at least one VDL doc — plus the top undocumented routines, ranked
by in-degree (highest-traffic-untested first).

```text
$ vista coverage --pkg PSO
# coverage: Outpatient Pharmacy (ns=PSO, app=PSO)

- routines: 17/905 (1%)
- rpcs:     0/0 (n/a)
- options:  0/0 (n/a)

## Top undocumented routines (by in-degree)

- `PSOBPSUT` in=109 · out=14 · 351 lines
- `PSOLSET` in=81 · out=11 · 85 lines
- `PSOHLSN1` in=78 · out=14 · 163 lines
- `PSOBPSU1` in=76 · out=21 · 339 lines
- `PSOUTL` in=57 · out=18 · 371 lines
- ...
```

### 6.22 `risk`

Composite 0–100 risk score for one routine, combining in-degree
(blast radius), patch count (churn), XINDEX findings (debt), P-class
PIKS globals, cross-package coupling, and doc coverage. Bucketed
low / moderate / high.

```text
$ vista risk PSOBPSUT
# risk: `PSOBPSUT` — 47/100 (moderate)

_package: Outpatient Pharmacy_

## Components

- in_degree                +11
- patch_count              +11
- xindex_findings          +0
- p_class_globals          +0
- cross_package_callees    +10
- undocumented             +15

## Facts

- in-degree:            109
- patches:              15
- XINDEX findings:      0
- P-class globals:      0
- cross-pkg callees:    7
- documented:           no
```

### 6.23 `layers`

Topological sort of intra-package calls. Layer 0 = leaves; layer N
depends only on layers `< N`. The natural reading order of a package
falls out — start at layer 0 to learn the package from the bottom up.

```text
$ vista layers --pkg PSO
# layers: Outpatient Pharmacy

## Layer 0 (245)

- `APSPT041`
- `APSPT042`
- `APSPT051`
- `APSPT052`
- `APSPT16`
- `APSPT161`
- `PSINFO`
- `PSINST`
- ...
```

Cyclic groups (mutual recursion) are listed separately.

### 6.24 `matrix`

N × N cross-package call-volume matrix. Off-diagonal cells are the
de facto package APIs; the heaviest cells call out the most-used
boundaries.

```text
$ vista matrix --top 5
# package call matrix — 172 packages

## Cross-package edges (top by call volume)

- `Integrated Billing` → `VA FileMan` ×14,912
- `Registration` → `VA FileMan` ×13,417
- `Scheduling` → `VA FileMan` ×8,326
- `Outpatient Pharmacy` → `VA FileMan` ×7,333
- `IFCAP` → `VA FileMan` ×6,960

## Intra-package totals

- `Integrated Billing` ×13,742
- `Scheduling` ×11,983
- `Registration` ×10,846
- `IFCAP` ×9,297
- `Order Entry Results Reporting` ×7,790
```

`--format tsv` and `--format json` give the full edge list.

### 6.25 `context`

Builds a self-contained markdown bundle for a routine or package:
routine info + every doc section that mentions it (full body) +
optionally the source. Pipe to a file and paste into an LLM chat.

```text
$ vista context PSOBPSUT --bytes 2000
# PSOBPSUT  [Outpatient Pharmacy]

351 lines · in=109 · out=14

**source:** `/opt/VistA-M/Packages/Outpatient Pharmacy/Routines/PSOBPSUT.m`
**header:** `;;7.0;OUTPATIENT PHARMACY;**148,247,260,281,287,289,358,385,403,408,512,630,562,680,753**;DEC 1997;Build 53`
**namespace:** `PSO`

## Code facts

**Callees**

- `GET1^DIQ` (func) ×50
- `LSTRFL^PSOBPSU1` (func) ×16
...
```

`--bytes N` (default 200 000) caps the output; truncated bundles end
with `…truncated`. `--with-source` appends the raw `.m` file inline.

### 6.26 `ask`

`context` with a question header at the top. The LLM sees the goal
before the bundle.

```text
$ vista ask "what does this routine do?" --routine PSOBPSUT --bytes 1500
# Question

what does this routine do?

# PSOBPSUT  [Outpatient Pharmacy]

351 lines · in=109 · out=14
...
```

Typical pattern — pipe to a temp file, paste into Claude/ChatGPT:

```text
$ vista ask "how does AR purge exempt bills end-to-end?" \
    --routine PRCA45PT --with-source --bytes 250000 > /tmp/q.md
```

---

## 7. Output formats

Every command that produces tabular data supports
`--format md|json|tsv`. A few flat commands do `md|json` only.

`md` (default) — human-friendly markdown:

```text
$ vista list packages --limit 3
# Packages

3 entries.

- **Automated Information Collection System**  ns=? app=?  (3147 routines, 0 rpcs, 0 options)
- **Integrated Billing**  ns=IB app=IB  (2451 routines, 0 rpcs, 0 options)
- **Registration**  ns=DG app=DG  (2179 routines, 0 rpcs, 0 options)
```

`tsv` — pipe-friendly, header on line 1:

```text
$ vista list packages --format tsv --limit 3
package	namespace	app_code	routines	rpcs	options
Automated Information Collection System			3147	0	0
Integrated Billing	IB	IB	2451	0	0
Registration	DG	DG	2179	0	0
```

`json` — structured, deterministic key order:

```text
$ vista routine PSOBPSUT --format json | head
{
  "callees": [
    {
      "callee_routine": "DIQ",
      "callee_tag": "GET1",
      "caller_name": "PSOBPSUT",
      "caller_package": "Outpatient Pharmacy",
      "kind": "func",
      "ref_count": "50"
    },
```

Pipe `--format json` into `jq` for ad-hoc transforms:

```text
$ vista coverage --pkg PSO --format json | jq -r '.undocumented[] | "\(.in_degree)\t\(.routine)"' | head -3
109	PSOBPSUT
81	PSOLSET
78	PSOHLSN1
```

That's the full surface. From here, [vista-cli-guide.md](vista-cli-guide.md)
goes deeper into workflow recipes, shell completion, typo tolerance,
and the troubleshooting matrix.
