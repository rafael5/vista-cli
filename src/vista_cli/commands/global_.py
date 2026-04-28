"""vista global NAME — global usages across routines + docs.

`global` is a Python reserved word, so the module is global_; the
Click command stays "global".
"""

from __future__ import annotations

from typing import Any

import click

from vista_cli.config import Config
from vista_cli.format import json_out, tsv_out
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.doc_model import DocModelStore

_TOP_N = 25
_DOC_TSV_COLUMNS = ("doc_id", "doc_type", "app_code", "patch_id", "title", "rel_path")


@click.command(name="global")
@click.argument("name")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json", "tsv"]),
    default="md",
)
@click.option("--no-docs", is_flag=True)
@click.option("--all-versions", is_flag=True)
@click.pass_context
def global_cmd(
    ctx: click.Context,
    name: str,
    fmt: str,
    no_docs: bool,
    all_versions: bool,
) -> None:
    """Show routines that touch a global and docs that mention it."""
    bare = name.lstrip("^").rstrip("(")
    cfg: Config = ctx.obj["config"]
    cms = CodeModelStore(cfg.code_model_dir)
    routines = cms.routines_using_global(bare)

    if not routines and bare not in {r.get("global_name", "") for r in routines}:
        # Still emit a result with empty routines if the doc store knows it.
        pass

    info: dict[str, Any] = {
        "global_name": bare,
        "routines": routines,
        "routine_count": len(routines),
        "total_refs": sum(_i(r.get("ref_count", "0")) for r in routines),
        "docs": [],
    }

    if not no_docs and cfg.doc_db.exists():
        dms = DocModelStore(cfg.doc_db)
        try:
            info["docs"] = dms.docs_by_global(bare, latest_only=not all_versions)
        finally:
            dms.close()

    if not routines and not info["docs"]:
        click.echo(f"Global '^{bare}' not referenced in either store.", err=True)
        ctx.exit(1)
        return

    if fmt == "json":
        click.echo(json_out.render(info))
    elif fmt == "tsv":
        click.echo(tsv_out.render_rows(info["docs"], _DOC_TSV_COLUMNS), nl=False)
    else:
        click.echo(_render_md(info), nl=False)


def _render_md(info: dict[str, Any]) -> str:
    name = info["global_name"]
    lines = [f"# Global `^{name}`", ""]
    lines.append(
        f"{info['routine_count']} routine(s) · {info['total_refs']} total ref(s)"
    )
    lines.append("")
    routines = info.get("routines") or []
    if routines:
        lines.append("## Top routines using this global")
        lines.append("")
        for r in routines[:_TOP_N]:
            lines.append(
                f"- `{r.get('routine_name', '?')}` "
                f"[{r.get('package', '?')}] ×{r.get('ref_count', '0')}"
            )
        lines.append("")
    docs = info.get("docs") or []
    lines.append("## Documentation")
    lines.append("")
    if not docs:
        lines.append("_No VDL documentation references this global._")
    else:
        for d in docs:
            patch = d.get("patch_id") or ""
            patch_s = f" (patch {patch})" if patch else ""
            lines.append(
                f"- **[{d.get('doc_type', '?')}]** "
                f"{d.get('title', '?')}{patch_s}"
            )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _i(s: Any) -> int:
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0
