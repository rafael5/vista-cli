# vista-cli

Unified CLI joining [vista-meta](https://github.com/rafael5/vista-meta)
(code model) with vista-docs (VDL documentation frontmatter) into one
queryable surface for VistA.

```bash
vista routine PRCA45PT       # code facts + every doc that mentions it
vista where EN^XUSCLEAN      # jump to source for any reference
vista doctor                 # health check of both data stores
```

Companion to:

- [m-cli](https://github.com/rafael5/m-cli) — M-language layer (fmt, lint, test)
- vista-meta — code-model bake, KIDS, VSCode sidebar
- vista-docs — VDL crawler + frontmatter pipeline

`vista-cli` reads from both vista-meta and vista-docs. It does not
modify either. See [docs/vista-cli-planning.md](docs/vista-cli-planning.md)
for design and roadmap.

## Status

Phase 1 — MVP. See `docs/vista-cli-planning.md § 13` for the roadmap.

## Install

**macOS** — via Homebrew (handles the Python interpreter for you):

```bash
brew tap rafael5/vista https://github.com/rafael5/vista-cli
brew install vista
vista init     # fetch the snapshot data bundle
```

**Linux** — self-contained tarball, no Python required on the target:

```bash
curl -LO https://github.com/rafael5/vista-cli/releases/latest/download/vista-linux-x86_64.tar.xz
tar -xJf vista-linux-x86_64.tar.xz
sudo ln -s "$PWD/vista/vista" /usr/local/bin/vista
vista init     # fetch the snapshot data bundle
```

**From source** (developers contributing to vista-cli):

```bash
git clone <this repo>
cd vista-cli
make install
vista doctor
```

See [docs/vista-cli-packaging.md](docs/vista-cli-packaging.md) for
the full distribution matrix.

## Configure

Defaults assume:

- vista-meta at `~/vista-meta/`
- vista-docs data at `~/data/vista-docs/`

Override via env vars: `VISTA_CODE_MODEL`, `VISTA_DOC_DB`,
`VISTA_M_HOST`, `VISTA_DOC_PUBLISH`. See `src/vista_cli/config.py`.
