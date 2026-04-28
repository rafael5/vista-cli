"""Canonical package id resolution and reference shape detection.

vista-meta names packages by directory ("Outpatient Pharmacy");
vista-docs names them by VDL app_code ("PSO") and VistA namespace
("PSO" — sometimes overlapping but not always). canonical.py owns
the bidirectional map.

The map is loaded from `src/vista_cli/data/packages.csv` (shipped
with the package). `VISTA_PACKAGES_CSV` overrides for testing or
local extensions.
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class PackageId:
    directory: str  # "Outpatient Pharmacy"
    ns: str  # "PSO"  (VistA namespace prefix)
    app_code: str  # "PSO"  (VDL app code)


_CACHED: tuple[PackageId, ...] | None = None
_CACHED_KEY: str | None = None


def _csv_path() -> Path:
    override = os.environ.get("VISTA_PACKAGES_CSV")
    if override:
        return Path(override)
    return Path(str(resources.files("vista_cli") / "data" / "packages.csv"))


def _load_packages() -> tuple[PackageId, ...]:
    global _CACHED, _CACHED_KEY
    path = _csv_path()
    key = str(path)
    if _CACHED is not None and _CACHED_KEY == key:
        return _CACHED
    rows: list[PackageId] = []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(
                PackageId(
                    directory=r["directory"],
                    ns=r["ns"],
                    app_code=r["app_code"],
                )
            )
    _CACHED = tuple(rows)
    _CACHED_KEY = key
    return _CACHED


def resolve_package(query: str) -> PackageId | None:
    """Resolve a package by directory name, namespace, or app_code.

    Lookup order:
      1. Directory match (case-insensitive)
      2. Namespace match (case-insensitive)
      3. App-code match (case-insensitive)

    Returns None if no match.
    """
    q = query.strip()
    if not q:
        return None
    qu = q.upper()
    pkgs = _load_packages()
    for p in pkgs:
        if p.directory.lower() == q.lower():
            return p
    for p in pkgs:
        if p.ns.upper() == qu:
            return p
    for p in pkgs:
        if p.app_code.upper() == qu:
            return p
    return None


def all_packages() -> tuple[PackageId, ...]:
    """Return the full canonical package map (for listing / coverage)."""
    return _load_packages()


# ── Reference shape detection ──────────────────────────────────────


_RE_GLOBAL = re.compile(r"^\^([A-Z%][A-Z0-9]{0,7})\(")
_RE_PATCH = re.compile(r"^[A-Z%][A-Z0-9]{0,3}\*\d+(?:\.\d+)?\*\d+$")
_RE_FILE_NUMBER = re.compile(r"^\d+(?:\.\d+)?$")
_RE_TAG_AT_RTN = re.compile(r"^([A-Za-z%][A-Za-z0-9]*)\^([A-Za-z%][A-Za-z0-9]{0,7})$")
_RE_CARET_RTN = re.compile(r"^\^([A-Za-z%][A-Za-z0-9]{0,7})$")
_RE_BARE = re.compile(r"^[A-Za-z%][A-Za-z0-9]{0,7}$")


def classify_ref(ref: str) -> tuple[str, str, str | None]:
    """Classify a reference string.

    Returns (kind, primary_name, tag_or_none) where kind is one of:
    'routine', 'global', 'file', 'patch', 'unknown'.

    Disambiguation rules:
    - Global with subscript: ^DPT(... → ('global', 'DPT', None)
    - Patch ID: PRCA*4.5*341 → ('patch', ...)
    - Numeric: 9.8 / 200 → ('file', ...)
    - TAG^RTN: → ('routine', RTN, TAG)
    - ^RTN: → ('routine', RTN, None)
    - Bare identifier: → ('routine', name, None)
      (Caller resolves further via routines.tsv membership.)
    """
    s = ref.strip()
    if not s:
        return ("unknown", s, None)

    if m := _RE_GLOBAL.match(s):
        return ("global", m.group(1), None)
    if _RE_PATCH.match(s):
        return ("patch", s, None)
    if _RE_FILE_NUMBER.match(s):
        return ("file", s, None)
    if m := _RE_TAG_AT_RTN.match(s):
        return ("routine", m.group(2), m.group(1))
    if m := _RE_CARET_RTN.match(s):
        return ("routine", m.group(1), None)
    if _RE_BARE.match(s):
        return ("routine", s, None)
    return ("unknown", s, None)
