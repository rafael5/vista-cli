"""Joined-cache builder + reader.

Materialises the cross-store joins from §6.2 of the planning doc into
a small SQLite at `cache_db`. The cache is a derived artifact:
regenerate via `vista build-cache` whenever vista-meta or vista-docs
changes.

Schema (verified against §6.2):
    routine_doc_refs (routine, doc_id, section_id, tag, ref_count)
    rpc_doc_refs    (rpc_name, doc_id, section_id)
    option_doc_refs (option_name, doc_id, section_id)
    file_doc_refs   (file_number, doc_id, section_id)
    patch_routine_refs (patch_id, routine, ref_kind)
    package_canonical (directory, ns, app_code, group_key)
    routines_mirror (subset of routines-comprehensive)
    routine_calls_mirror, routine_globals_mirror
    cache_meta (key, value)  — built_at, source mtimes, source hashes
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from vista_cli.canonical import all_packages
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.data_model import DataModelStore
from vista_cli.stores.doc_model import DocModelStore


def build(
    *,
    cache_db: Path,
    code_model_dir: Path,
    data_model_dir: Path,
    doc_db: Path,
) -> dict[str, int]:
    """Build the joined cache. Returns row counts per table."""
    cache_db = Path(cache_db)
    cache_db.parent.mkdir(parents=True, exist_ok=True)
    if cache_db.exists():
        cache_db.unlink()

    conn = sqlite3.connect(cache_db)
    try:
        _create_schema(conn)
        cms = CodeModelStore(code_model_dir)
        counts = {
            "routines_mirror": _mirror_routines(conn, cms),
            "routine_calls_mirror": _mirror_calls(conn, cms),
            "routine_globals_mirror": _mirror_globals(conn, cms),
            "package_canonical": _populate_package_canonical(conn),
            "patch_routine_refs": _populate_patch_routine_refs(conn, cms),
        }
        if doc_db.exists():
            dms = DocModelStore(doc_db)
            try:
                counts["routine_doc_refs"] = _populate_routine_doc_refs(conn, dms)
                counts["rpc_doc_refs"] = _populate_rpc_doc_refs(conn, dms)
                counts["option_doc_refs"] = _populate_option_doc_refs(conn, dms)
                counts["file_doc_refs"] = _populate_file_doc_refs(conn, dms)
            finally:
                dms.close()
        DataModelStore(data_model_dir)  # touch — not yet mirrored
        _write_meta(
            conn,
            code_model_dir=code_model_dir,
            data_model_dir=data_model_dir,
            doc_db=doc_db,
        )
        conn.commit()
    finally:
        conn.close()
    return counts


def _create_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE routines_mirror (
            routine_name TEXT PRIMARY KEY,
            package TEXT,
            line_count INTEGER,
            in_degree INTEGER,
            out_degree INTEGER,
            rpc_count INTEGER,
            option_count INTEGER,
            version_line TEXT,
            source_path TEXT
        );
        CREATE INDEX idx_rm_pkg ON routines_mirror(package);

        CREATE TABLE routine_calls_mirror (
            caller_name TEXT,
            caller_package TEXT,
            callee_routine TEXT,
            callee_tag TEXT,
            kind TEXT,
            ref_count INTEGER
        );
        CREATE INDEX idx_rcm_caller ON routine_calls_mirror(caller_name);
        CREATE INDEX idx_rcm_callee ON routine_calls_mirror(callee_routine);

        CREATE TABLE routine_globals_mirror (
            routine_name TEXT,
            package TEXT,
            global_name TEXT,
            ref_count INTEGER
        );
        CREATE INDEX idx_rgm_routine ON routine_globals_mirror(routine_name);
        CREATE INDEX idx_rgm_global ON routine_globals_mirror(global_name);

        CREATE TABLE routine_doc_refs (
            routine TEXT NOT NULL,
            doc_id INTEGER NOT NULL,
            section_id INTEGER,
            tag TEXT NOT NULL DEFAULT '',
            ref_count INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY(routine, doc_id, tag)
        );
        CREATE INDEX idx_rdr_routine ON routine_doc_refs(routine);

        CREATE TABLE rpc_doc_refs (
            rpc_name TEXT NOT NULL,
            doc_id INTEGER NOT NULL,
            section_id INTEGER,
            PRIMARY KEY(rpc_name, doc_id)
        );
        CREATE INDEX idx_rpc_dr_name ON rpc_doc_refs(rpc_name);

        CREATE TABLE option_doc_refs (
            option_name TEXT NOT NULL,
            doc_id INTEGER NOT NULL,
            section_id INTEGER,
            PRIMARY KEY(option_name, doc_id)
        );
        CREATE INDEX idx_opt_dr_name ON option_doc_refs(option_name);

        CREATE TABLE file_doc_refs (
            file_number TEXT NOT NULL,
            doc_id INTEGER NOT NULL,
            section_id INTEGER,
            PRIMARY KEY(file_number, doc_id)
        );

        CREATE TABLE patch_routine_refs (
            patch_id TEXT NOT NULL,
            routine TEXT NOT NULL,
            ref_kind TEXT NOT NULL DEFAULT 'line2',
            PRIMARY KEY(patch_id, routine)
        );
        CREATE INDEX idx_prr_patch ON patch_routine_refs(patch_id);
        CREATE INDEX idx_prr_routine ON patch_routine_refs(routine);

        CREATE TABLE package_canonical (
            directory TEXT PRIMARY KEY,
            ns TEXT NOT NULL,
            app_code TEXT NOT NULL,
            group_key TEXT
        );

        CREATE TABLE cache_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )


def _mirror_routines(conn: sqlite3.Connection, cms: CodeModelStore) -> int:
    rows = cms.all_routines()
    insert = (
        "INSERT INTO routines_mirror (routine_name, package, line_count, "
        "in_degree, out_degree, rpc_count, option_count, version_line, "
        "source_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    payload = [
        (
            r.get("routine_name", ""),
            r.get("package", ""),
            _i(r.get("line_count")),
            _i(r.get("in_degree")),
            _i(r.get("out_degree")),
            _i(r.get("rpc_count")),
            _i(r.get("option_count")),
            r.get("version_line", ""),
            r.get("source_path", ""),
        )
        for r in rows
        if r.get("routine_name")
    ]
    conn.executemany(insert, payload)
    return len(payload)


def _mirror_calls(conn: sqlite3.Connection, cms: CodeModelStore) -> int:
    rows = cms._load("routine-calls.tsv")
    insert = (
        "INSERT INTO routine_calls_mirror (caller_name, caller_package, "
        "callee_routine, callee_tag, kind, ref_count) "
        "VALUES (?, ?, ?, ?, ?, ?)"
    )
    payload = [
        (
            r.get("caller_name", ""),
            r.get("caller_package", ""),
            r.get("callee_routine", ""),
            r.get("callee_tag", ""),
            r.get("kind", ""),
            _i(r.get("ref_count")),
        )
        for r in rows
    ]
    conn.executemany(insert, payload)
    return len(payload)


def _mirror_globals(conn: sqlite3.Connection, cms: CodeModelStore) -> int:
    rows = cms._load("routine-globals.tsv")
    insert = (
        "INSERT INTO routine_globals_mirror (routine_name, package, "
        "global_name, ref_count) VALUES (?, ?, ?, ?)"
    )
    payload = [
        (
            r.get("routine_name", ""),
            r.get("package", ""),
            r.get("global_name", ""),
            _i(r.get("ref_count")),
        )
        for r in rows
    ]
    conn.executemany(insert, payload)
    return len(payload)


def _populate_package_canonical(conn: sqlite3.Connection) -> int:
    rows = [(p.directory, p.ns, p.app_code, None) for p in all_packages()]
    conn.executemany(
        "INSERT INTO package_canonical (directory, ns, app_code, group_key) "
        "VALUES (?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def _populate_patch_routine_refs(conn: sqlite3.Connection, cms: CodeModelStore) -> int:
    inserted = 0
    seen: set[tuple[str, str]] = set()
    for r in cms.all_routines():
        name = r.get("routine_name", "")
        if not name:
            continue
        for pid in cms.patches_for_routine(name):
            key = (pid, name)
            if key in seen:
                continue
            seen.add(key)
            conn.execute(
                "INSERT INTO patch_routine_refs (patch_id, routine, ref_kind) "
                "VALUES (?, ?, 'line2')",
                (pid, name),
            )
            inserted += 1
    return inserted


def _populate_routine_doc_refs(conn: sqlite3.Connection, dms: DocModelStore) -> int:
    cur = dms._conn_().execute(
        "SELECT routine, doc_id, tag, COUNT(*) AS c FROM doc_routines "
        "GROUP BY routine, doc_id, tag"
    )
    payload = [
        (r["routine"], r["doc_id"], None, r["tag"] or "", r["c"])
        for r in cur.fetchall()
    ]
    conn.executemany(
        "INSERT INTO routine_doc_refs (routine, doc_id, section_id, tag, "
        "ref_count) VALUES (?, ?, ?, ?, ?)",
        payload,
    )
    return len(payload)


def _populate_rpc_doc_refs(conn: sqlite3.Connection, dms: DocModelStore) -> int:
    cur = dms._conn_().execute(
        "SELECT DISTINCT rpc_name, doc_id FROM doc_rpcs"
    )
    payload = [(r["rpc_name"], r["doc_id"], None) for r in cur.fetchall()]
    conn.executemany(
        "INSERT INTO rpc_doc_refs (rpc_name, doc_id, section_id) "
        "VALUES (?, ?, ?)",
        payload,
    )
    return len(payload)


def _populate_option_doc_refs(conn: sqlite3.Connection, dms: DocModelStore) -> int:
    cur = dms._conn_().execute(
        "SELECT DISTINCT option_name, doc_id FROM doc_options"
    )
    payload = [(r["option_name"], r["doc_id"], None) for r in cur.fetchall()]
    conn.executemany(
        "INSERT INTO option_doc_refs (option_name, doc_id, section_id) "
        "VALUES (?, ?, ?)",
        payload,
    )
    return len(payload)


def _populate_file_doc_refs(conn: sqlite3.Connection, dms: DocModelStore) -> int:
    try:
        cur = dms._conn_().execute(
            "SELECT DISTINCT file_number, doc_id FROM doc_file_refs"
        )
    except sqlite3.OperationalError:
        # Older frontmatter.db without doc_file_refs
        return 0
    payload = [(r["file_number"], r["doc_id"], None) for r in cur.fetchall()]
    conn.executemany(
        "INSERT INTO file_doc_refs (file_number, doc_id, section_id) "
        "VALUES (?, ?, ?)",
        payload,
    )
    return len(payload)


def _write_meta(
    conn: sqlite3.Connection,
    *,
    code_model_dir: Path,
    data_model_dir: Path,
    doc_db: Path,
) -> None:
    items: list[tuple[str, str]] = [
        ("built_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        ("code_model_dir", str(code_model_dir)),
        ("data_model_dir", str(data_model_dir)),
        ("doc_db", str(doc_db)),
        ("code_model_mtime", _mtime_str(code_model_dir)),
        ("doc_db_mtime", _mtime_str(doc_db)),
        ("code_model_hash", _dir_hash(code_model_dir)),
        ("schema_version", "1"),
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)", items
    )


def _mtime_str(path: Path) -> str:
    try:
        return str(path.stat().st_mtime)
    except OSError:
        return ""


def _dir_hash(directory: Path) -> str:
    """SHA1 of the concatenated mtimes of TSVs in `directory` (cheap signature)."""
    h = hashlib.sha1()
    if not directory.exists():
        return ""
    for p in sorted(directory.glob("*.tsv")):
        try:
            h.update(p.name.encode())
            h.update(str(p.stat().st_mtime).encode())
        except OSError:
            continue
    return h.hexdigest()


def _i(value: object) -> int:
    if value is None:
        return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


# ── Reader ────────────────────────────────────────────────────────


class CacheStore:
    """Read-only handle on the joined cache."""

    def __init__(self, cache_db: Path):
        self.path = Path(cache_db)
        self._conn: sqlite3.Connection | None = None

    def _conn_(self) -> sqlite3.Connection:
        if self._conn is None:
            uri = f"file:{self.path}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def meta(self, key: str) -> str | None:
        cur = self._conn_().execute(
            "SELECT value FROM cache_meta WHERE key = ?", (key,)
        )
        row = cur.fetchone()
        return row[0] if row else None

    def is_stale(
        self,
        *,
        code_model_dir: Path,
        doc_db: Path,
    ) -> tuple[bool, list[str]]:
        """Return (stale, reasons) — `stale=True` means at least one source
        moved since the cache was built.

        Compares per-file mtime hashes (more reliable than directory
        mtime, which doesn't change when files inside are touched on
        most filesystems).
        """
        reasons: list[str] = []
        cm_now = _dir_hash(code_model_dir)
        cm_built = self.meta("code_model_hash") or ""
        if cm_now and cm_built and cm_now != cm_built:
            reasons.append("code-model TSVs changed")
        doc_now = _mtime_str(doc_db)
        doc_built = self.meta("doc_db_mtime") or ""
        if doc_now and doc_built and float(doc_now) > float(doc_built):
            reasons.append("doc DB updated")
        return (bool(reasons), reasons)

    def routine_doc_refs(self, routine: str) -> list[dict]:
        cur = self._conn_().execute(
            "SELECT * FROM routine_doc_refs WHERE routine = ?", (routine,)
        )
        return [dict(r) for r in cur.fetchall()]

    def patches_for_routine(self, routine: str) -> list[str]:
        cur = self._conn_().execute(
            "SELECT patch_id FROM patch_routine_refs WHERE routine = ? "
            "ORDER BY patch_id",
            (routine,),
        )
        return [r[0] for r in cur.fetchall()]

    # ── Code-model mirror lookups (match CodeModelStore signatures) ──
    #
    # These return rows shaped like the corresponding TSV reads so a
    # CacheStore can substitute for a CodeModelStore at the call sites
    # in `stores/code_view.py`. All values are stringified for parity
    # with the TSV path (CodeModelStore returns dict[str, str]).

    def routine(self, name: str) -> dict[str, str] | None:
        cur = self._conn_().execute(
            "SELECT * FROM routines_mirror WHERE routine_name = ?", (name,)
        )
        row = cur.fetchone()
        return _stringify(row) if row else None

    def all_routines(self) -> list[dict[str, str]]:
        cur = self._conn_().execute("SELECT * FROM routines_mirror")
        return [_stringify(r) for r in cur.fetchall()]

    def routines_by_package(self, pkg: str) -> list[dict[str, str]]:
        cur = self._conn_().execute(
            "SELECT * FROM routines_mirror WHERE package = ?", (pkg,)
        )
        return [_stringify(r) for r in cur.fetchall()]

    def callees(self, routine: str) -> list[dict[str, str]]:
        cur = self._conn_().execute(
            "SELECT * FROM routine_calls_mirror WHERE caller_name = ? "
            "ORDER BY ref_count DESC",
            (routine,),
        )
        return [_stringify(r) for r in cur.fetchall()]

    def callers(self, routine: str) -> list[dict[str, str]]:
        """Aggregate callers by routine name; sum ref_counts."""
        cur = self._conn_().execute(
            "SELECT caller_name, caller_package, callee_tag, "
            "       SUM(ref_count) AS ref_count "
            "FROM routine_calls_mirror "
            "WHERE callee_routine = ? "
            "GROUP BY caller_name, caller_package "
            "ORDER BY ref_count DESC",
            (routine,),
        )
        return [_stringify(r) for r in cur.fetchall()]

    def globals_for(self, routine: str) -> list[dict[str, str]]:
        cur = self._conn_().execute(
            "SELECT * FROM routine_globals_mirror WHERE routine_name = ? "
            "ORDER BY ref_count DESC",
            (routine,),
        )
        return [_stringify(r) for r in cur.fetchall()]

    def routines_using_global(self, global_name: str) -> list[dict[str, str]]:
        cur = self._conn_().execute(
            "SELECT * FROM routine_globals_mirror WHERE global_name = ? "
            "ORDER BY ref_count DESC",
            (global_name,),
        )
        return [_stringify(r) for r in cur.fetchall()]

    def routines_for_patch(self, patch_id: str) -> list[dict[str, str]]:
        """Resolve routines linked to a patch via patch_routine_refs.

        Returns enriched rows by joining patch_routine_refs back to
        routines_mirror so callers see the same shape as
        CodeModelStore.routines_for_patch.
        """
        cur = self._conn_().execute(
            "SELECT rm.* FROM patch_routine_refs prr "
            "JOIN routines_mirror rm ON rm.routine_name = prr.routine "
            "WHERE prr.patch_id = ? "
            "ORDER BY rm.routine_name",
            (patch_id,),
        )
        return [_stringify(r) for r in cur.fetchall()]


def _stringify(row: sqlite3.Row) -> dict[str, str]:
    """Convert a sqlite3.Row to dict[str, str] (matches TSV path shape)."""
    return {k: ("" if row[k] is None else str(row[k])) for k in row.keys()}
