"""vista tree [REF] — hierarchical browser.

`vista tree` (no arg) prints the full package list at depth 1.
`vista tree PSO` expands one package into its routines / rpcs / options.
`vista tree PSO --depth 2 --kind routines` walks one more level
(callees of each routine, capped).
"""

from __future__ import annotations

from typing import Any

import click

from vista_cli.canonical import resolve_package
from vista_cli.completion import complete_package
from vista_cli.config import Config
from vista_cli.format import json_out
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.code_view import make_code_view

_TOP_PER_KIND = 25


@click.command(name="tree")
@click.argument("ref", required=False, shell_complete=complete_package)
@click.option(
    "--depth",
    default=1,
    show_default=True,
    type=int,
    help="How many levels to walk under the package.",
)
@click.option(
    "--kind",
    type=click.Choice(["all", "routines", "rpcs", "options"]),
    default="all",
    help="Which children to expand (only meaningful with REF).",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json"]),
    default="md",
)
@click.option(
    "--top",
    "top_n",
    default=_TOP_PER_KIND,
    show_default=True,
    type=int,
    help="Cap children listed per kind.",
)
@click.pass_context
def tree(
    ctx: click.Context,
    ref: str | None,
    depth: int,
    kind: str,
    fmt: str,
    top_n: int,
) -> None:
    """Browse the catalog hierarchically."""
    cfg: Config = ctx.obj["config"]
    allow_cache = ctx.obj.get("allow_cache", True)

    if ref is None:
        # Corpus view: every package + roll-up counts at depth 1
        rows = _corpus_view(cfg)
        if fmt == "json":
            click.echo(json_out.render_list(rows))
        else:
            click.echo(_md_corpus(rows))
        return

    # Per-package view
    pkg_id = resolve_package(ref)
    directory = pkg_id.directory if pkg_id else ref
    cms = CodeModelStore(cfg.code_model_dir)
    view = make_code_view(
        code_model_dir=cfg.code_model_dir,
        cache_db=cfg.cache_db,
        doc_db=cfg.doc_db,
        allow_cache=allow_cache,
    )
    routines = view.routines_by_package(directory)
    rpcs = cms.rpcs_by_package(directory)
    options = cms.options_by_package(directory)
    if not (routines or rpcs or options):
        click.echo(
            f"Package '{ref}' not found in canonical map or TSVs.", err=True
        )
        ctx.exit(1)
        return

    info: dict[str, Any] = {
        "package": directory,
        "namespace": pkg_id.ns if pkg_id else "",
        "app_code": pkg_id.app_code if pkg_id else "",
        "counts": {
            "routines": len(routines),
            "rpcs": len(rpcs),
            "options": len(options),
        },
        "routines": [],
        "rpcs": [],
        "options": [],
    }

    if kind in ("all", "routines"):
        ranked = sorted(routines, key=lambda r: -_i(r.get("in_degree")))[:top_n]
        routine_rows: list[dict[str, Any]] = []
        for r in ranked:
            name = r.get("routine_name", "")
            callees = _expand_callees(view, name, depth, top_n) if depth >= 2 else []
            routine_rows.append(
                {
                    "routine_name": name,
                    "in_degree": _i(r.get("in_degree")),
                    "out_degree": _i(r.get("out_degree")),
                    "line_count": _i(r.get("line_count")),
                    "callees": callees,
                }
            )
        info["routines"] = routine_rows

    if kind in ("all", "rpcs"):
        info["rpcs"] = [
            {
                "name": r.get("name", ""),
                "tag": r.get("tag", ""),
                "routine": r.get("routine", ""),
            }
            for r in rpcs[:top_n]
        ]

    if kind in ("all", "options"):
        info["options"] = [
            {
                "name": o.get("name", ""),
                "type": o.get("type", ""),
                "menu_text": o.get("menu_text", ""),
            }
            for o in options[:top_n]
        ]

    if fmt == "json":
        click.echo(json_out.render(info))
    else:
        click.echo(_md_package(info, kind=kind))


# ── corpus view (no arg) ──────────────────────────────────────────


def _corpus_view(cfg: Config) -> list[dict[str, Any]]:
    cms = CodeModelStore(cfg.code_model_dir)
    out: list[dict[str, Any]] = []
    for p in cms.all_packages():
        directory = p.get("package", "")
        if not directory:
            continue
        pkg_id = resolve_package(directory)
        out.append(
            {
                "package": directory,
                "namespace": pkg_id.ns if pkg_id else "",
                "app_code": pkg_id.app_code if pkg_id else "",
                "routines": len(cms.routines_by_package(directory)),
                "rpcs": len(cms.rpcs_by_package(directory)),
                "options": len(cms.options_by_package(directory)),
            }
        )
    out.sort(key=lambda r: (-r["routines"], r["package"]))
    return out


def _md_corpus(rows: list[dict[str, Any]]) -> str:
    lines = ["# Packages", ""]
    lines.append(f"{len(rows)} packages.")
    lines.append(
        "Pass a package name as an argument to expand: `vista tree PSO`."
    )
    lines.append("")
    for r in rows:
        ns = r["namespace"] or "?"
        app = r["app_code"] or "?"
        lines.append(
            f"- **{r['package']}**  ns={ns} app={app}  "
            f"({r['routines']} routines, {r['rpcs']} rpcs, "
            f"{r['options']} options)"
        )
    return "\n".join(lines) + "\n"


# ── package view (with arg) ───────────────────────────────────────


def _md_package(info: dict[str, Any], *, kind: str) -> str:
    counts = info["counts"]
    ns = info["namespace"] or "?"
    app = info["app_code"] or "?"
    title = (
        f"# {info['package']}  [ns={ns}, app={app}]  "
        f"({counts['routines']} routines, {counts['rpcs']} rpcs, "
        f"{counts['options']} options)"
    )
    lines = [title, ""]

    if kind in ("all", "routines") and info["routines"]:
        lines.append("## routines (top by in-degree)")
        lines.append("")
        for r in info["routines"]:
            lines.append(
                f"- `{r['routine_name']}` "
                f"({r['line_count']} lines · in={r['in_degree']} · "
                f"out={r['out_degree']})"
            )
            for cc in r.get("callees", []):
                lines.append(
                    f"    - `{cc.get('callee_routine', '?')}` "
                    f"× {cc.get('ref_count', 0)}"
                )
        lines.append("")

    if kind in ("all", "rpcs") and info["rpcs"]:
        lines.append("## rpcs")
        lines.append("")
        for r in info["rpcs"]:
            lead = f"{r['tag']}^" if r["tag"] else ""
            lines.append(
                f"- `{r['name']}` → `{lead}{r['routine']}`"
            )
        lines.append("")

    if kind in ("all", "options") and info["options"]:
        lines.append("## options")
        lines.append("")
        for o in info["options"]:
            lines.append(
                f"- `{o['name']}` ({o['type'] or '?'}) {o['menu_text'] or ''}"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _expand_callees(view, routine: str, depth: int, top_n: int) -> list[dict]:
    """Depth-2+ walk: top callees of `routine`."""
    if depth < 2:
        return []
    return [
        {
            "callee_routine": c.get("callee_routine", ""),
            "callee_tag": c.get("callee_tag", ""),
            "ref_count": _i(c.get("ref_count")),
        }
        for c in view.callees(routine)[:top_n]
    ]


def _i(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
