# vista-viz-design — Visualization Design Guide

A reference for designing visualizations on top of `vista-cli`'s
unified data layer. Catalogues every category of interconnection
exposed by the code-model TSVs, the FileMan data-model TSVs, and the
vista-docs SQLite, and proposes visual motifs that fit each category
across four surfaces: CLI, TUI, Markdown+Mermaid, and on-demand web.

> Status: design reference. Not a roadmap. Implementation lands as
> separate features under [docs/vista-cli-planning.md](vista-cli-planning.md).
> Scope: visualization-only. Storage, joins, and command surface
> stay as designed in the planning doc.

---

## Table of contents

- [1. Executive summary](#1-executive-summary)
- [2. Scope and design constraints](#2-scope-and-design-constraints)
- [3. Prior art — OSEHRA ViViaN](#3-prior-art--osehra-vivian)
- [4. The connectivity taxonomy](#4-the-connectivity-taxonomy)
- [5. Visualization motifs by surface](#5-visualization-motifs-by-surface)
- [6. Pattern-to-motif mapping (master matrix)](#6-pattern-to-motif-mapping-master-matrix)
- [7. Per-entity catalogue](#7-per-entity-catalogue)
- [8. Cross-cutting concerns](#8-cross-cutting-concerns)
- [9. Suggested phasing](#9-suggested-phasing)
- [10. Reference](#10-reference)

---

## 1. Executive summary

`vista-cli` integrates three independently rich datasets — the
vista-meta code model (24 TSVs), the vista-meta data model (5 TSVs),
and the vista-docs frontmatter SQLite (12 tables, 138 k FTS5
sections). The joins between them are already implemented in
`stores/joined.py` and materialised in `joined.db`. What is not yet
designed is **how to render those joins visually** — beyond the
markdown / JSON / TSV output the existing 24 commands emit.

This document does three things:

1. **Categorises the connectivity** in the unified dataset into ten
   patterns, from strict containment (Package → Routines) to
   bipartite cross-reference (Routine ↔ Doc) to aggregated network
   (Package × Package call matrix).
2. **Catalogues visual motifs** that fit each pattern across four
   surfaces, with attention to terminal constraints, mermaid's
   limits, and on-demand web generation.
3. **Reviews ViViaN** — the OSEHRA web-based tool that is the
   closest existing prior art — and notes which of its choices
   transfer and which do not.

The goal is to keep the visualisation surface as deterministic,
composable, and offline-friendly as the rest of `vista-cli`.
Terminal-first. Web-on-demand. No always-on services.

---

## 2. Scope and design constraints

### 2.1 In scope

- Static and interactive renderings of the existing entities and
  joins. No new data sources.
- Four output surfaces:
  1. **CLI** — one-shot, deterministic stdout (text, possibly
     coloured). Pipeable. Composable with shell tools.
  2. **TUI** — interactive in-terminal app (Textual / urwid). Live
     navigation, multi-pane, keyboard-driven. Single binary,
     ships with the wheel.
  3. **Markdown + Mermaid** — embeddable diagrams in `vista
     context`, `vista coverage`, `vista timeline` markdown output.
     Renders in GitHub, Obsidian, mkdocs, IDE preview.
  4. **Web (on-demand)** — `vista serve` or `vista export-html`
     emits a static HTML/JS bundle. No daemon. The user opens the
     file, the JS reads inlined JSON, the browser does the layout.

### 2.2 Out of scope

- Live editing or write-back to FileMan or routines.
- Always-on web services with auth.
- Real-time streaming visualisations (no live VistA telemetry).
- 3-D layouts. VistA's graph density doesn't justify them.

### 2.3 Hard constraints

- **Determinism** — every rendering is a pure function of the
  cache. Same inputs, same bytes out (matches the project rule in
  CLAUDE.md). Layout seeds, sort orders, and tie-breakers must be
  fixed.
- **Offline-first** — the web bundle inlines its data and JS, no
  CDN required. Diagrams render without network.
- **Single binary distribution** — anything heavier than Textual
  goes in the on-demand web bundle, not the wheel.
- **Composability** — every motif must have a JSON twin so a user
  can pipe `vista … --format json` into their own renderer.

---

## 3. Prior art — OSEHRA ViViaN

ViViaN (Visualizing VistA and Namespace) is OSEHRA's web-based
browser for VistA hierarchy and connectivity. It is the most
directly comparable prior art and worth reviewing before designing
new motifs.

### 3.1 What ViViaN exposes

| Category | ViViaN page | Source data |
|---|---|---|
| Package hierarchy | Package Tree | Package category → package |
| Menu hierarchy | Option Menus, Protocol Menus | Menu options, protocols, security keys |
| Business framework | VHA BFF | Function → subfunction → activity |
| Package interactions | Circle Plot, Bar Charts, Force-Directed Graph | Package call/dependency edges |
| Patches | Install Timeline, Install Dependency Tree | KIDS install metadata |
| Interfaces | HL7, HLO, ICR, Protocols, RPC tables | FileMan exports |
| Namespace ↔ Number | Name and Number tables | Namespace and file-number registries |
| User data | Classify Data | User-uploaded JSON, pie chart |

### 3.2 What ViViaN does well

- **Multiple motifs per relationship.** Package interactions get
  three views (circular, bar, force-directed) and the user picks.
  This is the right move — different questions need different
  layouts even when the data is identical.
- **Tree-first for menus and BFF.** The menu hierarchy is genuinely
  recursive and ViViaN treats it that way. Not all VistA data is
  graph-shaped; some is honestly tree-shaped, and ViViaN doesn't
  over-engineer.
- **Search inside every visualisation.** Every page has a search
  box. At VistA scale (~40 k routines, 8 k files, hundreds of
  packages) this is non-negotiable.
- **Tabular fallback.** Interfaces and Name/Number are sortable
  searchable tables, not forced into a graph. A table is a
  visualisation.
- **Colour-blind mode.** Built into the circular and force-directed
  views.

### 3.3 What ViViaN doesn't do (and we should)

- **No documentation join.** ViViaN visualises the code model only.
  Every motif here can be enriched with the doc-side ribbon
  (mention count, doc layer, quality score) — that is the point of
  `vista-cli` over vista-meta alone.
- **No terminal surface.** ViViaN is web-only. The whole CLI/TUI
  axis is greenfield.
- **No PIKS-aware shading.** ViViaN doesn't ingest the
  P/I/K/S classification or the FileMan sensitivity / volatility
  fields, so its package views can't shade by data risk.
- **No deterministic export.** ViViaN is a browse tool, not an
  artefact generator. Markdown / JSON output for downstream
  consumption isn't its job.

### 3.4 Direct lifts

These ViViaN choices map cleanly onto `vista-cli`'s data and should
be reused as motifs:

- Circle plot for the package edge matrix.
- Force-directed for ego graphs of packages or routines.
- Bar chart for in-degree / out-degree / patch-frequency rankings.
- Install timeline for `vista timeline --pkg`.
- Install dependency tree for patch-prerequisite chains, when
  ingested.

---

## 4. The connectivity taxonomy

Every relationship in the unified dataset falls into one of ten
patterns. Each pattern has a different set of natural visual
idioms. The same entity can participate in several patterns at once
— a Routine is a node in a call graph (4.3) **and** a leaf of
package containment (4.1) **and** a column in a Routine ↔ Doc
bipartite (4.4).

### 4.1 Strict containment (1:N tree, no cycles)

A parent owns a fixed set of children of one or more types. No
shared ownership, no cycles.

| Parent | Children | Source |
|---|---|---|
| Package | Routines | `routines.tsv` |
| Package | RPCs | `rpcs.tsv` |
| Package | Options | `options.tsv` |
| Package | Protocols | `protocols.tsv` |
| Package | Files (by global root) | `files.tsv` + canonical |
| Package | Globals (touched) | `routine-globals.tsv` |
| Package | Patches (released) | `version_line` parsing |
| File | Fields | `field-piks.tsv` |
| Patch | Routines / Files / Options / Protocols modified | KIDS |
| Patch | Docs (install / release notes) | `documents.patch_id` |
| Doc | Sections | `doc_sections` |

**Best fit.** Indented tree, sunburst, treemap, ring chart. All
read top-down or centre-out. Treemap dominates when child sizes
matter (line counts, field counts, byte sizes); indented tree
dominates when names matter; sunburst when both depth and size
matter at a glance.

**Worst fit.** Force-directed (overkill, the structure is
deterministic) and matrix (containment is one-to-many, not
many-to-many).

### 4.2 Recursive hierarchy (true tree, depth unbounded)

Same parent / child relationship recurses arbitrarily deep.

| Relationship | Source | Notes |
|---|---|---|
| Menu Option → child Options | Option file #19, multiple field 10 | Genuinely recursive; canonical menu tree |
| Doc Section → subsections | `doc_sections.parent_section_id` | Bounded by header depth, typically ≤ 6 |
| FileMan File → multiples (subfiles) | Subfile is itself a File entry | Recursive by definition |

Distinct from 4.1 because the depth is unbounded and the same
*type* recurses. Menu trees can be 10+ deep in practice.

**Best fit.** Collapsible indented tree, miller columns, sunburst
(if leaves are roughly balanced), zoomable icicle. For depth > 5
the indented tree starts losing horizontal space — collapsible /
zoomable variants buy room.

### 4.3 Directed call graph (network with cycles)

Many-to-many directed edges, cycles common, fan-in and fan-out
both highly skewed.

| Source | Target | Edge attributes | Source TSV |
|---|---|---|---|
| Routine | Routine | kind, ref_count | `routine-calls.tsv` |
| Tag^Routine | Tag^Routine | inferred from caller's line | xindex + `routine-calls` |
| Protocol | Routine | entry_action / exit_action | `protocols.tsv` |
| RPC | Routine | tag entry | `rpcs.tsv` |
| Option | Routine | menu entry | `options.tsv` |
| Routine | Global | ref_count | `routine-globals.tsv` |
| Global | File | global_root match | `files.tsv` (resolved in `joined.py`) |

The full routine-level graph is ~40 k nodes and ~1 M edges. That is
not directly renderable as a force-directed picture in any surface.
What works is **ego graphs** (depth-1 or depth-2 around a chosen
root) and **aggregated views** (4.5).

**Best fit.** Ego trees (already implemented in `vista neighbors`),
force-directed for small ego graphs (≤ 200 nodes), Sankey for the
RPC → Routine → File chain, hierarchical edge bundling for
intra-package call density.

**Worst fit.** Adjacency matrix at routine granularity (40 k × 40 k
is a noise field). Matrix only works after aggregation (4.5).

### 4.4 Bipartite cross-reference (two sets, edges between)

Two sets of nodes; edges only ever cross. Zero in-set edges.

| Set A | Set B | Source |
|---|---|---|
| Routine | Doc | `routine_doc_refs` |
| Routine | Patch | `patch_routine_refs` |
| Routine | Global | `routine-globals.tsv` |
| Routine | Tag | xindex (tags belong to routines) |
| RPC | Doc | `rpc_doc_refs` |
| Option | Doc | `option_doc_refs` |
| Global | Doc | `doc_globals` |
| File | Doc | `file_doc_refs` |
| File | Routine (via global) | join through `files.global_root` |
| Section | Routine (mention) | FTS5 hits in `doc_sections_fts` |

**Best fit.** Two-column dot/line plot, biadjacency matrix, Sankey
(when one direction has order semantics, e.g. patch dates), arc
diagram, parallel categories. For sparse bipartite (most VistA
entities are mentioned in 0–3 docs) a simple two-column listing or
heatmap row beats anything fancier.

**Worst fit.** Force-directed. The two-set structure gets visually
flattened and the bipartite shape is lost.

### 4.5 Aggregated network (collapsed nodes, weighted edges)

Group routines by package (or layer, or subdomain) and collapse
the routine call graph into a much smaller weighted multigraph.

| Aggregate | Edge weight | Source |
|---|---|---|
| Package × Package | call_edges, distinct caller/callee | `package-edge-matrix.tsv` |
| Layer × Layer | edges crossing the canonical layer model | derived |
| Subdomain × Subdomain | calls between FileMan subdomains | `files.subdomain` join |
| Package × FileMan File | routines in pkg touching file's globals | derived |
| Package × Doc app_code | mention density | join through canonical |

Aggregation drops the count from millions of edges to hundreds.
**This is the unlock that makes whole-system views feasible.**

**Best fit.** Adjacency matrix with shaded cells (Unicode in CLI,
real heatmap on web), chord / circle plot, Sankey for layer
crossings, force-directed at aggregate scale (works because N is
small).

### 4.6 Temporal sequence

Events ordered by date.

| Stream | Source |
|---|---|
| Patch installs | `version_line` line-2 patch list, doc `pub_date` |
| Doc publication | `documents.pub_date` |
| Routine modification timeline | derived: patches that touched it |
| Package release cadence | aggregate of patches per package per year |

**Best fit.** Timeline / Gantt, swimlanes (one lane per package),
bar histogram (binned by month / quarter), small-multiples calendar
heatmap. ViViaN's Install Timeline is the canonical example.

### 4.7 Identity / aliasing

Same entity, multiple addresses.

| Aliases | Source |
|---|---|
| directory ↔ namespace ↔ app_code | `canonical.py`, `packages.csv` |
| Routine `^TAG` ↔ `TAG^ROUTINE` ↔ `Package::Tag` | parse |
| File number ↔ file name ↔ global root | `files.tsv` |
| Patch canonical ID ↔ display variants | regex |

These are not really visualised; they are the **resolver layer**
that lets a visualisation accept user input in any form. Every
motif in this guide should accept any alias and normalise via
`canonical.resolve_*`.

### 4.8 Categorical / classification

Discrete labels attached to entities.

| Entity | Categories | Source |
|---|---|---|
| File | PIKS class (P / I / K / S) | `piks.tsv` |
| File | sensitivity, volatility, portability, status | `files.tsv` |
| Routine | is_percent_routine, in_file_9_8 | `routines.tsv` |
| Call edge | kind (DO, XECUTE, $$, ref) | `routine-calls.tsv` |
| Doc | doc_type (User / Technical / Install), doc_layer | `documents.doc_type` |
| Doc | is_latest, is_stub | `documents` |
| Package | layer assignment (kernel / fileman / clinical) | derived from canonical |

Categories drive **encoding** rather than layout: colour, shape,
hatching, prefix glyph. Should be consistent across surfaces — the
same colour for `P` files in CLI ANSI as in mermaid as in web SVG.

### 4.9 Quality / weight / scalar overlays

Scalars attached to entities or edges that the visualisation can
encode by size, colour intensity, or sort order.

| Entity / edge | Scalar | Source |
|---|---|---|
| Routine | line_count, in_degree, out_degree, tag_count | `routines.tsv` |
| Routine | risk score (composite) | `vista risk` |
| Doc | quality_score, word_count, page_count | `documents` |
| File | record_count, field_count, piks_confidence | `files.tsv` |
| Edge (call) | ref_count | `routine-calls.tsv` |
| Edge (global) | ref_count | `routine-globals.tsv` |
| Package | total_lines, routine_count, outbound_cross_pkg | `package-manifest.tsv` |
| xindex | lints per routine | `xindex-errors.tsv` |

These never *replace* a layout choice; they enrich one. A
package-tree treemap sized by line count + coloured by doc-coverage
percentage uses two scalars on the same containment layout.

### 4.10 Spatial / positional

Position carries meaning *within* an entity.

| Entity | Position | Source |
|---|---|---|
| Tag | line number within routine | xindex |
| Section | seq within doc | `doc_sections.seq` |
| Field | field_number within file | `field-piks.tsv` |
| Patch | sequence within version stream | parsed patch ID |

Used in source-mapped views (`vista where`), inline annotation, and
the eventual Tag-graph. Rarely the headline motif on its own.

---

## 5. Visualization motifs by surface

For each motif, what it does, what data it needs, what its
strengths and limits are.

### 5.1 CLI — one-shot stdout

Constraints: deterministic, pipeable, fits 80 cols by default,
colour optional and degradable to plain ASCII.

| Motif | Pattern fit | Notes |
|---|---|---|
| **Indented ASCII tree** | 4.1, 4.2 | `tree(1)` style with `├── └── │`. Already prototyped for `neighbors`. Extend to `option`, `file`, `doc`, `package`. Cycle-safe via `↺ already-shown` markers. |
| **Two-pane miller list** | 4.1 | Left column = parent, right column = children, separated by `│`. Works in 80 cols if names ≤ 35 chars. Static snapshot only. |
| **Unicode heatmap matrix** | 4.5 | `░ ▒ ▓ █` for low → high. Already proposed for `vista matrix`. Quantile-bucketed for stable colour across runs. |
| **Sparkline column** | 4.6, 4.9 | Single-row Unicode bars (`▁▂▃▄▅▆▇█`) per timeline or scalar series. Fits inline next to a routine name. |
| **Bar chart** | 4.9 | Horizontal bars with `█` blocks. For top-N rankings (in-degree, line count, patch frequency). |
| **Two-column bipartite list** | 4.4 | `RoutineName  →  doc-id1, doc-id2, doc-id3`. Sort by either side. Truncate the right side to top-N. |
| **Adjacency table** | 4.5 | TSV-style cells with row/column labels. Fine for ≤ 30 × 30 (e.g., layer × layer). |
| **Sankey-text** | 4.3 (3-layer) | Three columns of names connected by `→`, weights inline. Reads less well than a real Sankey; good fallback. |
| **Source-mapped span** | 4.10 | `file:line` plus a 5-line excerpt with the tag highlighted. `vista where` already does this skeleton. |
| **Pretty-printed JSON** | any | The escape hatch. Every command must support `--format json` so the user can render their own. |

ANSI colour use should be opt-in (`--color auto` honouring `NO_COLOR`),
optional (degrade to glyph prefixes), and consistent across motifs
(see §8.4 colour palette).

### 5.2 TUI — interactive in-terminal

Constraints: keyboard-driven, single binary, runs over SSH, 24+
rows of vertical space available. Implementation language: Textual
(Python, fits the existing wheel) or urwid (lighter, fewer deps).

| Motif | Pattern fit | Notes |
|---|---|---|
| **Miller columns** | 4.1, 4.2 | Three or four panes drilling down: Package → Routine → Callees → Source/Doc. Arrow keys, `/` for search, Enter to drill. The single highest-ROI TUI motif for `vista-cli`. |
| **Master-detail split** | 4.1, 4.4 | Top: list of routines. Bottom: dense `vista links` output for the highlighted row. Live updates as cursor moves. |
| **Collapsible tree** | 4.1, 4.2 | Single-pane outliner with `+ / -` glyphs. Best for menu trees and doc section trees. |
| **Live ego graph** | 4.3 | ASCII-render `vista neighbors` and re-render with new root when user presses Enter on a callee. Tag-level variant zooms into a single routine. |
| **Heatmap navigator** | 4.5 | Unicode matrix as the canvas; arrow keys to highlight cells; Enter expands a cell to the underlying routine list. |
| **Timeline scrubber** | 4.6 | Bottom-row date scrubber, top pane shows patches / docs in the selected range. |
| **Search palette** | any | `Ctrl-K` style fuzzy finder over routines / RPCs / options / files / docs at once. Backed by FTS5 + canonical resolver. |
| **Tabbed workspace** | composite | Multiple of the above motifs as tabs in one TUI session, sharing a current-entity context. |

The miller-columns view is the spiritual successor to ViViaN's
package-then-detail flow, but in-terminal and joined to the doc
side.

### 5.3 Markdown + Mermaid

Constraints: must render in GitHub, mkdocs, and IDE preview without
custom plugins. Mermaid covers most cases; some motifs need
fallback to PNG/SVG generation.

| Motif | Mermaid type | Pattern fit | Notes |
|---|---|---|---|
| **Containment tree** | `flowchart TD` with subgraphs | 4.1 | `vista coverage --pkg --md` already emits this kind of bullet list; mermaid version draws it. Cap depth at 3 to stay readable. |
| **Recursive hierarchy** | `mindmap` | 4.2 | New mermaid mindmap renders option menus and section trees compactly. Falls back to flowchart in older renderers. |
| **Ego call graph** | `flowchart LR` | 4.3 | Depth-1 from a routine. Edge labels = ref_count. Cycle-safe via mermaid's natural node-merging. Cap at ~30 nodes. |
| **Sequence diagram** | `sequenceDiagram` | 4.3 | RPC entry → routine → DIE / DIC chain, when the user wants the temporal-call story rather than the static graph. |
| **Bipartite** | `flowchart LR` two columns | 4.4 | Routine ↔ Doc, RPC ↔ Doc. Subgraphs fix left/right placement. |
| **Aggregated network** | `flowchart` | 4.5 | Package × Package edges with weights. Clean only at ≤ 20 packages — pick a layer or subdomain. |
| **Timeline** | `timeline` (mermaid 9+) | 4.6 | Patch installs per package per year. Mermaid timeline is line-based and reads well. |
| **Gantt** | `gantt` | 4.6 | Doc publication windows by app_code. |
| **State / classification** | `stateDiagram-v2` | 4.8 | Patch state transitions, doc lifecycle (`is_stub` → published → `is_latest`). |
| **Class diagram** | `classDiagram` | 4.1 + 4.9 | FileMan file → fields with type and PIKS annotations. Reads as data-dictionary documentation. |
| **ER diagram** | `erDiagram` | 4.4 | File ↔ File pointer relationships. |
| **Sunburst / treemap** | not in mermaid | 4.1, 4.9 | Falls back to web (5.4) or static SVG via graphviz. |
| **Heatmap matrix** | not in mermaid | 4.5 | Falls back to inline HTML table with shaded cells (works in mkdocs / GitHub) or SVG asset. |

Mermaid's main limit at VistA scale is node count. The discipline:
**every mermaid diagram in `vista-cli` output must be sized for the
question being asked**, not the whole graph. A `vista neighbors
--md` is depth-bounded; a `vista matrix --md` is layer-aggregated.

### 5.4 Web (on-demand HTML)

Constraints: static bundle, no daemon, opens with `file://`. Single
HTML file with inlined JSON and inlined JS library. Generated by
`vista export-html` or `vista serve` (which is just a thin `python
-m http.server` wrapper). The browser does the rendering; the CLI
does no rendering.

| Motif | Library | Pattern fit | Notes |
|---|---|---|---|
| **Force-directed graph** | d3-force, cytoscape.js | 4.3, 4.5 | Best for ego graphs (depth ≤ 3) and aggregated networks. Hover for entity card; click to re-root. |
| **Hierarchical edge bundling** | d3 | 4.3, 4.5 | Excellent for intra-package call cohesion. Bundles routine-to-routine arcs along the package containment hierarchy. |
| **Sunburst** | d3-hierarchy | 4.1, 4.2, 4.9 | Centre = corpus, ring 1 = packages, ring 2 = routines. Size by lines, colour by doc coverage. |
| **Treemap** | d3-treemap | 4.1, 4.9 | Same data as sunburst, different visual contract: better for size comparison, worse for hierarchy clarity. |
| **Icicle** | d3-hierarchy | 4.2 | Zoomable. Ideal for menu trees with arbitrary depth. |
| **Sankey** | d3-sankey | 4.3, 4.4 | RPC → Routine → File. Patch → Routine → Doc. |
| **Chord diagram** | d3-chord | 4.5 | Package × Package matrix. ViViaN's circle plot is the same idiom. |
| **Adjacency matrix** | d3, observable plot | 4.5 | When chord gets too tangled, the matrix wins. Re-orderable rows/columns by clustering. |
| **Calendar heatmap** | observable plot | 4.6 | Patch installs per week. Doc publications per quarter. |
| **Timeline / swimlane** | vis-timeline, observable plot | 4.6 | One lane per package; bars are patches with hover details. |
| **Tabular data view** | datatables.js | any | Sortable, filterable, paginated. The honest fallback for any motif that doesn't beat a good table. |
| **Linked-views dashboard** | observable framework, evidence | composite | Pick a routine in the tree; force-graph and timeline both update. Selection-driven. The most powerful surface; also the heaviest to build. |

Because the bundle is static, the entire dataset for a given page
is inlined as JSON. The size budget per page is therefore the
constraint:

- A package-level page (one package): ≤ 5 MB inlined JSON.
- A whole-corpus page (force-directed): aggregate to package or
  layer; routine-level is too big.
- An entity detail page: ≤ 200 KB inlined; one fetch is fine.

`vista export-html --pkg PSO` should produce an `index.html` that
opens to a Pharmacy dashboard.

---

## 6. Pattern-to-motif mapping (master matrix)

Recommended primary motif per surface per pattern. Secondary motifs
in parentheses.

| Pattern | CLI | TUI | Markdown+Mermaid | Web |
|---|---|---|---|---|
| 4.1 Strict containment | indented ASCII tree | miller columns | `flowchart TD` (subgraphs) | sunburst (treemap) |
| 4.2 Recursive hierarchy | indented ASCII tree, collapsible | collapsible tree | `mindmap` (flowchart) | icicle (sunburst) |
| 4.3 Directed call graph | ego ASCII tree (Sankey-text) | live ego graph | `flowchart LR` ego (sequence) | force-directed (HEB) |
| 4.4 Bipartite | two-column list | master-detail | `flowchart LR` two-subgraph | sankey (matrix) |
| 4.5 Aggregated network | Unicode heatmap | heatmap navigator | `flowchart` weighted | chord (matrix) |
| 4.6 Temporal | sparkline / bar histogram | timeline scrubber | `timeline` / `gantt` | timeline / calendar heatmap |
| 4.7 Identity / aliasing | resolver behind every cmd | search palette | not visualised | search box on every page |
| 4.8 Categorical | glyph prefix + ANSI colour | colour + status row | mermaid `classDef` | colour legend |
| 4.9 Quality / weight | bar chart, scalar columns | bar in detail pane | `classDef` size hints | size + colour encoding |
| 4.10 Spatial | source-mapped span | source preview pane | code-block excerpts | linked source view |

---

## 7. Per-entity catalogue

For each entity: which patterns it participates in and which motifs
to reach for.

### 7.1 Package

- **Containment (4.1)** — owns Routines, RPCs, Options, Protocols,
  Globals, Patches, Files (by global root).
- **Aggregated network (4.5)** — node in the Package × Package call
  matrix.
- **Bipartite (4.4)** — to Docs via `app_code`.
- **Categorical (4.8)** — layer assignment (kernel / fileman /
  clinical).
- **Quality (4.9)** — total_lines, routine_count, percent of
  routines documented, outbound cross-pkg edges.

Primary motifs: sunburst (web), miller columns (TUI), flowchart
with subgraphs (markdown), indented tree (CLI). For inter-package
view: chord plot (web), heatmap (CLI/TUI).

### 7.2 Routine

- **Containment (4.1)** — owned by Package, owns Tags.
- **Call graph (4.3)** — node in routine-level network.
- **Bipartite (4.4)** — to Docs, Patches, Globals.
- **Quality (4.9)** — line_count, in/out degree, risk score.
- **Categorical (4.8)** — is_percent_routine, in_file_9_8.

Primary motifs: ego ASCII tree (CLI), live ego graph (TUI),
`flowchart LR` ego (markdown), force-directed depth-2 (web).
Master-detail with `vista links` payload as detail pane.

### 7.3 Tag (entry point)

- **Spatial (4.10)** — line within routine.
- **Call graph (4.3)** — finer-grained than routine-level. The
  honest call graph is at this level.
- **Bipartite (4.4)** — to RPCs, Options, Protocols (entry tag),
  Docs (`doc_routines.tag`).

Primary motifs: line-numbered tree-under-routine (CLI), tag-graph
ego in TUI (when implemented), `sequenceDiagram` for RPC →
tag-chain (markdown), force-directed at tag granularity (web).

### 7.4 File (FileMan)

- **Containment (4.1)** — owns Fields; recursive into subfiles
  (4.2).
- **Bipartite (4.4)** — to Routines (via global), to Docs, to other
  Files (pointer chains).
- **Categorical (4.8)** — PIKS class, sensitivity, volatility,
  portability, status, subdomain.
- **Quality (4.9)** — record_count, field_count.

Primary motifs: indented tree with PIKS glyph prefix (CLI),
miller-pane: File → Field → pointer-target File (TUI), `classDiagram`
or `erDiagram` (markdown), nested treemap (web).

### 7.5 Field

- **Containment (4.1)** — owned by File.
- **Bipartite (4.4)** — pointer fields target other Files (4.4 with
  ordered direction; can chain into 4.2 graph).
- **Categorical (4.8)** — data_type, sensitivity_flag.

Primary motifs: tabular row in CLI, detail pane in TUI, row inside
`classDiagram` (markdown), node inside ER diagram (web).

### 7.6 RPC

- **Containment (4.1)** — owned by Package.
- **Bipartite (4.4)** — to Doc, to Routine (via tag), to Option (if
  invoked).
- **Quality (4.9)** — availability, inactive flag.

Primary motifs: master-detail (TUI), three-layer Sankey (RPC →
Routine → File touched, web), `sequenceDiagram` (markdown).

### 7.7 Option

- **Recursive hierarchy (4.2)** — owns child Options. The genuine
  recursive case alongside doc sections.
- **Containment (4.1)** — owned by Package; entry routine link.
- **Bipartite (4.4)** — to Docs, to Routines.

Primary motifs: collapsible tree (CLI/TUI), `mindmap` (markdown),
zoomable icicle (web). The menu-tree visualisation is the lift
ViViaN does well; the contribution here is joining each option to
its docs.

### 7.8 Protocol

- Same shape as RPC + Option combined: containment, entry / exit
  routine bipartite, items can recurse.
- Sequence-diagram view (markdown) is the natural fit for entry +
  exit hooks across a transaction.

### 7.9 Patch

- **Containment (4.1)** — owns the routines / files / options /
  protocols it modifies.
- **Bipartite (4.4)** — to Docs (install / release notes), to
  Routines (modified).
- **Temporal (4.6)** — install date, version sequence within
  package.
- **Recursive (4.2)** — patch prerequisite chain (when ingested).

Primary motifs: timeline (CLI / TUI / markdown / web), Gantt for
batch installs (markdown), dependency tree from ViViaN's install
view (web).

### 7.10 Global

- **Bipartite (4.4)** — to Routines (touches), to File (global_root
  resolution).
- **Quality (4.9)** — ref_count.
- **Categorical (4.8)** — inherits PIKS via the resolved File.

Primary motifs: bipartite list (CLI), Sankey (Routine → Global →
File, web), heatmap of routine × global (TUI).

### 7.11 Doc

- **Containment (4.1)** — owns Sections.
- **Recursive (4.2)** — sections recurse.
- **Bipartite (4.4)** — to Routines, RPCs, Options, Globals, Files,
  Patches.
- **Temporal (4.6)** — pub_date.
- **Categorical (4.8)** — doc_type, doc_layer, is_latest, is_stub.
- **Quality (4.9)** — quality_score, word_count, page_count.

Primary motifs: section tree (CLI), miller pane with Doc → Section
→ Mentions (TUI), `mindmap` of section tree (markdown), linked-views
dashboard with FTS5 search (web).

### 7.12 Section

- **Containment (4.1)** — owned by Doc.
- **Recursive (4.2)** — subsections.
- **Bipartite (4.4)** — to Routines via FTS5 mentions.
- **Spatial (4.10)** — seq, level.

Primary motifs: indented tree (CLI), two-pane (heading-tree
left, body right) in TUI, `mindmap` (markdown), zoomable icicle
(web).

---

## 8. Cross-cutting concerns

### 8.1 Cycle handling

The call graph (4.3) and pointer chains (4.4 + 4.2) have cycles.
Visualisations that pretend to be trees must:

- Track a `seen: set[str]` and stop at the second occurrence.
- Emit a back-reference marker — `↺ FOO (above)` in CLI, a dashed
  edge in mermaid, a different node colour in web — rather than
  silently truncating.
- Cap depth and document the cap in the visualisation header.

### 8.2 Scaling thresholds

What works at what scale:

| Motif | Comfortable | Hard cap |
|---|---|---|
| Mermaid flowchart | ≤ 30 nodes | ~80 (renderer slows) |
| Mermaid mindmap | ≤ 100 nodes | ~250 |
| ASCII tree (terminal) | ≤ 200 lines | screen-bound |
| Force-directed (web) | ≤ 300 nodes | ~1 000 (browser GC) |
| Sunburst / treemap | ≤ 2 000 leaves | ~10 000 |
| Heatmap matrix | 50 × 50 | 200 × 200 |
| Adjacency table (terminal) | 30 × 30 | 50 × 50 |
| Calendar heatmap | unbounded (binned) | — |

Whole-corpus views always require aggregation. Routine-level
force-directed is never the right answer for the full graph.

### 8.3 Determinism

For every motif, fix:

- Sort order of children, edges, rows, columns (default: by name,
  with a documented secondary key).
- Layout seed for any randomised algorithm (force-directed,
  treemap squarified). Pin the seed in the export bundle.
- Quantile boundaries for shaded heatmap cells (re-derive from
  cache statistics, not per-render).
- Truncation rules — explicit `--top N` rather than implicit cuts.

Same input, same bytes out. Diffable in git for any markdown / SVG
output.

### 8.4 Colour palette (consistency across surfaces)

A single palette, mapped to the same semantics in every motif:

| Semantic | ANSI (CLI) | Hex (web/svg) | Use |
|---|---|---|---|
| package boundary | cyan | `#1abc9c` | borders, package nodes |
| routine | default | `#34495e` | routine nodes |
| call edge | dim white | `#7f8c8d` | call lines |
| doc | yellow | `#f1c40f` | doc nodes, mentions |
| patch | magenta | `#9b59b6` | patch markers |
| file (FileMan) | blue | `#3498db` | file nodes |
| global | green | `#2ecc71` | global nodes |
| risk / lint warning | red | `#e74c3c` | warnings, errors |
| layer violation | orange | `#e67e22` | upcalls |
| inactive / stub | grey | `#95a5a6` | de-emphasis |

PIKS colour overlay (only on file nodes):
`P=red, I=blue, K=green, S=grey`. Stable across surfaces.

### 8.5 Motif composition

Every visualisation in `vista-cli` is a function of the cache.
That makes them composable:

- **Layered overlays** — start with one motif (containment), add a
  second pattern as encoding (quality, classification). Example:
  package treemap (4.1) sized by lines + tinted by doc-coverage %
  (4.4 join collapsed to a scalar).
- **Cross-references between motifs** — a click on a node in the
  web force-directed view should be able to deep-link to `vista
  links ROUTINE` markdown. The web bundle exports anchor IDs.
- **Shared resolver** — every surface uses `canonical.resolve_*`,
  so a user types `PSO`, `Outpatient Pharmacy`, or
  `pharmacy-outpatient` and lands at the same package view.

### 8.6 Accessibility

- Colour-blind palette parallel to the default (ViViaN does this).
- Every colour-encoded distinction repeated as a glyph or label
  prefix in CLI.
- Keyboard-only navigation in TUI and web.
- Plain-text fallback for every motif (`--format text` or
  pre-rendered ASCII alongside SVG).

---

## 9. Suggested phasing

Visualisation work is independent of and orthogonal to the planning
doc's Phases 1–4. A reasonable sequence:

### Phase A — pure formatters in `format/` (no new deps)

1. ASCII tree renderer for `neighbors`, `option`, `file`, `doc`,
   `package`. Single `format/tree.py` with a `_Node` model.
2. Unicode heatmap for `matrix`, layer × layer, subdomain ×
   subdomain.
3. Sparkline column for timelines and per-routine scalar series.
4. Bipartite two-column listing for `links`.

These ship as `--format tree` / `--format heatmap` choices on the
existing commands. Zero new dependencies, zero distribution risk.

### Phase B — markdown / mermaid renderers in `format/markdown.py`

1. `flowchart` containment for `coverage --md` and `package --md`.
2. `flowchart LR` ego for `neighbors --md`.
3. `mindmap` for `option --md` and `doc --md` section trees.
4. `sequenceDiagram` for `rpc --md`.
5. `classDiagram` / `erDiagram` for `file --md`.
6. `timeline` / `gantt` for `timeline --md`.

Mermaid has zero runtime cost — these are pure string templating.

### Phase C — TUI app

`vista tui` as a Textual application. Single command, opens to a
miller-columns workspace. Reuses every formatter from A and B for
its panes. Optional dep group: `pip install vista-cli[tui]`. Adds
~2 MB to the wheel; users who don't want it skip the extra.

### Phase D — on-demand web bundle

`vista export-html --pkg PKG` (and `vista export-html --all`,
aggregate-only) generates a static directory:

```
dist-web/
  index.html              # entry, package picker
  pkg/PSO/index.html      # one per package
  data/PSO.json           # inlined dataset
  assets/                 # d3, observable plot, css (vendored)
```

Uses observable plot + d3 + datatables. No build step at user time
— assets are vendored at `vista` build time and shipped as
`importlib.resources` data files.

### Phase E — composite dashboards

Linked-views, cross-pattern dashboards for the high-traffic
package-level questions (Pharmacy, AR, Lab). Selection in one pane
filters the others. Heaviest to build, highest narrative value.

Each phase is independently shippable and adds no obligation to do
the next. Phase A alone closes the visible gap between `vista-cli`
and ViViaN for terminal users.

---

## 10. Reference

### 10.1 Internal documents

- [docs/vista-cli-planning.md](vista-cli-planning.md) — scope,
  phasing, command surface.
- [docs/vista-cli-guide.md](vista-cli-guide.md) — user guide for
  the existing 24 commands.
- [docs/vista-cli-packaging.md](vista-cli-packaging.md) —
  distribution constraints (Homebrew + PyInstaller tarball).

### 10.2 ViViaN

- [github.com/WorldVistA/ViViaN](https://github.com/WorldVistA/ViViaN)
  — source.
- [vivianr.worldvista.org](https://vivianr.worldvista.org/vivianr/)
  — live instance.
- [ViViaN User Guide](https://github.com/WorldVistA/ViViaN/blob/master/Documentation/UserGuide.rst)
  — page-by-page reference for the visualisations.

### 10.3 Visualisation references

- d3-hierarchy (sunburst, treemap, icicle) — d3js.org/d3-hierarchy
- d3-sankey, d3-chord, d3-force — d3js.org
- Cytoscape.js — cytoscape.org
- Observable Plot — observablehq.com/plot
- Mermaid — mermaid.js.org
- vis-timeline — visjs.github.io/vis-timeline
- DataTables — datatables.net
- Textual (TUI) — textual.textualize.io

### 10.4 Connectivity-pattern primary references

For each of the ten patterns, a canonical source on the
visualisation choices:

- Tree / containment — Tufte, *Envisioning Information* ch. 2.
- Recursive hierarchy — Stasko & Zhang, *Focus + Context Display*
  (icicle / sunburst).
- Directed call graph — Holten, *Hierarchical Edge Bundling*
  (IEEE Vis 2006).
- Bipartite — Munzner, *Visualization Analysis & Design* ch. 7.
- Aggregated network — Bostock et al., *D3* chord-diagram tutorial.
- Temporal — Aigner et al., *Visualization of Time-Oriented Data*.
- Identity — IRIs and resolvers, *Linked Data* (Heath & Bizer).
- Categorical encoding — Munzner, ch. 5 (channels).
- Scalar overlay — Cleveland, *Visualizing Data* (1993).
- Spatial / positional — Tufte, *The Visual Display of Quantitative
  Information* (small multiples).
