"""Tests for the code-model TSV reader.

Uses tiny fixture TSVs at tests/fixtures/code-model/.
"""

from pathlib import Path

import pytest

from vista_cli.stores.code_model import CodeModelStore

FIXTURES = Path(__file__).parent.parent / "fixtures" / "code-model"


@pytest.fixture
def store():
    return CodeModelStore(FIXTURES)


class TestRoutineLookup:
    def test_known_routine_returns_row(self, store):
        row = store.routine("PRCA45PT")
        assert row is not None
        assert row["package"] == "Accounts Receivable"
        assert int(row["line_count"]) == 74
        assert int(row["in_degree"]) == 0
        assert int(row["out_degree"]) == 5

    def test_unknown_routine_returns_none(self, store):
        assert store.routine("NOPENOPE") is None


class TestCalls:
    def test_callees_from_routine(self, store):
        callees = store.callees("PRCA45PT")
        assert len(callees) == 5
        names = [c["callee_routine"] for c in callees]
        assert "XPDUTL" in names
        assert "%ZIS" in names

    def test_callees_sorted_by_ref_count(self, store):
        callees = store.callees("PRCA45PT")
        counts = [int(c["ref_count"]) for c in callees]
        assert counts == sorted(counts, reverse=True)

    def test_callers_aggregated(self, store):
        # Fixture has PRCAACT → PRCA45PT once
        callers = store.callers("PRCA45PT")
        assert len(callers) == 1
        assert callers[0]["caller_name"] == "PRCAACT"
        assert callers[0]["caller_package"] == "Accounts Receivable"

    def test_callers_for_unreferenced_routine(self, store):
        # XUSCLEAN has no callers in fixture
        assert store.callers("XUSCLEAN") == []

    def test_unknown_routine_has_no_callees(self, store):
        assert store.callees("NOPENOPE") == []


class TestGlobals:
    def test_globals_for_routine(self, store):
        globs = store.globals_for("PRCA45PT")
        assert len(globs) == 1
        assert globs[0]["global_name"] == "PRCA"
        assert int(globs[0]["ref_count"]) == 18


class TestRoutinesByPackage:
    def test_filter_by_package(self, store):
        rs = store.routines_by_package("Accounts Receivable")
        assert "PRCA45PT" in {r["routine_name"] for r in rs}

    def test_unknown_package_empty(self, store):
        assert store.routines_by_package("Nope") == []
