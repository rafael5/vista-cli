"""vista package NAME — package overview joining code + docs."""

from __future__ import annotations

from typing import Any

import click

from vista_cli.canonical import all_packages, resolve_package
from vista_cli.completion import complete_package
from vista_cli.config import Config
from vista_cli.format import json_out, tsv_out
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.doc_model import DocModelStore
from vista_cli.suggestions import did_you_mean

_TOP_ROUTINES = 25
_DOC_TSV_COLUMNS = ("doc_id", "doc_type", "app_code", "patch_id", "title", "rel_path")


@click.command()
@click.argument("name", shell_complete=complete_package)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json", "tsv"]),
    default="md",
)
@click.option("--no-docs", is_flag=True)
@click.option("--all-versions", is_flag=True)
@click.pass_context
def package(
    ctx: click.Context,
    name: str,
    fmt: str,
    no_docs: bool,
    all_versions: bool,
) -> None:
    """Show a package: routine roll-up + docs (by directory, ns, or app_code)."""
    cfg: Config = ctx.obj["config"]
    pkg_id = resolve_package(name)
    cms = CodeModelStore(cfg.code_model_dir)

    directory = pkg_id.directory if pkg_id else name
    pkg_row = cms.package(directory)
    routines = cms.routines_by_package(directory)

    if pkg_row is None and not routines and not pkg_id:
        click.echo(f"Package '{name}' not found in canonical map or TSVs.", err=True)
        # Build candidates from canonical packages + every distinct
        # directory / ns / app_code so any one of them resolves.
        canonical = list(all_packages())
        candidates = sorted(
            {p.directory for p in canonical}
            | {p.ns for p in canonical}
            | {p.app_code for p in canonical}
            | {r.get("package", "") for r in cms.all_routines() if r.get("package")}
        )
        suggestions = did_you_mean(name, candidates)
        if suggestions:
            click.echo(f"Did you mean: {', '.join(suggestions)}?", err=True)
        ctx.exit(1)
        return

    info: dict[str, Any] = {
        "package": directory,
        "namespace": pkg_id.ns if pkg_id else None,
        "app_code": pkg_id.app_code if pkg_id else None,
        "routine_count": _i((pkg_row or {}).get("routine_count", len(routines))),
        "total_lines": _i((pkg_row or {}).get("total_lines", 0)),
        "total_bytes": _i((pkg_row or {}).get("total_bytes", 0)),
        "routines": _summarise_routines(routines),
        "rpcs": cms.rpcs_by_package(directory),
        "options": cms.options_by_package(directory),
        "docs": [],
    }

    if not no_docs and cfg.doc_db.exists() and pkg_id:
        dms = DocModelStore(cfg.doc_db)
        try:
            info["docs"] = dms.docs_by_app_code(
                pkg_id.app_code, latest_only=not all_versions
            )
        finally:
            dms.close()

    if fmt == "json":
        click.echo(json_out.render(info))
    elif fmt == "tsv":
        click.echo(tsv_out.render_rows(info["docs"], _DOC_TSV_COLUMNS), nl=False)
    else:
        click.echo(_render_md(info), nl=False)


def _summarise_routines(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pick a small, sortable subset of fields from routines-comprehensive.tsv."""
    out = []
    for r in rows:
        out.append(
            {
                "routine_name": r.get("routine_name", ""),
                "line_count": _i(r.get("line_count", "0")),
                "in_degree": _i(r.get("in_degree", "0")),
                "out_degree": _i(r.get("out_degree", "0")),
            }
        )
    return sorted(out, key=lambda r: -int(r["in_degree"]))


def _render_md(info: dict[str, Any]) -> str:
    pkg = info["package"]
    ns = info.get("namespace") or "?"
    app = info.get("app_code") or "?"
    lines = [f"# {pkg}", ""]
    lines.append(f"namespace `{ns}` · app_code `{app}`")
    lines.append("")
    bits = [
        f"{info['routine_count']} routines",
        f"{info['total_lines']} lines",
        f"{len(info.get('rpcs') or [])} RPCs",
        f"{len(info.get('options') or [])} options",
    ]
    lines.append(" · ".join(bits))
    lines.append("")

    routines = info.get("routines") or []
    if routines:
        lines.append("## Top routines (by in-degree)")
        lines.append("")
        for r in routines[:_TOP_ROUTINES]:
            lines.append(
                f"- `{r['routine_name']}` "
                f"in={r['in_degree']} · out={r['out_degree']} · "
                f"{r['line_count']} lines"
            )
        lines.append("")

    rpcs = info.get("rpcs") or []
    if rpcs:
        lines.append("## RPCs")
        lines.append("")
        for r in rpcs[:_TOP_ROUTINES]:
            lines.append(
                f"- `{r.get('name', '?')}` "
                f"({r.get('tag', '?')}^{r.get('routine', '?')})"
            )
        lines.append("")

    options = info.get("options") or []
    if options:
        lines.append("## Options")
        lines.append("")
        for o in options[:_TOP_ROUTINES]:
            lines.append(f"- `{o.get('name', '?')}` ({o.get('type', '?')})")
        lines.append("")

    docs = info.get("docs") or []
    lines.append("## Documentation")
    lines.append("")
    if not docs:
        lines.append("_No VDL documentation found for this package._")
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
