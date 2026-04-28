"""vista routine RTN — code facts joined with documentation refs."""

from __future__ import annotations

from typing import Any

import click

from vista_cli.canonical import resolve_package
from vista_cli.config import Config
from vista_cli.format import json_out, markdown
from vista_cli.stores.code_view import make_code_view
from vista_cli.stores.doc_model import DocModelStore


@click.command()
@click.argument("name")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json"]),
    default="md",
    help="Output format.",
)
@click.option(
    "--no-docs",
    is_flag=True,
    help="Skip the documentation join (vista-meta only).",
)
@click.option(
    "--all-versions",
    is_flag=True,
    help="Include doc references from non-latest patch versions.",
)
@click.pass_context
def routine(
    ctx: click.Context, name: str, fmt: str, no_docs: bool, all_versions: bool
) -> None:
    """Show code facts and documentation refs for a routine."""
    cfg: Config = ctx.obj["config"]
    allow_cache = ctx.obj.get("allow_cache", True)
    info = _build_info(
        name,
        cfg,
        with_docs=not no_docs,
        latest_only=not all_versions,
        allow_cache=allow_cache,
    )
    if info is None:
        click.echo(f"Routine '{name}' not found in code-model TSVs.", err=True)
        ctx.exit(1)
        return

    if fmt == "json":
        click.echo(json_out.render(info))
    else:
        click.echo(markdown.render_routine(info), nl=False)


def _build_info(
    name: str,
    cfg: Config,
    *,
    with_docs: bool,
    latest_only: bool = True,
    allow_cache: bool = True,
) -> dict[str, Any] | None:
    view = make_code_view(
        code_model_dir=cfg.code_model_dir,
        cache_db=cfg.cache_db,
        doc_db=cfg.doc_db,
        allow_cache=allow_cache,
    )
    row = view.routine(name)
    if row is None:
        return None

    pkg = row.get("package", "")
    pkg_id = resolve_package(pkg)

    info: dict[str, Any] = {
        "routine_name": row.get("routine_name", ""),
        "package": pkg,
        "package_ns": pkg_id.ns if pkg_id else None,
        "package_app_code": pkg_id.app_code if pkg_id else None,
        "source_path": row.get("source_path", ""),
        "line_count": _i(row.get("line_count")),
        "in_degree": _i(row.get("in_degree")),
        "out_degree": _i(row.get("out_degree")),
        "rpc_count": _i(row.get("rpc_count")),
        "option_count": _i(row.get("option_count")),
        "version_line": row.get("version_line", ""),
        "callees": view.callees(name),
        "callers": view.callers(name),
        "globals": view.globals_for(name),
        "xindex": view.xindex_errors(name),
        "rpcs": view.rpcs_in_routine(name),
        "options": view.options_in_routine(name),
        "docs": [],
    }

    if with_docs and cfg.doc_db.exists():
        try:
            dms = DocModelStore(cfg.doc_db)
            info["docs"] = dms.docs_by_routine(name, latest_only=latest_only)
            dms.close()
        except Exception as e:  # noqa: BLE001
            # Doc store failure is non-fatal — code facts still useful
            info["docs"] = []
            info["docs_error"] = str(e)

    return info


def _i(s: Any) -> int:
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0
