"""Path resolution from environment variables with sensible defaults.

vista-cli reads from two on-disk stores it does not own:
- vista-meta TSVs (default: ~/vista-meta/vista/export/...)
- vista-docs SQLite + publish tree (default: ~/data/vista-docs/...)

All paths are overridable via env vars; the defaults match the
single-user setup documented in CLAUDE.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    code_model_dir: Path
    data_model_dir: Path
    vista_m_host: Path
    doc_db: Path
    doc_publish_dir: Path
    cache_db: Path

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        env = env if env is not None else dict(os.environ)
        home = Path.home()
        return cls(
            code_model_dir=Path(
                env.get(
                    "VISTA_CODE_MODEL",
                    str(home / "vista-meta/vista/export/code-model"),
                )
            ),
            data_model_dir=Path(
                env.get(
                    "VISTA_DATA_MODEL",
                    str(home / "vista-meta/vista/export/data-model"),
                )
            ),
            vista_m_host=Path(
                env.get(
                    "VISTA_M_HOST",
                    str(home / "vista-meta/vista/vista-m-host"),
                )
            ),
            doc_db=Path(
                env.get(
                    "VISTA_DOC_DB",
                    str(home / "data/vista-docs/state/frontmatter.db"),
                )
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
