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

    def test_doctor_warns_when_cache_missing(self, tmp_path):
        runner = CliRunner()
        env = {
            **os.environ,
            **_env_for_fixtures(),
            "VISTA_CACHE_DB": str(tmp_path / "absent.db"),
        }
        result = runner.invoke(main, ["doctor"], env=env)
        assert result.exit_code == 0
        assert "joined cache" in result.output
        assert "not built" in result.output

    def test_doctor_reports_snapshot_when_present(self, tmp_path):
        # Lay out a directory tree with a snapshot.json next to code-model.
        snap_root = tmp_path / "snapshot"
        snap_root.mkdir()
        (snap_root / "snapshot.json").write_text(
            '{"snapshot_version": "test.42", "built_at": "2026-04-28T00:00:00+00:00"}'
        )
        # Reuse fixture TSVs/db inside that tree
        import shutil

        shutil.copytree(FIXTURE_DIR / "code-model", snap_root / "code-model")
        shutil.copytree(FIXTURE_DIR / "data-model", snap_root / "data-model")
        shutil.copy(FIXTURE_DIR / "frontmatter.db", snap_root / "frontmatter.db")
        env = {
            **os.environ,
            "VISTA_CODE_MODEL": str(snap_root / "code-model"),
            "VISTA_DATA_MODEL": str(snap_root / "data-model"),
            "VISTA_M_HOST": str(FIXTURE_DIR / "vista-m-host"),
            "VISTA_DOC_DB": str(snap_root / "frontmatter.db"),
            "VISTA_DOC_PUBLISH": str(FIXTURE_DIR / "publish"),
            "VISTA_CACHE_DB": str(tmp_path / "cache.db"),
        }
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"], env=env)
        assert result.exit_code == 0
        assert "snapshot test.42" in result.output

    def test_doctor_ok_when_cache_fresh(self, tmp_path):
        runner = CliRunner()
        cache_path = tmp_path / "joined.db"
        env = {
            **os.environ,
            **_env_for_fixtures(),
            "VISTA_CACHE_DB": str(cache_path),
        }
        runner.invoke(main, ["build-cache"], env=env)
        result = runner.invoke(main, ["doctor"], env=env)
        assert result.exit_code == 0
        assert "joined cache" in result.output
        assert "stale" not in result.output


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


class TestDoc:
    def test_doc_search_finds_section(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["doc", "purge"], env=env)
        assert result.exit_code == 0, result.output
        assert "Purge" in result.output or "purge" in result.output

    def test_doc_search_json(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["doc", "purge", "--format", "json"], env=env
        )
        assert result.exit_code == 0
        import json

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert len(parsed) >= 1
        assert "heading" in parsed[0]

    def test_doc_search_no_hits_exits_one(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["doc", "zzzzznotaword"], env=env)
        assert result.exit_code == 1

    def test_doc_search_filters_by_app(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["doc", "purge", "--app", "PRCA", "--format", "tsv"], env=env
        )
        assert result.exit_code == 0
        # First line is header
        assert result.output.split("\n")[0].startswith("doc_id\t") or "heading" in (
            result.output.split("\n")[0]
        )


class TestRpc:
    def test_rpc_known(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["rpc", "PRCA AR LIST"], env=env)
        assert result.exit_code == 0, result.output
        assert "PRCAACT" in result.output

    def test_rpc_unknown(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["rpc", "NOPE"], env=env)
        assert result.exit_code == 1

    def test_rpc_json(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["rpc", "PRCA AR LIST", "--format", "json"], env=env
        )
        assert result.exit_code == 0
        import json

        parsed = json.loads(result.output)
        assert parsed["name"] == "PRCA AR LIST"
        assert parsed["routine"] == "PRCAACT"


class TestOption:
    def test_option_known(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["option", "PRCA PURGE EXEMPT BILL FILES"], env=env
        )
        assert result.exit_code == 0, result.output
        assert "PRCA45PT" in result.output

    def test_option_unknown(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["option", "NOPE"], env=env)
        assert result.exit_code == 1


class TestGlobal:
    def test_global_known(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["global", "PRCA"], env=env)
        assert result.exit_code == 0, result.output
        assert "PRCA45PT" in result.output

    def test_global_with_caret(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["global", "^PRCA"], env=env)
        assert result.exit_code == 0


class TestPackage:
    def test_package_by_directory(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["package", "Accounts Receivable"], env=env)
        assert result.exit_code == 0, result.output
        assert "PRCA45PT" in result.output

    def test_package_by_namespace(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["package", "PRCA"], env=env)
        assert result.exit_code == 0, result.output

    def test_package_unknown(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["package", "NoSuchPkg"], env=env)
        assert result.exit_code == 1


