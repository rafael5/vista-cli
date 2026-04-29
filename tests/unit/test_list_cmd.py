"""Tests for `vista list` — flat enumeration of packages / routines /
rpcs / options / files / globals."""

import json
import os
from pathlib import Path

from click.testing import CliRunner

from vista_cli.cli import main

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _env() -> dict[str, str]:
    return {
        "VISTA_CODE_MODEL": str(FIXTURES / "code-model"),
        "VISTA_DATA_MODEL": str(FIXTURES / "data-model"),
        "VISTA_M_HOST": str(FIXTURES / "vista-m-host"),
        "VISTA_DOC_DB": str(FIXTURES / "frontmatter.db"),
        "VISTA_DOC_PUBLISH": str(FIXTURES / "publish"),
    }


def _full_env() -> dict[str, str]:
    return {**os.environ, **_env()}


class TestListPackages:
    def test_default_md_lists_packages(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "packages"], env=_full_env())
        assert result.exit_code == 0, result.output
        assert "Accounts Receivable" in result.output
        assert "Kernel" in result.output

    def test_json_returns_array_of_objects(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["list", "packages", "--format", "json"], env=_full_env()
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        names = {p["package"] for p in data}
        assert "Accounts Receivable" in names
        # Each row carries roll-up counts
        ar = next(p for p in data if p["package"] == "Accounts Receivable")
        assert ar["routines"] >= 2
        assert "rpcs" in ar
        assert "options" in ar

    def test_tsv_has_header_and_rows(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["list", "packages", "--format", "tsv"], env=_full_env()
        )
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "package\tnamespace\tapp_code\troutines\trpcs\toptions"
        assert any("Accounts Receivable" in line for line in lines[1:])

    def test_ranked_by_routine_count_desc(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["list", "packages", "--format", "json"], env=_full_env()
        )
        data = json.loads(result.output)
        counts = [p["routines"] for p in data]
        assert counts == sorted(counts, reverse=True)


class TestListRoutines:
    def test_filtered_by_package(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["list", "routines", "--pkg", "Accounts Receivable", "--format", "json"],
            env=_full_env(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        names = {r["routine_name"] for r in data}
        assert "PRCA45PT" in names

    def test_unfiltered_returns_all_routines(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["list", "routines", "--format", "json"], env=_full_env()
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        names = {r["routine_name"] for r in data}
        # Fixture has 4 routines
        assert {"PRCA45PT", "PRCAACT", "XUSCLEAN", "XPDUTL"} <= names

    def test_ranked_by_in_degree(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["list", "routines", "--format", "json"], env=_full_env()
        )
        data = json.loads(result.output)
        in_degrees = [int(r["in_degree"]) for r in data]
        assert in_degrees == sorted(in_degrees, reverse=True)

    def test_limit_caps_results(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["list", "routines", "--limit", "2", "--format", "json"],
            env=_full_env(),
        )
        data = json.loads(result.output)
        assert len(data) == 2

    def test_unknown_package_returns_empty(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["list", "routines", "--pkg", "NotARealPackage", "--format", "json"],
            env=_full_env(),
        )
        # No match → exit 0 with empty array, not an error
        assert result.exit_code == 0
        assert json.loads(result.output) == []


class TestListRpcs:
    def test_lists_rpcs_with_columns(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["list", "rpcs", "--format", "json"], env=_full_env()
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        # Fixture rpcs.tsv may have entries
        if data:
            assert "name" in data[0]
            assert "routine" in data[0]


class TestListOptions:
    def test_lists_options_with_columns(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["list", "options", "--format", "json"], env=_full_env()
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        if data:
            assert "name" in data[0]


class TestListFiles:
    def test_lists_fileman_files(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["list", "files", "--format", "json"], env=_full_env()
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        if data:
            assert "file_number" in data[0]
            assert "file_name" in data[0]


class TestListGlobals:
    def test_lists_globals_aggregated(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["list", "globals", "--format", "json"], env=_full_env()
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        if data:
            assert "global_name" in data[0]
            # Aggregate ref_count across routines
            assert "ref_count" in data[0]

    def test_globals_filtered_by_routine(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["list", "globals", "--routine", "PRCA45PT", "--format", "json"],
            env=_full_env(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        names = {g["global_name"] for g in data}
        # PRCA45PT touches ^PRCA per fixtures
        assert "PRCA" in names
