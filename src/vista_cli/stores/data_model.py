"""Read vista-meta data-model TSVs (FileMan files + PIKS).

Mirrors the lazy-load pattern of CodeModelStore. Files are looked up
by file_number (the canonical FileMan identifier).
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

Row = dict[str, str]


class DataModelStore:
    """Lazy reader for the data-model TSVs (files.tsv, piks.tsv, ...)."""

    def __init__(self, data_model_dir: Path):
        self.dir = Path(data_model_dir)
        self._tables: dict[str, list[Row]] = {}
        self._indexes: dict[tuple[str, str], dict[str, list[Row]]] = {}

    def _load(self, name: str) -> list[Row]:
        if name in self._tables:
            return self._tables[name]
        path = self.dir / name
        rows: list[Row] = []
        if not path.exists():
            logger.warning("TSV not found: %s", path)
            self._tables[name] = rows
            return rows
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        if len(lines) < 2:
            self._tables[name] = rows
            return rows
        header = lines[0].split("\t")
        for ln in lines[1:]:
            if not ln:
                continue
            parts = ln.split("\t")
            row = {
                h: (parts[i] if i < len(parts) else "") for i, h in enumerate(header)
            }
            rows.append(row)
        self._tables[name] = rows
        return rows

    def _by(self, name: str, col: str) -> dict[str, list[Row]]:
        key = (name, col)
        if key in self._indexes:
            return self._indexes[key]
        idx: dict[str, list[Row]] = {}
        for row in self._load(name):
            k = row.get(col, "")
            if not k:
                continue
            idx.setdefault(k, []).append(row)
        self._indexes[key] = idx
        return idx

    # ── files.tsv ──────────────────────────────────────────────────

    def file(self, number: str) -> Row | None:
        rows = self._by("files.tsv", "file_number").get(str(number))
        return rows[0] if rows else None

    def all_files(self) -> list[Row]:
        return self._load("files.tsv")

    def files_by_global_root(self, root: str) -> list[Row]:
        return self._by("files.tsv", "global_root").get(root, [])

    # ── piks.tsv ───────────────────────────────────────────────────

    def piks(self, number: str) -> Row | None:
        rows = self._by("piks.tsv", "file_number").get(str(number))
        return rows[0] if rows else None