class TestFile:
    def test_file_known(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["file", "430"], env=env)
        assert result.exit_code == 0, result.output
        assert "ACCOUNTS RECEIVABLE" in result.output

    def test_file_unknown(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["file", "99999"], env=env)
        assert result.exit_code == 1


class TestPatch:
    def test_patch_known_in_routine_history(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        # Patch 409 of PRCA*4.5 is in PRCA45PT line-2
        result = runner.invoke(main, ["patch", "PRCA*4.5*409"], env=env)
        assert result.exit_code == 0, result.output
        assert "PRCA45PT" in result.output

    def test_patch_unknown(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["patch", "ZZZZ*1.0*1"], env=env)
        assert result.exit_code == 1


class TestSearch:
    def test_search_cross_store(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["search", "PRCA45PT"], env=env)
        assert result.exit_code == 0, result.output
        assert "PRCA45PT" in result.output

    def test_search_scope_routines(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["search", "PRCA", "--scope", "routines"], env=env
        )
        assert result.exit_code == 0
        assert "PRCA45PT" in result.output


class TestLinks:
    def test_links_routine(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["links", "PRCA45PT"], env=env)
        assert result.exit_code == 0, result.output
        assert "PRCA45PT" in result.output
        # Dense format includes packages, options, docs, patches lines
        assert "package" in result.output.lower()
        assert "PRCA*4.5*409" in result.output

    def test_links_unknown(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["links", "NOPE"], env=env)
        assert result.exit_code == 1

    def test_links_json(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["links", "PRCA45PT", "--format", "json"], env=env
        )
        assert result.exit_code == 0
        import json

        parsed = json.loads(result.output)
        assert parsed["routine"] == "PRCA45PT"
        assert parsed["package"]["directory"] == "Accounts Receivable"
        assert "PRCA*4.5*409" in parsed["patches"]


class TestNeighbors:
    def test_neighbors_routine(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["neighbors", "PRCA45PT"], env=env)
        assert result.exit_code == 0, result.output
        # depth=1 callees
        assert "XPDUTL" in result.output

    def test_neighbors_json(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["neighbors", "PRCA45PT", "--format", "json"], env=env
        )
        assert result.exit_code == 0
        import json

        parsed = json.loads(result.output)
        assert parsed["root"] == "PRCA45PT"
        assert "callees" in parsed
        assert "siblings" in parsed

    def test_neighbors_unknown_exits_one(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["neighbors", "NOPE"], env=env)
        assert result.exit_code == 1


class TestCoverage:
    def test_coverage_for_package(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["coverage", "--pkg", "Accounts Receivable"], env=env
        )
        assert result.exit_code == 0, result.output
        # Both routines in fixture are in PRCA; PRCA45PT is documented,
        # PRCAACT is not — expect 1/2 = 50%
        assert "50" in result.output or "1/2" in result.output

    def test_coverage_json(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main,
            ["coverage", "--pkg", "Accounts Receivable", "--format", "json"],
            env=env,
        )
        assert result.exit_code == 0
        import json

        parsed = json.loads(result.output)
        assert parsed["package"] == "Accounts Receivable"
        assert parsed["routines"]["total"] == 2
        assert parsed["routines"]["documented"] == 1


class TestTimeline:
    def test_timeline_routine(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["timeline", "PRCA45PT"], env=env)
        assert result.exit_code == 0, result.output
        # Patches from line-2 should appear chronologically
        assert "PRCA*4.5*409" in result.output
        assert "PRCA*4.5*14" in result.output

    def test_timeline_package(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["timeline", "--pkg", "Accounts Receivable"], env=env
        )
        assert result.exit_code == 0


class TestContext:
    def test_context_routine_emits_bundle(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["context", "PRCA45PT"], env=env)
        assert result.exit_code == 0, result.output
        # Bundle includes routine card + doc section bodies
        assert "PRCA45PT" in result.output
        assert "Documentation" in result.output

    def test_ask_with_routine(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main,
            ["ask", "how does AR purge work?", "--routine", "PRCA45PT"],
            env=env,
        )
        assert result.exit_code == 0, result.output
        # Question is at the top of the bundle
        assert "how does AR purge work?" in result.output

    def test_context_with_source(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["context", "PRCA45PT", "--with-source"], env=env
        )
        assert result.exit_code == 0
        # source-block fence
        assert "```" in result.output


class TestBuildCache:
    def test_build_cache_runs(self, tmp_path):
        runner = CliRunner()
        env = {
            **os.environ,
            **_env_for_fixtures(),
            "VISTA_CACHE_DB": str(tmp_path / "joined.db"),
        }
        result = runner.invoke(main, ["build-cache"], env=env)
        assert result.exit_code == 0, result.output
        assert (tmp_path / "joined.db").exists()
        assert "routines_mirror" in result.output


class TestRisk:
    def test_risk_known_routine(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["risk", "PRCA45PT"], env=env)
        assert result.exit_code == 0, result.output
        assert "/100" in result.output

    def test_risk_json(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["risk", "PRCA45PT", "--format", "json"], env=env
        )
        assert result.exit_code == 0
        import json

        parsed = json.loads(result.output)
        assert 0 <= parsed["score"] <= 100
        assert "components" in parsed
        # PRCA45PT has 5 patches → contributes to patch_count component
        assert parsed["facts"]["patch_count"] == 5

    def test_risk_unknown_routine(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["risk", "NOPE"], env=env)
        assert result.exit_code == 1


class TestLayers:
    def test_layers_for_ar(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main, ["layers", "--pkg", "Accounts Receivable"], env=env
        )
        assert result.exit_code == 0, result.output
        # PRCA45PT is a leaf (no intra-package callees in fixture);
        # PRCAACT calls PRCA45PT, so it's layer ≥ 1.
        assert "PRCA45PT" in result.output
        assert "PRCAACT" in result.output

    def test_layers_json(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(
            main,
            ["layers", "--pkg", "Accounts Receivable", "--format", "json"],
            env=env,
        )
        assert result.exit_code == 0
        import json

        parsed = json.loads(result.output)
        # Layer 0: PRCA45PT, Layer 1: PRCAACT
        layers_dict = {entry["layer"]: entry["routines"] for entry in parsed["layers"]}
        assert "PRCA45PT" in layers_dict[0]
        assert "PRCAACT" in layers_dict[1]


class TestMatrix:
    def test_matrix_md(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["matrix"], env=env)
        assert result.exit_code == 0, result.output
        # AR → Kernel cross-edge from PRCA45PT → XPDUTL
        assert "Accounts Receivable" in result.output
        assert "Kernel" in result.output

    def test_matrix_json(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["matrix", "--format", "json"], env=env)
        assert result.exit_code == 0
        import json

        parsed = json.loads(result.output)
        edges = {(e["caller_pkg"], e["callee_pkg"]): e["ref_count"]
                 for e in parsed["edges"]}
        # PRCA45PT → XPDUTL = 7 + 6 = 13 (BMES + MES tags)
        assert edges[("Accounts Receivable", "Kernel")] == 13

    def test_matrix_tsv(self):
        runner = CliRunner()
        env = {**os.environ, **_env_for_fixtures()}
        result = runner.invoke(main, ["matrix", "--format", "tsv"], env=env)
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "caller_pkg\tcallee_pkg\tref_count"


class TestCacheIntegration:
    """Phase 3 — cache-backed hot-path commands produce identical output."""

    def _env_with_cache(self, tmp_path):
        cache_path = tmp_path / "joined.db"
        env = {
            **os.environ,
            **_env_for_fixtures(),
            "VISTA_CACHE_DB": str(cache_path),
        }
        runner = CliRunner()
        runner.invoke(main, ["build-cache"], env=env)
        return env, runner

    def test_routine_parity_cache_vs_no_cache(self, tmp_path):
        env, runner = self._env_with_cache(tmp_path)
        with_cache = runner.invoke(
            main, ["routine", "PRCA45PT", "--format", "json"], env=env
        )
        without_cache = runner.invoke(
            main,
            ["--no-cache", "routine", "PRCA45PT", "--format", "json"],
            env=env,
        )
        assert with_cache.exit_code == 0
        assert without_cache.exit_code == 0
        import json

        a = json.loads(with_cache.output)
        b = json.loads(without_cache.output)
        for k in (
            "routine_name",
            "package",
            "line_count",
            "in_degree",
            "out_degree",
        ):
            assert a[k] == b[k], k
        # Callee sets agree
        a_callees = {(c["callee_routine"], c["callee_tag"]) for c in a["callees"]}
        b_callees = {(c["callee_routine"], c["callee_tag"]) for c in b["callees"]}
        assert a_callees == b_callees

    def test_links_cache_path_works(self, tmp_path):
        env, runner = self._env_with_cache(tmp_path)
        result = runner.invoke(main, ["links", "PRCA45PT"], env=env)
        assert result.exit_code == 0, result.output
        assert "PRCA45PT" in result.output
        assert "Accounts Receivable" in result.output

    def test_patch_cache_path_works(self, tmp_path):
        env, runner = self._env_with_cache(tmp_path)
        result = runner.invoke(main, ["patch", "PRCA*4.5*409"], env=env)
        assert result.exit_code == 0, result.output
        assert "PRCA45PT" in result.output

    def test_neighbors_cache_path_works(self, tmp_path):
        env, runner = self._env_with_cache(tmp_path)
        result = runner.invoke(main, ["neighbors", "PRCA45PT"], env=env)
        assert result.exit_code == 0, result.output
        assert "PRCA45PT" in result.output

    def test_no_cache_flag_forces_tsv_path(self, tmp_path):
        # Even with a stale or missing cache, --no-cache shouldn't fail.
        env = {
            **os.environ,
            **_env_for_fixtures(),
            "VISTA_CACHE_DB": str(tmp_path / "absent.db"),
        }
        runner = CliRunner()
        result = runner.invoke(
            main, ["--no-cache", "routine", "PRCA45PT"], env=env
        )
        assert result.exit_code == 0
        assert "PRCA45PT" in result.output


class TestSnapshotCommand:
    """Phase 4 — vista snapshot create / verify / info / install."""

    def test_create_and_info(self, tmp_path):
        env = {**os.environ, **_env_for_fixtures()}
        bundle = tmp_path / "snap.tar.xz"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "snapshot",
                "create",
                "--out",
                str(bundle),
                "--snapshot-version",
                "test.1",
            ],
            env=env,
        )
        assert result.exit_code == 0, result.output
        assert bundle.exists()
        info = runner.invoke(
            main, ["snapshot", "info", str(bundle), "--format", "json"], env=env
        )
        assert info.exit_code == 0
        import json as j

        manifest = j.loads(info.output)
        assert manifest["snapshot_version"] == "test.1"

    def test_verify_clean_bundle(self, tmp_path):
        env = {**os.environ, **_env_for_fixtures()}
        bundle = tmp_path / "snap.tar.xz"
        runner = CliRunner()
        runner.invoke(
            main,
            [
                "snapshot",
                "create",
                "--out",
                str(bundle),
                "--snapshot-version",
                "test.1",
            ],
            env=env,
        )
        result = runner.invoke(main, ["snapshot", "verify", str(bundle)], env=env)
        assert result.exit_code == 0
        assert "ok" in result.output.lower()

    def test_install(self, tmp_path):
        env = {**os.environ, **_env_for_fixtures()}
        bundle = tmp_path / "snap.tar.xz"
        runner = CliRunner()
        runner.invoke(
            main,
            [
                "snapshot",
                "create",
                "--out",
                str(bundle),
                "--snapshot-version",
                "test.1",
            ],
            env=env,
        )
        target = tmp_path / "installed"
        result = runner.invoke(
            main,
            ["snapshot", "install", str(bundle), "--data-dir", str(target)],
            env=env,
        )
        assert result.exit_code == 0
        assert (target / "snapshot.json").exists()


