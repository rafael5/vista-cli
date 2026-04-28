"""Tests for the snapshot bundle primitives (create / verify / info / install).

Bundles are tar.xz archives with a `snapshot.json` manifest at the
root, plus mirrors of `code-model/`, `data-model/`, and
`frontmatter.db`. Tests use the existing fixtures as source data.
"""

import hashlib
import json
import sqlite3
import tarfile
from pathlib import Path

import pytest

from vista_cli.snapshot import (
    SCHEMA_VERSION,
    SnapshotError,
    create_bundle,
    info_bundle,
    install_bundle,
    verify_bundle,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def bundle_path(tmp_path):
    return tmp_path / "vista-snapshot-test.tar.xz"


@pytest.fixture
def built_bundle(tmp_path, bundle_path):
    create_bundle(
        out=bundle_path,
        code_model_dir=FIXTURES / "code-model",
        data_model_dir=FIXTURES / "data-model",
        doc_db=FIXTURES / "frontmatter.db",
        snapshot_version="2026.04.28",
        sources={
            "vista_meta_commit": "abc1234",
            "vista_docs_commit": "def5678",
            "vista_m_version": "test-fixture",
        },
    )
    return bundle_path


class TestCreateBundle:
    def test_creates_archive(self, built_bundle):
        assert built_bundle.exists()
        assert built_bundle.suffix == ".xz"

    def test_archive_contains_manifest_at_root(self, built_bundle):
        with tarfile.open(built_bundle, "r:xz") as tar:
            names = tar.getnames()
        assert "snapshot.json" in names

    def test_archive_contains_code_model(self, built_bundle):
        with tarfile.open(built_bundle, "r:xz") as tar:
            names = set(tar.getnames())
        assert any(n.startswith("code-model/") and n.endswith(".tsv") for n in names)

    def test_archive_contains_data_model(self, built_bundle):
        with tarfile.open(built_bundle, "r:xz") as tar:
            names = set(tar.getnames())
        assert any(n.startswith("data-model/") and n.endswith(".tsv") for n in names)

    def test_archive_contains_frontmatter_db(self, built_bundle):
        with tarfile.open(built_bundle, "r:xz") as tar:
            names = set(tar.getnames())
        assert "frontmatter.db" in names

    def test_manifest_has_required_fields(self, built_bundle):
        with tarfile.open(built_bundle, "r:xz") as tar:
            f = tar.extractfile("snapshot.json")
            assert f is not None
            manifest = json.loads(f.read().decode())
        assert manifest["snapshot_version"] == "2026.04.28"
        assert manifest["schema_version"] == SCHEMA_VERSION
        assert "built_at" in manifest
        assert manifest["sources"]["vista_meta_commit"] == "abc1234"
        assert "code_model" in manifest["contents"]
        assert "data_model" in manifest["contents"]
        assert "frontmatter_db" in manifest["contents"]

    def test_manifest_records_sha256s(self, built_bundle):
        with tarfile.open(built_bundle, "r:xz") as tar:
            f = tar.extractfile("snapshot.json")
            assert f is not None
            manifest = json.loads(f.read().decode())
        assert len(manifest["contents"]["code_model"]["sha256"]) == 64
        assert len(manifest["contents"]["data_model"]["sha256"]) == 64
        assert len(manifest["contents"]["frontmatter_db"]["sha256"]) == 64

    def test_manifest_records_row_counts(self, built_bundle):
        with tarfile.open(built_bundle, "r:xz") as tar:
            f = tar.extractfile("snapshot.json")
            assert f is not None
            manifest = json.loads(f.read().decode())
        assert manifest["contents"]["code_model"]["files"] >= 1
        assert manifest["contents"]["frontmatter_db"]["rows_documents"] >= 1

    def test_sha256_sidecar_written(self, built_bundle):
        sidecar = built_bundle.with_suffix(built_bundle.suffix + ".sha256")
        assert sidecar.exists()
        text = sidecar.read_text()
        assert len(text.split()[0]) == 64


class TestVerifyBundle:
    def test_verify_clean_bundle(self, built_bundle):
        manifest = verify_bundle(built_bundle)
        assert manifest["snapshot_version"] == "2026.04.28"

    def test_verify_rejects_truncated_archive(self, built_bundle):
        # Truncate to break the xz stream.
        size = built_bundle.stat().st_size
        with open(built_bundle, "rb+") as f:
            f.truncate(size // 2)
        with pytest.raises(SnapshotError):
            verify_bundle(built_bundle)

    def test_verify_rejects_missing_manifest(self, tmp_path):
        bad = tmp_path / "no-manifest.tar.xz"
        with tarfile.open(bad, "w:xz") as tar:
            payload = tmp_path / "junk"
            payload.write_text("hello")
            tar.add(payload, arcname="junk")
        with pytest.raises(SnapshotError, match="manifest"):
            verify_bundle(bad)

    def test_verify_rejects_sha256_mismatch(self, built_bundle, tmp_path):
        # Repack with a corrupted manifest (pretends to know hashes that
        # don't match the embedded contents).
        with tarfile.open(built_bundle, "r:xz") as tar:
            f = tar.extractfile("snapshot.json")
            assert f is not None
            manifest = json.loads(f.read().decode())
        manifest["contents"]["frontmatter_db"]["sha256"] = "0" * 64
        rebuilt = tmp_path / "tampered.tar.xz"
        with tarfile.open(built_bundle, "r:xz") as src, tarfile.open(
            rebuilt, "w:xz"
        ) as dst:
            for member in src.getmembers():
                if member.name == "snapshot.json":
                    new_bytes = json.dumps(manifest).encode()
                    info = tarfile.TarInfo(name="snapshot.json")
                    info.size = len(new_bytes)
                    import io

                    dst.addfile(info, io.BytesIO(new_bytes))
                else:
                    extracted = src.extractfile(member)
                    dst.addfile(member, extracted)
        with pytest.raises(SnapshotError, match="sha256"):
            verify_bundle(rebuilt)


class TestInfoBundle:
    def test_info_returns_manifest_without_extracting_data(
        self, built_bundle, tmp_path
    ):
        before = list(tmp_path.iterdir())
        manifest = info_bundle(built_bundle)
        after = list(tmp_path.iterdir())
        assert before == after  # nothing extracted to tmp_path
        assert manifest["snapshot_version"] == "2026.04.28"


class TestInstallBundle:
    def test_install_lays_out_files(self, built_bundle, tmp_path):
        target = tmp_path / "install"
        manifest = install_bundle(bundle=built_bundle, data_dir=target)
        assert (target / "snapshot.json").exists()
        assert (target / "code-model").is_dir()
        assert (target / "data-model").is_dir()
        assert (target / "frontmatter.db").exists()
        assert manifest["snapshot_version"] == "2026.04.28"

    def test_install_idempotent(self, built_bundle, tmp_path):
        target = tmp_path / "install"
        install_bundle(bundle=built_bundle, data_dir=target)
        install_bundle(bundle=built_bundle, data_dir=target)
        # Re-install should still leave a valid layout
        assert (target / "snapshot.json").exists()

    def test_install_atomic_on_swap(self, built_bundle, tmp_path):
        target = tmp_path / "install"
        # First install
        install_bundle(bundle=built_bundle, data_dir=target)
        first_db = (target / "frontmatter.db").read_bytes()
        # Second install — old contents are pushed to .bak/
        install_bundle(bundle=built_bundle, data_dir=target)
        bak = target.parent / (target.name + ".bak")
        assert bak.exists()
        assert (bak / "frontmatter.db").read_bytes() == first_db

    def test_installed_db_is_readable(self, built_bundle, tmp_path):
        target = tmp_path / "install"
        install_bundle(bundle=built_bundle, data_dir=target)
        # Confirm it's a valid SQLite file
        conn = sqlite3.connect(target / "frontmatter.db")
        try:
            cur = conn.execute("SELECT COUNT(*) FROM documents")
            assert cur.fetchone()[0] > 0
        finally:
            conn.close()

    def test_install_rejects_corrupt_bundle(self, tmp_path):
        bad = tmp_path / "bad.tar.xz"
        bad.write_bytes(b"not an archive")
        with pytest.raises(SnapshotError):
            install_bundle(bundle=bad, data_dir=tmp_path / "x")


class TestSidecarHash:
    def test_sidecar_hash_matches_archive(self, built_bundle):
        sidecar = built_bundle.with_suffix(built_bundle.suffix + ".sha256")
        recorded = sidecar.read_text().split()[0]
        h = hashlib.sha256()
        h.update(built_bundle.read_bytes())
        assert recorded == h.hexdigest()
