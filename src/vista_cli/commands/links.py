"""vista links REF — dense one-line-per-section cross-reference summary."""

from __future__ import annotations

from typing import Any

import click

from vista_cli.config import Config
from vista_cli.format import json_out
from vista_cli.stores.code_view import make_code_view
from vista_cli.stores.data_model import DataModelStore
from vista_cli.stores.doc_model import DocModelStore
from vista_cli.stores.joined import routine_links


@click.command()
@click.argument("ref")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json"]),
    default="md",
)
@click.option("--all-versions", is_flag=True)
@click.pass_context
def links(
    ctx: click.Context,
    ref: str,
    fmt: str,
    all_versions: bool,
) -> None:
    """Show all interlinks for a routine reference."""
    cfg: Config = ctx.obj["config"]
    allow_cache = ctx.obj.get("allow_cache", True)
    view = make_code_view(
        code_model_dir=cfg.code_model_dir,
        cache_db=cfg.cache_db,
        doc_db=cfg.doc_db,
        allow_cache=allow_cache,
    )
    dms = DocModelStore(cfg.doc_db) if cfg.doc_db.exists() else None
    dms_data = DataModelStore(cfg.data_model_dir)

    try:
        info = routine_links(
            view, dms, dms_data, ref, latest_only=not all_versions
        )
    finally:
        if dms is not None:
            dms.close()

    if info is None:
        click.echo(f"Reference '{ref}' not found in code-model.", err=True)
        ctx.exit(1)
        return

    if fmt == "json":
        click.echo(json_out.render(info))
    else:
        click.echo(_render_md(info), nl=False)


def _render_md(info: dict[str, Any]) -> str:
    lines: list[str] = []
    pkg = info["package"]
    pkg_label = pkg["directory"] or "?"
    ns = pkg.get("namespace") or "?"
    app = pkg.get("app_code") or "?"
    lines.append(f"routine          {info['routine']}")
    lines.append(f"package          {pkg_label} (ns={ns}, app={app})")

    opts = info.get("options") or []
    lines.append("opts             " + (", ".join(o["name"] for o in opts) or "(none)"))
    rpcs = info.get("rpcs") or []
    lines.append("rpcs             " + (", ".join(r["name"] for r in rpcs) or "(none)"))

    files = info.get("files") or []
    if files:
        lines.append(
            "files            "
            + ", ".join(f"{f['file_number']} {f['file_name']}" for f in files)
        )
    else:
        lines.append("files            (none)")

    docs = info.get("docs") or []
    lines.append(f"docs             {len(docs)}")
    for d in docs:
        doc_id = d.get("doc_id", "?")
        title = d.get("title", "?")
        patch = d.get("patch_id") or ""
        suffix = f"  patch {patch}" if patch else ""
        lines.append(f"   doc {doc_id}  {title}{suffix}")

    extras = info.get("extra_section_count") or 0
    if extras:
        lines.append(
            f"sections-fts     {extras} additional sections mention this routine"
        )

    patches = info.get("patches") or []
    if patches:
        nums = sorted(
            {p.rsplit("*", 1)[-1] for p in patches},
            key=lambda n: int(n) if n.isdigit() else -1,
        )
        ns_ver = patches[0].rsplit("*", 1)[0]
        lines.append(f"patches          {ns_ver}*{{{','.join(nums)}}}")
    else:
        lines.append("patches          (none)")

    return "\n".join(lines) + "\n"
