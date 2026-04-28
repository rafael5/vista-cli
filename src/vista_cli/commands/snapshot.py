"""vista snapshot — create / verify / info bundle commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from vista_cli.config import Config
from vista_cli.format import json_out
from vista_cli.snapshot import (
    SnapshotError,
    create_bundle,
    info_bundle,
    install_bundle,
    verify_bundle,
)


@click.group(name="snapshot")
def snapshot() -> None:
    """Build and inspect portable data bundles."""


@snapshot.command(name="create")
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="Output path for the .tar.xz bundle.",
)
@click.option(
    "--snapshot-version",
    default=None,
    help="Snapshot version tag (default: today, calver YYYY.MM.DD).",
)
@click.option(
    "--vista-meta-commit",
    default="",
    help="Provenance: source commit of vista-meta.",
)
@click.option(
    "--vista-docs-commit",
    default="",
    help="Provenance: source commit of vista-docs.",
)
@click.option(
    "--vista-m-version",
    default="",
    help="Provenance: VistA-M release identifier.",
)
@click.pass_context
def snapshot_create(
    ctx: click.Context,
    out: Path,
    snapshot_version: str | None,
    vista_meta_commit: str,
    vista_docs_commit: str,
    vista_m_version: str,
) -> None:
    """Pack the configured stores into a portable .tar.xz bundle."""
    cfg: Config = ctx.obj["config"]
    if snapshot_version is None:
        from datetime import datetime, timezone

        snapshot_version = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    sources = {
        k: v
        for k, v in {
            "vista_meta_commit": vista_meta_commit,
            "vista_docs_commit": vista_docs_commit,
            "vista_m_version": vista_m_version,
        }.items()
        if v
    }
    try:
        manifest = create_bundle(
            out=out,
            code_model_dir=cfg.code_model_dir,
            data_model_dir=cfg.data_model_dir,
            doc_db=cfg.doc_db,
            snapshot_version=snapshot_version,
            sources=sources,
        )
    except SnapshotError as e:
        click.echo(f"snapshot create failed: {e}", err=True)
        ctx.exit(1)
        return
    click.echo(f"wrote {out}")
    click.echo(f"  version  {manifest['snapshot_version']}")
    click.echo(f"  built_at {manifest['built_at']}")
    click.echo(f"  sha256   {out}.sha256")


@snapshot.command(name="verify")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
)
@click.pass_context
def snapshot_verify(ctx: click.Context, path: Path, fmt: str) -> None:
    """Validate a bundle's structure and recompute its content hashes."""
    try:
        manifest = verify_bundle(path)
    except SnapshotError as e:
        click.echo(f"verify failed: {e}", err=True)
        ctx.exit(1)
        return
    if fmt == "json":
        click.echo(json_out.render(manifest))
    else:
        click.echo(f"ok: {path}")
        click.echo(f"  version  {manifest['snapshot_version']}")
        click.echo(f"  built_at {manifest['built_at']}")


@snapshot.command(name="info")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
)
@click.pass_context
def snapshot_info(ctx: click.Context, path: Path, fmt: str) -> None:
    """Print the embedded manifest without extracting data."""
    try:
        manifest = info_bundle(path)
    except SnapshotError as e:
        click.echo(f"info failed: {e}", err=True)
        ctx.exit(1)
        return
    if fmt == "json":
        click.echo(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        c = manifest["contents"]
        click.echo(f"version       {manifest['snapshot_version']}")
        click.echo(f"schema        {manifest['schema_version']}")
        click.echo(f"built_at      {manifest['built_at']}")
        srcs = manifest.get("sources") or {}
        if srcs:
            joined = ", ".join(f"{k}={v}" for k, v in srcs.items())
            click.echo(f"sources       {joined}")
        click.echo(
            f"code-model    {c['code_model']['files']} files, "
            f"{c['code_model']['rows']} rows"
        )
        click.echo(
            f"data-model    {c['data_model']['files']} files, "
            f"{c['data_model']['rows']} rows"
        )
        fdb = c["frontmatter_db"]
        click.echo(
            f"frontmatter   {fdb['rows_documents']} docs, "
            f"{fdb['rows_doc_sections']} sections, "
            f"fts5={'yes' if fdb['fts5_included'] else 'no'}"
        )


@snapshot.command(name="install")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Where to extract (default: ~/data/vista/snapshot).",
)
@click.pass_context
def snapshot_install(
    ctx: click.Context, path: Path, data_dir: Path | None
) -> None:
    """Install a local bundle into `data_dir`."""
    if data_dir is None:
        data_dir = Path.home() / "data/vista/snapshot"
    try:
        manifest = install_bundle(bundle=path, data_dir=data_dir)
    except SnapshotError as e:
        click.echo(f"install failed: {e}", err=True)
        ctx.exit(1)
        return
    click.echo(f"installed {manifest['snapshot_version']} → {data_dir}")
