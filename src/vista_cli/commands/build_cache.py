"""vista build-cache — materialise the joined manifest at cache_db."""

from __future__ import annotations

import time

import click

from vista_cli.config import Config
from vista_cli.stores.cache import build


@click.command(name="build-cache")
@click.option(
    "--out",
    "out_path",
    default=None,
    help="Override cache path (defaults to $VISTA_CACHE_DB).",
)
@click.pass_context
def build_cache(ctx: click.Context, out_path: str | None) -> None:
    """Build the joined SQLite manifest from vista-meta + vista-docs."""
    cfg: Config = ctx.obj["config"]
    target = (
        click.format_filename(out_path) if out_path else cfg.cache_db
    )
    from pathlib import Path

    target = Path(target) if not isinstance(target, Path) else target

    if not cfg.code_model_dir.exists():
        click.echo(f"code-model dir missing: {cfg.code_model_dir}", err=True)
        ctx.exit(1)
        return

    click.echo(f"Building cache → {target}")
    t0 = time.monotonic()
    counts = build(
        cache_db=target,
        code_model_dir=cfg.code_model_dir,
        data_model_dir=cfg.data_model_dir,
        doc_db=cfg.doc_db,
    )
    elapsed = time.monotonic() - t0
    for name, n in sorted(counts.items()):
        click.echo(f"  {name:<28} {n:>10,}")
    click.echo(f"Done in {elapsed:.1f}s.")
