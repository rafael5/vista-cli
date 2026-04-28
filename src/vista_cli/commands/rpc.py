"""vista rpc NAME — RPC definition + every doc that mentions it."""

from __future__ import annotations

from typing import Any

import click

from vista_cli.config import Config
from vista_cli.format import json_out, tsv_out
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.doc_model import DocModelStore

_DOC_TSV_COLUMNS = ("doc_id", "doc_type", "app_code", "patch_id", "title", "rel_path")


@click.command()
@click.argument("name")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json", "tsv"]),
    default="md",
)
@click.option("--no-docs", is_flag=True, help="Skip the documentation join.")
@click.option("--all-versions", is_flag=True, help="Include non-latest doc references.")
@click.pass_context
def rpc(
    ctx: click.Context,
    name: str,
    fmt: str,
    no_docs: bool,
    all_versions: bool,
) -> None:
    """Show an RPC: tag, source routine, return-type, and docs."""
    cfg: Config = ctx.obj["config"]
    cms = CodeModelStore(cfg.code_model_dir)
    row = cms.rpc(name)
    if row is None:
        click.echo(f"RPC '{name}' not found in rpcs.tsv.", err=True)
        ctx.exit(1)
        return

    info: dict[str, Any] = {
        "name": row.get("name", ""),
        "tag": row.get("tag", ""),
        "routine": row.get("routine", ""),
        "return_type": row.get("return_type", ""),
        "availability": row.get("availability", ""),
        "inactive": row.get("inactive", ""),
        "version": row.get("version", ""),
        "package": row.get("package", ""),
        "docs": [],
    }

    if not no_docs and cfg.doc_db.exists():
        dms = DocModelStore(cfg.doc_db)
        try:
            info["docs"] = dms.docs_by_rpc(name, latest_only=not all_versions)
        finally:
            dms.close()

    if fmt == "json":
        click.echo(json_out.render(info))
    elif fmt == "tsv":
        click.echo(tsv_out.render_rows(info["docs"], _DOC_TSV_COLUMNS), nl=False)
    else:
        click.echo(_render_md(info), nl=False)


def _render_md(info: dict[str, Any]) -> str:
    lines = [f"# RPC `{info['name']}`", ""]
    bits = []
    if info.get("tag") and info.get("routine"):
        bits.append(f"entry: `{info['tag']}^{info['routine']}`")
    if info.get("return_type"):
        bits.append(f"returns: {info['return_type']}")
    if info.get("availability"):
        bits.append(f"availability: {info['availability']}")
    if info.get("version"):
        bits.append(f"version: {info['version']}")
    if bits:
        lines.append(" · ".join(bits))
        lines.append("")
    if info.get("package"):
        lines.append(f"**package:** {info['package']}")
        lines.append("")

    docs = info.get("docs") or []
    lines.append("## Documentation")
    lines.append("")
    if not docs:
        lines.append("_No VDL documentation references this RPC._")
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