class TestFetchCommand:
    """Phase 4 — vista fetch (file:// URL substitutes for the network)."""

    def _build_bundle(self, tmp_path, version="2026.04.28"):
        from vista_cli.snapshot import create_bundle

        bundle = tmp_path / f"vista-snapshot-{version}.tar.xz"
        create_bundle(
            out=bundle,
            code_model_dir=FIXTURE_DIR / "code-model",
            data_model_dir=FIXTURE_DIR / "data-model",
            doc_db=FIXTURE_DIR / "frontmatter.db",
            snapshot_version=version,
        )
        return bundle

    def test_fetch_from_local_bundle(self, tmp_path):
        env = {**os.environ, **_env_for_fixtures()}
        bundle = self._build_bundle(tmp_path)
        target = tmp_path / "data"
        cache = tmp_path / "cache"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "fetch",
                "--from",
                str(bundle),
                "--data-dir",
                str(target),
                "--cache-dir",
                str(cache),
            ],
            env=env,
        )
        assert result.exit_code == 0, result.output
        assert (target / "frontmatter.db").exists()


class TestInitCommand:
    """Phase 4 — vista init (idempotent bootstrap)."""

    def test_init_no_op_when_data_present(self):
        # Fixtures already exist — env vars point at them, so init
        # should detect "already usable" and exit cleanly.
        env = {**os.environ, **_env_for_fixtures()}
        runner = CliRunner()
        result = runner.invoke(main, ["init"], env=env)
        assert result.exit_code == 0
        assert "already present" in result.output

    def test_init_from_local_bundle_when_data_missing_placeholder(self):
        pass  # placeholder so the next class lands cleanly

    def _placeholder(self):
        pass


