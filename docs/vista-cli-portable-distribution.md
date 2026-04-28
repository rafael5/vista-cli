# vista-cli — Portable Distribution Addendum

Addendum to [vista-cli-planning.md](vista-cli-planning.md). Specifies
how vista-cli ships **without** a pre-existing vista-meta or
vista-docs install on the host, so a user can go from a fresh
install (Homebrew on macOS, PyInstaller tarball on Linux — see
[vista-cli-packaging.md](vista-cli-packaging.md)) to working queries
with one bootstrap command.

> Status: implemented (phase 4). Depends on `vista build-cache`
> (phase 3).

---

## 1. Motivation

Today vista-cli assumes both upstream stores already exist on disk:

- vista-meta TSVs at `~/vista-meta/vista/export/code-model/`
- vista-docs SQLite at `~/data/vista-docs/state/frontmatter.db`

For the project's primary user that's true. For a fresh install on
any other machine — a colleague's laptop, a clean VM, an air-gapped
host — it isn't, and standing up vista-meta (which needs a YDB
container + a VistA-M tree) or vista-docs (which needs DOCX/PDF
ingest) just to query data those projects have already produced is
overkill.

The fix is a portable **snapshot bundle** of the data both projects
output, plus a CLI command that fetches and installs it. Combined
size is ~60 MB compressed (see §1.3 of the guide for the breakdown);
that's a single GitHub release artifact, not an LFS object, not a
multi-step build.

Two non-negotiables:

- **No install-time code execution.** Bootstrap is an explicit
  command (`vista init`). The CLI install (Homebrew or the
  PyInstaller tarball) is a pure file-copy operation that never
  reaches out to the network during install.
- **Existing-install path stays first-class.** A user with their own
  vista-meta/vista-docs sets the env vars from §1.3 of the guide and
  ignores `vista init` entirely. The bundle is a fallback, not a
  takeover.

---

## 2. Command surface

Three new commands; the existing `vista doctor` learns to report
snapshot status.

### 2.1 `vista init`

The one-shot bootstrap. Idempotent, safe to re-run.

```
vista init [--snapshot VERSION] [--from PATH] [--data-dir PATH]
           [--with-source] [--with-publish] [--force]
```

Behavior:

1. If env vars (`VISTA_CODE_MODEL`, `VISTA_DOC_DB`, ...) point at
   readable data, print the existing setup and exit 0 — never
   overwrite a user's own install.
2. Otherwise, if `--from PATH` is given, install from a local bundle
   (air-gapped path).
3. Otherwise, call `vista fetch` to pull the latest snapshot release
   from GitHub.
4. Extract to `~/data/vista/snapshot/` (or `--data-dir PATH`).
5. Run `vista build-cache` to materialize `~/data/vista/joined.db`.
6. Run `vista doctor` and print the result.

Flags:

| Flag | Default | Effect |
|---|---|---|
| `--snapshot VERSION` | `latest` | Pin to a specific snapshot (`2026.04.28`) |
| `--from PATH` | — | Install from a local `.tar.xz` instead of fetching |
| `--data-dir PATH` | `~/data/vista/snapshot/` | Where the bundle lands |
| `--with-source` | off | Also fetch the 7 GB VistA-M source mirror |
| `--with-publish` | off | Also fetch the 2 GB published markdown tree |
| `--force` | off | Reinstall even when data is already present |

Exit codes: 0 = installed (or already present), 1 = network /
verification failure, 2 = bundle corrupt, 64 = bad flags.

### 2.2 `vista fetch`

The download step on its own. Used for upgrades, scripting, and
the air-gapped two-step pattern.

```
vista fetch [--snapshot VERSION] [--list] [--check]
            [--from PATH] [--download-only --out PATH]
            [--rollback]
```

Behavior:

- Default: downloads the latest snapshot release, verifies its
  SHA-256, atomically swaps it in (old snapshot moves to
  `~/data/vista/snapshot.bak/`).
- `--list` queries the GitHub Releases API, prints available
  snapshots with built-at dates and source commits.
- `--check` reports whether a newer snapshot exists without
  downloading. Suitable for cron / CI.
- `--download-only --out PATH` saves the tarball to disk and stops
  — the connected-machine half of an air-gapped install.
- `--from PATH` skips download and installs from a local tarball —
  the air-gapped-machine half.
- `--rollback` swaps `snapshot.bak/` back into `snapshot/` if a new
  snapshot turns out broken. One-deep history; second `--rollback`
  is a no-op.

### 2.3 `vista snapshot`

The producer side. Mostly run by CI; a developer touches it only
when reproducing a bundle locally.

```
vista snapshot create --out bundle.tar.xz
vista snapshot verify bundle.tar.xz
vista snapshot info   bundle.tar.xz
```

- `create` reads the locally-configured paths (the env vars from
  §1.3 of the guide) and packs them into a portable tarball with
  `snapshot.json` at the root.
- `verify` checks structure, schema versions, and recomputes the
  SHA-256 the manifest claims.
- `info` prints the manifest without extracting.

### 2.4 Doctor integration

