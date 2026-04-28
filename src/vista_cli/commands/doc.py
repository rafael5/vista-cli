"""vista doc QUERY — FTS5 search over VDL doc sections."""

from __future__ import annotations

import click

from vista_cli.config import Config
from vista_cli.format import json_out, tsv_out
from vista_cli.stores.doc_model import DocModelStore

_TSV_COLUMNS = (
    "doc_id",
    "section_id",
    "app_code",
    "doc_type",
    "doc_title",
    "heading",
    "anchor",
    "rel_path",
    "snippet",
)


@click.command()
@click.argument("query")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json", "tsv"]),
    default="md",
)
@click.option(
    "--app",
    "app_code",
    default=None,
    help="Filter by VDL app_code (PRCA, PSO, ...).",
)
@click.option("--all-versions", is_flag=True, help="Include non-latest documents.")
@click.option(
    "--limit", default=20, show_default=True, help="Max number of section hits."
)
@click.pass_context
def doc(
    ctx: click.Context,
    query: str,
    fmt: str,
    app_code: str | None,
    all_versions: bool,
    limit: int,
) -> None:
    """Search VDL docs (FTS5 over headings + bodies)."""
    cfg: Config = ctx.obj["config"]
    if not cfg.doc_db.exists():
        click.echo(f"doc DB missing: {cfg.doc_db}", err=True)
        ctx.exit(1)
        return

    dms = DocModelStore(cfg.doc_db)
    try:
        hits = dms.search_sections(
            query,
            app_code=app_code,
            latest_only=not all_versions,
            limit=limit,
        )
    finally:
        dms.close()

    if not hits:
        click.echo(f"No section matches for: {query}", err=True)
        ctx.exit(1)
        return

    if fmt == "json":
        click.echo(json_out.render_list(hits))
    elif fmt == "tsv":
        click.echo(tsv_out.render_rows(hits, _TSV_COLUMNS), nl=False)
    else:
        click.echo(_render_md(query, hits), nl=False)


def _render_md(query: str, hits: list[dict]) -> str:
    lines = [f"# doc search: `{query}` — {len(hits)} hit(s)", ""]
    for h in hits:
        title = h.get("doc_title") or "?"
        heading = h.get("heading") or "?"
        app = h.get("app_code") or "?"
        dt = h.get("doc_type") or "?"
        snippet = (h.get("snippet") or "").strip()
        rel = h.get("rel_path") or ""
        anchor = h.get("anchor") or ""
        lines.append(f"## [{app} · {dt}] {title} — {heading}")
        if snippet:
            lines.append(f"> {snippet}")
        if rel:
            ref = f"{rel}#{anchor}" if anchor else rel
            lines.append(f"`{ref}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
