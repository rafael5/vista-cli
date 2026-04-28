"""Tests for CodeModelView — the cache-aware code-model wrapper.

The view is a transparent proxy:
- If a fresh cache is present, cached lookups (routine, callees,
  callers, globals_for, routines_using_global, routines_by_package,
  patches_for_routine, all_routines) come from the cache.
- Anything not mirrored in the cache (xindex_errors, rpcs_in_routine,
  options_in_routine, packages.tsv, etc.) falls through to the
  CodeModelStore as before.
- A stale cache is ignored — the view falls back to TSV reads to
  avoid serving wrong data.
"""

import os
from pathlib import Path

import pytest

from vista_cli.stores.cache import CacheStore, build
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.code_view import CodeModelView, make_code_view

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def cache_path(tmp_path):
    return tmp_path / "joined.db"


@pytest.fixture
def built_cache(cache_path):
    build(
        cache_db=cache_path,
        code_model_dir=FIXTURES / "code-model",
        data_model_dir=FIXTURES / "data-model",
        doc_db=FIXTURES / "frontmatter.db",
    )
    return cache_path


@pytest.fixture
def cms():
    return CodeModelStore(FIXTURES / "code-model")


class TestParityWithoutCache:
    """Without a cache, the view is a pure passthrough."""

    def test_routine_matches_cms(self, cms):
        view = CodeModelView(cms, cache=None)
        assert view.routine("PRCA45PT") == cms.routine("PRCA45PT")

    def test_callees_matches_cms(self, cms):
        view = CodeModelView(cms, cache=None)
        assert view.callees("PRCA45PT") == cms.callees("PRCA45PT")

    def test_callers_matches_cms(self, cms):
        view = CodeModelView(cms, cache=None)
        assert view.callers("XPDUTL") == cms.callers("XPDUTL")

    def test_unknown_routine_returns_none(self, cms):
        view = CodeModelView(cms, cache=None)
        assert view.routine("NOPE") is None

    def test_passthrough_for_uncached_methods(self, cms):
        view = CodeModelView(cms, cache=None)
        # xindex_errors is not mirrored in the cache — must reach cms
        assert view.xindex_errors("PRCA45PT") == cms.xindex_errors("PRCA45PT")
        assert view.rpcs_in_routine("PRCA45PT") == cms.rpcs_in_routine("PRCA45PT")


class TestParityWithCache:
    """With a fresh cache, results agree with the TSV-only path."""

    def test_routine_parity(self, cms, built_cache):
        cache = CacheStore(built_cache)
        try:
            view = CodeModelView(cms, cache=cache)
            cached = view.routine("PRCA45PT")
            direct = cms.routine("PRCA45PT")
            assert cached is not None and direct is not None
            # Same key fields agree
            for k in ("routine_name", "package", "line_count", "in_degree"):
                assert str(cached.get(k, "")) == str(direct.get(k, ""))
        finally:
            cache.close()

    def test_callees_parity(self, cms, built_cache):
        cache = CacheStore(built_cache)
        try:
            view = CodeModelView(cms, cache=cache)
            cached = view.callees("PRCA45PT")
            direct = cms.callees("PRCA45PT")
            assert len(cached) == len(direct)
            cached_set = {(c["callee_routine"], c["callee_tag"]) for c in cached}
            direct_set = {(c["callee_routine"], c["callee_tag"]) for c in direct}
            assert cached_set == direct_set
        finally:
            cache.close()

    def test_callers_parity(self, cms, built_cache):
        cache = CacheStore(built_cache)
        try:
            view = CodeModelView(cms, cache=cache)
            cached_set = {c["caller_name"] for c in view.callers("XPDUTL")}
            direct_set = {c["caller_name"] for c in cms.callers("XPDUTL")}
            assert cached_set == direct_set
        finally:
            cache.close()

    def test_globals_for_parity(self, cms, built_cache):
        cache = CacheStore(built_cache)
        try:
            view = CodeModelView(cms, cache=cache)
            cached = {g["global_name"] for g in view.globals_for("PRCA45PT")}
            direct = {g["global_name"] for g in cms.globals_for("PRCA45PT")}
            assert cached == direct
        finally:
            cache.close()

    def test_routines_using_global_parity(self, cms, built_cache):
        cache = CacheStore(built_cache)
        try:
            view = CodeModelView(cms, cache=cache)
            cached = {r["routine_name"] for r in view.routines_using_global("PRCA")}
            direct = {r["routine_name"] for r in cms.routines_using_global("PRCA")}
            assert cached == direct
        finally:
            cache.close()

    def test_routines_by_package_parity(self, cms, built_cache):
        cache = CacheStore(built_cache)
        try:
            view = CodeModelView(cms, cache=cache)
            cached = {
                r["routine_name"]
                for r in view.routines_by_package("Accounts Receivable")
            }
            direct = {
                r["routine_name"]
                for r in cms.routines_by_package("Accounts Receivable")
            }
            assert cached == direct
        finally:
            cache.close()

    def test_patches_for_routine_parity(self, cms, built_cache):
        cache = CacheStore(built_cache)
        try:
            view = CodeModelView(cms, cache=cache)
            assert (
                set(view.patches_for_routine("PRCA45PT"))
                == set(cms.patches_for_routine("PRCA45PT"))
            )
        finally:
            cache.close()

    def test_all_routines_parity(self, cms, built_cache):
        cache = CacheStore(built_cache)
        try:
            view = CodeModelView(cms, cache=cache)
            cached = {r["routine_name"] for r in view.all_routines()}
            direct = {r["routine_name"] for r in cms.all_routines()}
            assert cached == direct
        finally:
            cache.close()


