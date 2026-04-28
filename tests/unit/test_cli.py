"""End-to-end CLI smoke tests using Click's CliRunner against fixtures."""

import os
from pathlib import Path

from click.testing import CliRunner

from vista_cli.cli import main

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def _env_for_fixtures() -> dict[str, str]:
    return {
        "VISTA_CODE_MODEL": str(FIXTURE_DIR / "code-model"),
        "VISTA_DATA_MODEL": str(FIXTURE_DIR / "data-model"),
        "VISTA_M_HOST": str(FIXTURE_DIR / "vista-m-host"),
        "VISTA_DOC_DB": str(FIXTURE_DIR / "frontmatter.db"),
        "VISTA_DOC_PUBLISH": str(FIXTURE_DIR / "publish"),
    }


class TestDoctor:
    def test_doctor_runs(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["doctor"], env=env)
        # Doctor returns 0 if all paths exist, 1 if any are missing.
        # Fixtures exist; expect 0.
        assert result.exit_code == 0, result.output
        assert "code-model" in result.output


class TestRoutine:
    def test_routine_known_succeeds(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["routine", "PRCA45PT"], env=env)
        assert result.exit_code == 0, result.output
        assert "PRCA45PT" in result.output
        assert "Accounts Receivable" in result.output

    def test_routine_unknown_exits_nonzero(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["routine", "NOPENOPE"], env=env)
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_routine_json_format(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["routine", "PRCA45PT", "--format", "json"], env=env
        )
        assert result.exit_code == 0
        # Output should be valid JSON
        import json

        parsed = json.loads(result.output)
        assert parsed["routine_name"] == "PRCA45PT"
        assert parsed["package"] == "Accounts Receivable"


class TestWhere:
    def test_where_routine(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["where", "PRCA45PT"], env=env)
        assert result.exit_code == 0
        # Path output should contain the package directory
        assert "PRCA45PT" in result.output

    def test_where_tag_at_routine(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["where", "EN^PRCA45PT"], env=env)
        assert result.exit_code == 0


class TestVersion:
    def test_version_prints(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
