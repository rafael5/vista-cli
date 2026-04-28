"""Tests for the joined-cache builder + reader (stores/cache.py)."""

import sqlite3
from pathlib import Path

import pytest

from vista_cli.stores.cache import CacheStore, build

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def cache_path(tmp_path):
    return tmp_path / "joined.db"


@pytest.fixture
def built(cache_path):
    counts = build(
        cache_db=cache_path,
        code_model_dir=FIXTURES / "code-model",
        data_model_dir=FIXTURES / "data-model",
        doc_db=FIXTURES / "frontmatter.db",
    )
    return cache_path, counts


class TestBuild:
    def test_build_creates_file(self, built):
        path, _ = built
        assert path.exists()

    def test_build_returns_row_counts(self, built):
        _, counts = built
        # Four routines in fixture: PRCA45PT, PRCAACT, XUSCLEAN, XPDUTL
        assert counts["routines_mirror"] == 4
        # Three patches × 1 routine + three patches × XUSCLEAN
        assert counts["patch_routine_refs"] >= 5
        # PRCA45PT has 4 doc_routines rows; group by (routine,doc_id,tag)
        assert counts["routine_doc_refs"] >= 1
        assert counts["package_canonical"] >= 10

    def test_routines_mirror_has_full_columns(self, cache_path, built):
        conn = sqlite3.connect(cache_path)
        cur = conn.execute(
            "SELECT routine_name, line_count, in_degree FROM routines_mirror "
            "WHERE routine_name = 'PRCA45PT'"
        )
        row = cur.fetchone()
        conn.close()
        assert row is not None
        assert row[1] == 74

    def test_routine_calls_mirror_indexed_by_caller(self, cache_path, built):
        conn = sqlite3.connect(cache_path)
        cur = conn.execute(
            "SELECT COUNT(*) FROM routine_calls_mirror WHERE caller_name = ?",
            ("PRCA45PT",),
        )
        n = cur.fetchone()[0]
        conn.close()
        assert n == 5

    def test_patch_routine_refs_finds_known_patch(self, cache_path, built):
        conn = sqlite3.connect(cache_path)
        cur = conn.execute(
            "SELECT routine FROM patch_routine_refs WHERE patch_id = ?",
            ("PRCA*4.5*409",),
        )
        names = {r[0] for r in cur.fetchall()}
        conn.close()
        assert names == {"PRCA45PT"}

    def test_rebuild_overwrites(self, cache_path):
        path = cache_path
        path.write_text("garbage")
        build(
            cache_db=path,
            code_model_dir=FIXTURES / "code-model",
            data_model_dir=FIXTURES / "data-model",
            doc_db=FIXTURES / "frontmatter.db",
        )
        # File should now be a valid SQLite db
        conn = sqlite3.connect(path)
        cur = conn.execute("SELECT COUNT(*) FROM routines_mirror")
        assert cur.fetchone()[0] == 4
        conn.close()


class TestCacheStore:
    def test_meta_round_trip(self, built):
        path, _ = built
        s = CacheStore(path)
        try:
            assert s.meta("schema_version") == "1"
            assert s.meta("built_at") is not None
            assert s.meta("nope") is None
        finally:
            s.close()

    def test_routine_doc_refs(self, built):
        path, _ = built
        s = CacheStore(path)
        try:
            refs = s.routine_doc_refs("PRCA45PT")
            assert len(refs) >= 1
            assert refs[0]["routine"] == "PRCA45PT"
        finally:
            s.close()

    def test_patches_for_routine_via_cache(self, built):
        path, _ = built
        s = CacheStore(path)
        try:
            ids = s.patches_for_routine("PRCA45PT")
            assert "PRCA*4.5*409" in ids
        finally:
            s.close()

    def test_freshness_clean_after_build(self, built):
        path, _ = built
        s = CacheStore(path)
        try:
            stale, reasons = s.is_stale(
                code_model_dir=FIXTURES / "code-model",
                doc_db=FIXTURES / "frontmatter.db",
            )
            assert stale is False
            assert reasons == []
        finally:
            s.close()

    def test_freshness_detects_updated_source(self, built, tmp_path):
        path, _ = built
        # Touch a TSV — bump its mtime past the cache's recorded value
        sentinel = FIXTURES / "code-model" / "routines-comprehensive.tsv"
        old_mtime = sentinel.stat().st_mtime
        try:
            future = old_mtime + 10
            import os

            os.utime(sentinel, (future, future))
            s = CacheStore(path)
            stale, reasons = s.is_stale(
                code_model_dir=FIXTURES / "code-model",
                doc_db=FIXTURES / "frontmatter.db",
            )
            s.close()
            assert stale is True
            assert any("code-model" in r for r in reasons)
        finally:
            import os

            os.utime(sentinel, (old_mtime, old_mtime))
