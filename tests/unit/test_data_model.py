"""Tests for the data-model TSV reader (files.tsv, piks.tsv)."""

from pathlib import Path

import pytest

from vista_cli.stores.data_model import DataModelStore

FIXTURES = Path(__file__).parent.parent / "fixtures" / "data-model"


@pytest.fixture
def store():
    return DataModelStore(FIXTURES)


class TestFileLookup:
    def test_known_file_returns_row(self, store):
        row = store.file("430")
        assert row is not None
        assert row["file_name"] == "ACCOUNTS RECEIVABLE"
        assert row["global_root"] == "^PRCA(430)"
        assert row["piks"] == "K"

    def test_known_file_integer_input(self, store):
        # Caller may pass an int-like value
        assert store.file(2) is not None  # type: ignore[arg-type]

    def test_unknown_file_returns_none(self, store):
        assert store.file("99999") is None

    def test_all_files_returned(self, store):
        nums = {r["file_number"] for r in store.all_files()}
        assert {"2", "4", "430"}.issubset(nums)


class TestFilesByGlobal:
    def test_filter_by_global_root(self, store):
        rs = store.files_by_global_root("^DPT")
        assert len(rs) == 1
        assert rs[0]["file_number"] == "2"


class TestPiks:
    def test_piks_for_known_file(self, store):
        row = store.piks("2")
        assert row is not None
        assert row["piks"] == "P"

    def test_piks_unknown_file(self, store):
        assert store.piks("99999") is None
