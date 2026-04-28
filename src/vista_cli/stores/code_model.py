"""Read vista-meta code-model TSVs.

Mirrors the lazy-load + per-column index pattern from the vista-meta
VSCode extension (see vista-meta/vscode-extension/src/tsv.ts).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

Row = dict[str, str]

# Line-2 patch list embedded in routine version_line, e.g.:
#   ;;4.5;Accounts Receivable;**14,79,153,302,409**;Mar 20, 1995
_RE_PATCH_LIST = re.compile(r"\*\*([0-9,\s]+)\*\*")


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

    def rpc(self, name: str) -> Row | None:
        rows = self._by("rpcs.tsv", "name").get(name)
        return rows[0] if rows else None

    def rpcs_by_package(self, package: str) -> list[Row]:
        return self._by("rpcs.tsv", "package").get(package, [])

    def all_rpcs(self) -> list[Row]:
        return self._load("rpcs.tsv")

    # ── options.tsv ────────────────────────────────────────────────

    def options_in_routine(self, routine: str) -> list[Row]:
        return self._by("options.tsv", "routine").get(routine, [])

    def option(self, name: str) -> Row | None:
        rows = self._by("options.tsv", "name").get(name)
        return rows[0] if rows else None

    def options_by_package(self, package: str) -> list[Row]:
        return self._by("options.tsv", "package").get(package, [])

    def all_options(self) -> list[Row]:
        return self._load("options.tsv")

    # ── routine-globals.tsv (reverse) ──────────────────────────────

    def routines_using_global(self, global_name: str) -> list[Row]:
        rows = self._by("routine-globals.tsv", "global_name").get(global_name, [])
        return sorted(rows, key=lambda r: -_to_int(r.get("ref_count", "0")))

    # ── packages.tsv ───────────────────────────────────────────────

    def package(self, name: str) -> Row | None:
        rows = self._by("packages.tsv", "package").get(name)
        return rows[0] if rows else None

    def all_packages(self) -> list[Row]:
        return self._load("packages.tsv")

    # ── routines-comprehensive.tsv (cross filters) ─────────────────

    def all_routines(self) -> list[Row]:
        return self._load("routines-comprehensive.tsv")

    def patches_for_routine(self, name: str) -> list[str]:
        """Return canonical patch IDs from a routine's line-2 version line.

        Examples for `PRCA45PT` whose version_line is
        `;;4.5;Accounts Receivable;**14,79,153,302,409**;...` and whose
        package namespace is `PRCA` →
        `["PRCA*4.5*14", "PRCA*4.5*79", ...]`.
        """
        row = self.routine(name)
        if row is None:
            return []
        v_line = row.get("version_line", "")
        m = _RE_PATCH_LIST.search(v_line)
        if not m:
            return []
        # Version is the first ";;<ver>;" segment.
        ver_match = re.search(r";;([0-9]+(?:\.[0-9]+)?);", v_line)
        if not ver_match:
            return []
        ver = ver_match.group(1)
        # Namespace: walk the routine name back until it stops being
        # alphabetic (matches the convention `<NS><digits/letters>`).
        ns = _routine_namespace(name)
        nums = [p.strip() for p in m.group(1).split(",") if p.strip()]
        return [f"{ns}*{ver}*{n}" for n in nums]

    def routines_for_patch(self, patch_id: str) -> list[Row]:
        """Routines whose line-2 patch list mentions this patch.

        `patch_id` is in canonical KIDS form, e.g. `PRCA*4.5*409`.
        Matches on namespace + version + number.
        """
        m = re.match(
            r"^([A-Z%][A-Z0-9]{0,3})\*(\d+(?:\.\d+)?)\*(\d+)$",
            patch_id.upper(),
        )
        if not m:
            return []
        ns, ver, num = m.group(1), m.group(2), m.group(3)
        out: list[Row] = []
        for r in self.all_routines():
            name = r.get("routine_name", "")
            if not name.upper().startswith(ns):
                continue
            v_line = r.get("version_line", "")
            if f";{ver};" not in v_line and not v_line.startswith(f";;{ver};"):
                continue
            patch_list = _RE_PATCH_LIST.search(v_line)
            if not patch_list:
                continue
            nums = {p.strip() for p in patch_list.group(1).split(",") if p.strip()}
            if num in nums:
                out.append(r)
        return out


def _to_int(s: str) -> int:
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


def _routine_namespace(name: str) -> str:
    """Heuristic: leading letters of a routine name form its namespace.

    `PRCA45PT` → `PRCA`, `XUSCLEAN` → `XUSCLEAN` (all alpha), `%ZTLOAD` → `%ZTLOAD`.
    Stops at the first digit; `%` is treated as alphabetic.
    """
    if not name:
        return ""
    out = ""
    for ch in name:
        if ch.isalpha() or ch == "%":
            out += ch
        else:
            break
    return out
