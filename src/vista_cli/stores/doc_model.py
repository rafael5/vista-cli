"""Read vista-docs frontmatter SQLite.

Read-only access to ~/data/vista-docs/state/frontmatter.db.

Production schema (verified):
- documents       2,842 rows  (rel_path, title, doc_type, app_code, ...)
- doc_routines   23,714 rows  (doc_id, routine, tag, full_ref)
- doc_globals               (doc_id, global_name)
- doc_rpcs          631      (doc_id, rpc_name)
- doc_options    23,199      (doc_id, option_name)
- doc_sections  138,711      (section_id, doc_id, level, heading, body, ...)
- doc_sections_fts           FTS5 over heading + body
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

Row = dict[str, Any]


class DocModelStore:
    """Read-only SQLite handle for vista-docs frontmatter.db."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def _conn_(self) -> sqlite3.Connection:
        if self._conn is None:
            # Read-only mode via URI
            uri = f"file:{self.db_path}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── document lookup ────────────────────────────────────────────

    def docs_by_routine(self, routine: str, *, latest_only: bool = True) -> list[Row]:
        """Documents that mention the given routine name.

        Joins doc_routines → documents.
        """
        sql = """
            SELECT DISTINCT d.doc_id, d.rel_path, d.title, d.doc_type,
                   d.app_code, d.pkg_ns, d.patch_id, d.is_latest,
                   d.quality_score, d.pub_date
            FROM documents d
            JOIN doc_routines r ON r.doc_id = d.doc_id
            WHERE r.routine = ?
        """
        if latest_only:
            sql += " AND d.is_latest = 1"
        sql += " ORDER BY d.quality_score DESC, d.pub_date DESC"
        cur = self._conn_().execute(sql, (routine,))
        return [dict(r) for r in cur.fetchall()]

    def docs_by_app_code(self, app_code: str, *, latest_only: bool = True) -> list[Row]:
        sql = "SELECT * FROM documents WHERE app_code = ?"
        if latest_only:
            sql += " AND is_latest = 1"
        sql += " ORDER BY quality_score DESC"
        cur = self._conn_().execute(sql, (app_code,))
        return [dict(r) for r in cur.fetchall()]

    def docs_by_rpc(self, rpc_name: str, *, latest_only: bool = True) -> list[Row]:
        sql = """
            SELECT DISTINCT d.doc_id, d.rel_path, d.title, d.doc_type,
                   d.app_code, d.pkg_ns, d.patch_id
            FROM documents d
            JOIN doc_rpcs r ON r.doc_id = d.doc_id
            WHERE r.rpc_name = ?
        """
        if latest_only:
            sql += " AND d.is_latest = 1"
        sql += " ORDER BY d.quality_score DESC"
        cur = self._conn_().execute(sql, (rpc_name,))
        return [dict(r) for r in cur.fetchall()]

    def docs_by_option(
        self, option_name: str, *, latest_only: bool = True
    ) -> list[Row]:
        sql = """
            SELECT DISTINCT d.doc_id, d.rel_path, d.title, d.doc_type,
                   d.app_code, d.pkg_ns, d.patch_id
            FROM documents d
            JOIN doc_options o ON o.doc_id = d.doc_id
            WHERE o.option_name = ?
        """
        if latest_only:
            sql += " AND d.is_latest = 1"
        sql += " ORDER BY d.quality_score DESC"
        cur = self._conn_().execute(sql, (option_name,))
        return [dict(r) for r in cur.fetchall()]

    def docs_by_global(
        self, global_name: str, *, latest_only: bool = True
    ) -> list[Row]:
        sql = """
            SELECT DISTINCT d.doc_id, d.rel_path, d.title, d.doc_type,
                   d.app_code, d.pkg_ns, d.patch_id
            FROM documents d
            JOIN doc_globals g ON g.doc_id = d.doc_id
            WHERE g.global_name = ?
        """
        if latest_only:
            sql += " AND d.is_latest = 1"
        sql += " ORDER BY d.quality_score DESC"
        cur = self._conn_().execute(sql, (global_name,))
        return [dict(r) for r in cur.fetchall()]

    def docs_by_file(
        self, file_number: str, *, latest_only: bool = True
    ) -> list[Row]:
        sql = """
            SELECT DISTINCT d.doc_id, d.rel_path, d.title, d.doc_type,
                   d.app_code, d.pkg_ns, d.patch_id
            FROM documents d
            JOIN doc_file_refs f ON f.doc_id = d.doc_id
            WHERE f.file_number = ?
        """
        if latest_only:
            sql += " AND d.is_latest = 1"
        sql += " ORDER BY d.quality_score DESC"
        cur = self._conn_().execute(sql, (str(file_number),))
        return [dict(r) for r in cur.fetchall()]

    def docs_by_patch(self, patch_id: str) -> list[Row]:
        """Documents bound to a specific patch_id (no latest filter)."""
        sql = """
            SELECT doc_id, rel_path, title, doc_type, app_code, pkg_ns,
                   patch_id, patch_ver, pub_date
            FROM documents
            WHERE patch_id = ?
            ORDER BY pub_date DESC
        """
        cur = self._conn_().execute(sql, (patch_id,))
        return [dict(r) for r in cur.fetchall()]

    # ── section lookup ─────────────────────────────────────────────

    def sections_mentioning_routine(self, routine: str) -> list[Row]:
        """Sections that mention the routine.

        Uses doc_routines (the curated extraction); for free-text
        search across all section bodies, use search_sections().
        """
        sql = """
            SELECT DISTINCT s.section_id, s.doc_id, s.heading, s.anchor,
                   s.level, s.word_count, d.title AS doc_title, d.rel_path
            FROM doc_sections s
            JOIN documents d ON d.doc_id = s.doc_id
            JOIN doc_routines r ON r.doc_id = d.doc_id
            WHERE r.routine = ?
            ORDER BY d.quality_score DESC, s.seq
        """
        cur = self._conn_().execute(sql, (routine,))
        return [dict(r) for r in cur.fetchall()]

    def search_sections(
        self,
        query: str,
        *,
        app_code: str | None = None,
        latest_only: bool = True,
        limit: int = 50,
    ) -> list[Row]:
        """Free-text search over section headings + bodies via FTS5.

        `query` is passed through to FTS5 MATCH. Callers should pre-quote
        phrase queries themselves.
        """
        sql = """
            SELECT s.section_id, s.doc_id, s.heading, s.anchor, s.level,
                   s.word_count, d.title AS doc_title, d.rel_path,
                   d.app_code, d.doc_type, d.is_latest, d.quality_score,
                   snippet(doc_sections_fts, 1, '[', ']', '…', 12) AS snippet
            FROM doc_sections_fts
            JOIN doc_sections s ON s.section_id = doc_sections_fts.rowid
            JOIN documents d ON d.doc_id = s.doc_id
            WHERE doc_sections_fts MATCH ?
        """
        params: list[Any] = [query]
        if app_code:
            sql += " AND d.app_code = ?"
            params.append(app_code)
        if latest_only:
            sql += " AND d.is_latest = 1"
        sql += " ORDER BY d.quality_score DESC, rank LIMIT ?"
        params.append(limit)
        cur = self._conn_().execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
