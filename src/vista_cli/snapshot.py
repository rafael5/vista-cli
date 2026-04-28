"""Snapshot bundle primitives — create, verify, info, install.

A snapshot bundle is a single `.tar.xz` archive containing:

    snapshot.json          # manifest (see schema below)
    code-model/*.tsv       # vista-meta code-model TSVs
    data-model/*.tsv       # vista-meta data-model TSVs
    frontmatter.db         # vista-docs SQLite

The manifest is the source of truth for what's in the bundle:

    {
      "snapshot_version": "2026.04.28",
      "schema_version": 1,
      "built_at": "...",
      "sources": {...},
      "contents": {
        "code_model": {"files": N, "rows": N, "sha256": "..."},
        "data_model": {"files": N, "rows": N, "sha256": "..."},
        "frontmatter_db": {
          "rows_documents": N, "rows_doc_routines": N,
          "rows_doc_sections": N, "fts5_included": bool,
          "sha256": "..."
        }
      },
      "min_vista_cli_version": "0.4.0"
    }

A sidecar `.sha256` file records the hash of the archive itself.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sqlite3
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vista_cli import __version__

SCHEMA_VERSION = 1
MANIFEST_NAME = "snapshot.json"
CODE_MODEL_PREFIX = "code-model"
DATA_MODEL_PREFIX = "data-model"
FRONTMATTER_DB_NAME = "frontmatter.db"


class SnapshotError(Exception):
    """Raised on any bundle-format problem (bad archive, mismatched SHA, etc.)."""


# ── Create ─────────────────────────────────────────────────────────


def create_bundle(
    *,
    out: Path,
    code_model_dir: Path,
    data_model_dir: Path,
    doc_db: Path,
    snapshot_version: str,
    sources: dict[str, str] | None = None,
    min_vista_cli_version: str = __version__,
) -> dict[str, Any]:
    """Pack the configured stores into a portable `.tar.xz` bundle.

    Returns the embedded manifest.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    code_model_dir = Path(code_model_dir)
    data_model_dir = Path(data_model_dir)
    doc_db = Path(doc_db)

    code_files = sorted(code_model_dir.glob("*.tsv")) if code_model_dir.exists() else []
    data_files = (
        sorted(p for p in data_model_dir.iterdir() if p.suffix in (".tsv", ".csv"))
        if data_model_dir.exists()
        else []
    )

    if not doc_db.exists():
        raise SnapshotError(f"frontmatter.db not found at {doc_db}")

    manifest: dict[str, Any] = {
        "snapshot_version": snapshot_version,
        "schema_version": SCHEMA_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": dict(sources or {}),
        "contents": {
            "code_model": {
                "files": len(code_files),
                "rows": _sum_tsv_rows(code_files),
                "sha256": _hash_files(code_files),
            },
            "data_model": {
                "files": len(data_files),
                "rows": _sum_tsv_rows([p for p in data_files if p.suffix == ".tsv"]),
                "sha256": _hash_files(data_files),
            },
            "frontmatter_db": _frontmatter_db_summary(doc_db),
        },
        "min_vista_cli_version": min_vista_cli_version,
    }

    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode()

    with tarfile.open(out, "w:xz", preset=6) as tar:
        info = tarfile.TarInfo(name=MANIFEST_NAME)
        info.size = len(manifest_bytes)
        info.mtime = int(datetime.now(timezone.utc).timestamp())
        tar.addfile(info, io.BytesIO(manifest_bytes))
        for src in code_files:
            tar.add(src, arcname=f"{CODE_MODEL_PREFIX}/{src.name}")
        for src in data_files:
            tar.add(src, arcname=f"{DATA_MODEL_PREFIX}/{src.name}")
        tar.add(doc_db, arcname=FRONTMATTER_DB_NAME)

    _write_sidecar_sha256(out)
    return manifest


# ── Verify ─────────────────────────────────────────────────────────


def verify_bundle(path: Path) -> dict[str, Any]:
    """Validate a bundle's structure and recompute SHA-256s vs. the manifest.

    Returns the manifest on success. Raises `SnapshotError` on any
    discrepancy.
    """
    path = Path(path)
    try:
        with tarfile.open(path, "r:xz") as tar:
            manifest = _read_manifest(tar)
            sums = _hash_archive_contents(tar)
    except (tarfile.TarError, OSError, EOFError) as e:
        raise SnapshotError(f"unreadable archive: {e}") from e

    expected = {
        "code_model": manifest["contents"]["code_model"]["sha256"],
        "data_model": manifest["contents"]["data_model"]["sha256"],
        "frontmatter_db": manifest["contents"]["frontmatter_db"]["sha256"],
    }
    for key, exp in expected.items():
        actual = sums.get(key, "")
        if actual != exp:
            raise SnapshotError(
                f"sha256 mismatch for {key}: manifest={exp!r} actual={actual!r}"
            )
    return manifest


# ── Info ───────────────────────────────────────────────────────────


def info_bundle(path: Path) -> dict[str, Any]:
    """Return the embedded manifest without extracting the data."""
    try:
        with tarfile.open(path, "r:xz") as tar:
            return _read_manifest(tar)
    except (tarfile.TarError, OSError, EOFError) as e:
        raise SnapshotError(f"unreadable archive: {e}") from e


# ── Install ────────────────────────────────────────────────────────