`vista doctor` adds two lines:

```
[ok]   snapshot       2026.04.28  built 2026-04-26
                      (vista-meta @ abc1234, vista-docs @ def5678)
[warn] snapshot       a newer snapshot is available: 2026.05.05
                      run: vista fetch
```

`[!!]` if no data is reachable at all, with a `run: vista init`
hint.

---

## 3. Bundle layout

Single tarball, deterministic structure. Extracted in place at
`~/data/vista/snapshot/`:

```
~/data/vista/snapshot/
├── snapshot.json          # manifest (see §3.1)
├── code-model/            # 19 TSVs (~42 MB raw / ~6 MB xz)
│   ├── routines-comprehensive.tsv
│   ├── routine-calls.tsv
│   └── ...
├── data-model/            # 5 TSVs (~13 MB raw / ~2 MB xz)
│   ├── files.tsv
│   ├── piks.tsv
│   └── ...
└── frontmatter.db         # SQLite (~283 MB raw / ~50 MB xz)
```

Plus a separately-fetched cache (built locally, not bundled):

```
~/data/vista/joined.db     # built by `vista build-cache`
~/data/vista/snapshot.bak/ # previous snapshot, one-deep
```

### 3.1 `snapshot.json` manifest

Embedded at the root of every bundle. The single source of truth
for "what's in here."

```json
{
  "snapshot_version": "2026.04.28",
  "schema_version": 1,
  "built_at": "2026-04-28T15:00:00Z",
  "sources": {
    "vista_meta_commit": "abc1234",
    "vista_docs_commit": "def5678",
    "vista_m_version": "WorldVistA-2018-06"
  },
  "contents": {
    "code_model": {"files": 19, "rows": 1120956, "sha256": "..."},
    "data_model": {"files": 5,  "rows": 86430,  "sha256": "..."},
    "frontmatter_db": {
      "rows_documents": 2842,
      "rows_doc_routines": 23714,
      "rows_doc_sections": 138711,
      "fts5_included": true,
      "sha256": "..."
    }
  },
  "min_vista_cli_version": "0.4.0"
}
```

`min_vista_cli_version` lets a snapshot refuse to install on a
too-old CLI when the schema bumps. `schema_version` is the bundle
layout version; `1` = §3 layout.

### 3.2 FTS5 — ship or strip

Two reasonable options, each measured against the actual data.

| Option | Bundle size | First-run cost | Disk after install |
|---|---:|---:|---:|
| **A. Ship FTS5 index** | ~60 MB xz | extract only (~5 s) | 283 MB |
| **B. Strip + rebuild on init** | ~40 MB xz | ~30 s rebuild | 283 MB |

Recommendation: **A (ship the index).** The 20 MB savings doesn't
justify the 30 s install delay on the user's first impression of
the tool, and disk after install is the same either way. Option B
is the lever to pull *only* if GitHub Release asset-size limits
ever start mattering.

The producer side strips trivially when needed:

```sql
DROP TABLE doc_sections_fts;
-- on init: CREATE VIRTUAL TABLE doc_sections_fts USING fts5(...);
--          INSERT INTO doc_sections_fts SELECT ... FROM doc_sections;
```

### 3.3 Optional auxiliary bundles

Not in the main snapshot; opt-in via `--with-source` /
`--with-publish` on `vista init`:

| Bundle | Raw | xz | Provides |
|---|---:|---:|---|
| `snapshot-YYYY.MM.DD-source.tar.zst` | 7.1 GB | ~1.5 GB | VistA-M source mirror — needed by `vista where` to print `path:line` |
| `snapshot-YYYY.MM.DD-publish.tar.zst` | 2.0 GB | ~400 MB | Published markdown — useful as a destination for "open the doc" workflows |

Each is a separate GitHub Release asset on the same tag.
zstd-19 over xz here because compression ratio is closer on the
large mixed-content trees and decompression is 5× faster — the
size differential matters more for files this big.

---

## 4. Distribution

### 4.1 Hosting

GitHub Releases on the **vista-cli** repository (not on vista-meta
or vista-docs). Rationale:

- The snapshot is a join product of both upstreams; vista-cli is
  the only project that can produce it coherently.
- One stable URL pattern for `vista fetch` to consume.
- Decoupled release cadence: vista-cli `0.4.0` and snapshot
  `2026.04.28` are independent versions.

URL pattern (resolvable without auth):

```
https://github.com/rafael5/vista-cli/releases/tag/snapshot-2026.04.28
  ├── vista-snapshot-2026.04.28.tar.xz          (~60 MB)  required
  ├── vista-snapshot-2026.04.28.sha256          (~100 B)  required
  ├── vista-snapshot-2026.04.28-source.tar.zst  (~1.5 GB) optional
  └── vista-snapshot-2026.04.28-publish.tar.zst (~400 MB) optional
```

`vista fetch --list` calls the Releases API and filters tags
matching `snapshot-*`.

### 4.2 Versioning

