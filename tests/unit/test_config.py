"""Tests for path resolution from env vars + defaults."""

from pathlib import Path

from vista_cli.config import Config


class TestConfig:
    def test_defaults_set(self):
        cfg = Config.from_env({})
        assert cfg.code_model_dir == Path.home() / "vista-meta/vista/export/code-model"
        assert cfg.doc_db == Path.home() / "data/vista-docs/state/frontmatter.db"
        assert cfg.vista_m_host == Path.home() / "vista-meta/vista/vista-m-host"

    def test_env_var_overrides_code_model(self):
        cfg = Config.from_env({"VISTA_CODE_MODEL": "/tmp/code-model"})
        assert cfg.code_model_dir == Path("/tmp/code-model")

    def test_env_var_overrides_doc_db(self):
        cfg = Config.from_env({"VISTA_DOC_DB": "/tmp/fm.db"})
        assert cfg.doc_db == Path("/tmp/fm.db")

    def test_env_var_overrides_data_model(self):
        cfg = Config.from_env({"VISTA_DATA_MODEL": "/tmp/data-model"})
        assert cfg.data_model_dir == Path("/tmp/data-model")

    def test_env_var_overrides_publish(self):
        cfg = Config.from_env({"VISTA_DOC_PUBLISH": "/tmp/publish"})
        assert cfg.doc_publish_dir == Path("/tmp/publish")

    def test_unrelated_env_vars_ignored(self):
        cfg = Config.from_env({"PATH": "/usr/bin", "HOME": "/home/x"})
        assert cfg.code_model_dir == Path.home() / "vista-meta/vista/export/code-model"
