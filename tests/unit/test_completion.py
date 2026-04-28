"""Function-level tests for the shell-completion callbacks.

We don't shell out to bash/zsh — Click's completion is a Python
function called per <TAB>; testing it directly is enough.
"""

from pathlib import Path

import pytest

from vista_cli.completion import (
    complete_file,
    complete_option,
    complete_package,
    complete_routine,
    complete_rpc,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture(autouse=True)
def fixture_env(monkeypatch):
    monkeypatch.setenv("VISTA_CODE_MODEL", str(FIXTURES / "code-model"))
    monkeypatch.setenv("VISTA_DATA_MODEL", str(FIXTURES / "data-model"))
    monkeypatch.setenv("VISTA_M_HOST", str(FIXTURES / "vista-m-host"))
    monkeypatch.setenv("VISTA_DOC_DB", str(FIXTURES / "frontmatter.db"))
    monkeypatch.setenv("VISTA_DOC_PUBLISH", str(FIXTURES / "publish"))
    yield


class TestRoutineCompletion:
    def test_prefix_match(self):
        out = complete_routine(None, None, "PRC")
        assert "PRCA45PT" in out
        assert "PRCAACT" in out

    def test_lowercase_input_uppercased(self):
        out = complete_routine(None, None, "prc")
        assert "PRCA45PT" in out

    def test_no_match_empty(self):
        assert complete_routine(None, None, "ZZZZ") == []

    def test_empty_returns_all(self):
        # Empty incomplete should match everything (capped)
        out = complete_routine(None, None, "")
        # Fixture has 4 routines; all should appear
        assert len(out) >= 4


class TestPackageCompletion:
    def test_directory_prefix(self):
        out = complete_package(None, None, "Acc")
        assert "Accounts Receivable" in out

    def test_ns_prefix(self):
        out = complete_package(None, None, "PRC")
        # PRCA is the namespace
        assert "PRCA" in out

    def test_lowercase_input_matches_mixed_case(self):
        out = complete_package(None, None, "acc")
        assert "Accounts Receivable" in out


class TestRpcCompletion:
    def test_does_not_raise_on_empty(self):
        # Even if no fixture RPCs, must return a list (possibly empty)
        out = complete_rpc(None, None, "")
        assert isinstance(out, list)


class TestOptionCompletion:
    def test_does_not_raise_on_empty(self):
        out = complete_option(None, None, "")
        assert isinstance(out, list)


class TestFileCompletion:
    def test_returns_list(self):
        out = complete_file(None, None, "")
        assert isinstance(out, list)

    def test_prefix_matches_numeric(self):
        # Try the leading digit of the first fixture file
        files = (FIXTURES / "data-model/files.tsv").read_text().splitlines()
        if len(files) < 2:
            pytest.skip("fixture has no files")
        first_num = files[1].split("\t")[0]
        if not first_num:
            pytest.skip("fixture file has no number")
        out = complete_file(None, None, first_num[0])
        assert any(n.startswith(first_num[0]) for n in out)


class TestCompletersAreSafe:
    def test_unreachable_data_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setenv("VISTA_CODE_MODEL", str(tmp_path / "absent"))
        monkeypatch.setenv("VISTA_DATA_MODEL", str(tmp_path / "absent"))
        monkeypatch.setenv("VISTA_DOC_DB", str(tmp_path / "absent.db"))
        monkeypatch.setenv("VISTA_CACHE_DB", str(tmp_path / "absent-cache.db"))
        # Each completer should be a no-op rather than raise
        assert complete_routine(None, None, "P") == []
        assert complete_rpc(None, None, "P") == []
        assert complete_option(None, None, "P") == []
        assert complete_file(None, None, "1") == []
        # Package may still find canonical entries even without data
        # — that's fine; it's the only one that's stateless.
        result = complete_package(None, None, "PRC")
        assert isinstance(result, list)
