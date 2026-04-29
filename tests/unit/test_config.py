"""Tests for path resolution from env vars + defaults."""

from pathlib import Path

from vista_cli.config import Config


class TestConfig:
    def test_defaults_set(self, tmp_path: Path):
        cfg = Config.from_env({}, home=tmp_path)
        assert cfg.code_model_dir == tmp_path / "vista-meta/vista/export/code-model"
        assert cfg.doc_db == tmp_path / "data/vista-docs/state/frontmatter.db"
        assert cfg.vista_m_host == tmp_path / "vista-meta/vista/vista-m-host"

    def test_env_var_overrides_code_model(self, tmp_path: Path):
        cfg = Config.from_env({"VISTA_CODE_MODEL": "/tmp/code-model"}, home=tmp_path)
        assert cfg.code_model_dir == Path("/tmp/code-model")

    def test_env_var_overrides_doc_db(self, tmp_path: Path):
        cfg = Config.from_env({"VISTA_DOC_DB": "/tmp/fm.db"}, home=tmp_path)
        assert cfg.doc_db == Path("/tmp/fm.db")

    def test_env_var_overrides_data_model(self, tmp_path: Path):
        cfg = Config.from_env({"VISTA_DATA_MODEL": "/tmp/data-model"}, home=tmp_path)
        assert cfg.data_model_dir == Path("/tmp/data-model")

    def test_env_var_overrides_publish(self, tmp_path: Path):
        cfg = Config.from_env({"VISTA_DOC_PUBLISH": "/tmp/publish"}, home=tmp_path)
        assert cfg.doc_publish_dir == Path("/tmp/publish")

    def test_env_var_overrides_cache_db(self, tmp_path: Path):
        cfg = Config.from_env({"VISTA_CACHE_DB": "/tmp/joined.db"}, home=tmp_path)
        assert cfg.cache_db == Path("/tmp/joined.db")

    def test_default_cache_db(self, tmp_path: Path):
        cfg = Config.from_env({}, home=tmp_path)
        assert cfg.cache_db == tmp_path / "data/vista/joined.db"

    def test_unrelated_env_vars_ignored(self, tmp_path: Path):
        cfg = Config.from_env(
            {"PATH": "/usr/bin", "HOME": "/home/x"}, home=tmp_path
        )
        assert cfg.code_model_dir == tmp_path / "vista-meta/vista/export/code-model"

    def test_snapshot_install_overrides_legacy_default(self, tmp_path: Path):
        snap = tmp_path / "data/vista/snapshot"
        (snap / "code-model").mkdir(parents=True)
        (snap / "data-model").mkdir(parents=True)
        (snap / "frontmatter.db").touch()

        cfg = Config.from_env({}, home=tmp_path)

        assert cfg.code_model_dir == snap / "code-model"
        assert cfg.data_model_dir == snap / "data-model"
        assert cfg.doc_db == snap / "frontmatter.db"

    def test_env_var_beats_installed_snapshot(self, tmp_path: Path):
        snap = tmp_path / "data/vista/snapshot"
        (snap / "code-model").mkdir(parents=True)
        (snap / "frontmatter.db").touch()

        cfg = Config.from_env(
            {
                "VISTA_CODE_MODEL": "/explicit/code",
                "VISTA_DOC_DB": "/explicit/fm.db",
            },
            home=tmp_path,
        )

        assert cfg.code_model_dir == Path("/explicit/code")
        assert cfg.doc_db == Path("/explicit/fm.db")

    def test_partial_snapshot_only_picks_up_present_pieces(self, tmp_path: Path):
        snap = tmp_path / "data/vista/snapshot"
        (snap / "code-model").mkdir(parents=True)
        # No frontmatter.db, no data-model — only code-model present.

        cfg = Config.from_env({}, home=tmp_path)

        assert cfg.code_model_dir == snap / "code-model"
        assert cfg.data_model_dir == tmp_path / "vista-meta/vista/export/data-model"
        assert cfg.doc_db == tmp_path / "data/vista-docs/state/frontmatter.db"

    def test_snapshot_does_not_affect_vista_m_host(self, tmp_path: Path):
        snap = tmp_path / "data/vista/snapshot"
        (snap / "code-model").mkdir(parents=True)

        cfg = Config.from_env({}, home=tmp_path)

        assert cfg.vista_m_host == tmp_path / "vista-meta/vista/vista-m-host"
