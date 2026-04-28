"""Tests for the vista-docs SQLite reader.

Uses a tiny fixture SQLite at tests/fixtures/frontmatter.db that
mirrors the production schema with 2-3 representative documents.
"""

from pathlib import Path

import pytest

from vista_cli.stores.doc_model import DocModelStore

FIXTURE_DB = Path(__file__).parent.parent / "fixtures" / "frontmatter.db"


@pytest.fixture
def store():
    return DocModelStore(FIXTURE_DB)


class TestDocsByRoutine:
    def test_known_routine_returns_docs(self, store):
        docs = store.docs_by_routine("PRCA45PT")
        assert len(docs) >= 1
        # Each result includes title, doc_type, app_code, rel_path
        first = docs[0]
        assert "title" in first
        assert "doc_type" in first

    def test_unknown_routine_returns_empty(self, store):
        assert store.docs_by_routine("NOPENOPE") == []


class TestDocsByPackage:
    def test_filter_by_app_code(self, store):
        docs = store.docs_by_app_code("PRCA")
        assert len(docs) >= 1
        assert all(d["app_code"] == "PRCA" for d in docs)


class TestSectionLookup:
    def test_sections_mentioning_routine(self, store):
        sections = store.sections_mentioning_routine("PRCA45PT")
        # Each section has heading + doc context
        if (
            sections
        ):  # may be empty for routines only in doc_routines but not in section bodies
            s = sections[0]
            assert "heading" in s
            assert "doc_id" in s


class TestDocsByEntity:
    def test_docs_by_rpc(self, store):
        docs = store.docs_by_rpc("PRCA AR LIST")
        assert len(docs) >= 1
        assert all(d["app_code"] == "PRCA" for d in docs)

    def test_docs_by_option(self, store):
        docs = store.docs_by_option("PRCA PURGE EXEMPT BILL FILES")
        assert len(docs) >= 1

    def test_docs_by_global(self, store):
        docs = store.docs_by_global("PRCA")
        assert len(docs) >= 1

    def test_docs_by_file(self, store):
        docs = store.docs_by_file("430")
        # Three docs reference file 430 in fixture; latest filter returns 2
        assert len(docs) == 2

    def test_docs_by_file_all_versions(self, store):
        docs = store.docs_by_file("430", latest_only=False)
        assert len(docs) == 3

    def test_docs_by_patch(self, store):
        docs = store.docs_by_patch("PRCA*4.5*341")
        assert len(docs) == 1
        assert docs[0]["doc_type"] == "IG"


class TestSearchSections:
    def test_search_finds_section(self, store):
        hits = store.search_sections("purge")
        assert len(hits) >= 1
        # snippet should contain bracket markers around the matched term
        assert any("[" in h["snippet"] and "]" in h["snippet"] for h in hits)

    def test_search_filters_by_app(self, store):
        hits = store.search_sections("purge", app_code="PRCA")
        assert len(hits) >= 1
        assert all(h["app_code"] == "PRCA" for h in hits)

    def test_search_no_hits(self, store):
        assert store.search_sections("zzzzznotaword") == []

    def test_search_respects_latest_only(self, store):
        # Doc 2 is non-latest. "installing" appears only in its body,
        # so latest-only should drop it; all-versions should keep it.
        hits_latest = store.search_sections("installing")
        assert all(h["is_latest"] == 1 for h in hits_latest)
        hits_all = store.search_sections("installing", latest_only=False)
        assert any(h["is_latest"] == 0 for h in hits_all)
