# vista-cli — Packaging & Distribution

Addendum to [vista-cli-planning.md](vista-cli-planning.md). Specifies
how vista-cli is built and shipped to developers on Linux and macOS,
without requiring Python or pip on the target machine.

> Status: implemented. PyInstaller spec, Homebrew formula, and a
> release CI workflow ship in this repo. Tag a `v*` release to
> publish.

---

## 1. Audience and constraints

- **Target users**: developers running Linux or macOS.
- **macOS users have Homebrew.** This is a hard assumption — it gives
  us a one-liner install path with no Python or pip in the user-facing
  surface, even though Homebrew is installing Python under the hood.
- **Linux users do not have a single common package manager.** We
  ship a self-contained tarball that bundles its own Python runtime.
- **No Python or pip required by the user on either platform.**

A secondary path (`pip install vista-cli`) exists for developers who
already use pipx / uv / poetry, but it is not the documented happy
path.

---

## 2. Distribution matrix

| Platform | Method | What ships | Size | User command |
|---|---|---|---|---|
| **macOS (any arch)** | Homebrew formula | `vista-cli` source + `python@3.12` dep | <1 MB (formula); Homebrew handles Python | `brew install rafael5/vista/vista` |
| **Linux x86_64** | PyInstaller tarball | self-contained binary bundle | ~10 MB compressed / ~35 MB extracted | extract + drop on `$PATH` |
| **Linux aarch64** | PyInstaller tarball | self-contained binary bundle | ~10 MB compressed / ~35 MB extracted | extract + drop on `$PATH` |
| **Anywhere with Python** | PyPI | sdist + wheel | <1 MB | `pipx install vista-cli` |

The snapshot data bundle (~60 MB compressed; covered in
[vista-cli-portable-distribution.md](vista-cli-portable-distribution.md))
ships separately on the same GitHub release. Users install the CLI
with one command, then run `vista init` to fetch the data.

---

## 3. macOS — Homebrew formula

[Formula/vista.rb](../Formula/vista.rb) defines the formula. The
distribution model is a tap on this same repository:

```bash
brew tap rafael5/vista https://github.com/rafael5/vista-cli
brew install vista
```

Why a Homebrew formula instead of a PyInstaller binary on macOS:

- Code-signing / notarization is real friction. Unsigned PyInstaller
  binaries trigger Gatekeeper on first launch and require the user
  to right-click → Open or run `xattr -d com.apple.quarantine`.
  Homebrew sidesteps the entire issue — formulae are trusted.
- macOS developers expect `brew install`. It's the native UX.
- Homebrew handles its own Python (`python@3.12`), so the
  no-Python-required property still holds from the user's
  perspective. They never see pip or a venv.
- Tap maintenance is one URL bump + one SHA per release. The CI
  workflow (§5) emits the metadata to do it.

The formula uses Homebrew's `Language::Python::Virtualenv` mixin,
which automates the venv creation and resource installation. Each
release of vista-cli requires bumping `url` to the new sdist on the
GitHub release and recomputing `sha256`:

```bash
curl -L https://github.com/rafael5/vista-cli/releases/download/v0.X.0/vista_cli-0.X.0.tar.gz \
  | shasum -a 256
```

`brew livecheck` against the GitHub Releases atom feed can automate
the bump if you want to publish a Homebrew tap that updates itself.

---

## 4. Linux — PyInstaller tarball

[vista.spec](../vista.spec) is the PyInstaller spec. It produces a
single directory at `dist/vista/` containing the launcher, an
embedded Python interpreter, click, vista-cli's source, and the
canonical `packages.csv`. The directory is then `tar -cJf`'d into
`dist/vista-linux-${ARCH}.tar.xz`.

### 4.1 `--onedir`, not `--onefile`

