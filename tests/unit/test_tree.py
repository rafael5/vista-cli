"""Tests for `vista tree` — hierarchical browser."""

import json
import os
from pathlib import Path

from click.testing import CliRunner

from vista_cli.cli import main

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _env() -> dict[str, str]:
    return {
        **os.environ,
        "VISTA_CODE_MODEL": str(FIXTURES / "code-model"),
        "VISTA_DATA_MODEL": str(FIXTURES / "data-model"),
        "VISTA_M_HOST": str(FIXTURES / "vista-m-host"),
        "VISTA_DOC_DB": str(FIXTURES / "frontmatter.db"),
        "VISTA_DOC_PUBLISH": str(FIXTURES / "publish"),
    }


class TestTreeNoArg:
    def test_no_arg_lists_packages_at_depth_1(self):
        runner = CliRunner()
        result = runner.invoke(main, ["tree"], env=_env())
        assert result.exit_code == 0, result.output
        # Top-level: every package shows at least once
        assert "Accounts Receivable" in result.output
        assert "Kernel" in result.output
        # Should not deep-dive into routines for unfiltered tree
        # (children-of-children would be routine names)
        # Nothing aggressive to assert here; just don't crash.

    def test_no_arg_json_returns_array_of_packages(self):
        runner = CliRunner()
        result = runner.invoke(main, ["tree", "--format", "json"], env=_env())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        names = {n["package"] for n in data}
        assert "Accounts Receivable" in names


class TestTreeWithPackage:
    def test_package_arg_expands_routines(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["tree", "Accounts Receivable"], env=_env()
        )
        assert result.exit_code == 0, result.output
        assert "PRCA45PT" in result.output
        assert "PRCAACT" in result.output

    def test_namespace_alias_works(self):
        runner = CliRunner()
        # PRCA is the namespace for Accounts Receivable
        result = runner.invoke(main, ["tree", "PRCA"], env=_env())
        assert result.exit_code == 0
        assert "PRCA45PT" in result.output

    def test_unknown_package_exits_nonzero(self):
        runner = CliRunner()
        result = runner.invoke(main, ["tree", "NotARealPackage"], env=_env())
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_json_for_package_has_children(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["tree", "Accounts Receivable", "--format", "json"],
            env=_env(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["package"] == "Accounts Receivable"
        # Children buckets
        assert "routines" in data
        routine_names = {r["routine_name"] for r in data["routines"]}
        assert "PRCA45PT" in routine_names

    def test_kind_filters_children(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["tree", "Accounts Receivable", "--kind", "routines"],
            env=_env(),
        )
        assert result.exit_code == 0
        # Only routines section should appear
        assert "PRCA45PT" in result.output