def install_bundle(*, bundle: Path, data_dir: Path) -> dict[str, Any]:
    """Atomically install a bundle at `data_dir`.

    The installation lands in `data_dir.new/` (extracted), then is swapped
    into place: any existing `data_dir/` is moved to `data_dir.bak/` and
    the new tree replaces it. On verification failure the existing tree
    is left untouched.
    """
    bundle = Path(bundle)
    data_dir = Path(data_dir)

    # 1. Verify (fails fast on tampered or broken bundles)
    manifest = verify_bundle(bundle)

    # 2. Stage to a sibling .new/ directory so the swap is atomic.
    staging = data_dir.parent / (data_dir.name + ".new")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        with tarfile.open(bundle, "r:xz") as tar:
            _safe_extract_all(tar, staging)
    except (tarfile.TarError, OSError) as e:
        shutil.rmtree(staging, ignore_errors=True)
        raise SnapshotError(f"failed to extract bundle: {e}") from e

    # 3. Swap: move existing → .bak/, .new/ → real path.
    backup = data_dir.parent / (data_dir.name + ".bak")
    if backup.exists():
        shutil.rmtree(backup)
    if data_dir.exists():
        data_dir.rename(backup)
    staging.rename(data_dir)
    return manifest


# ── Helpers ────────────────────────────────────────────────────────


def _hash_files(files: list[Path]) -> str:
    """SHA-256 over the concatenated file contents (in sorted order).

    A single hash for a group of files keeps the manifest tight; for
    integrity we re-hash the same way during verify. Order is fixed
    (sorted by name in `create_bundle`) so the hash is deterministic.
    """
    h = hashlib.sha256()
    for p in files:
        h.update(p.read_bytes())
    return h.hexdigest()


def _hash_streamed(stream: io.BufferedIOBase) -> str:
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(65536), b""):
        h.update(chunk)
    return h.hexdigest()


def _hash_concat_streams(streams: list[io.BufferedIOBase]) -> str:
    h = hashlib.sha256()
    for s in streams:
        while True:
            chunk = s.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _sum_tsv_rows(files: list[Path]) -> int:
    total = 0
    for p in files:
        if not p.exists():
            continue
        try:
            with p.open("rb") as f:
                total += max(0, sum(1 for _ in f) - 1)  # minus header
        except OSError:
            continue
    return total


def _frontmatter_db_summary(doc_db: Path) -> dict[str, Any]:
    h = hashlib.sha256()
    with doc_db.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    sha = h.hexdigest()

    conn = sqlite3.connect(doc_db)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        rows_documents = _safe_count(cur, "documents")
        rows_doc_routines = _safe_count(cur, "doc_routines")
        rows_doc_sections = _safe_count(cur, "doc_sections")
        fts_included = _table_exists(cur, "doc_sections_fts")
    finally:
        conn.close()

    return {
        "rows_documents": rows_documents,
        "rows_doc_routines": rows_doc_routines,
        "rows_doc_sections": rows_doc_sections,
        "fts5_included": fts_included,
        "sha256": sha,
    }


def _safe_count(cur: sqlite3.Cursor, table: str) -> int:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])
    except sqlite3.Error:
        return 0


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
        (table,),
    )
    return cur.fetchone() is not None


def _read_manifest(tar: tarfile.TarFile) -> dict[str, Any]:
    try:
        f = tar.extractfile(MANIFEST_NAME)
    except KeyError as e:
        raise SnapshotError("bundle missing snapshot.json manifest") from e
    if f is None:
        raise SnapshotError("bundle missing snapshot.json manifest")
    try:
        return json.loads(f.read().decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise SnapshotError(f"manifest unreadable: {e}") from e


def _hash_archive_contents(tar: tarfile.TarFile) -> dict[str, str]:
    """Recompute the three group hashes from the archive contents."""
    code_streams: list[bytes] = []
    data_streams: list[bytes] = []
    db_bytes: bytes | None = None

    members = sorted(tar.getmembers(), key=lambda m: m.name)
    for m in members:
        if m.name == MANIFEST_NAME:
            continue
        if not m.isreg():
            continue
        if m.name.startswith(CODE_MODEL_PREFIX + "/"):
            f = tar.extractfile(m)
            if f is not None:
                code_streams.append(f.read())
        elif m.name.startswith(DATA_MODEL_PREFIX + "/"):
            f = tar.extractfile(m)
            if f is not None:
                data_streams.append(f.read())
        elif m.name == FRONTMATTER_DB_NAME:
            f = tar.extractfile(m)
            if f is not None:
                db_bytes = f.read()

    return {
        "code_model": _hash_concat_bytes(code_streams),
        "data_model": _hash_concat_bytes(data_streams),
        "frontmatter_db": _hash_concat_bytes([db_bytes] if db_bytes else []),
    }


def _hash_concat_bytes(parts: list[bytes]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.hexdigest()


def _write_sidecar_sha256(archive: Path) -> None:
    h = hashlib.sha256()
    with archive.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    sidecar.write_text(f"{h.hexdigest()}  {archive.name}\n")


def _safe_extract_all(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract a tarfile rejecting absolute paths and `..` traversal."""
    dest = dest.resolve()
    for m in tar.getmembers():
        target = (dest / m.name).resolve()
        if not str(target).startswith(str(dest) + "/") and target != dest:
            raise SnapshotError(f"unsafe path in bundle: {m.name}")
    # Python 3.12+: pass filter='data' for the hardened extraction.
    tar.extractall(dest, filter="data")
