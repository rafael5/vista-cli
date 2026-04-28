"""Build tests/fixtures/frontmatter.db — a tiny mirror of the
vista-docs production schema with 3 representative documents.

Run from the project root:
    python tests/fixtures/build_fixture_db.py

Schema mirrors what's in ~/data/vista-docs/state/frontmatter.db.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "frontmatter.db"


def build() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # documents table — schema verified against production
    cur.execute(
        """
        CREATE TABLE documents (
            doc_id INTEGER PRIMARY KEY,
            rel_path TEXT UNIQUE NOT NULL,
            title TEXT, doc_type TEXT, doc_label TEXT, doc_layer TEXT,
            app_code TEXT, app_name TEXT, section TEXT, app_status TEXT,
            pkg_ns TEXT, patch_ver TEXT, patch_id TEXT, group_key TEXT,
            word_count INTEGER, page_count INTEGER, is_stub INTEGER,
            pub_date TEXT, docx_url TEXT, pdf_url TEXT,
            menu_options INTEGER, audit_applied TEXT,
            description TEXT, audience TEXT,
            patch_num_int INTEGER, is_latest INTEGER DEFAULT 0,
            quality_score INTEGER DEFAULT 0
        )
        """
    )
    cur.execute("CREATE INDEX idx_doc_app ON documents(app_code)")
    cur.execute("CREATE INDEX idx_doc_pkg ON documents(pkg_ns)")
    cur.execute("CREATE INDEX idx_doc_section ON documents(section)")

    cur.execute(
        """
        CREATE TABLE doc_routines (
            doc_id INTEGER NOT NULL,
            routine TEXT NOT NULL,
            tag TEXT NOT NULL DEFAULT '',
            full_ref TEXT NOT NULL,
            PRIMARY KEY(doc_id, full_ref)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE doc_globals (
            doc_id INTEGER NOT NULL,
            global_name TEXT NOT NULL,
            PRIMARY KEY(doc_id, global_name)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE doc_rpcs (
            doc_id INTEGER NOT NULL,
            rpc_name TEXT NOT NULL,
            PRIMARY KEY(doc_id, rpc_name)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE doc_options (
            doc_id INTEGER NOT NULL,
            option_name TEXT NOT NULL,
            PRIMARY KEY(doc_id, option_name)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE doc_file_refs (
            doc_id INTEGER NOT NULL,
            file_number TEXT NOT NULL,
            PRIMARY KEY(doc_id, file_number)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE doc_sections (
            section_id INTEGER PRIMARY KEY,
            doc_id INTEGER NOT NULL,
            parent_section_id INTEGER,
            level INTEGER NOT NULL,
            seq INTEGER NOT NULL,
            heading TEXT NOT NULL,
            anchor TEXT NOT NULL,
            char_start INTEGER,
            char_end INTEGER,
            word_count INTEGER,
            body TEXT,
            FOREIGN KEY(doc_id) REFERENCES documents(doc_id)
        )
        """
    )

    # 3 docs all referencing PRCA45PT
    docs = [
        (
            1,
            "publish/financial-administrative/prca--ar/technical-manual.md",
            "AR Technical Manual & Security Guide v4.5",
            "TM",
            "Technical Manual",
            "tech",
            "PRCA",
            "Accounts Receivable",
            "financial-administrative",
            "active",
            "PRCA",
            "4.5",
            "PRCA*4.5*409",
            "prca-tm",
            12000,
            240,
            0,
            "2018-08-01",
            None,
            None,
            8,
            None,
            None,
            "developer",
            409,
            1,
            85,
        ),
        (
            2,
            "publish/financial-administrative/prca--ar/installation-guide.md",
            "AR Installation Guide (PRCA*4.5*341)",
            "IG",
            "Installation Guide",
            "install",
            "PRCA",
            "Accounts Receivable",
            "financial-administrative",
            "active",
            "PRCA",
            "4.5",
            "PRCA*4.5*341",
            "prca-ig",
            5400,
            54,
            0,
            "2018-08-01",
            None,
            None,
            0,
            None,
            None,
            "installer",
            341,
            0,
            70,
        ),
        (
            3,
            "publish/financial-administrative/prca--ar/user-manual--supervisor.md",
            "AR User Manual — Supervisor's AR Menu",
            "UM",
            "User Manual",
            "user",
            "PRCA",
            "Accounts Receivable",
            "financial-administrative",
            "active",
            "PRCA",
            "4.5",
            None,
            "prca-um-sup",
            8200,
            120,
            0,
            "2017-04-01",
            None,
            None,
            12,
            None,
            None,
            "supervisor",
            None,
            1,
            80,
        ),
    ]
    cur.executemany(f"INSERT INTO documents VALUES ({','.join('?' * 27)})", docs)

    # Routine references
    cur.executemany(
        "INSERT INTO doc_routines VALUES (?, ?, ?, ?)",
        [
            (1, "PRCA45PT", "", "PRCA45PT"),
            (1, "PRCA45PT", "EN", "EN^PRCA45PT"),
            (2, "PRCA45PT", "", "PRCA45PT"),
            (3, "PRCA45PT", "EN", "EN^PRCA45PT"),
            # PRCAACT intentionally not in doc_routines so coverage
            # reports a 1/2 documented split for the AR package fixture.
        ],
    )
    cur.executemany(
        "INSERT INTO doc_globals VALUES (?, ?)",
        [(1, "PRCA"), (3, "PRCA")],
    )
    cur.executemany(
        "INSERT INTO doc_options VALUES (?, ?)",
        [(3, "PRCA PURGE EXEMPT BILL FILES")],
    )
    cur.executemany(
        "INSERT INTO doc_rpcs VALUES (?, ?)",
        [(1, "PRCA AR LIST"), (3, "PRCA AR LIST")],
    )
    cur.executemany(
        "INSERT INTO doc_file_refs VALUES (?, ?)",
        [(1, "430"), (2, "430"), (3, "430")],
    )

    # A few sections; one of them mentions PRCA45PT in its body
    cur.executemany(
        """
        INSERT INTO doc_sections (
            section_id, doc_id, parent_section_id, level, seq,
            heading, anchor, char_start, char_end, word_count, body
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                10,
                1,
                None,
                1,
                1,
                "Purge Routines",
                "purge-routines",
                0,
                400,
                65,
                "PRCA45PT purges exempt bill files. Run from the cleanup menu.",
            ),
            (
                11,
                2,
                None,
                1,
                1,
                "Pre-installation purge",
                "pre-installation-purge",
                0,
                300,
                40,
                "Run PRCA45PT before installing the patch.",
            ),
            (
                12,
                3,
                None,
                1,
                1,
                "Exempt Bill Cleanup",
                "exempt-bill-cleanup",
                0,
                250,
                30,
                "Use the PRCA PURGE EXEMPT BILL FILES menu option.",
            ),
        ],
    )

    # FTS5 mirror of doc_sections (heading + body) — production schema.
    cur.execute(
        """
        CREATE VIRTUAL TABLE doc_sections_fts USING fts5(
            heading, body,
            content='doc_sections',
            content_rowid='section_id',
            tokenize='porter unicode61'
        )
        """
    )
    cur.execute(
        "INSERT INTO doc_sections_fts(rowid, heading, body) "
        "SELECT section_id, heading, body FROM doc_sections"
    )

    conn.commit()
    conn.close()
    print(f"Built {DB_PATH}")


if __name__ == "__main__":
    build()
    sys.exit(0)
