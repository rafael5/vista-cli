"""vista patch ID — KIDS patch overview joined to routines + docs."""

from __future__ import annotations

from typing import Any

import click

from vista_cli.config import Config
from vista_cli.format import json_out, tsv_out
from vista_cli.stores.code_view import make_code_view
from vista_cli.stores.doc_model import DocModelStore

_DOC_TSV_COLUMNS = ("doc_id", "doc_type", "app_code", "patch_id", "title", "rel_path")


@click.command()
@click.argument("patch_id")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json", "tsv"]),
    default="md",
)
@click.option("--no-docs", is_flag=True)
@click.pass_context
def patch(
    ctx: click.Context,
    patch_id: str,
    fmt: str,
    no_docs: bool,
) -> None:
    """Show routines patched + docs bound to this KIDS patch_id."""
    cfg: Config = ctx.obj["config"]
    allow_cache = ctx.obj.get("allow_cache", True)
    view = make_code_view(
        code_model_dir=cfg.code_model_dir,
        cache_db=cfg.cache_db,
        doc_db=cfg.doc_db,
        allow_cache=allow_cache,
    )
    routines = view.routines_for_patch(patch_id)

    info: dict[str, Any] = {
        "patch_id": patch_id,
        "routines": [
            {
                "routine_name": r.get("routine_name", ""),
                "package": r.get("package", ""),
                "line_count": _i(r.get("line_count", "0")),
            }
            for r in routines
        ],
        "routine_count": len(routines),
        "docs": [],
    }

    if not no_docs and cfg.doc_db.exists():
        dms = DocModelStore(cfg.doc_db)
        try:
            info["docs"] = dms.docs_by_patch(patch_id)
        finally:
            dms.close()

    if not routines and not info["docs"]:
        click.echo(f"Patch '{patch_id}' not referenced in either store.", err=True)
        ctx.exit(1)
        return

    if fmt == "json":
        click.echo(json_out.render(info))
    elif fmt == "tsv":
        click.echo(tsv_out.render_rows(info["docs"], _DOC_TSV_COLUMNS), nl=False)
    else:
        click.echo(_render_md(info), nl=False)


def _render_md(info: dict[str, Any]) -> str:
    pid = info["patch_id"]
    lines = [f"# Patch `{pid}`", ""]
    lines.append(f"{info['routine_count']} routine(s) carry this patch in line-2.")
    lines.append("")
    routines = info.get("routines") or []
    if routines:
        lines.append("## Routines patched")
        lines.append("")
        for r in routines:
            lines.append(
                f"- `{r['routine_name']}` "
                f"[{r['package']}] · {r['line_count']} lines"
            )
        lines.append("")
    docs = info.get("docs") or []
    lines.append("## Documentation")
    lines.append("")
    if not docs:
        lines.append("_No VDL documents bound to this patch_id._")
    else:
        for d in docs:
            lines.append(f"- **[{d.get('doc_type', '?')}]** {d.get('title', '?')}")
            if d.get("rel_path"):
                lines.append(f"  `{d['rel_path']}`")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _i(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
