"""vista search PATTERN — unified search across code model + docs.

Substring match on the code-model (routine names, RPC names, option
names, file names) plus FTS5 phrase match on document sections.
"""

from __future__ import annotations

from typing import Any

import click

from vista_cli.config import Config
from vista_cli.format import json_out, tsv_out
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.data_model import DataModelStore
from vista_cli.stores.doc_model import DocModelStore

_SCOPES = ("all", "routines", "rpcs", "options", "files", "docs")
_TSV_COLUMNS = ("scope", "name", "package", "snippet")


@click.command()
@click.argument("pattern")
@click.option(
    "--scope",
    type=click.Choice(_SCOPES),
    default="all",
    show_default=True,
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json", "tsv"]),
    default="md",
)
@click.option("--limit", default=20, show_default=True)
@click.pass_context
def search(
    ctx: click.Context,
    pattern: str,
    scope: str,
    fmt: str,
    limit: int,
) -> None:
    """Unified substring + FTS search across both stores."""
    cfg: Config = ctx.obj["config"]
    needle = pattern.upper()
    hits: list[dict[str, Any]] = []

    if scope in ("all", "routines"):
        cms = CodeModelStore(cfg.code_model_dir)
        for r in cms.all_routines():
            if needle in r.get("routine_name", "").upper():
                hits.append(
                    {
                        "scope": "routines",
                        "name": r.get("routine_name", ""),
                        "package": r.get("package", ""),
                        "snippet": (r.get("version_line", "") or "").strip(),
                    }
                )
                if len(hits) >= limit and scope == "routines":
                    break

    if scope in ("all", "rpcs"):
        cms = CodeModelStore(cfg.code_model_dir)
        for r in cms._load("rpcs.tsv"):
            if needle in r.get("name", "").upper():
                hits.append(
                    {
                        "scope": "rpcs",
                        "name": r.get("name", ""),
                        "package": r.get("package", ""),
                        "snippet": f"{r.get('tag', '')}^{r.get('routine', '')}",
                    }
                )

    if scope in ("all", "options"):
        cms = CodeModelStore(cfg.code_model_dir)
        for r in cms._load("options.tsv"):
            if needle in r.get("name", "").upper():
                hits.append(
                    {
                        "scope": "options",
                        "name": r.get("name", ""),
                        "package": r.get("package", ""),
                        "snippet": r.get("menu_text", ""),
                    }
                )

    if scope in ("all", "files"):
        try:
            dms_data = DataModelStore(cfg.data_model_dir)
            for r in dms_data.all_files():
                fn = r.get("file_name", "")
                num = r.get("file_number", "")
                if needle in fn.upper() or needle == num:
                    hits.append(
                        {
                            "scope": "files",
                            "name": f"{num} {fn}".strip(),
                            "package": r.get("subdomain", ""),
                            "snippet": r.get("global_root", ""),
                        }
                    )
        except Exception:  # noqa: BLE001
            pass

    if scope in ("all", "docs") and cfg.doc_db.exists():
        dms = DocModelStore(cfg.doc_db)
        try:
            for s in dms.search_sections(pattern, limit=limit):
                hits.append(
                    {
                        "scope": "docs",
                        "name": s.get("doc_title") or s.get("heading") or "",
                        "package": s.get("app_code") or "",
                        "snippet": (s.get("snippet") or "").strip(),
                    }
                )
        finally:
            dms.close()

    hits = hits[:limit]

    if not hits:
        click.echo(f"No matches for: {pattern}", err=True)
        ctx.exit(1)
        return

    if fmt == "json":
        click.echo(json_out.render_list(hits))
    elif fmt == "tsv":
        click.echo(tsv_out.render_rows(hits, _TSV_COLUMNS), nl=False)
    else:
        click.echo(_render_md(pattern, hits), nl=False)


def _render_md(pattern: str, hits: list[dict[str, Any]]) -> str:
    lines = [f"# search `{pattern}` — {len(hits)} hit(s)", ""]
    by_scope: dict[str, list[dict[str, Any]]] = {}
    for h in hits:
        by_scope.setdefault(h["scope"], []).append(h)
    for scope in ("routines", "rpcs", "options", "files", "docs"):
        items = by_scope.get(scope) or []
        if not items:
            continue
        lines.append(f"## {scope}")
        lines.append("")
        for h in items:
            pkg = f" [{h['package']}]" if h.get("package") else ""
            snip = f" — {h['snippet']}" if h.get("snippet") else ""
            lines.append(f"- `{h['name']}`{pkg}{snip}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
