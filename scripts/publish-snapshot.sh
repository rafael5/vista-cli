#!/usr/bin/env bash
# Build and publish a vista-cli snapshot bundle as a GitHub release.
#
# Run on a host that has the source data on disk (vista-meta TSVs +
# vista-docs frontmatter.db). Creates a release tagged
# `snapshot-<calver>` and uploads the bundle so `vista init` can find it.
#
# Usage:
#   scripts/publish-snapshot.sh [--snapshot-version YYYY.MM.DD]
#
# Environment overrides (optional — defaults match config.py):
#   VISTA_CODE_MODEL    code-model TSV directory
#   VISTA_DOC_DB        frontmatter.db path
#   VISTA_META_DIR      where vista-meta is checked out (for provenance)
#   VISTA_DOCS_DIR      where vista-docs is checked out (for provenance)

set -euo pipefail

CALVER="${1:-}"
if [[ "$CALVER" == "--snapshot-version" ]]; then
  CALVER="$2"
fi
: "${CALVER:=$(date -u +%Y.%m.%d)}"

REPO="rafael5/vista-cli"
TAG="snapshot-${CALVER}"
BUNDLE="vista-snapshot-${CALVER}.tar.xz"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# ── Provenance: best-effort read commit shas from sibling checkouts ──
META_DIR="${VISTA_META_DIR:-$HOME/projects/vista-meta}"
DOCS_DIR="${VISTA_DOCS_DIR:-$HOME/projects/vista-docs}"
META_COMMIT="$(git -C "$META_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
DOCS_COMMIT="$(git -C "$DOCS_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
VISTA_M_VERSION="${VISTA_M_VERSION:-unknown}"

echo ">>> building $BUNDLE (snapshot-version=$CALVER)"
echo "    vista-meta commit: $META_COMMIT"
echo "    vista-docs commit: $DOCS_COMMIT"
echo "    vista-m version:   $VISTA_M_VERSION"

vista snapshot create \
  --out "$WORK/$BUNDLE" \
  --snapshot-version "$CALVER" \
  --vista-meta-commit "$META_COMMIT" \
  --vista-docs-commit "$DOCS_COMMIT" \
  --vista-m-version "$VISTA_M_VERSION"

echo ">>> verifying"
vista snapshot verify "$WORK/$BUNDLE"

echo ">>> manifest"
vista snapshot info "$WORK/$BUNDLE"

SHA="$(sha256sum "$WORK/$BUNDLE" | cut -d' ' -f1)"
SIZE="$(stat -c%s "$WORK/$BUNDLE" 2>/dev/null || stat -f%z "$WORK/$BUNDLE")"
echo ">>> sha256: $SHA"
echo ">>> size:   $SIZE bytes"

# ── Create release (idempotent) and upload bundle ────────────────────
if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  echo ">>> release $TAG already exists — re-uploading bundle (--clobber)"
  gh release upload "$TAG" "$WORK/$BUNDLE" --repo "$REPO" --clobber
else
  echo ">>> creating release $TAG"
  gh release create "$TAG" "$WORK/$BUNDLE" \
    --repo "$REPO" \
    --title "snapshot $CALVER" \
    --notes "$(cat <<EOF
vista-cli data snapshot bundle.

| field | value |
|---|---|
| snapshot-version | $CALVER |
| sha256 | \`$SHA\` |
| size | $SIZE bytes |
| vista-meta commit | \`$META_COMMIT\` |
| vista-docs commit | \`$DOCS_COMMIT\` |
| vista-m version | $VISTA_M_VERSION |

Install with \`vista init\` (auto-picks latest) or
\`vista init --snapshot $CALVER\`.
EOF
)"
fi

echo ">>> sanity check: discoverable via the API?"
gh api "repos/$REPO/releases" \
  --jq ".[] | select(.tag_name==\"$TAG\") | {tag: .tag_name, assets: [.assets[].name]}"

echo ">>> done. clients can now run: vista init"
