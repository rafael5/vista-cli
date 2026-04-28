"""vista neighbors REF --depth N — graph walk around a routine."""

from __future__ import annotations

from typing import Any

import click

from vista_cli.config import Config
from vista_cli.format import json_out
from vista_cli.stores.code_view import make_code_view
from vista_cli.stores.data_model import DataModelStore
from vista_cli.stores.joined import neighbors as walk


@click.command()
@click.argument("ref")
@click.option("--depth", default=1, show_default=True, type=int)
@click.option("--top", "top_n", default=5, show_default=True, type=int)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json"]),
    default="md",
)
@click.pass_context
def neighbors(
    ctx: click.Context,
    ref: str,
    depth: int,
    top_n: int,
    fmt: str,
) -> None:
    """Show callees, sibling routines, and same-data routines around REF."""
    cfg: Config = ctx.obj["config"]
    allow_cache = ctx.obj.get("allow_cache", True)
    view = make_code_view(
        code_model_dir=cfg.code_model_dir,
        cache_db=cfg.cache_db,
        doc_db=cfg.doc_db,
        allow_cache=allow_cache,
    )
    dms_data = DataModelStore(cfg.data_model_dir)

    if view.routine(ref) is None:
        click.echo(f"Routine '{ref}' not found.", err=True)
        ctx.exit(1)
        return

    info = walk(view, dms_data, ref, depth=depth, top_n=top_n)

    if fmt == "json":
        click.echo(json_out.render(info))
    else:
        click.echo(_render_md(info, depth=depth), nl=False)


def _render_md(info: dict[str, Any], *, depth: int) -> str:
    lines = [f"# {info['root']} — neighbors (depth {depth})", ""]
    if info.get("package"):
        lines.append(f"_package: {info['package']}_")
        lines.append("")

    callees = info.get("callees") or []
    if callees:
        lines.append("## Callees (depth 1)")
        lines.append("")
        for c in callees:
            tag = c.get("callee_tag", "")
            rtn = c.get("callee_routine", "")
            ref = f"{tag}^{rtn}" if tag else f"^{rtn}"
            lines.append(
                f"- `{ref}` ({c.get('kind', '')}) ×{c.get('ref_count', 0)}"
            )
        lines.append("")

    deeper = info.get("callees_depth_2") or []
    if deeper:
        lines.append("## Callees of callees (depth 2)")
        lines.append("")
        for c in deeper:
            via = c.get("via", "?")
            tgt = c.get("callee_routine", "?")
            lines.append(f"- `{tgt}` (via `{via}`) ×{c.get('ref_count', 0)}")
        lines.append("")

    siblings = info.get("siblings") or []
    if siblings:
        lines.append("## Same-package siblings (by call cohesion)")
        lines.append("")
        for s in siblings:
            lines.append(
                f"- `{s['routine_name']}` shared callees: "
                f"{s['shared_callee_count']}"
            )
        lines.append("")

    same_data = info.get("same_data") or []
    if same_data:
        lines.append("## Same-data routines (touching the same globals)")
        lines.append("")
        for r in same_data:
            shared = ", ".join(f"^{g}" for g in r.get("shared_globals", []))
            lines.append(
                f"- `{r['routine_name']}` [{r['package']}] "
                f"×{r['ref_count']} (shares: {shared})"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
