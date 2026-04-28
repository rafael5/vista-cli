"""Tests for cross-store joins (stores/joined.py)."""

from pathlib import Path

import pytest

from vista_cli.canonical import resolve_package
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.data_model import DataModelStore
from vista_cli.stores.doc_model import DocModelStore
from vista_cli.stores.joined import (
    file_for_global,
    neighbors,
    package_coverage,
    routine_links,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def cms():
    return CodeModelStore(FIXTURES / "code-model")


@pytest.fixture
def dms():
    return DocModelStore(FIXTURES / "frontmatter.db")


@pytest.fixture
def dms_data():
    return DataModelStore(FIXTURES / "data-model")


class TestRoutineLinks:
    def test_basic_routine(self, cms, dms, dms_data):
        info = routine_links(cms, dms, dms_data, "PRCA45PT")
        assert info is not None
        assert info["routine"] == "PRCA45PT"
        assert info["package"]["directory"] == "Accounts Receivable"
        assert info["package"]["namespace"] == "PRCA"
        assert info["patches"] == [
            "PRCA*4.5*14",
            "PRCA*4.5*79",
            "PRCA*4.5*153",
            "PRCA*4.5*302",
            "PRCA*4.5*409",
        ]

    def test_resolves_files_via_globals(self, cms, dms, dms_data):
        info = routine_links(cms, dms, dms_data, "PRCA45PT")
        assert info is not None
        # ^PRCA(430) → file 430 ACCOUNTS RECEIVABLE
        assert any(f["file_number"] == "430" for f in info["files"])

    def test_unknown_routine_returns_none(self, cms, dms, dms_data):
        assert routine_links(cms, dms, dms_data, "NOPE") is None

    def test_missing_doc_store_falls_back(self, cms, dms_data):
        info = routine_links(cms, None, dms_data, "PRCA45PT")
        assert info is not None
        assert info["docs"] == []


class TestFileForGlobal:
    def test_resolves_subscript_root(self, dms_data):
        f = file_for_global(dms_data, "PRCA")
        assert f is not None
        assert f["file_number"] == "430"

    def test_resolves_caret_only_root(self, dms_data):
        f = file_for_global(dms_data, "DPT")
        assert f is not None
        assert f["file_number"] == "2"

    def test_unknown_returns_none(self, dms_data):
        assert file_for_global(dms_data, "NOTAFILE") is None


class TestPackageCoverage:
    def test_coverage_for_ar(self, cms, dms):
        pkg_id = resolve_package("Accounts Receivable")
        assert pkg_id is not None
        cov = package_coverage(cms, dms, pkg_id)
        # Both fixture routines in AR are PRCA45PT (documented) +
        # PRCAACT (not documented in fixtures)
        assert cov["routines"]["total"] == 2
        assert cov["routines"]["documented"] == 1
        # PRCAACT ranked first by in-degree (8 > 0)
        names = [r["routine_name"] for r in cov["routines"]["undocumented"]]
        assert names == ["PRCAACT"]

    def test_coverage_rpcs_counted(self, cms, dms):
        pkg_id = resolve_package("Accounts Receivable")
        cov = package_coverage(cms, dms, pkg_id)
        # Two PRCA RPCs in fixture; PRCA AR LIST has docs, PRCA AR DETAIL doesn't
        assert cov["rpcs"]["total"] == 2
        assert cov["rpcs"]["documented"] == 1


class TestNeighbors:
    def test_callees_depth_1(self, cms, dms_data):
        info = neighbors(cms, dms_data, "PRCA45PT", depth=1, top_n=10)
        names = {c["callee_routine"] for c in info["callees"]}
        assert "XPDUTL" in names

    def test_siblings_share_callees(self, cms, dms_data):
        # PRCAACT shares no fixture callees with PRCA45PT (different
        # callee rows), but globals overlap on ^PRCA
        info = neighbors(cms, dms_data, "PRCA45PT", depth=1, top_n=10)
        # same_data routines: PRCAACT touches ^PRCA
        same = {r["routine_name"] for r in info["same_data"]}
        assert "PRCAACT" in same

    def test_unknown_routine_returns_empty_callees(self, cms, dms_data):
        info = neighbors(cms, dms_data, "NOPE", depth=1, top_n=10)
        assert info["callees"] == []
        assert info["package"] == ""