class TestStaleCacheIgnored:
    """A stale cache must not be served — fall back to TSV reads."""

    def test_stale_cache_falls_back(self, cms, built_cache):
        # Bump a TSV's mtime so the cache reports stale.
        sentinel = FIXTURES / "code-model" / "routines-comprehensive.tsv"
        old = sentinel.stat().st_mtime
        try:
            os.utime(sentinel, (old + 100, old + 100))
            view = make_code_view(
                code_model_dir=FIXTURES / "code-model",
                cache_db=built_cache,
                doc_db=FIXTURES / "frontmatter.db",
            )
            # Still works — falls back to TSVs.
            assert view.routine("PRCA45PT") is not None
            # And the inner view did not retain a cache.
            assert view.cache is None
        finally:
            os.utime(sentinel, (old, old))

    def test_no_cache_db_returns_view_without_cache(self, tmp_path):
        view = make_code_view(
            code_model_dir=FIXTURES / "code-model",
            cache_db=tmp_path / "absent.db",
            doc_db=FIXTURES / "frontmatter.db",
        )
        assert view.cache is None
        assert view.routine("PRCA45PT") is not None

    def test_allow_cache_false_returns_view_without_cache(self, built_cache):
        view = make_code_view(
            code_model_dir=FIXTURES / "code-model",
            cache_db=built_cache,
            doc_db=FIXTURES / "frontmatter.db",
            allow_cache=False,
        )
        assert view.cache is None
        assert view.routine("PRCA45PT") is not None


class TestCacheStoreCodeModelMethods:
    """The cache exposes routine-level lookups directly."""

    def test_routine_returns_dict(self, built_cache):
        cache = CacheStore(built_cache)
        try:
            row = cache.routine("PRCA45PT")
            assert row is not None
            assert row["routine_name"] == "PRCA45PT"
            assert row["package"] == "Accounts Receivable"
            assert int(row["line_count"]) == 74
        finally:
            cache.close()

    def test_routine_unknown_returns_none(self, built_cache):
        cache = CacheStore(built_cache)
        try:
            assert cache.routine("NOPE") is None
        finally:
            cache.close()

    def test_callees(self, built_cache):
        cache = CacheStore(built_cache)
        try:
            rows = cache.callees("PRCA45PT")
            assert len(rows) == 5
            # ref_count desc
            counts = [int(r["ref_count"]) for r in rows]
            assert counts == sorted(counts, reverse=True)
        finally:
            cache.close()

    def test_callers(self, built_cache):
        cache = CacheStore(built_cache)
        try:
            rows = cache.callers("XPDUTL")
            assert any(r["caller_name"] == "PRCA45PT" for r in rows)
        finally:
            cache.close()

    def test_globals_for(self, built_cache):
        cache = CacheStore(built_cache)
        try:
            rows = cache.globals_for("PRCA45PT")
            assert any(r["global_name"] == "PRCA" for r in rows)
        finally:
            cache.close()

    def test_routines_using_global(self, built_cache):
        cache = CacheStore(built_cache)
        try:
            rows = cache.routines_using_global("PRCA")
            assert any(r["routine_name"] == "PRCA45PT" for r in rows)
        finally:
            cache.close()

    def test_routines_by_package(self, built_cache):
        cache = CacheStore(built_cache)
        try:
            rows = cache.routines_by_package("Accounts Receivable")
            names = {r["routine_name"] for r in rows}
            assert "PRCA45PT" in names
        finally:
            cache.close()

    def test_routines_for_patch(self, built_cache):
        cache = CacheStore(built_cache)
        try:
            rows = cache.routines_for_patch("PRCA*4.5*409")
            names = {r["routine_name"] for r in rows}
            assert "PRCA45PT" in names
        finally:
            cache.close()

    def test_all_routines(self, built_cache):
        cache = CacheStore(built_cache)
        try:
            rows = cache.all_routines()
            names = {r["routine_name"] for r in rows}
            assert "PRCA45PT" in names
            assert len(names) == 4  # PRCA45PT, PRCAACT, XUSCLEAN, XPDUTL
        finally:
            cache.close()
