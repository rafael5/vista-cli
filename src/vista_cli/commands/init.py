"""vista init — idempotent bootstrap of the data stores.

If usable data already exists at the configured paths, prints what's
there and exits cleanly — never overwrites a user's own
vista-meta/vista-docs install. Otherwise, fetches a snapshot bundle
(or installs from `--from`) and runs `build-cache`.
"""

from __future__ import annotations

from pathlib import Path

import click

from vista_cli.config import Config
from vista_cli.fetch import (
    DEFAULT_RELEASES_API,
    FetchError,
    fetch_and_install,
    list_remote_snapshots,
)
from vista_cli.stores.cache import build as build_cache_fn


@click.command(name="init")
@click.option(
    "--snapshot",
    "snapshot_version",
    default="latest",
    help="Snapshot version to fetch (default: latest).",
)
@click.option(
    "--from",
    "from_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Install from a local bundle (air-gapped).",
)
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Where to install the snapshot (default: ~/data/vista/snapshot).",
)
@click.option(
    "--force",
    is_flag=True,
    help="Reinstall even when data is already present.",
)
@click.option(
    "--releases-api",
    default=DEFAULT_RELEASES_API,
    help="GitHub Releases API URL (override for testing).",
)
@click.pass_context
def init_cmd(
    ctx: click.Context,
    snapshot_version: str,
    from_path: Path | None,
    data_dir: Path | None,
    force: bool,
    releases_api: str,
) -> None:
    """Bootstrap vista-cli's data stores from a snapshot bundle."""
    cfg: Config = ctx.obj["config"]

    if not force and _stores_already_usable(cfg):
        click.echo("vista-cli data already present:")
        click.echo(f"  code-model:  {cfg.code_model_dir}")
        click.echo(f"  doc-db:      {cfg.doc_db}")
        click.echo("(use --force to reinstall)")
        return

    if data_dir is None:
        data_dir = Path.home() / "data/vista/snapshot"
    cache_dir = Path.home() / "data/vista/cache"

    if from_path is not None:
        source = from_path.as_uri()
    else:
        try:
            snapshots = list_remote_snapshots(releases_api=releases_api)
        except FetchError as e:
            click.echo(f"could not query releases: {e}", err=True)
            ctx.exit(1)
            return
        chosen = _pick_snapshot(snapshots, snapshot_version)
        if chosen is None:
            click.echo(
                f"no snapshot found for version {snapshot_version!r}",
                err=True,
            )
            ctx.exit(1)
            return
        source = chosen["url"]
        click.echo(f"fetching snapshot {chosen['version']}")

    try:
        manifest = fetch_and_install(
            url=source, data_dir=data_dir, cache_dir=cache_dir
        )
    except FetchError as e:
        click.echo(f"install failed: {e}", err=True)
        ctx.exit(1)
        return

    click.echo(f"installed {manifest['snapshot_version']} → {data_dir}")
    click.echo("")
    click.echo("hint: point env vars at the new install:")
    click.echo(f"  export VISTA_CODE_MODEL={data_dir}/code-model")
    click.echo(f"  export VISTA_DATA_MODEL={data_dir}/data-model")
    click.echo(f"  export VISTA_DOC_DB={data_dir}/frontmatter.db")

    # Build cache against the freshly-installed paths.
    code_model = data_dir / "code-model"
    data_model = data_dir / "data-model"
    doc_db = data_dir / "frontmatter.db"
    if code_model.exists() and doc_db.exists():
        try:
            counts = build_cache_fn(
                cache_db=cfg.cache_db,
                code_model_dir=code_model,
                data_model_dir=data_model,
                doc_db=doc_db,
            )
            click.echo(
                f"built cache → {cfg.cache_db}  "
                f"({sum(counts.values())} rows across {len(counts)} tables)"
            )
        except Exception as e:  # noqa: BLE001
            click.echo(f"warning: cache build failed: {e}", err=True)


def _stores_already_usable(cfg: Config) -> bool:
    return cfg.code_model_dir.exists() and cfg.doc_db.exists()


def _pick_snapshot(snapshots: list[dict], version: str) -> dict | None:
    if not snapshots:
        return None
    if version in ("latest", ""):
        return snapshots[0]
    for s in snapshots:
        if s.get("version") == version or s.get("tag") == version:
            return s
    return None
