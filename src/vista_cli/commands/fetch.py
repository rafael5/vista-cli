"""vista fetch — download + verify + install a snapshot bundle."""

from __future__ import annotations

import json
from pathlib import Path

import click

from vista_cli.fetch import (
    DEFAULT_RELEASES_API,
    FetchError,
    fetch_and_install,
    list_remote_snapshots,
)


@click.command(name="fetch")
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
    help="Install from a local bundle instead of fetching (air-gapped).",
)
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Where to install (default: ~/data/vista/snapshot).",
)
@click.option(
    "--cache-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Where to cache the downloaded tarball (default: ~/data/vista/cache).",
)
@click.option("--list", "list_only", is_flag=True, help="List available snapshots.")
@click.option(
    "--releases-api",
    default=DEFAULT_RELEASES_API,
    help="GitHub Releases API URL (override for testing).",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
)
@click.pass_context
def fetch(
    ctx: click.Context,
    snapshot_version: str,
    from_path: Path | None,
    data_dir: Path | None,
    cache_dir: Path | None,
    list_only: bool,
    releases_api: str,
    fmt: str,
) -> None:
    """Download a snapshot bundle and install it locally."""
    if data_dir is None:
        data_dir = Path.home() / "data/vista/snapshot"
    if cache_dir is None:
        cache_dir = Path.home() / "data/vista/cache"

    if list_only:
        try:
            snapshots = list_remote_snapshots(releases_api=releases_api)
        except FetchError as e:
            click.echo(f"could not list snapshots: {e}", err=True)
            ctx.exit(1)
            return
        if fmt == "json":
            click.echo(json.dumps(snapshots, indent=2, sort_keys=True))
        else:
            if not snapshots:
                click.echo("(no snapshots published)")
            for s in snapshots:
                size_mb = s.get("size", 0) / 1_000_000
                click.echo(
                    f"{s['version']:>10}  {s.get('published_at', ''):<25}  "
                    f"{size_mb:6.1f} MB  {s.get('url', '')}"
                )
        return

    # Resolve which URL / file to install
    if from_path is not None:
        source: str = from_path.as_uri()
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
        click.echo(f"fetching snapshot {chosen['version']} from {source}")

    try:
        manifest = fetch_and_install(
            url=source, data_dir=data_dir, cache_dir=cache_dir
        )
    except FetchError as e:
        click.echo(f"fetch failed: {e}", err=True)
        ctx.exit(1)
        return

    click.echo(f"installed {manifest['snapshot_version']} → {data_dir}")


def _pick_snapshot(snapshots: list[dict], version: str) -> dict | None:
    if not snapshots:
        return None
    if version in ("latest", ""):
        return snapshots[0]
    for s in snapshots:
        if s.get("version") == version or s.get("tag") == version:
            return s
    return None
