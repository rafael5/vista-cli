"""Path resolution from environment variables with sensible defaults.

vista-cli reads from two on-disk stores it does not own:
- vista-meta TSVs (default: ~/vista-meta/vista/export/...)
- vista-docs SQLite + publish tree (default: ~/data/vista-docs/...)

All paths are overridable via env vars. When env vars are unset and
an installed snapshot is present at ~/data/vista/snapshot/ (the
target of `vista init`), the resolver prefers the snapshot's
contents over the legacy source-repo defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SNAPSHOT_INSTALL_SUBPATH = "data/vista/snapshot"


@dataclass(frozen=True)
class Config:
    code_model_dir: Path
    data_model_dir: Path
    vista_m_host: Path
    doc_db: Path
    doc_publish_dir: Path
    cache_db: Path

    @classmethod
    def from_env(
        cls,
        env: dict[str, str] | None = None,
        *,
        home: Path | None = None,
    ) -> "Config":
        env = env if env is not None else dict(os.environ)
        home = home if home is not None else Path.home()
        snapshot = home / SNAPSHOT_INSTALL_SUBPATH

        def resolve(env_key: str, snapshot_relative: str, legacy: Path) -> Path:
            if env_key in env:
                return Path(env[env_key])
            snap_path = snapshot / snapshot_relative
            if snap_path.exists():
                return snap_path
            return legacy

        return cls(
            code_model_dir=resolve(
                "VISTA_CODE_MODEL",
                "code-model",
                home / "vista-meta/vista/export/code-model",
            ),
            data_model_dir=resolve(
                "VISTA_DATA_MODEL",
                "data-model",
                home / "vista-meta/vista/export/data-model",
            ),
            vista_m_host=Path(
                env.get(
                    "VISTA_M_HOST",
                    str(home / "vista-meta/vista/vista-m-host"),
                )
            ),
            doc_db=resolve(
                "VISTA_DOC_DB",
                "frontmatter.db",
                home / "data/vista-docs/state/frontmatter.db",
            ),
            doc_publish_dir=Path(
                env.get(
                    "VISTA_DOC_PUBLISH",
                    str(home / "data/vista-docs/publish"),
                )
            ),
            cache_db=Path(
                env.get(
                    "VISTA_CACHE_DB",
                    str(home / "data/vista/joined.db"),
                )
            ),
        )