Calver: `YYYY.MM.DD` of the build day. Multiple builds in one day
get `.1`, `.2` suffixes. The version embeds in the manifest, the
release tag, and every artifact filename — three places in
agreement is enough to detect tampering or rename mistakes.

### 4.3 Producer pipeline

A GitHub Actions workflow in vista-cli, scheduled weekly + on
manual dispatch:

1. Check out vista-meta release (or pinned commit), download its
   pre-built TSV release artifact.
2. Check out vista-docs release, download its `frontmatter.db`
   artifact.
3. Stage them at the canonical paths.
4. Run `vista snapshot create --out vista-snapshot-$(date +%Y.%m.%d).tar.xz`.
5. Run `vista snapshot verify` on the output as a sanity gate.
6. Create a GitHub Release with the tarball, the `.sha256`, and
   release notes auto-generated from the embedded manifest.

This implies vista-meta and vista-docs each publish their own
artifacts on their own release cadence. If they don't yet, the
producer pipeline can build them in-line — slower CI, but no
upstream changes required.

---

## 5. Air-gapped install

The use case: a dev laptop with internet builds the bundle, an
analyst workstation behind a corporate firewall consumes it.

```bash
# On the connected machine
#   (install vista-cli per the platform install path in
#    vista-cli-packaging.md, then download a snapshot)
vista fetch --download-only --out ~/Downloads/vista-snapshot.tar.xz

# Transfer both the CLI install artifact and the snapshot tarball
# across the air-gap (USB, secure copy, etc.):
#   - macOS:  the auto-generated tag archive Homebrew taps from
#   - Linux:  vista-linux-${ARCH}.tar.xz from the GitHub Release

# On the air-gapped machine
#   - macOS:  brew install --build-from-source ./vista.rb (sideload)
#   - Linux:  tar -xJf vista-linux-${ARCH}.tar.xz; ln -s ... /usr/local/bin/vista
vista init --from ~/Downloads/vista-snapshot.tar.xz
vista doctor            # green
```

Both halves of the workflow run the same command surface as the
network path; `--from` is the only difference. The Linux PyInstaller
tarball is fully self-contained (its own Python interpreter is
embedded), so the air-gapped target needs nothing pre-installed.

---

## 6. Failure modes

| Failure | Behavior |
|---|---|
| Network unreachable during `fetch` | Print the resolved URL + sha256, suggest manual download + `--from` |
| SHA-256 mismatch | Refuse to install, leave existing snapshot intact, exit 1 |
| Disk full mid-extract | Detect required space *before* extract via the manifest, fail fast |
| Snapshot newer than CLI (`min_vista_cli_version`) | Refuse, suggest `brew upgrade vista` (macOS) or re-download the Linux tarball |
| Snapshot older than CLI (`schema_version` retired) | Refuse, suggest `vista fetch` for a newer snapshot |
| User has env vars set (existing vista-meta) | `vista init` reports the existing setup and exits 0 — don't overwrite |
| `--rollback` with no `snapshot.bak/` | Print a clear message, exit 1 |

Two atomic-swap properties to preserve:

- **Old snapshot stays intact until the new one is verified.**
  Extract to `~/data/vista/snapshot.new/`, fsync, then `mv` swap
  with `snapshot.bak/`.
- **Cache is rebuilt only after the swap.** `vista build-cache` is
  idempotent and points at whatever `snapshot/` is current.

---

## 7. Phasing

Fits the existing planning doc roadmap as **phase 4 work**, after
`vista build-cache` (phase 3) lands. The dependency direction is:

```
phase 1 (MVP)        phase 2 (joins)        phase 3 (cache)
        │                    │                    │
        └────────────┬───────┴───────┬────────────┘
                     ▼               ▼
        phase 4: portable distribution
        (init / fetch / snapshot)
```

Definition of done:

- A clean machine with only `python3.12` and `pip` can go from
  zero to working `vista routine PRCA45PT` output in under three
  minutes, two commands.
- The same flow works air-gapped given a pre-downloaded bundle.
- `vista doctor` reports snapshot version + freshness.
- A GitHub Actions workflow produces a verified snapshot release
  on a schedule.
- Existing-install users (env vars set) are unaffected — `vista
  init` is a no-op for them.

---

## 8. Open questions

1. **Does the snapshot include a redacted form of `frontmatter.db`?**
   The VDL is public, but if any downstream user runs against an
   internal-VA corpus, the bundle pipeline shouldn't accidentally
   exfiltrate. Recommendation: producer pipeline runs only against
   the public WorldVistA + VDL inputs; private corpora stay
   off-bundle.
2. **Do we sign the bundles (minisign / sigstore)?** SHA-256 +
   GitHub release auth is enough for v1. Revisit if the project
   ever has a non-trusted distribution path.
3. **Refresh cadence.** Weekly is the obvious default but most
   users won't care if their snapshot is a month old. Recommend:
   weekly auto-build; `vista doctor` warns at 60 days.
4. **Source-mirror licensing.** WorldVistA is public domain;
   confirming redistribution rights for `--with-source` before
   shipping. (The TSVs and frontmatter.db are derived metadata —
   not the same question.)