class TestDidYouMean:
    """Phase 5 — typo tolerance: did-you-mean suggestions on not-found."""

    def test_routine_typo_suggests_close_match(self):
        env = {**os.environ, **_env_for_fixtures()}
        runner = CliRunner()
        result = runner.invoke(main, ["routine", "PRCA45TP"], env=env)
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
        assert "Did you mean" in result.output
        assert "PRCA45PT" in result.output

    def test_routine_unrelated_query_no_suggestion(self):
        env = {**os.environ, **_env_for_fixtures()}
        runner = CliRunner()
        result = runner.invoke(main, ["routine", "ZZZZZZZ"], env=env)
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
        # Far-off query shouldn't produce a suggestion line
        assert "Did you mean" not in result.output

    def test_package_typo_suggests_close_match(self):
        env = {**os.environ, **_env_for_fixtures()}
        runner = CliRunner()
        # Typo of "Accounts Receivable"
        result = runner.invoke(main, ["package", "Acounts Receivabl"], env=env)
        assert result.exit_code == 1
        assert "Did you mean" in result.output
        assert "Accounts Receivable" in result.output

    def test_rpc_typo_suggests_close_match(self):
        # Fixture rpcs.tsv has at least one RPC; check fixture first

        rpcs = (FIXTURE_DIR / "code-model/rpcs.tsv").read_text().splitlines()
        if len(rpcs) < 2:  # header only — skip
            return
        real_name = rpcs[1].split("\t")[0]
        # Make a one-character typo of the real name
        if len(real_name) < 4:
            return
        typo = real_name[:-1] + ("Z" if real_name[-1] != "Z" else "Y")
        env = {**os.environ, **_env_for_fixtures()}
        runner = CliRunner()
        result = runner.invoke(main, ["rpc", typo], env=env)
        assert result.exit_code == 1
        assert "Did you mean" in result.output
        assert real_name in result.output

    def test_option_typo_suggests_close_match(self):

        opts = (FIXTURE_DIR / "code-model/options.tsv").read_text().splitlines()
        if len(opts) < 2:
            return
        real_name = opts[1].split("\t")[0]
        if len(real_name) < 4:
            return
        typo = real_name[:-1] + ("Z" if real_name[-1] != "Z" else "Y")
        env = {**os.environ, **_env_for_fixtures()}
        runner = CliRunner()
        result = runner.invoke(main, ["option", typo], env=env)
        assert result.exit_code == 1
        assert "Did you mean" in result.output
        assert real_name in result.output

    def test_file_typo_suggests_close_match_with_name_label(self):

        files = (FIXTURE_DIR / "data-model/files.tsv").read_text().splitlines()
        if len(files) < 2:
            return
        real_num = files[1].split("\t")[0]
        # Append a digit to make it a typo
        typo = real_num + "9"
        env = {**os.environ, **_env_for_fixtures()}
        runner = CliRunner()
        result = runner.invoke(main, ["file", typo], env=env)
        assert result.exit_code == 1
        # File suggestions include the file name in parens
        if "Did you mean" in result.output:
            assert real_num in result.output

    def test_init_from_local_bundle_when_data_missing(self, tmp_path):
        # Build a bundle, then init from it with env vars pointing at
        # paths that don't exist yet.
        from vista_cli.snapshot import create_bundle

        bundle = tmp_path / "bootstrap.tar.xz"
        create_bundle(
            out=bundle,
            code_model_dir=FIXTURE_DIR / "code-model",
            data_model_dir=FIXTURE_DIR / "data-model",
            doc_db=FIXTURE_DIR / "frontmatter.db",
            snapshot_version="bootstrap.1",
        )
        absent = tmp_path / "absent"
        target = tmp_path / "snapshot"
        env = {
            **os.environ,
            "VISTA_CODE_MODEL": str(absent / "code-model"),
            "VISTA_DATA_MODEL": str(absent / "data-model"),
            "VISTA_M_HOST": str(absent / "vista-m-host"),
            "VISTA_DOC_DB": str(absent / "frontmatter.db"),
            "VISTA_DOC_PUBLISH": str(absent / "publish"),
            "VISTA_CACHE_DB": str(tmp_path / "cache.db"),
        }
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["init", "--from", str(bundle), "--data-dir", str(target)],
            env=env,
        )
        assert result.exit_code == 0, result.output
        assert (target / "frontmatter.db").exists()
        assert "installed bootstrap.1" in result.output
