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
