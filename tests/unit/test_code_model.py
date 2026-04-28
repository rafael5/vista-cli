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


class TestRpcs:
    def test_rpc_lookup(self, store):
        row = store.rpc("PRCA AR LIST")
        assert row is not None
        assert row["routine"] == "PRCAACT"
        assert row["tag"] == "LIST"

    def test_rpc_unknown_returns_none(self, store):
        assert store.rpc("NOPE") is None

    def test_rpcs_by_package(self, store):
        rs = store.rpcs_by_package("Accounts Receivable")
        assert {r["name"] for r in rs} == {"PRCA AR LIST", "PRCA AR DETAIL"}


class TestOptions:
    def test_option_lookup(self, store):
        row = store.option("PRCA PURGE EXEMPT BILL FILES")
        assert row is not None
        assert row["routine"] == "PRCA45PT"

    def test_options_by_package(self, store):
        rs = store.options_by_package("Kernel")
        assert {r["name"] for r in rs} == {"XU CLEAN"}


class TestGlobalReverse:
    def test_routines_using_global(self, store):
        rs = store.routines_using_global("PRCA")
        assert "PRCA45PT" in {r["routine_name"] for r in rs}


class TestPackages:
    def test_package_lookup(self, store):
        row = store.package("Accounts Receivable")
        assert row is not None
        assert int(row["routine_count"]) == 2

    def test_all_packages_returned(self, store):
        names = {r["package"] for r in store.all_packages()}
        assert {"Accounts Receivable", "Kernel"}.issubset(names)


class TestPatchesForRoutine:
    def test_extracts_canonical_ids(self, store):
        ids = store.patches_for_routine("PRCA45PT")
        assert ids == [
            "PRCA*4.5*14",
            "PRCA*4.5*79",
            "PRCA*4.5*153",
            "PRCA*4.5*302",
            "PRCA*4.5*409",
        ]

    def test_kernel_routine_uses_alpha_prefix(self, store):
        # XUSCLEAN has version 8.0 patch list **1,2,3** — namespace = "XUSCLEAN"
        # All-alpha names use the full name as namespace.
        ids = store.patches_for_routine("XUSCLEAN")
        assert ids == ["XUSCLEAN*8.0*1", "XUSCLEAN*8.0*2", "XUSCLEAN*8.0*3"]

    def test_unknown_routine_empty(self, store):
        assert store.patches_for_routine("NOPE") == []


class TestPatchScan:
    def test_routines_for_patch_finds_match(self, store):
        # Fixture: PRCA45PT line-2 has **14,79,153,302,409** at version 4.5
        rs = store.routines_for_patch("PRCA*4.5*409")
        assert {r["routine_name"] for r in rs} == {"PRCA45PT"}

    def test_routines_for_patch_unrelated_namespace(self, store):
        assert store.routines_for_patch("ABCD*1.0*1") == []

    def test_routines_for_patch_invalid_id(self, store):
        assert store.routines_for_patch("not-a-patch") == []

    def test_routines_for_patch_kernel_xu_namespace(self, store):
        # XUSCLEAN has **1,2,3** at version 8.0
        rs = store.routines_for_patch("XU*8.0*3")
        assert "XUSCLEAN" in {r["routine_name"] for r in rs}
