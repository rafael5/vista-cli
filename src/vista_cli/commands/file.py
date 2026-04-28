"""vista file NUMBER — FileMan file metadata + code use + docs."""

from __future__ import annotations

from typing import Any

import click

from vista_cli.config import Config
from vista_cli.format import json_out, tsv_out
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.data_model import DataModelStore
from vista_cli.stores.doc_model import DocModelStore

_TOP_ROUTINES = 25
_DOC_TSV_COLUMNS = ("doc_id", "doc_type", "app_code", "patch_id", "title", "rel_path")


@click.command()
@click.argument("number")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json", "tsv"]),
    default="md",
)
@click.option("--no-docs", is_flag=True)
@click.option("--all-versions", is_flag=True)
@click.pass_context
def file(
    ctx: click.Context,
    number: str,
    fmt: str,
    no_docs: bool,
    all_versions: bool,
) -> None:
    """Show a FileMan file: name, global root, PIKS, top routines, and docs."""
    cfg: Config = ctx.obj["config"]
    dms_data = DataModelStore(cfg.data_model_dir)
    row = dms_data.file(number)
    if row is None:
        click.echo(f"File '{number}' not found in files.tsv.", err=True)
        ctx.exit(1)
        return

    cms = CodeModelStore(cfg.code_model_dir)
    global_root = row.get("global_root", "")
    bare_global = _bare_global(global_root)
    routines = cms.routines_using_global(bare_global) if bare_global else []

    info: dict[str, Any] = {
        "file_number": row.get("file_number", ""),
        "file_name": row.get("file_name", ""),
        "global_root": global_root,
        "field_count": _i(row.get("field_count", "0")),
        "record_count": _i(row.get("record_count", "0")),
        "piks": row.get("piks", ""),
        "piks_method": row.get("piks_method", ""),
        "piks_confidence": row.get("piks_confidence", ""),
        "volatility": row.get("volatility", ""),
        "sensitivity": row.get("sensitivity", ""),
        "subdomain": row.get("subdomain", ""),
        "routines": _summarise_routines(routines),
        "docs": [],
    }

    if not no_docs and cfg.doc_db.exists():
        doc_store = DocModelStore(cfg.doc_db)
        try:
            info["docs"] = doc_store.docs_by_file(
                number, latest_only=not all_versions
            )
        finally:
            doc_store.close()

    if fmt == "json":
        click.echo(json_out.render(info))
    elif fmt == "tsv":
        click.echo(tsv_out.render_rows(info["docs"], _DOC_TSV_COLUMNS), nl=False)
    else:
        click.echo(_render_md(info), nl=False)


def _bare_global(root: str) -> str:
    """`^DPT` → `DPT`; `^DIC(4)` → `DIC`."""
    if not root:
        return ""
    s = root.lstrip("^")
    out = ""
    for ch in s:
        if ch.isalnum() or ch == "%":
            out += ch
        else:
            break
    return out


def _summarise_routines(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        out.append(
            {
                "routine_name": r.get("routine_name", ""),
                "package": r.get("package", ""),
                "ref_count": _i(r.get("ref_count", "0")),
            }
        )
    return out


def _render_md(info: dict[str, Any]) -> str:
    n = info.get("file_number", "?")
    name = info.get("file_name", "?")
    lines = [f"# File {n} — {name}", ""]
    bits = [f"global `{info.get('global_root', '?')}`"]
    if info.get("field_count"):
        bits.append(f"{info['field_count']} fields")
    if info.get("record_count"):
        bits.append(f"{info['record_count']} records")
    if info.get("piks"):
        piks = f"PIKS={info['piks']}"
        conf = info.get("piks_confidence")
        if conf:
            piks += f" ({conf})"
        bits.append(piks)
    lines.append(" · ".join(bits))
    lines.append("")

    routines = info.get("routines") or []
    if routines:
        lines.append("## Top routines touching this global")
        lines.append("")
        for r in routines[:_TOP_ROUTINES]:
            lines.append(
                f"- `{r['routine_name']}` [{r['package']}] ×{r['ref_count']}"
            )
        lines.append("")

    docs = info.get("docs") or []
    lines.append("## Documentation")
    lines.append("")
    if not docs:
        lines.append("_No VDL documentation references this file number._")
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


def _i(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
