"""vista doctor — health check on both data stores."""

from __future__ import annotations

import sqlite3

import click

from vista_cli.config import Config
from vista_cli.stores.cache import CacheStore


@click.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Check that both data stores are reachable and well-formed."""
    cfg: Config = ctx.obj["config"]
    failures = 0

    # Code-model directory
    failures += _check_path("code-model dir", cfg.code_model_dir, must_exist=True)
    failures += _check_path(
        "  routines-comprehensive.tsv",
        cfg.code_model_dir / "routines-comprehensive.tsv",
        must_exist=True,
    )
    failures += _check_path(
        "  routine-calls.tsv",
        cfg.code_model_dir / "routine-calls.tsv",
        must_exist=True,
    )

    # Data-model directory
    failures += _check_path("data-model dir", cfg.data_model_dir, must_exist=False)

    # vista-m-host
    failures += _check_path("vista-m-host", cfg.vista_m_host, must_exist=False)

    # Doc DB
    failures += _check_path("doc DB", cfg.doc_db, must_exist=True)
    if cfg.doc_db.exists():
        failures += _check_doc_db(cfg.doc_db)

    # Doc publish tree
    failures += _check_path("doc publish dir", cfg.doc_publish_dir, must_exist=False)

    # Joined cache (optional)
    _check_cache(cfg)

    # Installed snapshot (optional)
    _check_snapshot(cfg)

    if failures:
        click.echo()
        click.echo(f"FAIL — {failures} check(s) did not pass", err=True)
        ctx.exit(1)
    click.echo()
    click.echo("OK — all checks passed")


def _check_snapshot(cfg: Config) -> None:
    """Report on a `snapshot.json` if one sits alongside the data dir.

    The bootstrap installs at `<data-dir>/snapshot.json`. If the user's
    `code_model_dir` is under that tree, the manifest tells us version
    + provenance for the doctor report.
    """
    # Walk up the code_model_dir looking for a sibling snapshot.json.
    candidate = None
    for parent in (cfg.code_model_dir.parent, cfg.code_model_dir.parent.parent):
        if parent and (parent / "snapshot.json").exists():
            candidate = parent / "snapshot.json"
            break
    if candidate is None:
        return
    try:
        import json

        manifest = json.loads(candidate.read_text())
    except (OSError, ValueError):
        return
    version = manifest.get("snapshot_version", "?")
    built_at = manifest.get("built_at", "?")
    click.echo(f"  [ok] snapshot {version} (built {built_at})")


def _check_cache(cfg: Config) -> None:
    if not cfg.cache_db.exists():
        click.echo(
            f"  [warn] joined cache: {cfg.cache_db} — not built "
            "(run `vista build-cache`)"
        )
        return
    cache = CacheStore(cfg.cache_db)
    try:
        built_at = cache.meta("built_at") or "?"
        stale, reasons = cache.is_stale(
            code_model_dir=cfg.code_model_dir, doc_db=cfg.doc_db
        )
    except sqlite3.Error as e:
        click.echo(f"  [warn] joined cache unreadable: {e}")
        cache.close()
        return
    cache.close()
    if stale:
        click.echo(
            f"  [warn] joined cache built {built_at} — stale "
            f"({'; '.join(reasons)})"
        )
    else:
        click.echo(f"  [ok] joined cache: {cfg.cache_db} (built {built_at})")


def _check_path(label: str, path, *, must_exist: bool) -> int:
    if path.exists():
        click.echo(f"  [ok] {label}: {path}")
        return 0
    if must_exist:
        click.echo(f"  [!!] {label}: {path} — missing", err=True)
        return 1
    click.echo(f"  [warn] {label}: {path} — not present (optional)")
    return 0


def _check_doc_db(path) -> int:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        cur = conn.execute("SELECT COUNT(*) FROM documents WHERE is_latest = 1")
        n_latest = cur.fetchone()[0]
        cur = conn.execute("SELECT COUNT(*) FROM doc_routines")
        n_links = cur.fetchone()[0]
        conn.close()
        click.echo(
            f"  [ok] doc DB content: {n_latest} latest docs, {n_links} routine refs"
        )
        return 0
    except sqlite3.Error as e:
        click.echo(f"  [!!] doc DB unreadable: {e}", err=True)
        return 1
