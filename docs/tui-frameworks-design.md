# tui-frameworks-design — TUI Frameworks & Design Motifs Guide

A reference for building terminal-user-interface applications. Surveys
the rendering stack from raw ANSI up through high-level frameworks,
catalogues UI design motifs and architecture patterns, names a
representative app for every major framework, and uses **btop** — a
hand-rolled C++ status monitor — as the reference for what
"high-performance, visually rich, no framework" looks like.

> Status: design reference. Vendor-neutral; the
> [§9 vista-cli selection](#9-selection-guidance-for-vista-cli) note
> at the end is the only project-specific section.
> Companion to [docs/vista-viz-design.md](vista-viz-design.md).

---

## Table of contents

- [1. Executive summary](#1-executive-summary)
- [2. The TUI rendering stack](#2-the-tui-rendering-stack)
- [3. Architecture patterns](#3-architecture-patterns)
- [4. UI design motifs](#4-ui-design-motifs)
- [5. Reference implementation — btop](#5-reference-implementation--btop)
- [6. Framework survey by language](#6-framework-survey-by-language)
- [7. Comparative feature matrix](#7-comparative-feature-matrix)
- [8. Choosing a framework](#8-choosing-a-framework)
- [9. Selection guidance for vista-cli](#9-selection-guidance-for-vista-cli)
- [10. Reference](#10-reference)

---

## 1. Executive summary

A TUI is built from three independent decisions:

1. **A rendering stack** — raw ANSI, a low-level backend (terminfo,
   crossterm, tcell), or a high-level framework with widgets.
2. **An architecture pattern** — Elm-style (TEA), component / React,
   retained widget tree, immediate mode, or direct ANSI.
3. **A set of UI design motifs** — dashboard, master-detail, miller
   columns, modal, command palette, real-time charts, etc.

These are orthogonal. btop ships a real-time chart dashboard motif
on top of a direct-ANSI architecture written in C++23 with no
framework at all. Lazygit ships master-detail + floating overlay
motifs on Bubble Tea / Bubbles in Go. Helix ships modal editing on
its own Rust event loop using Crossterm directly. Same end-user
experience genre (rich, polished TUI), three radically different
implementation choices.

The framework survey in §6 covers ~40 libraries across 11 languages
with a representative app for each and the distinguishing features
that drive the choice. The motif catalogue in §4 is independent of
language and applies equally to any framework or hand-rolled
renderer.

---

## 2. The TUI rendering stack

Every TUI sits on the same physical interface — a stream of bytes
to the terminal, a stream of bytes back from stdin — but
abstractions stack in distinct layers.

### 2.1 Layer 0 — the terminal itself

- **ANSI / VT escape sequences** — `ESC [` followed by parameters.
  Encodes cursor moves, colour, mode toggles, mouse reports,
  bracketed paste, alternate-screen swap, window-title changes.
  Standardised in ECMA-48 / ISO 6429.
- **Termios** — POSIX raw / cooked mode, signal forwarding,
  echo control. The kernel-level switch into the alternate input
  regime any TUI requires.
- **Terminfo / Termcap** — historical capability database. Maps
  capability names (`smcup`, `cup`, `bold`) to the right escape
  sequence per terminal type. Largely replaced in modern TUIs by
  hardcoding "the common subset that works in xterm-256color and
  every emulator that pretends to be one".
- **Extension protocols** — Sixel (image bitmaps), Kitty graphics
  protocol, iTerm2 inline images, Synchronized Output (DEC mode
  2026), bracketed paste (mode 2004), focus events (mode 1004),
  mouse modes (1000 / 1006 / 1015), undercurl (SGR 4:3), 24-bit
  colour (SGR 38:2), hyperlinks (OSC 8). These are how a 2025-era
  TUI gets graphical-app-like polish.

### 2.2 Layer 1 — minimal terminal libraries

Wrap layer 0 with input parsing, screen-buffer management, basic
drawing primitives, but no widgets.

| Library | Language | What it covers |
|---|---|---|
| **ncurses** | C | The grandparent. Window stack, refresh model, terminfo-driven. |
| **termbox / termbox2** | C | "ncurses minus the ceremony." Cell-based double buffer. |
| **Crossterm** | Rust | Cross-platform (incl. Windows) raw I/O, mouse, colours. Backend for Ratatui, Iocraft. |
| **Termion** | Rust | Unix-only counterpart to Crossterm. |
| **tcell** | Go | Backend for tview and Bubble Tea. |
| **Notcurses** | C / C++ / Python / Rust | Maximalist: 24-bit colour, multimedia, sixel/kitty graphics, threads. |
| **Vty** | Haskell | Backend for Brick. |

Choose this layer when you want full control of the event loop,
your own widget vocabulary, and minimal dependency surface. btop
sits roughly here (it skips even termbox and writes ANSI directly).

### 2.3 Layer 2 — widget toolkits

Widgets, layout, input routing, focus management. Above this layer
you stop writing draw calls and start describing trees.

| Toolkit | Language | Style |
|---|---|---|
| **Textual** | Python | CSS-styled, async, web-shaped |
| **Urwid** | Python | Mature, callback-driven |
| **PyTermTk** | Python | Qt-flavoured signals/slots |
| **Bubble Tea** | Go | Elm Architecture (TEA) |
| **tview** | Go | Classic widget set on tcell |
| **Ratatui** | Rust | Immediate-mode-feeling layout + widgets |
| **Iocraft** | Rust | React-like JSX-ish |
| **Cursive** | Rust | Retained tree, Brick-like |
| **FTXUI** | C++ | Functional combinators |
| **Tvision** | C++ | Modern Turbo Vision port |
| **FINAL CUT** | C++ | Widget-rich, X-windows-flavoured |
| **Imtui** | C++ | Immediate-mode (Dear ImGui style) |
| **Ink** | TS / JS | React renderer to terminal |
| **Blessed** | Node | Original JS TUI toolkit |
| **OpenTUI** | TS | Newer reactive TUI for Bun/Deno |
| **Brick** | Haskell | Pure declarative |
| **Lanterna** | Java | Curses-shaped |
| **Terminal.Gui** | .NET | Cross-platform widgets |
| **Spectre.Console** | .NET | Output-formatting + lightweight TUI |

### 2.4 Layer 3 — meta-frameworks and ecosystems

Suites of cooperating libraries — styling, components, prompts,
log rendering — sharing a render model. The Charm ecosystem (Go)
is the canonical example: **Bubble Tea** (loop), **Bubbles**
(components), **Lip Gloss** (styling), **Glamour** (markdown),
**Huh** (forms), **Wish** (SSH wrapping). Python's analogue is
**Rich** (output) + **Textual** (app) + **Textual-Web** (browser
mirror).

---

## 3. Architecture patterns

### 3.1 The Elm Architecture (TEA)

Pure `Model`, pure `Update(model, msg) → (model, cmd)`, pure `View(model)
→ ui`. No mutable state outside the model. Side effects are
described as commands and run by the runtime.

- **Pros** — referentially transparent, easy to test, easy to
  time-travel debug, predictable.
- **Cons** — verbose for forms, every keystroke produces a `Msg`
  variant, intermediate state for transient UI (modal open?
  search query?) lives in the same model as everything else.
- **Frameworks** — Bubble Tea (Go), Brick (Haskell, with
  `EventM` instead of pure update), Iocraft (Rust), TUI4J (Java),
  Ashen (Swift), Blessed (Swift).

### 3.2 Component / React-like

Tree of stateful or stateless components. Each owns local state via
hooks. Re-renders driven by state changes propagate down a virtual
DOM diff.

- **Pros** — familiar to web developers, composes well, animation
  hooks straightforward.
- **Cons** — runtime overhead (virtual tree diff every tick),
  stateful hooks introduce closure pitfalls.
- **Frameworks** — Ink (Node, literal React reconciler), Iocraft
  (Rust, JSX-ish), OpenTUI (TS), Nocterm (Dart, Flutter-like).

### 3.3 Retained widget tree

A persistent tree of widget objects with input handlers. The
framework tracks focus, dispatches events, redraws dirty regions.

- **Pros** — efficient incremental redraws, ergonomic for
  forms-heavy apps, Qt-shaped familiarity.
- **Cons** — state lives across the tree; reasoning about where
  data flows is harder than TEA.
- **Frameworks** — Textual (Python, with reactive bindings + CSS),
  Urwid (Python), tview (Go), Cursive (Rust), Lanterna (Java),
  Terminal.Gui (.NET), Tvision (C++), FINAL CUT (C++), PyTermTk
  (Python).

### 3.4 Immediate mode

Each frame, the application calls draw functions for everything
visible. The framework owns no widget state; the app owns it all.
Inputs are checked synchronously inside the same loop.

- **Pros** — minimal state to track, trivially supports dynamic
  layouts, easy to reason about.
- **Cons** — re-runs every layout call per frame; per-widget state
  is the app's problem.
- **Frameworks** — Ratatui (Rust — strictly retained-state but
  feels immediate), Imtui (C++, Dear ImGui-shaped), FTXUI (C++ —
  hybrid functional + immediate).

### 3.5 Direct ANSI / no framework

Hand-write escape sequences. Manage your own input parser, your own
double buffer (or none), your own redraw loop.

- **Pros** — peak performance, total control over rendering, zero
  third-party dependency.
- **Cons** — months of plumbing; portable input parsing alone is a
  serious project.
- **Examples** — btop (C++23), bandwhich (Rust, mostly), htop (C
  with light ncurses), early bashtop (literally bash plus ANSI).

### 3.6 Reactive / declarative styling

Orthogonal to the above: how state changes propagate to the view.

- **Reactive variables** — Textual's `reactive` attributes
  re-render automatically.
- **CSS-shaped styling** — Textual, Lip Gloss, Spectre.Console.
- **Style structs / combinators** — Lip Gloss (Go), Ratatui's
  `Style`, Brick's attribute maps.
- **Direct ANSI** — btop computes attribute strings inline.

---

## 4. UI design motifs

A motif is the shape of the UI as the user perceives it,
independent of which framework drew it.

### 4.1 Single-pane status dashboard

One full-screen view continuously refreshing data. Often gauge /
bar-heavy. Examples: `top`, `htop`, `btop`, `glances`, `gtop`,
`bashtop`, `bandwhich`, `gotop`, `bottom`.

### 4.2 Multi-pane split

Two or more rectangular regions, each with its own content stream
and (sometimes) its own focus. Examples: `tmux`, `vim` splits,
`lazygit`, `lazydocker`, `tig`. Often mixes a navigation pane with
a detail / preview pane.

### 4.3 Master-detail

A list on one side, a detail view of the highlighted item on the
other. Updates live as the cursor moves. Examples: `mutt`,
`neomutt`, `k9s`, `aerc`, `gh dash`, `lazygit` commits view.

### 4.4 Miller columns (NeXT / Finder-style)

Three or more columns, each one drilling deeper into the previous
column's selection. Arrow keys move between columns; right-arrow
descends. Examples: `ranger`, `nnn`, `broot`, `yazi`, `vifm`, the
macOS Finder column view.

### 4.5 Modal editing

Distinct input modes (normal / insert / visual / command). Same
key has different meaning per mode. The dominant pattern in serious
text editors. Examples: `vim`, `neovim`, `helix`, `kakoune`,
`emacs evil-mode`.

### 4.6 Command palette / fuzzy finder

A modal overlay that takes a query and ranks all available
commands or items. Often invoked with `Ctrl-K` / `Ctrl-P`.
Examples: `fzf` (the canonical), `vim` Telescope, `vscode`
palette, `lazygit` filter prompt, `zellij` find, `atuin`.

### 4.7 Tab / workspace bar

Top or bottom row of named tabs swapping between full-screen
views. Examples: `gh dash`, `tig`, `zellij` tabs, `glow`'s view
modes.

### 4.8 Floating overlay / popup

Modal dialogs, dropdowns, autocompletes, confirmations rendered
above the underlying content. Requires the framework to support
z-ordering and dirty-rect compositing. Examples: `lazygit`
confirmations, `k9s` actions menu, `helix` popup completions,
`fzf` preview window.

### 4.9 Tree explorer

A nested tree (often expandable) on the left, content on the
right. The "IDE sidebar" in terminal form. Examples: `ranger`,
`yazi`, `nnn` in tree mode, `tig` log tree, GitHub `gh repo
browse`.

### 4.10 Form / wizard

Sequential or grouped input fields. Tab between fields, submit at
the end. Examples: `dialog`, `whiptail`, `gum form`, OS installer
TUIs (Debian d-i, Arch `archinstall`, RHEL Anaconda), `huh` forms
in Charm apps.

### 4.11 REPL / chat

Scrollback above, single input line below. Optional sidebar of
channels / contexts. Examples: `irssi`, `weechat`, `gomuks`
(Matrix), `senpai`, `aerc` compose, `ipython`, `bpython`.

### 4.12 Real-time chart dashboard

Densely packed multi-region view, each cell a live gauge / chart /
sparkline / heatmap. The visual high-water mark for "rich TUI."
Examples: `btop` (CPU + mem + net + procs), `glances`, `bandwhich`
(network), `wtfutil` (info dashboard), `nvtop` (GPU), `iotop`,
`procs`.

### 4.13 Scrollback + status bar

Pager-shaped: long scrollable buffer plus a thin status row. The
classic Unix shape. Examples: `less`, `more`, `most`, `git log`,
`pspg`.

### 4.14 Notebook / outline

Collapsible sections, often with rich-text rendering. Examples:
`euporie` (Jupyter in terminal), `glow` (markdown), `mdcat`,
`bat`'s syntax-highlighted paging.

### 4.15 Composite / linked-views workspace

Several motifs in one app, with selection in one driving update of
others. Examples: `lazygit` (master-detail + multi-pane + modal +
overlay), `k9s` (tab bar + master-detail + overlay + command),
`yazi` (miller + preview + form). The polished serious-app shape.

---

## 5. Reference implementation — btop

btop is the right point of comparison whenever a TUI aspires to
"web-app-grade visual polish". It achieves it without a framework.

### 5.1 What btop is

A real-time system monitor: CPU (per-core, with frequency,
temperature, wattage), memory + swap, network throughput, disk I/O
+ usage, GPU (NVIDIA / AMD / Intel), battery, and a sortable
process list with filter / signal-send / tree mode. Written in
**C++23**.

Lineage: bashtop (bash, ANSI-only) → bpytop (Python rewrite) →
btop (C++ rewrite, current). Each rewrite kept the same visual
language while moving the engine closer to the metal.

### 5.2 Architecture choices

- **No framework.** Direct ANSI escape sequences. No ncurses, no
  termbox, no FTXUI.
- **Custom render loop.** The app drives its own tick (default 2
  Hz, configurable). Each tick: collect samples → compose a frame
  buffer of strings → diff against the previous frame → emit only
  the changed runs.
- **Cell-grain dirty tracking.** Avoids repainting the whole screen
  every tick — critical for low CPU overhead while idle.
- **Multiple symbol sets per chart.** Braille (4 × 2 sub-cells per
  char, highest density), block (1 × 1), TTY (ASCII fallback).
  Selected per terminal capability + user preference.
- **Mouse-driven UI.** Clickable buttons, scrollable lists,
  draggable column dividers. Implemented by parsing SGR mouse
  reports (mode 1006) directly.
- **Theme files.** ANSI colour table loaded from disk; backwards
  compatible with bashtop / bpytop themes. Game-menu styled
  picker.
- **Native data collection.** Reads `/proc`, `/sys`, syscalls, GPU
  vendor SDKs (dynamically loaded). No external monitoring lib.

### 5.3 What this earns

- **Visual density.** Braille graphs squeeze 8 sub-pixels into one
  cell. A 20-cell-wide CPU history graph carries 160 samples.
- **Idle frugality.** CPU usage stays in the 0.1–0.5 % range
  because most ticks emit only a few hundred bytes of diff.
- **No framework upgrade tax.** No dependency churn. The code
  compiled in 2021 still compiles in 2026.
- **Portability across BSDs.** Linux, macOS, FreeBSD, NetBSD,
  OpenBSD all in-tree, behind small per-OS sample collectors.

### 5.4 What it costs

- **Months of plumbing.** Every TUI primitive a framework gives
  you for free is in the btop source tree: input parser, mouse
  protocol decoder, alternate-screen handling, SIGWINCH resize,
  Unicode width calculation, theme loader.
- **Ports are hard.** Adding a Windows backend is a major
  engineering project; btop's Windows support relies on third-party
  forks.
- **Inflexible at the rendering layer.** Want a different chart
  shape? Edit C++. There is no widget vocabulary.

### 5.5 What to copy when you are using a framework

- **Decouple the sample collector from the renderer.** A 2 Hz tick
  pulling fresh data into a model the framework redraws is the
  same pattern, with the rendering loop replaced.
- **Cell-grain dirty tracking.** Most modern frameworks already do
  this (Textual's compositor, Ratatui's diff, Bubble Tea's diff).
  Validate it on your target terminal — over a slow SSH link the
  diff is the difference between usable and unusable.
- **Multiple symbol sets per chart.** Honor terminal capability and
  user preference. Braille is unbeatable for density when
  available; ASCII is the only thing that works in `script(1)`
  recordings and CI logs.
- **Mouse + keyboard always.** btop's clickable headers and
  scroll-aware lists make it usable for someone who wandered in
  without reading docs. Most TUIs neglect this.
- **Themes as data, not code.** Ship a default theme, parse user
  themes from a known directory, never hardcode colours past the
  semantic role.

---

## 6. Framework survey by language

For each: representative apps and the distinguishing features that
drive the choice.

### 6.1 Python

**Textual** — Will McGugan / Textualize. CSS-styled widgets, async
event loop, reactive attributes, devtools (live reload of CSS),
optional web mirror via Textual-Web / Textual-Serve. Compiles
naturally to Python wheels.
- *Apps:* Elia (LLM chat), Posting (Postman-shaped HTTP client),
  Harlequin (SQL IDE), Memray TUI (memory profiler), `dolphie`
  (MySQL diagnostics), `frogmouth` (markdown browser).
- *Distinguishing:* CSS + reactive properties + async; the only
  major framework with first-class browser export.

**Urwid** — long-standing, callback-driven, mature. Heavier
ergonomic cost than Textual but reliable.
- *Apps:* Mitmproxy console UI, `wicd-curses`, `pythondialog`-shaped
  installers.
- *Distinguishing:* Lowest abstraction in the Python widget tier;
  callback-and-listbox model.

**Rich** — output formatting library, not a TUI per se. Pretty
prints tables, syntax highlighting, progress bars, markdown, logs.
The substrate Textual builds on.
- *Apps:* Pip's progress UI, virtually every modern Python CLI's
  output style, `pytest --tb`, `httpx` log lines.

**Python Prompt Toolkit** — single-line and multi-line prompts with
syntax highlighting, completions, history. The right pick for
"shell-shaped" interactive tools rather than full-screen apps.
- *Apps:* IPython, `bpython`, pgcli, mycli, `litecli`, Vi /
  ptpython.

**PyTermTk** — Qt-flavoured signals-and-slots widget toolkit with
splitters, tab bars, modal dialogs.
- *Distinguishing:* Familiar to Qt developers; widget set is wider
  than Textual's.

**Vindauga** — Python port of Borland Turbo Vision. Genuinely
interesting if you want the 90s aesthetic without writing C++.

**Blessed** (Python) — Pythonic terminal feature wrapper, not a full
framework. Cursor moves, colour, key parsing.

### 6.2 Go

**Bubble Tea** — Charm ecosystem; The Elm Architecture (TEA);
single binary, fast startup, no GC pauses noticeable in a TUI.
Pairs with **Lip Gloss** (style) and **Bubbles** (components).
- *Apps:* Glow (markdown viewer), Soft Serve (Git server TUI),
  Charm (account TUI), `gum` (interactive shell prompts), `wishlist`
  (SSH directory), Rosé Pine theme picker.
- *Distinguishing:* Cleanest TEA implementation in any language;
  Charm's ecosystem (Lip Gloss, Glamour, Huh, Wish, VHS for
  recording) is the most polished suite anywhere.

**tview** — classic widget set on tcell. Less opinionated than
Bubble Tea; closer to the curses lineage.
- *Apps:* K9s (Kubernetes), Lazydocker (Docker), Lazygit (early
  versions), `cointop` (crypto tracker), `fyne-cli`.
- *Distinguishing:* Pre-built widgets (Pages, Flex, Table, Form);
  fast to assemble a working app.

**tcell** — terminal cell library; backend for tview and others.
Direct API for raw rendering when you don't want a widget tree.

**gocui** — minimalist; layouts by callback returning rectangles.
- *Apps:* Lazygit (modern), Lazydocker (bridge layers).
- *Distinguishing:* Layout-by-function rather than widget-tree;
  ergonomic for highly custom interfaces.

**Pterm** — output formatting closer to Rich than to Bubble Tea.

### 6.3 Rust

**Ratatui** — community fork of `tui-rs`; immediate-mode-feeling
widget API on Crossterm / Termion / Termwiz. The dominant Rust
choice.
- *Apps:* Yazi (file manager), Helix (parts of its UI),
  `spotify-player`, `gitui`, `bottom`, `oxker` (Docker), `atuin`
  (shell history), `bandwhich` (network), `zellij` (terminal
  multiplexer parts).
- *Distinguishing:* No prescribed app architecture; idiomatic Rust
  borrow-checker fit; ~30–40 % less memory than Bubble Tea
  equivalents in benchmarks; widely adopted.

**Iocraft** — JSX-ish React-like Rust TUI. Newer.
- *Distinguishing:* Component-and-hooks model; appeals to React /
  Ink developers wanting Rust speed.

**Cursive** — retained-tree widgets with high-level API.
- *Apps:* `cursive-async-view` demos, internal admin tools.
- *Distinguishing:* Closest to Brick / Lanterna in shape; less
  ceremony than Ratatui for simple apps.

**Crossterm** / **Termion** / **Termwiz** — backends; you build
your own loop.

**Zaz** — efficient terminal rendering primitive.

### 6.4 C / C++

**ncurses** — the foundation. C, terminfo-driven, omnipresent.
Slow on modern hardware compared to direct ANSI but still the
default for serious portability across exotic terminals.
- *Apps:* `htop`, `nethack`, `mutt`, `irssi`, `tig` (early), `ranger`
  (Python with curses bindings).

**Notcurses** — C / C++ / Python / Rust bindings. Maximalist:
Sixel + Kitty graphics + Linux framebuffer, multimedia (image /
video), threading, 24-bit colour. The library to reach for when
you want real images in the terminal.
- *Apps:* `notcurses-demo` (the showcase), `omphalos` (network
  monitor), `growlight` (block-device manager).
- *Distinguishing:* Graphical capability ceiling above every other
  framework on this list; multimedia in-terminal.

**FTXUI** — modern C++ functional terminal UI. Composable element
combinators, declarative.
- *Apps:* Various game-dev menu tools, `nbtui`, internal tooling.
- *Distinguishing:* Clean modern C++17/20 API; small dep footprint;
  good for embedded use.

**Tvision** — modern port of Borland Turbo Vision 2.0 with Unicode
support.
- *Apps:* `turbo` (text editor in the Turbo Vision style).
- *Distinguishing:* Authentic Turbo-Vision aesthetic; window
  manager + native dialogs.

**FINAL CUT** — widget-rich terminal toolkit, X-windows-shaped
event model.

**Imtui** — immediate-mode TUI in the Dear ImGui mould.
- *Distinguishing:* Familiar to anyone who's used Dear ImGui; the
  most "redraw-every-frame" of any framework here.

**termbox / termbox2** — minimal cell-grid library on top of ANSI
escape codes, no widgets.
- *Apps:* `mc` (Midnight Commander) variants, custom pet projects.

**tuibox** — single-header C TUI for mouse-driven apps.

### 6.5 Node.js / JavaScript / TypeScript

**Ink** — React for terminals; JSX components reconciled to a
text canvas. The dominant JS choice.
- *Apps:* Gatsby's CLI, GitHub Copilot CLI, Prisma CLI, Shopify
  CLI, Cloudflare Wrangler, Twilio CLI, `tsuru` CLI, `oclif`-based
  apps.
- *Distinguishing:* Literal React; flexbox layout (Yoga); easy
  migration path for web devs.

**Blessed** (Node) — original JS TUI library, widget-tree-shaped.
Mostly superseded by Ink for new projects.
- *Apps:* `slack-term`, `bbn` (BlessingBoard), various dashboards.

**OpenTUI** — newer TS framework targeting Bun / Deno; reactive
component model.

**Melker** — HTML-document-first TUI for TS.

### 6.6 Java / JVM

**Lanterna** — pure-Java curses-shaped library. Widget hierarchy,
modal dialogs, tables.
- *Apps:* Kafka tools, `jline` integrations.
- *Distinguishing:* No JNI; runs anywhere a JVM does; classic
  curses ergonomics.

**Jexer** — text-based windowing system in Java; multi-window UI
inside one terminal. Closer to Tvision in spirit.

**TUI4J** — Bubble Tea port to Java; same TEA pattern.

**Casciian** — designed for GraalVM AOT; minimal startup cost.

### 6.7 .NET

**Terminal.Gui** — cross-platform widget toolkit; v2 brought a
significant rewrite.
- *Apps:* PowerShell admin tools, internal Microsoft utilities.
- *Distinguishing:* First-class on Windows console; .NET MAUI-ish
  ergonomics.

**Spectre.Console** — output-formatting library plus light TUI
(prompts, progress, tables, trees, live displays). Comparable to
Rich.
- *Apps:* `dotnet`-tooling output styles, `cake` build system.
- *Distinguishing:* The "Rich for .NET" but with more interactive
  primitives.

**Consolonia** — XAML-based; ports Avalonia patterns to terminal.
- *Distinguishing:* Designers can author terminal layouts in XAML.

### 6.8 Haskell

**Brick** — pure declarative TUI on top of **Vty**. State + event
function + view function. Pure functions, exceptional testability.
- *Apps:* `matterhorn` (Mattermost client), `tasty-rerun`,
  `ghcup-tui`, `gitit-hs` UI parts.
- *Distinguishing:* Cleanest pure-functional TUI in any language;
  the reference for "what TEA looks like with strong typing."

### 6.9 Other languages

| Lang | Library | Notes |
|---|---|---|
| Swift | **Ashen**, **Blessed (Swift)** | Elm-inspired |
| Dart | **Nocterm** | Flutter-like, 45+ components |
| Nim | **Nimwave** | Targets terminal *and* browser |
| Lua | **lcurses**, **luaposix.curses** | Curses bindings |
| Elixir | **ratatouille** | TEA-shaped on top of termbox |
| OCaml | **lambda-term**, **notty** | Pure-functional rendering |
| PHP | **php-tui** | Heavy port of Ratatui |
| Crystal | **crysterm** | Blessed-for-Crystal port |
| Zig | **vaxis**, **libvaxis** | Minimal cell renderer |
| Ruby | **TTY** suite (`tty-prompt`, `tty-table`) | Output-formatting + prompts |

---

## 7. Comparative feature matrix

A coarse comparison across the major frameworks. `Y` = supported
out of the box, `o` = via plug-in or extension, `—` = not really.

| Feature | Textual | Bubble Tea | Ratatui | FTXUI | Notcurses | Brick | Ink | Lanterna | Term.Gui |
|---|---|---|---|---|---|---|---|---|---|
| **Language** | Python | Go | Rust | C++ | C/C++/Py/Rs | Haskell | TS/JS | Java | .NET |
| **Architecture** | Retained + reactive | TEA | Immediate-feeling | Functional | Imperative | Pure declarative | React | Retained | Retained |
| **CSS-style theming** | Y | o (Lip Gloss) | o | — | — | — | o | — | o |
| **Async event loop** | Y | Y | o | o | o (threads) | Y | Y | — | Y |
| **Mouse** | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| **Sixel / Kitty graphics** | o | — | o | — | Y | — | — | — | — |
| **Browser export** | Y | — | — | — | — | — | — | — | — |
| **Hot-reload styling** | Y | — | — | — | — | — | — | — | — |
| **Cross-platform Win** | Y | Y | Y | Y | partial | Y | Y | Y | Y |
| **First-party form widgets** | Y | o (Huh, Bubbles) | Y | Y | Y | Y | o | Y | Y |
| **Built-in tables / trees** | Y | o (Bubbles) | Y | Y | Y | Y | o | Y | Y |
| **Markdown render** | Y (Rich) | o (Glamour) | o | — | — | — | o | — | o |
| **Test harness** | Y | Y | Y | o | o | Y | Y | o | Y |
| **Maturity (years)** | 5 | 6 | 4 (post-fork) | 6 | 7 | 13 | 9 | 15+ | 4 (v2) |

The matrix isn't a verdict — it's a coordinate system. Pick rows
that matter for your app, then read columns.

---

## 8. Choosing a framework

The decision tree most teams actually walk:

1. **What language is your team / ecosystem already in?**
   That answer eliminates ~80 % of the list.
2. **Do you need browser-mirrored output?**
   Yes → Textual (Textual-Serve) is the only first-class option.
3. **Are you allergic to GC pauses or cold-start latency?**
   Yes → Rust (Ratatui) or C++ (FTXUI / Notcurses / direct ANSI).
4. **Do you want images / sixel / kitty graphics in-terminal?**
   Notcurses, or Textual with `textual-image` plugins.
5. **Is your team React / web-shaped?**
   Ink (TS) or Iocraft (Rust) or Textual (closest CSS feel in
   Python).
6. **Do you want maximum visual density at minimum CPU?**
   Hand-roll on Crossterm / Termion / direct ANSI, btop-style.
7. **Do you want a polished suite (forms, prompts, markdown,
   styling) day one?**
   Charm (Bubble Tea + Bubbles + Lip Gloss + Huh + Glamour) is
   unmatched for completeness; Textual is the closest in Python.
8. **Pure functional / strong typing as a hard requirement?**
   Brick (Haskell).

Failure modes to avoid:

- **Over-frameworking.** A pager or wizard does not need a TUI
  framework. Prompt Toolkit, `gum`, or `dialog` is the right size.
- **Under-frameworking.** A multi-pane app with focus, mouse,
  resize, and overlays will out-grow direct ANSI in week three.
  btop-quality direct-ANSI work is months of plumbing for the
  framework features you skipped.
- **Mixing render models.** Don't compose two frameworks in one
  binary. Pick one, commit.
- **Ignoring degradation.** Test in `dumb`, `xterm`, `xterm-256color`,
  `tmux-256color`, and one truecolour terminal. Test in `script(1)`
  output. Pre-2026 emulators still exist in the wild; CI logs are
  always degraded.

---

## 9. Selection guidance for vista-cli

(Project-specific note. Skip if you are reading this generically.)

Among the candidates, **Textual** is the best fit for a `vista
tui` subcommand:

- Already in the Python ecosystem of `vista-cli`. No second runtime
  to ship.
- The four motifs the visualization design doc calls for —
  miller columns, master-detail, command palette, live ego graph —
  are directly supported by built-in Textual widgets (Tree,
  ListView, Input, DataTable).
- CSS makes the colour palette in [vista-viz-design.md §8.4](vista-viz-design.md#84-colour-palette-consistency-across-surfaces)
  trivial to enforce: one `vista.tcss` file, every motif inherits.
- Textual-Serve gives a free path to the [§5.4 web bundle](vista-viz-design.md#54-web-on-demand-html)
  if a browser surface is wanted later — same code, two
  surfaces.
- Adds ~2 MB to the wheel; gated as an optional dep group
  (`pip install vista-cli[tui]`) to keep the base install lean.

A direct-ANSI / btop-style approach is overkill for this project —
the data is queried lazily from `joined.db`, not sampled at 2 Hz,
so no rendering hotpath benefits from the extra control. A Bubble
Tea / Ratatui rewrite would mean leaving Python, which conflicts
with the single-binary distribution rule in CLAUDE.md.

The one btop pattern worth importing as-is: **multi-symbol-set
charts**. The sparkline / heatmap / matrix renderers proposed in
the visualisation guide should ship with a `--symbols
braille|block|ascii` flag so output works in `script(1)` recordings,
CI logs, and over the rare narrow-charset terminal.

---

## 10. Reference

### 10.1 Frameworks

- **Textual** — textual.textualize.io · github.com/Textualize/textual
- **Rich** — github.com/Textualize/rich
- **Urwid** — urwid.org
- **Python Prompt Toolkit** — python-prompt-toolkit.readthedocs.io
- **Bubble Tea** — github.com/charmbracelet/bubbletea
- **Bubbles / Lip Gloss / Huh / Glamour** — github.com/charmbracelet
- **tview** — github.com/rivo/tview
- **gocui** — github.com/jroimartin/gocui
- **Ratatui** — ratatui.rs
- **Iocraft** — github.com/ccbrown/iocraft
- **Cursive** — github.com/gyscos/cursive
- **Crossterm** — github.com/crossterm-rs/crossterm
- **FTXUI** — github.com/ArthurSonzogni/FTXUI
- **Notcurses** — notcurses.com
- **Tvision** — github.com/magiblot/tvision
- **FINAL CUT** — github.com/gansm/finalcut
- **Imtui** — github.com/ggerganov/imtui
- **Ink** — github.com/vadimdemedes/ink
- **Blessed (Node)** — github.com/chjj/blessed
- **OpenTUI** — github.com/sst/opentui
- **Brick** — hackage.haskell.org/package/brick
- **Lanterna** — github.com/mabe02/lanterna
- **Terminal.Gui** — github.com/gui-cs/Terminal.Gui
- **Spectre.Console** — spectreconsole.net

### 10.2 Reference apps

- **btop** — github.com/aristocratos/btop
- **bashtop / bpytop** — predecessors
- **htop** — htop.dev
- **lazygit** — github.com/jesseduffield/lazygit
- **k9s** — k9scli.io
- **helix** — helix-editor.com
- **yazi** — github.com/sxyazi/yazi
- **ranger** — github.com/ranger/ranger
- **broot** — github.com/Canop/broot
- **glow** — github.com/charmbracelet/glow
- **gh dash** — github.com/dlvhdr/gh-dash
- **fzf** — github.com/junegunn/fzf
- **mutt / neomutt** — neomutt.org
- **zellij** — zellij.dev
- **bandwhich** — github.com/imsnif/bandwhich
- **bottom** — github.com/ClementTsang/bottom

### 10.3 Listings and surveys

- [awesome-tuis](https://github.com/rothgar/awesome-tuis) — the
  canonical curated list.
- [OSS Insight TUI Framework Ranking](https://ossinsight.io/collections/tui-framework)
  — popularity + activity over time.
- [Bubble Tea vs Ratatui benchmark](https://blog.tng.sh/2026/03/go-vs-rust-for-tui-development-deep.html)
  — performance comparison on a 1 000-point dashboard.
- [LogRocket — 7 TUI libraries for interactive terminal apps](https://blog.logrocket.com/7-tui-libraries-interactive-terminal-apps/)

### 10.4 Background reading

- [ANSI escape code (Wikipedia)](https://en.wikipedia.org/wiki/ANSI_escape_code)
  — the underlying signalling.
- Julia Evans, [Standards for ANSI escape codes](https://jvns.ca/blog/2025/03/07/escape-code-standards/)
  — how messy the real-world support actually is.
- Notcurses' design rationale (notcurses.com) — argues for the
  multimedia-capable terminal as a serious app surface.