`--onefile` is a single executable that extracts to a temp dir on
every invocation. That extraction adds ~200 ms to startup — felt
when typing `vista routine X` repeatedly. `--onedir` loads instantly
(measured: 96 ms cold) at the cost of shipping a directory instead
of a single file. Tarred and xz-compressed, both ship as one file
anyway, so the only real cost of `--onefile` is the latency tax —
not worth paying.

### 4.2 glibc compatibility

Linux PyInstaller binaries are dynamically linked against the build
host's glibc. Build on a recent distro and the binary won't run on
older systems with `GLIBC_2.34 not found`. The CI matrix builds
inside `quay.io/pypa/manylinux2014_x86_64` (and `_aarch64`) — both
based on CentOS 7 with glibc 2.17, which gives forward compatibility
to essentially any Linux from 2014 onward (RHEL 7, Ubuntu 18.04,
Debian 10, anything newer).

### 4.3 Local build

```bash
make package
# →  dist/vista/                       (35 MB extracted bundle)
# →  dist/vista-linux-x86_64.tar.xz    (10 MB compressed)
```

`make package-smoke` builds and verifies the binary runs.

### 4.4 User install

```bash
curl -LO https://github.com/rafael5/vista-cli/releases/download/vX.Y.Z/vista-linux-x86_64.tar.xz
tar -xJf vista-linux-x86_64.tar.xz
sudo mv vista /opt/   # or anywhere
sudo ln -s /opt/vista/vista /usr/local/bin/vista
vista doctor
vista init   # fetches the snapshot data bundle
```

The bundle is self-contained — no Python, no pip, no venv on the
target.

---

## 5. CI release workflow

[.github/workflows/release.yml](../.github/workflows/release.yml)
runs on `v*` tag pushes (and via manual dispatch). Three concurrent
jobs:

1. **`pypi`** — builds sdist + wheel via `python -m build`.
2. **`linux-binary`** — matrix of `(x86_64, aarch64)` running the
   PyInstaller build inside the `manylinux2014_*` containers.
3. **`release`** — gathers all artifacts, computes
   `SHA256SUMS`, attaches everything to the GitHub release, and
   pushes the wheel + sdist to PyPI via trusted publishing.

The release ends up with a flat list of assets on the GitHub
release page:

```
vista_cli-0.1.0-py3-none-any.whl
vista_cli-0.1.0.tar.gz
vista-linux-x86_64.tar.xz
vista-linux-aarch64.tar.xz
SHA256SUMS
```

Plus, separately (built by the snapshot pipeline in the
portable-distribution doc):

```
vista-snapshot-2026.04.28.tar.xz
vista-snapshot-2026.04.28.tar.xz.sha256
```

---

## 6. After the formula is published

To bump the Homebrew formula on each release, the maintainer
either:

- runs `brew bump-formula-pr` against the formula in the tap (manual,
  one PR per release), or
- adds an extra CI step that opens the bump PR automatically using
  the `dawidd6/action-homebrew-bump-formula` action.

Either way, the user-facing install command never changes:

```bash
brew install rafael5/vista/vista
brew upgrade vista
```

---

## 7. Why not other options

Considered and rejected:

- **`uv tool install vista-cli`** — works fine for developers who
  already have uv, but isn't a clean Mac story. Conflicts with the
  Homebrew expectation set by the audience.
- **PyOxidizer / Nuitka** — smaller binaries, faster startup, but
  more brittle around dynamic imports and longer CI builds.
  Revisit only if the 96 ms PyInstaller startup or 35 MB bundle
  becomes a real complaint.
- **Snap / Flatpak / AppImage** — heavyweight for a CLI dev tool,
  and Snap in particular has confinement issues with shelling out
  to `m fmt` / `m lint` cleanly.
- **Docker image** — the wrong UX for a CLI you type 50 times a
  day. Useful as a sidecar (e.g. for CI), not as the primary
  install path.
- **PyInstaller `--onefile`** — see §4.1 above.
- **macOS PyInstaller binary** — see §3 (codesign/notarization
  friction). Homebrew is strictly better for the developer
  audience.
