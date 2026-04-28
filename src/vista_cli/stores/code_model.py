"""Read vista-meta code-model TSVs.

Mirrors the lazy-load + per-column index pattern from the vista-meta
VSCode extension (see vista-meta/vscode-extension/src/tsv.ts).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

Row = dict[str, str]


class CodeModelStore:
    """Lazy reader for the 19 code-model TSVs.

    One file is loaded once on first access and cached. Per-column
    indexes are memoized.
    """

    def __init__(self, code_model_dir: Path):
        self.dir = Path(code_model_dir)
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

    # ── routines-comprehensive.tsv ─────────────────────────────────

    def routine(self, name: str) -> Row | None:
        rows = self._by("routines-comprehensive.tsv", "routine_name").get(name)
        return rows[0] if rows else None

    def routines_by_package(self, pkg: str) -> list[Row]:
        return self._by("routines-comprehensive.tsv", "package").get(pkg, [])

    # ── routine-calls.tsv ──────────────────────────────────────────

    def callees(self, routine: str) -> list[Row]:
        rows = self._by("routine-calls.tsv", "caller_name").get(routine, [])
        return sorted(rows, key=lambda r: -_to_int(r.get("ref_count", "0")))

    def callers(self, routine: str) -> list[Row]:
        """Aggregate callers by routine, sum ref_counts."""
        rows = self._by("routine-calls.tsv", "callee_routine").get(routine, [])
        agg: dict[str, dict[str, Any]] = {}
        for r in rows:
            key = r.get("caller_name", "")
            cur = agg.get(key)
            if cur is None:
                agg[key] = {
                    "caller_name": key,
                    "caller_package": r.get("caller_package", ""),
                    "callee_tag": r.get("callee_tag", ""),
                    "ref_count": _to_int(r.get("ref_count", "0")),
                }
            else:
                cur["ref_count"] += _to_int(r.get("ref_count", "0"))
        out = sorted(agg.values(), key=lambda r: -int(r["ref_count"]))
        return [{k: str(v) for k, v in row.items()} for row in out]

    # ── routine-globals.tsv ────────────────────────────────────────

    def globals_for(self, routine: str) -> list[Row]:
        rows = self._by("routine-globals.tsv", "routine_name").get(routine, [])
        return sorted(rows, key=lambda r: -_to_int(r.get("ref_count", "0")))

    # ── xindex-errors.tsv ──────────────────────────────────────────

    def xindex_errors(self, routine: str) -> list[Row]:
        return self._by("xindex-errors.tsv", "routine").get(routine, [])

    # ── rpcs.tsv ───────────────────────────────────────────────────

    def rpcs_in_routine(self, routine: str) -> list[Row]:
        return self._by("rpcs.tsv", "routine").get(routine, [])

    # ── options.tsv ────────────────────────────────────────────────

    def options_in_routine(self, routine: str) -> list[Row]:
        return self._by("options.tsv", "routine").get(routine, [])


def _to_int(s: str) -> int:
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0
