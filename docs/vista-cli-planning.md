# vista-cli — Planning & Design Document

A planning document for **`vista`**, a single CLI that joins
vista-meta's code/data model with vista-docs's documentation
frontmatter into one queryable, interlinked surface for VistA. This
is the design — not the implementation.

> Status: design proposal. No code committed yet.
> Scope: planning document for review and refinement before
> implementation. See [§13 phasing](#13-phasing-roadmap) for what
> ships first.

---

## Table of contents

- [1. Executive summary](#1-executive-summary)
- [2. Problem statement](#2-problem-statement)
- [3. The three-CLI ecosystem](#3-the-three-cli-ecosystem)
- [4. Inventory of available artifacts](#4-inventory-of-available-artifacts)
- [5. The interlinkage taxonomy](#5-the-interlinkage-taxonomy)
- [6. Unified data layer](#6-unified-data-layer)
- [7. CLI surface](#7-cli-surface)
- [8. Worked query scenarios](#8-worked-query-scenarios)
- [9. Output formats and AI integration](#9-output-formats-and-ai-integration)
- [10. Relation to sibling tools](#10-relation-to-sibling-tools)
- [11. Additional features for legacy-code situational awareness](#11-additional-features-for-legacy-code-situational-awareness)
- [12. Architecture & implementation plan](#12-architecture--implementation-plan)
- [13. Phasing roadmap](#13-phasing-roadmap)
- [14. Open questions](#14-open-questions)
- [15. Reference](#15-reference)

---

## 1. Executive summary

VistA's situational-awareness problem has two halves:

- **What is the code?** vista-meta has solved this — 19 code-model
  TSVs and 5 data-model TSVs cover routines, packages, calls,
  globals, FileMan files, RPCs, options, protocols, and PIKS
  classifications.
- **What does the documentation say?** vista-docs has solved this —
  a SQLite `frontmatter.db` with 2,842 docs, 23,714 routine
  references, 631 RPC references, 23,199 option references, and
  138,711 FTS5-indexed sections drawn from the VA Document Library.

Today they don't talk to each other. When you open `PRCA45PT.m` you
see what *the code* says, and you'd have to manually search 2,842
docs to find the seven that mention it. When you find a doc
section, you'd have to grep the VistA-M tree to see which routines
actually implement it.

`vista` is the CLI that closes the loop:

```bash
vista routine PRCA45PT     # code-model facts + every doc that mentions it
vista doc "agent cashier"  # doc hits + every routine each section names
vista links PSO            # all interlinks for a package, in one report
vista ask "how does an order get verified?"  # AI-ready bundle
```

Single binary, two backends (TSV + SQLite), one cross-product
manifest. VistA-specific. Orthogonal to **m-cli** (which handles
the M language itself: `m fmt`, `m lint`, `m test`) and **vista-meta**
(which builds the code model). It composes both.

---

## 2. Problem statement

### 2.1 The legacy code-base scale problem

VistA is ~40,000 routines, ~8,000 FileMan files, hundreds of
packages, 40 years of accreted convention, ~3,000 manuals. Cognitive
overhead is the binding constraint. Three layers of fragmentation
amplify it:

1. **Code lives in 40,000 `.m` files** spread across packages, with
   8-character names and no module system.
2. **Behavior is documented in 2,842 manuals** that the VA produces
   in DOCX/PDF, addressed by app code (CPRS, PRCA, PSO) but
   organized by audience (User, Technical, Installation).
3. **No bidirectional index.** A doc says "use the AGENT CASHIER
   menu" but doesn't link to `EN^PRCAACT` directly. The routine
   has no field saying "documented in §4.2 of the User Manual."

vista-meta solved (1). vista-docs solved (2) — frontmatter,
heading-tree extraction, FTS5 search, automatic entity recognition
(routines, RPCs, options, globals, security keys, file references,
keywords). What's missing is the join between (1) and (2).

### 2.2 The questions a unified tool should answer

These are the questions that today require switching between two
projects, two CLIs, and a grep window:

- "Looking at routine X — what's its package, callers, callees,
  globals, AND every documentation section that mentions it?"
- "What's the User Manual say about the AGENT CASHIER menu, and
  which routine implements each action?"
- "FileMan file 433 — what's its data-dictionary, what routines
  read/write it, what manuals describe it, what RPCs expose it?"
- "RPC `PSO LM ALLERGY` — broker entry, source tag, doc sections,
  HL7 mappings if any, last patch that touched it."
- "Option `PSO MAINTENANCE` — menu tree, sub-options, entry
  routines, screenshot in user manual."
- "Patch `PRCA*4.5*341` — what files/routines/options/protocols it
  touched, the install guide for it, and any release notes."
- "Show me the documentation neighborhood of any tag I have under
  the cursor in VSCode."

A single CLI subcommand should answer each in under a second.

---

## 3. The three-CLI ecosystem

Three CLIs, three layers, no overlap. Each owns one part of the
stack and exposes a stable surface to the others.

```
┌─────────────────────────────────────────────────────────────┐
│  vista        (this document — VistA-specific cross-model)  │
│  - joins code, data, KIDS, and documentation                │
│  - vista routine X / vista package PSO / vista doc Q        │
│  - reads vista-meta TSVs + vista-docs frontmatter.db        │
└────────────┬─────────────────────────────────┬──────────────┘
             │                                 │
             ▼                                 ▼
┌──────────────────────────┐      ┌──────────────────────────┐
│ vista-meta (code model)  │      │ vista-docs (doc model)   │
│ - bake VistA-M → 19 TSVs │      │ - crawl VDL → frontmatter│
│ - kids-vc, mfmt, lint    │      │ - SQLite + FTS5 + extract│
│ - VSCode sidebar         │      │ - per-package consolidate│
└──────────────────────────┘      └──────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────┐
│  m-cli   (language-level — orthogonal, used by all of above) │
│  - m fmt    (formatter, byte-identical round-trip on 99.04%) │
│  - m lint   (XINDEX rules, parser-backed)                    │
│  - m test   (planned — M-Unit harness)                       │
│  - tree-sitter-m parser, language-neutral                    │
└──────────────────────────────────────────────────────────────┘
```

### 3.1 Boundary rules

| Concern | Owner | Rationale |
|---|---|---|
| MUMPS parsing, AST | `m-cli` (tree-sitter-m) | Language-neutral; reusable in any tool |
| Formatting, lint, test | `m-cli` | Same |
| Code-model TSV bake | `vista-meta` | Needs YDB container; one-time per VistA release |
| KIDS decompose / assemble | `vista-meta` | Tied to bake corpus + patch tree |
| VSCode extension | `vista-meta` | Sidebar reads code-model TSVs only |
| VDL crawl, ingest, frontmatter | `vista-docs` | Heavy DOCX/PDF dependencies |
| FTS5 over doc sections | `vista-docs` | Owns the SQLite |
| **Cross-product queries** | **`vista`** | **Reads from both, owns the join** |
| Interactive navigation | `vista` | The CLI a developer types daily |
| AI context bundling | `vista` | Aggregates code + docs + history |

Both vista-meta and vista-docs continue to ship their own narrow
CLIs (`vista-meta`, `vista-docs`); `vista` is **not** a replacement,
it's the integrator.

### 3.2 Why "vista" as the root command

- Memorable, three syllables shorter than `vista-meta`.
- Distinguishable from `vista-docs` (which crawls + ingests; not the
  daily-use tool).
- Doesn't collide with the M-language layer (`m`).
- Reads as "tell me about VistA" — exactly what it does.

---

## 4. Inventory of available artifacts

What's actually on disk today, with real counts, that `vista` will
join.

### 4.1 vista-meta — code model

[`vista/export/code-model/`](../vista/export/code-model/) — 19 TSVs,
~1.0 M rows. Schemas in
[code-model-guide.md](code-model-guide.md). Highlights:

| TSV | Rows | Owns |
|---|---|---|
| `routines-comprehensive.tsv` | ~39,500 | per-routine metadata (package, line count, in/out-degree, RPC×/OPT×, source path) |
| `routine-calls.tsv` | ~325 k | every call edge with caller/callee package |
| `routine-globals.tsv` | ~165 k | global usages with ref-counts |
| `xindex-tags.tsv` | (per-tag) | tag kind, line, formal-list, doc summary |
| `xindex-errors.tsv` | (per-finding) | XINDEX findings with severity |
| `rpcs.tsv` | ~3,500 | RPC name → tag → routine |
| `options.tsv` | ~30 k | option name → entry routine + tag |
| `protocols.tsv` | ~10 k | protocol type, entry/exit actions |
| `packages.tsv` | ~150 | package roll-up |
| `package-data.tsv` | (per-pkg) | files/globals owned by each package |
| `vista-file-9-8.tsv` | ~39,500 | File 9.8 (Routine file) — VA's own description, package owner |

### 4.2 vista-meta — data model

[`vista/export/data-model/`](../vista/export/data-model/) — 5 TSVs,
~170 k rows. Schemas in
[piks-analysis-guide.md](piks-analysis-guide.md):

- `files.tsv` — every FileMan file (~8,261 rows) with global root,
  PIKS class, properties (volatility, sensitivity, portability,
  volume), record count.
- `fields.tsv` — every field across all files (~70 k rows).
- `field-piks.tsv` — cross-PIKS pointer matrix.
- `piks.tsv` — file → PIKS class with confidence + heuristic ID.
- (Plus secondary derived files.)

### 4.3 vista-meta — source mirror

[`vista/vista-m-host/`](../vista/vista-m-host/) — host-visible copy
of `/opt/VistA-M/`, organized as
`Packages/<Package Name>/Routines/<RTN>.m`. ~39,500 .m files.

### 4.4 vista-meta — KIDS patches

- [`patches/`](../patches/) — on-disk, decomposed patch trees
  (kids-vc native form).
- Historical `.KID` files round-trip via `kids_vc.py`.
- The line-2 patch list in every `.m` file is the audit trail per
  routine (e.g. `**14,79,153,302,409**`).

### 4.5 vista-docs — frontmatter SQLite

`~/data/vista-docs/state/frontmatter.db` — ~2,842 documents indexed,
with the following relevant tables (verified schemas):

```sql
documents (
  doc_id, rel_path, title, doc_type, doc_label, doc_layer,
  app_code, app_name, section, app_status,
  pkg_ns, patch_ver, patch_id, group_key,
  word_count, page_count, is_stub,
  pub_date, docx_url, pdf_url,
  menu_options, audit_applied,
  description, audience,
  patch_num_int, is_latest, quality_score
)

doc_routines (doc_id, routine, tag, full_ref)        -- 23,714 rows
doc_globals  (doc_id, global_name)
doc_rpcs     (doc_id, rpc_name)                      --    631 rows
doc_options  (doc_id, option_name)                   -- 23,199 rows
doc_security_keys (doc_id, key_name)
doc_file_refs (doc_id, file_number)
doc_codes (doc_id, ...)
doc_keywords (doc_id, keyword)

doc_sections (
  section_id, doc_id, parent_section_id,
  level, seq, heading, anchor,
  char_start, char_end, word_count, body
)                                                    -- 138,711 rows
doc_sections_fts (...)   -- FTS5 over heading + body

-- Coverage views already exist:
v_routine_coverage, v_rpc_coverage, v_option_coverage,
v_global_coverage, v_file_coverage, v_key_coverage,
v_app_latest, v_group_latest, v_doc_enriched
```

This is **already the join engine** for the doc side. `vista` reads
it directly. The `v_*_coverage` views are the most underrated asset
— they say "for routine X, here are all the docs that mention it,
already aggregated."

### 4.6 vista-docs — published markdown tree

`~/data/vista-docs/publish/<section>/<app>--<title>/<doc>.md` — the
human-readable consolidated docs with YAML frontmatter on every
file, organized by VA section (clinical / financial-administrative /
infrastructure / vista-gui-hybrids) and app. Example:

```
publish/financial-administrative/prca--accounts-receivable-ar/
├── document.md
├── installation-guide.md
├── installation-guide--ar.md
├── release-notes.md
├── user-manual--accounts-receivable-v4-5.md
├── accounts-receivable-version-4-5-technical-manual-security-guide/
├── accounts-receivable-version-4-5-user-manual-agent-cashier/
└── patches/
```

`vista` opens these directly when the user wants to read the source.

### 4.7 vista-docs — VDL inventory

`~/data/vista-docs/inventory/vdl_inventory_enriched.csv` — every
manual on the VA Document Library, with app code, DOCX/PDF URL,
publication date, doc type. Used for "is there a newer version
than what we ingested?" checks.

### 4.8 What's missing (the gap `vista` fills)

There is **no table or file today** that says:

- "Routine `PRCA45PT` is documented in section §4.2 of doc #1487."
- "FileMan file 433 is described in §3.1 of the AR Technical Manual."
- "RPC `PSO LM ALLERGY` is documented in §6.4 of the Pharmacy
  User Manual."

The data is there — `doc_routines` has the routine name, `documents`
has the section, `doc_sections` has the heading tree. But nothing
joins them with the **code-model** side (calls, globals, package,
PIKS). That's the cross-product `vista` builds.

---

## 5. The interlinkage taxonomy

Eleven join classes the unified tool must support. Each lists which
TSVs and tables participate.

| # | Join | Code side | Doc side |
|---|---|---|---|
| 1 | Routine ↔ Docs that mention it | `routines-comprehensive.tsv` | `doc_routines` → `documents` → `doc_sections` |
| 2 | Tag ↔ Doc sections | `xindex-tags.tsv` | `doc_routines` (tag column) → `doc_sections` |
| 3 | RPC ↔ Doc sections | `rpcs.tsv` | `doc_rpcs` → `documents` → `doc_sections` |
| 4 | Option ↔ Doc sections | `options.tsv` | `doc_options` → `documents` → `doc_sections` |
| 5 | Protocol ↔ Doc sections | `protocols.tsv` | (no direct table — match by name in `doc_keywords` / FTS5) |
| 6 | Global ↔ Doc sections | `routine-globals.tsv` | `doc_globals` → `documents` |
| 7 | FileMan file ↔ Docs | `files.tsv` | `doc_file_refs` (file_number) |
| 8 | Security key ↔ Routines that LOCK it | `routine-globals.tsv` (`^XUSEC` patterns) | `doc_security_keys` |
| 9 | KIDS patch ↔ Doc | line-2 patch list per `.m` | `documents.patch_id` / `documents.patch_ver` |
| 10 | Package ↔ Doc(s) | `packages.tsv`, `package-manifest.tsv` | `documents.pkg_ns`, `documents.app_code` |
| 11 | Doc section ↔ All entities mentioned | n/a | `doc_sections` text + FTS5 + entity tables |

**The two namespace mismatches that cost time** if not handled in
the join layer:

- vista-meta names packages by **directory** (`Outpatient
  Pharmacy`); vista-docs names them by **VDL app code** (`PSO`) AND
  **VistA M namespace** (`PSO` — sometimes the same, sometimes not).
  Need a canonical `package_id` map: `directory ↔ ns ↔ app_code`.
- A doc may exist in multiple versions/patches; `documents.is_latest`
  is the filter for "currently authoritative."

---

## 6. Unified data layer

Two architectural options. Each has a clear winner for one phase.

### 6.1 Option A — Live joins at query time

`vista` opens the SQLite + reads the TSVs on every command, joins
in memory, returns.

- **Pros:** zero extra storage; always fresh; matches existing
  vista-meta ergonomics.
- **Cons:** 200–400 ms cold-start on TSV reads each invocation.

Good fit for: phase 1, low query volume, scripts.

### 6.2 Option B — Pre-built joined manifest

A nightly (or post-bake) build that produces a small SQLite or DuckDB
file at `~/data/vista/joined.db` containing pre-computed cross-tables:

```sql
-- The 11 joins from §5 materialized
routine_doc_refs (routine, doc_id, section_id, tag, ref_count)
rpc_doc_refs (rpc_name, doc_id, section_id)
option_doc_refs (option_name, doc_id, section_id)
file_doc_refs (file_number, doc_id, section_id)
patch_routine_refs (patch_id, routine, ref_kind)
package_canonical (directory, ns, app_code, group_key)
-- plus mirror copies of the most-queried code-model TSVs
```

- **Pros:** sub-100 ms queries; one place to look for "does X exist
  in either store"; portable (one file).
- **Cons:** staleness (rebuild after every bake or doc ingest).

Good fit for: phase 2, frequent interactive use, VSCode integration.

### 6.3 Recommendation

Ship Option A first (4–6 weeks of work, no new infra). Add Option B
as a `vista build-cache` subcommand once the query patterns settle
— probably phase 3 once we know which joins are hot.

The cache is a derived artifact, regenerated by:

```bash
vista build-cache         # ~30 s; reads vista-meta TSVs + vista-docs SQLite
```

A `vista doctor` check warns when the cache is older than either
source.

---

## 7. CLI surface

### 7.1 Top-level groups

```
vista routine RTN [--tag TAG]            inspect a routine + its docs
vista package  PKG                       package overview joining both stores
vista file     N                         FM file with code use + doc references
vista rpc      NAME                      RPC end-to-end (definition → docs)
vista option   NAME                      Option / menu with sub-options + docs
vista protocol NAME                      Protocol with callers + docs
vista patch    PATCH_ID                  KIDS patch: targets + install guide
vista global   NAME                      Global with FM file + PIKS + docs

vista search   PATTERN [--scope ...]     unified search (code + docs)
vista doc      QUERY [--app PSO]         doc-only search (FTS5)
vista where    REF                       jump-to-source for any artifact

vista links    REF                       all interlinks for one ref
vista neighbors REF [--depth N]          surrounding artifacts (graph walk)
vista timeline REF                       patch / commit / doc-version history

vista context  PKG/RTN [--with-source]   AI-ready bundle (code + docs)
vista ask      "question"                shorthand: pick context + format

vista coverage [--scope routines|rpcs|options]   doc coverage report
vista doctor                             health check (both stores fresh)
vista build-cache                        rebuild joined manifest (phase 2+)
```

Conventions:

- **`REF`** is permissive: `RTN`, `TAG^RTN`, `^GLOBAL`, `RPC NAME`,
  `OPTION NAME`, file number, patch ID. `vista` infers from shape.
- **`--format json|md|tsv|table`** on every command.
- **`--latest`** filters to `documents.is_latest = 1` (default on);
  `--all-versions` opts out.
- **`-q` / `--quiet`** for terse output suitable for shell pipes.
- Exit codes: 0 OK, 1 not-found, 2 ambiguous (multiple matches), 64
  usage error.

### 7.2 Anchor command — `vista routine`

The most-used command. Output shape:

```
$ vista routine PRCA45PT

PRCA45PT  [Accounts Receivable]
  74 lines · in=0 · out=5 · OPT×1 · RPC×0
  source: vista/vista-m-host/Packages/Accounts Receivable/Routines/PRCA45PT.m
  patches: 14, 79, 153, 302, 409  (5 patches over 25 years)
  line-1: ALB/CMS - PURGE EXEMPT BILL FILES (1997-06-30)

CODE FACTS                                            (vista-meta)
  Tags        V, EN, 430, 433, XCLN
  Callers     (none — entrypoint only)
  Callees     BMES^XPDUTL ×7, MES^XPDUTL ×6, HOME^%ZIS ×1,
              ^%ZTLOAD ×1, ^DIK ×1
  Globals     ^PRCA ×18  [P · file 430 ACCOUNTS RECEIVABLE]
  XINDEX      2 Style findings  (line 41, 53 — Lock missing Timeout)
  Exposures   OPT: PRCA PURGE EXEMPT BILL FILES (menu)

DOCUMENTATION                                         (vista-docs)
  3 documents mention this routine:
    [1] AR Technical Manual & Security Guide v4.5         (latest)
        §3.4 "Purge Routines" · §A "Routine Listing"
        publish/.../accounts-receivable-version-4-5-technical-manual-security-guide/
    [2] AR Installation Guide (PRCA*4.5*341)              (patch-bound)
        §2.1 "Pre-installation purge"
    [3] AR User Manual — Supervisor's AR Menu             (latest)
        §4.7 "Exempt Bill Cleanup"  ← option-named section

KIDS HISTORY (line-2 patch list × VDL release notes)
  PRCA*4.5*14   1996-...   (no doc)
  PRCA*4.5*79   1999-...   release-notes available
  PRCA*4.5*153  2002-...   release-notes available
  PRCA*4.5*302  2010-...   release-notes available
  PRCA*4.5*409  2018-...   release-notes available + install guide

NEIGHBORS (graph walk depth 1)
  Same cluster (PRCA45*):  PRCA45A, PRCA45B, PRCA45C
  Same package OPT family: PRCA PURGE * (3 menu options)
```

Every line is clickable in terminals that support OSC 8 (paths) and
copy-friendly. The same data goes to JSON when `--format json`.

### 7.3 Anchor command — `vista links`

Just the cross-references, denser:

```
$ vista links PRCA45PT

routine          PRCA45PT
package          Accounts Receivable (ns=PRCA, app=PRCA)
opts             PRCA PURGE EXEMPT BILL FILES
rpcs             (none)
files (write)   430 ACCOUNTS RECEIVABLE
files (read)     430 ACCOUNTS RECEIVABLE
docs             3
   doc 1487  AR Technical Manual v4.5  §3.4
   doc 1612  AR Install Guide v4.5*341 §2.1
   doc 1701  AR User Manual            §4.7
patches          PRCA*4.5*{14,79,153,302,409}
sections-fts     5 sections also mention this routine outside doc_routines
```

`--format json` gives an LLM-friendly structured object.

### 7.4 Anchor command — `vista neighbors`

Graph walk across the joined model — **the situational-awareness
killer feature**. Show what lives "near" any reference.

```
$ vista neighbors PRCA45PT --depth 2

PRCA45PT
├── callees (depth 1)
│   ├── BMES^XPDUTL  [Kernel]
│   ├── MES^XPDUTL   [Kernel]
│   └── ^DIK         [FileMan]
├── callees-of-callees (depth 2, top-3 by traffic)
│   └── EN^DIK       [FileMan]    used by ^DIK
├── same-package siblings (top-3 by call-cohesion)
│   ├── PRCA45A   shared callee count: 3
│   ├── PRCA45B   shared callee count: 3
│   └── PRCAACT   shared global ^PRCA (212 refs)
├── same-data routines (top-3 writers of file 430)
│   ├── PRCAACT   2,418 refs
│   ├── PRCABIL    412 refs
│   └── PRCAREG    218 refs
└── docs nearby
    └── §A "Routine Listing" of AR Technical Manual co-mentions
         PRCA45PT alongside PRCA45A, PRCA45B, PRCAACT
```

A developer learns the **conceptual neighborhood** of a routine
without reading any code.

### 7.5 Anchor command — `vista ask`

Bundles context for an AI conversation. Doesn't call the LLM —
emits a markdown packet you paste:

```
$ vista ask "how does AR purge exempt bills end-to-end" --routine PRCA45PT > /tmp/q.md
```

Builds:

1. `vista routine PRCA45PT` (full output, markdown).
2. `vista package "Accounts Receivable"` summary.
3. The 3 doc sections that mention `PRCA45PT`, full body text from
   `doc_sections.body`.
4. The release notes for `PRCA*4.5*409` (the most recent patch).
5. The source of `PRCA45PT.m` if `--with-source`.

Default budget 200 KB, capped per `--bytes`. The user's question
goes at the top so the AI sees the goal before the bundle.

This is the "what does it look like to actually use this CLI to ask
hard VistA questions" answer.

---

## 8. Worked query scenarios

Concrete examples — what the user types, what they get back.

### 8.1 "I'm in `PRCA45PT.m` and need the documentation"

```
vista routine PRCA45PT --format md --docs-only > /tmp/d.md
```

Three doc sections, full bodies, ranked by latest first. Pasted
into the editor or read in a preview.

### 8.2 "What's the AGENT CASHIER menu and what implements it?"

```
vista option "PRCA AGENT CASHIER" --tree --with-impls
```

Output: option, sub-options, entry routine + tag for each, doc
section under "Agent Cashier" in the User Manual.

### 8.3 "FileMan file 430 — everything about it"

```
vista file 430
```

Output: data-dictionary fields (top 25), PIKS class, top 10 routines
that touch it, every doc section that names it, every RPC that
returns it.

### 8.4 "What did patch PRCA*4.5*341 actually change?"

```
vista patch "PRCA*4.5*341"
```

Output: routines / files / options / protocols delivered (from KIDS
header parse), the install guide, the release notes, and any doc
revisions tied to that patch_id.

### 8.5 "What's the doc coverage for Pharmacy?"

```
vista coverage --pkg PSO --scope routines
```

Output: of 421 PSO routines, 287 (68%) are mentioned in at least
one VDL doc; 134 (32%) are not. List the un-mentioned, ordered by
in-degree (the most-called undocumented routines first).

### 8.6 "Find every doc section about cross-servicing"

```
vista doc "cross servicing" --app PRCA
```

Hits ranked by `quality_score`; each shows heading path, doc title,
section excerpt, and the entities (routines / RPCs / options) named
inside it.

### 8.7 "Which routines write Patient data while called from CPRS?"

```
vista search --kind routine \
            --writes-piks P \
            --called-by-package CPRS
```

Code-model-only — the doc joins are off here. PIKS-aware filtering
is the data-model side's bread and butter; pre-existing
[four-way join from CLAUDE.md § "Two models, one join"](../CLAUDE.md).

### 8.8 "What documentation neighborhood surrounds routine X?"

```
vista neighbors PSOORNE --scope docs --depth 2
```

Walks doc sections that mention PSOORNE, then sibling sections in
the same docs, returning the doc-level concept neighborhood.

### 8.9 "Show me the timeline of the AR package"

```
vista timeline --pkg PRCA
```

Combines:
- KIDS patches (line-2 patch lists across all PRCA routines, deduped).
- Documents from `documents.patch_id` and `documents.pub_date`.
- Optionally: `git log` against `vista/vista-m-host/Packages/PRCA*`.

Output: a single chronological column. Useful when answering "when
did this behavior change and why?"

### 8.10 "Hand me an AI bundle for this question"

```
vista ask "how does the AR purge interact with KIDS install?" \
   --routine PRCA45PT \
   --pkg PRCA \
   --with-source --bytes 250000 > /tmp/q.md
```

Already worked through in §7.5.

---

## 9. Output formats and AI integration

### 9.1 Format philosophy

Every command supports four formats. Pick the right one.

| Format | When | Why |
|---|---|---|
| `--format md` (default) | terminal reading, `\| less`, paste to editor | human-friendly headings, links |
| `--format json` | shell pipes, automation, MCP servers | structured, no parsing |
| `--format tsv` | join with awk / `vista-meta` outputs / spreadsheets | consistent with bake conventions |
| `--format table` | quick one-line views, status checks | tight columnar |

### 9.2 AI-assistant ergonomics

Two modes:

**Pull** — `vista ask` builds a packet, the user pastes it into a
chat. Already designed (§7.5).

**Push** — a small MCP server wrapping `vista`. Each subcommand
becomes an MCP tool. The AI calls `vista_routine(name="PRCA45PT")`
and gets the structured object back. Same logic, no copy-paste.

The MCP server is a thin shim — phase 4 work, not phase 1. The CLI
is the contract.

### 9.3 Determinism

Every output is deterministic given the same TSV/SQLite inputs.
Same file in, same bytes out — the `mfmt` / kids-vc rule applied
to reports. CI verifies with golden snapshots.

---

## 10. Relation to sibling tools

### 10.1 vista vs vista-meta

`vista-meta` stays as the **bake + maintenance** CLI:

- `vista-meta doctor` — environment health (kept; `vista doctor`
  delegates).
- `vista-meta xindex` — live container XINDEX.
- `vista-meta lint` — doc-comment lint of new code.
- KIDS workflow (`make patch-*`).
- The VSCode extension keeps reading vista-meta TSVs.

`vista` replaces the **read-only inspection** subcommands:

| vista-meta (old) | vista (new) |
|---|---|
| `vista-meta pkg PSO` | `vista package PSO` |
| `vista-meta where TAG^RTN` | `vista where TAG^RTN` |
| `vista-meta callers TAG^RTN` | included in `vista routine` and `vista links` |
| `vista-meta context PKG` | `vista context PKG` (extended with docs) |
| `vista-meta search PAT` | `vista search PAT` (extended across docs) |
| `vista-meta file N` | `vista file N` (extended with docs) |

The old commands stay aliased for one release, then deprecated with
a notice that points at the new names. No big-bang break.

### 10.2 vista vs vista-docs

`vista-docs` stays as the **ingest + maintenance** CLI:

- `vista-docs crawl / fetch / ingest / enrich / survey / verify`.
- Pipeline state in SQLite (`pipeline.db`).
- Producer; not the daily-use tool.

`vista` is the **consumer** — it never writes to `frontmatter.db`;
only reads.

### 10.3 vista vs m-cli

Zero overlap.

| Concern | Owner |
|---|---|
| Format `.m` files | `m fmt` |
| Lint `.m` files | `m lint` |
| Run M-Unit tests | `m test` (planned) |
| Parse MUMPS to AST | `tree-sitter-m` |
| Anything VistA-specific | `vista` |

`vista` may *call* `m lint` (for example, if `vista routine` wants
to show live lint findings instead of TSV-cached ones), but does
not replicate it.

---

## 11. Additional features for legacy-code situational awareness

The eleven features below are concrete extensions worth scoping
into phases 2–4. Each leverages an existing artifact; none requires
new bake passes from scratch.

### 11.1 Time-machine view (`vista timeline`)

Already noted in §8.9. Per-artifact chronological timeline drawn
from KIDS line-2 patch lists, `documents.patch_id`/`pub_date`, and
git log. Answers "when did X start/stop being a thing?"

### 11.2 Test-gap finder

`vista coverage --scope tests` — for every routine in the corpus,
check whether `T<RTN>.m` exists (with truncation for 8-char limit).
Cross-reference with in-degree (highest-traffic untested routines
first) and PIKS class (Patient-data routines are highest priority).
Output: triage list.

### 11.3 Risk / heat scoring

`vista risk RTN` — single number 0–100 combining:

- in-degree (blast radius)
- patch count (churn)
- XINDEX findings (debt)
- Time since last commit (stale or active?)
- PIKS class of touched globals (P-class doubles weight)
- Cross-package outbound coupling (interface vs internal)
- Doc coverage (undocumented += risk)

Useful for code review triage and "what should we touch first?"

### 11.4 Dependency-layer / topological sort

`vista layers --pkg PSO` — runs a topological sort on intra-package
calls. Layer 0 = leaves (no callees inside PSO). Layer N = depends
only on layer < N. The package's *natural reading order* falls out.

### 11.5 Cross-reference matrix

`vista matrix --kind package` — N × N matrix of cross-package call
volumes. The off-diagonal cells are the package boundaries; the
heaviest cells are the *de facto* APIs (regardless of whether the VA
documented them as such).

### 11.6 Living docs generator

`vista doc generate --pkg PSO --out /tmp/pso-living.md` — for each
routine, render: name, line-1 title, in/out-degree, top callers, top
callees, globals, all VDL doc sections that mention it, link to
source. Produce one mega-doc per package. Refresh on every bake.

This is what every engineer wishes existed for VistA. The data is
already there; the report is one Jinja template away.

### 11.7 "What changed between two versions"

`vista diff --pkg PSO --from v52.0 --to v52.1` — diff at the level
of routines added/removed, RPCs added/removed, fields added/removed,
options renamed. Pulls from the KIDS install headers + the relevant
release-notes doc.

### 11.8 Glossary / acronym resolver

`vista glossary RXACTION` — VistA is built on hundreds of cryptic
abbreviations. The doc corpus *defines* most of them, just buried.
Search `doc_sections` (FTS5) for the acronym in section headings or
the first definition-shaped sentence. Cache hits.

### 11.9 Concept neighborhoods

`vista neighbors --concept "drug interaction"` — given a free-text
concept, find:

1. Doc sections matching via FTS5.
2. Entities (routines / globals / options) named inside those
   sections.
3. The cluster around those entities (callers, callees, files).

Returns the cohesive subgraph of code that implements a documented
concept. Closer to "topic-based code search" than to grep.

### 11.10 Coverage dashboard

`vista coverage --dashboard` — one report per package: % routines
documented, % RPCs documented, % options documented, % files
documented, count of orphan docs (mention routines that don't
exist), count of orphan code (no doc mentions). Track over time.

A small but high-value artifact for the "is the docs corpus
healthy?" question.

### 11.11 AI hint provider

`vista hint <RTN_or_question>` — emits a one-paragraph natural-
language hint built from joined facts: "PRCA45PT is a 74-line
single-purpose cleanup routine in Accounts Receivable, called only
from the OPT menu, last patched in 2018, documented in §3.4 of the
AR Tech Manual." Useful as a pre-prompt or status-bar item, not as
a final answer.

---

## 12. Architecture & implementation plan

### 12.1 Language and dependencies

- **Python 3.12** — same as vista-docs; same as host scripts in
  vista-meta.
- **Standard library + sqlite3**, plus `pyyaml` if frontmatter
  parsing is needed.
- **No new heavyweight deps.** No DuckDB, no Polars, no FastAPI in
  phase 1. The TSV reads + a SQLite client are enough.

### 12.2 Repository layout

Open question (§14): does `vista` live in vista-meta, vista-docs,
or its own repo? Recommendation: **its own repo** (`vista-cli/`)
to enforce the boundary. It depends on both projects' artifacts but
on neither's source tree.

```
vista-cli/
├── pyproject.toml
├── src/vista_cli/
│   ├── __main__.py          # `python -m vista_cli` → `vista`
│   ├── cli.py               # Click subcommand wiring
│   ├── stores/
│   │   ├── code_model.py    # TSV reader (mirrors vista-meta tsv.ts logic)
│   │   ├── doc_model.py     # SQLite reader
│   │   └── joined.py        # cross-store joins
│   ├── commands/
│   │   ├── routine.py       # vista routine
│   │   ├── package.py
│   │   ├── file.py
│   │   ├── rpc.py           # ...
│   │   ├── search.py
│   │   ├── links.py
│   │   ├── neighbors.py
│   │   ├── coverage.py
│   │   ├── ask.py
│   │   └── doctor.py
│   ├── format/
│   │   ├── markdown.py
│   │   ├── json_out.py
│   │   ├── tsv_out.py
│   │   └── table.py
│   └── canonical.py         # package id resolution (dir ↔ ns ↔ app_code)
├── tests/                   # pytest, unit + integration
└── README.md
```

### 12.3 Configuration

- `~/.config/vista/config.toml` — paths to vista-meta TSVs, vista-docs
  SQLite, optional cache dir. Sensible defaults so most users never
  edit it.
- Override via env vars (`VISTA_CODE_MODEL`, `VISTA_DOC_DB`).

### 12.4 Testing

- Unit tests on canonicalization (the package-id triple-map),
  formatters, ref-shape detection.
- Integration tests against fixture TSVs + a tiny SQLite fixture
  derived from a 5-doc cut of `frontmatter.db`.
- Golden-snapshot tests on `vista routine X` for ~10 representative
  routines (leaf, hub, RPC, option-only, undocumented, etc.).

### 12.5 Performance targets

| Command | Target (cold) | Target (warm cache) |
|---|---|---|
| `vista routine X` | < 500 ms | < 50 ms |
| `vista package X` | < 800 ms | < 100 ms |
| `vista search PAT` | < 1.5 s on full corpus | < 200 ms |
| `vista doc Q` | < 300 ms (FTS5) | < 100 ms |
| `vista build-cache` | < 60 s | n/a |

The SQLite side already meets these. The TSV side does too if the
indexes are built lazily (vista-meta extension proves this).

---

## 13. Phasing roadmap

Four phases, each independently shippable.

### Phase 1 — MVP (4–6 weeks)

- Repo + Click skeleton + config.
- `vista routine`, `vista package`, `vista file`, `vista rpc`,
  `vista option`, `vista patch`, `vista global`.
- `vista where`, `vista search`, `vista doc`.
- `vista doctor`.
- `--format md|json|tsv`.
- 10 golden-snapshot tests.

This already covers ~80% of daily use.

### Phase 2 — Joins and graph (3–4 weeks)

- `vista links` + `vista neighbors --depth N`.
- `vista coverage` + `vista timeline`.
- `vista context` / `vista ask` (AI bundling).
- The canonical package-id layer (§5 namespace mismatch).

### Phase 3 — Cache and polish (2–3 weeks)

- `vista build-cache` → `~/data/vista/joined.db`.
- 10× speedup on hot queries.
- `vista risk`, `vista layers`, `vista matrix` (the §11 features).

### Phase 4 — VSCode + MCP (open-ended)

- VSCode extension calls `vista` as a subprocess for hover,
  CodeLens, package sidebar (extends the
  [extension internals roadmap](vscode-extension-internals.md)).
- MCP server wrapping each subcommand as a tool.
- Living-docs generator (§11.6) wired into a CI job.

### 13.1 Definition of done per phase

A phase ships when:

- All listed subcommands return correct results on the golden
  snapshot suite.
- `vista doctor` is green on a clean clone.
- The README has a quickstart that works copy-pasted.
- Performance targets (§12.5) are met on a current laptop.

---

## 14. Open questions

Listed for resolution before phase 1 starts.

1. **Repo location.** Own repo, or `tools/vista-cli/` inside
   vista-meta, or vista-docs? Current lean: own repo, depends on
   both via path config.
2. **Canonical package ID.** vista-meta uses directory names;
   vista-docs uses VDL `app_code` (CPRS, PRCA, PSO) AND VistA
   namespace `pkg_ns` (OR, PRCA, PSO). Where does the master map
   live, and who maintains it when a new package is added?
   Recommendation: ship a `packages.csv` in `vista-cli` itself;
   audit periodically.
3. **Doc freshness.** `documents.is_latest` is computed by
   vista-docs's stage 6.7. How often does vista-cli need to refresh?
   Recommendation: read it live; the SQLite is updated in place.
4. **Source-tree drift.** vista-meta's bake mirrors VistA-M as of a
   point in time; vista-docs's manuals describe a different (often
   newer) point. Mismatches will exist (a routine documented in
   2024 not yet in the bake). How is this surfaced? Recommendation:
   `vista coverage --orphans` reports both directions.
5. **Cache invalidation.** Phase 3's joined cache must invalidate
   when either source moves. Simple mtime-based invalidation, or
   content hashing? mtime is enough for v1.
6. **Output of `vista context` vs `vista ask`.** Are they truly
   distinct, or is `ask` just `context --question Q`? Probably the
   latter — collapse if so.
7. **Extension hover provider** ([Tier A in the extension internals doc](vscode-extension-internals.md#71-tier-a--hoverprovider-highest-leverage))
   — does it shell out to `vista` (slower, fewer dependencies in
   the extension) or read TSVs directly (faster, duplicated logic)?
   Probably direct read for routine/tag, shell-out to `vista` for
   doc neighborhoods. Phase 4 work; pin then.
8. **Redaction.** VDL docs occasionally contain `REDACTED` author
   strings; some patches reference internal-VA hostnames. Does
   `vista` need any output filtering? Recommendation: pass through
   verbatim; user is already authorized.
9. **Multi-installation.** Future: someone running this against
   their site's VistA, not WorldVistA-on-VEHU. Path config (§12.3)
   covers it; revisit when the first non-VEHU user appears.

---

## 15. Reference

### 15.1 Source projects

- **vista-meta** — this repo. Code model, kids-vc, mfmt, VSCode
  extension. See [CLAUDE.md](../CLAUDE.md) and
  [vista-meta-guide.md](vista-meta-guide.md).
- **vista-docs** — `~/projects/vista-docs/`. VDL crawler, ingest,
  frontmatter SQLite. See `~/projects/vista-docs/CLAUDE.md`.
- **m-cli** — `~/projects/m-cli/`. M-language formatter, linter,
  test runner. See `~/projects/m-cli/README.md`.

### 15.2 Internal docs that informed this design

- [code-model-guide.md](code-model-guide.md) — the 19 code-model
  TSV schemas.
- [piks-analysis-guide.md](piks-analysis-guide.md) — the data-model
  side.
- [routine-situational-awareness.md](routine-situational-awareness.md)
  — per-routine cognitive sweep that this CLI accelerates.
- [package-situational-awareness.md](package-situational-awareness.md)
  — per-package scans this CLI promotes from shell recipes to
  subcommands.
- [vscode-extension-internals.md](vscode-extension-internals.md) —
  where this CLI feeds VSCode hover/sidebar in phase 4.

### 15.3 External references

- VA Document Library — https://www.va.gov/vdl/
- WorldVistA — https://worldvista.org/
- YottaDB — https://yottadb.com/
- Click (CLI framework) — https://click.palletsprojects.com/
- SQLite FTS5 — https://www.sqlite.org/fts5.html

### 15.4 Glossary

- **Bake** — the one-shot extraction job that produces vista-meta's
  TSVs from a running VistA-on-YDB container.
- **Frontmatter.db** — vista-docs's SQLite with documents +
  extracted entities + FTS5 sections.
- **PIKS** — Patient / Institution / Knowledge / System; vista-meta's
  4-class taxonomy of FileMan files and globals.
- **VDL** — Veterans Affairs Document Library, the source of all
  manuals.
- **KIDS** — Kernel Installation & Distribution System, VistA's
  patch format (`.KID` files).
- **Tag** — a column-0 label in a `.m` routine; the equivalent of a
  function entry-point.
- **Routine** — a `.m` source file in VistA.
- **Package** — a coherent VistA subsystem (Pharmacy, AR, Lab, etc.),
  identified by directory in the source tree and by app_code +
  pkg_ns in the doc corpus.
