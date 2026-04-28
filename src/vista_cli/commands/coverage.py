"""vista coverage --pkg PKG — doc-coverage report."""

from __future__ import annotations

from typing import Any

import click

from vista_cli.canonical import resolve_package
from vista_cli.config import Config
from vista_cli.format import json_out
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.doc_model import DocModelStore
from vista_cli.stores.joined import package_coverage

_TOP_UNDOCUMENTED = 25


@click.command()
@click.option(
    "--pkg",
    "package",
    required=True,
    help="Package directory, ns, or app_code.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json"]),
    default="md",
)
@click.option("--all-versions", is_flag=True)
@click.pass_context
def coverage(
    ctx: click.Context,
    package: str,
    fmt: str,
    all_versions: bool,
) -> None:
    """Show how much of a package is covered by VDL documentation."""
    cfg: Config = ctx.obj["config"]
    pkg_id = resolve_package(package)
    if pkg_id is None:
        click.echo(f"Package '{package}' not in canonical map.", err=True)
        ctx.exit(1)
        return

    cms = CodeModelStore(cfg.code_model_dir)
    if not cfg.doc_db.exists():
        click.echo(f"doc DB missing: {cfg.doc_db}", err=True)
        ctx.exit(1)
        return

    dms = DocModelStore(cfg.doc_db)
    try:
        info = package_coverage(cms, dms, pkg_id, latest_only=not all_versions)
    finally:
        dms.close()

    if fmt == "json":
        click.echo(json_out.render(info))
    else:
        click.echo(_render_md(info), nl=False)


def _render_md(info: dict[str, Any]) -> str:
    name = info.get("package", "?")
    ns = info.get("namespace") or "?"
    app = info.get("app_code") or "?"
    lines = [f"# coverage: {name} (ns={ns}, app={app})", ""]

    rt = info["routines"]
    pct = _pct(rt["documented"], rt["total"])
    lines.append(f"- routines: {rt['documented']}/{rt['total']} ({pct})")
    rp = info["rpcs"]
    lines.append(
        f"- rpcs:     {rp['documented']}/{rp['total']} "
        f"({_pct(rp['documented'], rp['total'])})"
    )
    op = info["options"]
    lines.append(
        f"- options:  {op['documented']}/{op['total']} "
        f"({_pct(op['documented'], op['total'])})"
    )
    lines.append("")

    undoc = rt.get("undocumented") or []
    if undoc:
        lines.append("## Top undocumented routines (by in-degree)")
        lines.append("")
        for r in undoc[:_TOP_UNDOCUMENTED]:
            lines.append(
                f"- `{r['routine_name']}` "
                f"in={r['in_degree']} · out={r['out_degree']} · "
                f"{r['line_count']} lines"
            )
    return "\n".join(lines).rstrip() + "\n"


def _pct(documented: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{(100 * documented) // total}%"
