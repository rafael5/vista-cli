"""vista option NAME — option/menu metadata + docs that mention it."""

from __future__ import annotations

from typing import Any

import click

from vista_cli.completion import complete_option
from vista_cli.config import Config
from vista_cli.format import json_out, tsv_out
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.doc_model import DocModelStore
from vista_cli.suggestions import did_you_mean

_DOC_TSV_COLUMNS = ("doc_id", "doc_type", "app_code", "patch_id", "title", "rel_path")


@click.command()
@click.argument("name", shell_complete=complete_option)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json", "tsv"]),
    default="md",
)
@click.option("--no-docs", is_flag=True)
@click.option("--all-versions", is_flag=True)
@click.pass_context
def option(
    ctx: click.Context,
    name: str,
    fmt: str,
    no_docs: bool,
    all_versions: bool,
) -> None:
    """Show an option: type, entry routine + tag, package, and docs."""
    cfg: Config = ctx.obj["config"]
    cms = CodeModelStore(cfg.code_model_dir)
    row = cms.option(name)
    if row is None:
        click.echo(f"Option '{name}' not found in options.tsv.", err=True)
        suggestions = did_you_mean(
            name, [o.get("name", "") for o in cms.all_options()]
        )
        if suggestions:
            click.echo(f"Did you mean: {', '.join(suggestions)}?", err=True)
        ctx.exit(1)
        return

    info: dict[str, Any] = {
        "name": row.get("name", ""),
        "menu_text": row.get("menu_text", ""),
        "type": row.get("type", ""),
        "package": row.get("package", ""),
        "routine": row.get("routine", ""),
        "tag": row.get("tag", ""),
        "docs": [],
    }

    if not no_docs and cfg.doc_db.exists():
        dms = DocModelStore(cfg.doc_db)
        try:
            info["docs"] = dms.docs_by_option(name, latest_only=not all_versions)
        finally:
            dms.close()

    if fmt == "json":
        click.echo(json_out.render(info))
    elif fmt == "tsv":
        click.echo(tsv_out.render_rows(info["docs"], _DOC_TSV_COLUMNS), nl=False)
    else:
        click.echo(_render_md(info), nl=False)


def _render_md(info: dict[str, Any]) -> str:
    lines = [f"# OPTION `{info['name']}`", ""]
    if info.get("menu_text"):
        lines.append(f"_{info['menu_text']}_")
        lines.append("")
    bits = []
    if info.get("type"):
        bits.append(f"type: {info['type']}")
    if info.get("routine"):
        ref = (
            f"{info['tag']}^{info['routine']}"
            if info.get("tag")
            else f"^{info['routine']}"
        )
        bits.append(f"entry: `{ref}`")
    if info.get("package"):
        bits.append(f"package: {info['package']}")
    if bits:
        lines.append(" · ".join(bits))
        lines.append("")

    docs = info.get("docs") or []
    lines.append("## Documentation")
    lines.append("")
    if not docs:
        lines.append("_No VDL documentation references this option._")
    else:
        for d in docs:
            patch = d.get("patch_id") or ""
            patch_s = f" (patch {patch})" if patch else ""
            lines.append(
                f"- **[{d.get('doc_type', '?')}]** "
                f"{d.get('title', '?')}{patch_s}"
            )
            if d.get("rel_path"):
                lines.append(f"  `{d['rel_path']}`")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
