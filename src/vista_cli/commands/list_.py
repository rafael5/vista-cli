"""vista list <kind> — flat enumeration of packages / routines / rpcs /
options / files / globals.

The "I don't know where to start" entry point. Each subcommand prints
the catalog for one kind of entity, optionally filtered by package or
routine, in any of the four formats.
"""

from __future__ import annotations

from typing import Any

import click

from vista_cli.canonical import resolve_package
from vista_cli.completion import complete_package, complete_routine
from vista_cli.config import Config
from vista_cli.format import json_out, tsv_out
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.code_view import make_code_view
from vista_cli.stores.data_model import DataModelStore


@click.group(name="list")
def list_cmd() -> None:
    """Enumerate the catalog: packages, routines, rpcs, options, files, globals."""


# ── packages ──────────────────────────────────────────────────────


@list_cmd.command(name="packages")
@click.option(
    "--format", "fmt", type=click.Choice(["md", "json", "tsv"]), default="md"
)
@click.option("--limit", default=200, show_default=True, type=int)
@click.pass_context
def list_packages(ctx: click.Context, fmt: str, limit: int) -> None:
    """List packages with rolled-up routine / RPC / option counts."""
    cfg: Config = ctx.obj["config"]
    cms = CodeModelStore(cfg.code_model_dir)
    rows: list[dict[str, Any]] = []
    for p in cms.all_packages():
        directory = p.get("package", "")
        if not directory:
            continue
        pkg_id = resolve_package(directory)
        rows.append(
            {
                "package": directory,
                "namespace": pkg_id.ns if pkg_id else "",
                "app_code": pkg_id.app_code if pkg_id else "",
                "routines": len(cms.routines_by_package(directory)),
                "rpcs": len(cms.rpcs_by_package(directory)),
                "options": len(cms.options_by_package(directory)),
            }
        )
    rows.sort(key=lambda r: (-int(r["routines"]), str(r["package"])))
    rows = rows[:limit]
    _emit(
        ctx,
        rows,
        fmt,
        columns=("package", "namespace", "app_code", "routines", "rpcs", "options"),
        md_title="Packages",
        md_row=lambda r: (
            f"- **{r['package']}**  ns={r['namespace'] or '?'} "
            f"app={r['app_code'] or '?'}  "
            f"({r['routines']} routines, {r['rpcs']} rpcs, {r['options']} options)"
        ),
    )


# ── routines ──────────────────────────────────────────────────────


@list_cmd.command(name="routines")
@click.option(
    "--pkg", "package", default=None, shell_complete=complete_package
)
@click.option(
    "--format", "fmt", type=click.Choice(["md", "json", "tsv"]), default="md"
)
@click.option("--limit", default=100, show_default=True, type=int)
@click.pass_context
def list_routines(
    ctx: click.Context, package: str | None, fmt: str, limit: int
) -> None:
    """List routines (optionally filtered by --pkg), ranked by in-degree."""
    cfg: Config = ctx.obj["config"]
    allow_cache = ctx.obj.get("allow_cache", True)
    view = make_code_view(
        code_model_dir=cfg.code_model_dir,
        cache_db=cfg.cache_db,
        doc_db=cfg.doc_db,
        allow_cache=allow_cache,
    )
    if package is not None:
        pkg_id = resolve_package(package)
        directory = pkg_id.directory if pkg_id else package
        candidates = view.routines_by_package(directory)
    else:
        candidates = view.all_routines()

    rows = [
        {
            "routine_name": r.get("routine_name", ""),
            "package": r.get("package", ""),
            "line_count": _i(r.get("line_count")),
            "in_degree": _i(r.get("in_degree")),
            "out_degree": _i(r.get("out_degree")),
        }
        for r in candidates
        if r.get("routine_name")
    ]
    rows.sort(key=lambda r: (-int(r["in_degree"]), str(r["routine_name"])))
    rows = rows[:limit]
    _emit(
        ctx,
        rows,
        fmt,
        columns=("routine_name", "package", "line_count", "in_degree", "out_degree"),
        md_title=f"Routines{' in ' + package if package else ''}",
        md_row=lambda r: (
            f"- `{r['routine_name']}` "
            f"[{r['package'] or '?'}]  "
            f"{r['line_count']} lines · in={r['in_degree']} · out={r['out_degree']}"
        ),
    )


# ── rpcs ──────────────────────────────────────────────────────────


@list_cmd.command(name="rpcs")
@click.option(
    "--pkg", "package", default=None, shell_complete=complete_package
)
@click.option(
    "--format", "fmt", type=click.Choice(["md", "json", "tsv"]), default="md"
)
@click.option("--limit", default=200, show_default=True, type=int)
@click.pass_context
def list_rpcs(
    ctx: click.Context, package: str | None, fmt: str, limit: int
) -> None:
    """List RPCs (optionally filtered by --pkg)."""
    cfg: Config = ctx.obj["config"]
    cms = CodeModelStore(cfg.code_model_dir)
    if package is not None:
        pkg_id = resolve_package(package)
        directory = pkg_id.directory if pkg_id else package
        candidates = cms.rpcs_by_package(directory)
    else:
        candidates = cms.all_rpcs()
    rows = [
        {
            "name": r.get("name", ""),
            "tag": r.get("tag", ""),
            "routine": r.get("routine", ""),
            "package": r.get("package", ""),
            "return_type": r.get("return_type", ""),
            "version": r.get("version", ""),
        }
        for r in candidates
        if r.get("name")
    ]
    rows.sort(key=lambda r: r["name"])
    rows = rows[:limit]
    _emit(
        ctx,
        rows,
        fmt,
        columns=("name", "tag", "routine", "package", "return_type", "version"),
        md_title=f"RPCs{' in ' + package if package else ''}",
        md_row=lambda r: (
            f"- `{r['name']}`  → "
            f"`{r['tag'] + '^' if r['tag'] else ''}{r['routine']}`  "
            f"[{r['package'] or '?'}]"
        ),
    )


# ── options ───────────────────────────────────────────────────────


@list_cmd.command(name="options")
@click.option(
    "--pkg", "package", default=None, shell_complete=complete_package
)
@click.option(
    "--format", "fmt", type=click.Choice(["md", "json", "tsv"]), default="md"
)
@click.option("--limit", default=200, show_default=True, type=int)
@click.pass_context
def list_options(
    ctx: click.Context, package: str | None, fmt: str, limit: int
) -> None:
    """List options (optionally filtered by --pkg)."""
    cfg: Config = ctx.obj["config"]
    cms = CodeModelStore(cfg.code_model_dir)
    if package is not None:
        pkg_id = resolve_package(package)
        directory = pkg_id.directory if pkg_id else package
        candidates = cms.options_by_package(directory)
    else:
        candidates = cms.all_options()
    rows = [
        {
            "name": o.get("name", ""),
            "type": o.get("type", ""),
            "menu_text": o.get("menu_text", ""),
            "package": o.get("package", ""),
            "routine": o.get("routine", ""),
            "tag": o.get("tag", ""),
        }
        for o in candidates
        if o.get("name")
    ]
    rows.sort(key=lambda r: r["name"])
    rows = rows[:limit]
    _emit(
        ctx,
        rows,
        fmt,
        columns=("name", "type", "menu_text", "package", "routine", "tag"),
        md_title=f"Options{' in ' + package if package else ''}",
        md_row=lambda r: (
            f"- `{r['name']}` ({r['type'] or '?'})  "
            f"[{r['package'] or '?'}]  {r['menu_text'] or ''}"
        ),
    )


# ── files ─────────────────────────────────────────────────────────


@list_cmd.command(name="files")
@click.option(
    "--format", "fmt", type=click.Choice(["md", "json", "tsv"]), default="md"
)
@click.option("--limit", default=200, show_default=True, type=int)
@click.pass_context
def list_files(ctx: click.Context, fmt: str, limit: int) -> None:
    """List FileMan files, ranked by record count desc."""
    cfg: Config = ctx.obj["config"]
    dms = DataModelStore(cfg.data_model_dir)
    rows = [
        {
            "file_number": f.get("file_number", ""),
            "file_name": f.get("file_name", ""),
            "global_root": f.get("global_root", ""),
            "piks": f.get("piks", ""),
            "field_count": _i(f.get("field_count")),
            "record_count": _i(f.get("record_count")),
        }
        for f in dms.all_files()
        if f.get("file_number")
    ]
    rows.sort(
        key=lambda r: (-int(r["record_count"]), str(r["file_number"]))  # type: ignore[call-overload]
    )
    rows = rows[:limit]
    _emit(
        ctx,
        rows,
        fmt,
        columns=(
            "file_number",
            "file_name",
            "global_root",
            "piks",
            "field_count",
            "record_count",
        ),
        md_title="FileMan files",
        md_row=lambda r: (
            f"- **{r['file_number']}** {r['file_name']}  "
            f"`{r['global_root'] or '?'}`  "
            f"PIKS={r['piks'] or '?'} · {r['record_count']} records"
        ),
    )


# ── globals ───────────────────────────────────────────────────────


@list_cmd.command(name="globals")
@click.option(
    "--routine", "routine", default=None, shell_complete=complete_routine
)
@click.option(
    "--format", "fmt", type=click.Choice(["md", "json", "tsv"]), default="md"
)
@click.option("--limit", default=200, show_default=True, type=int)
@click.pass_context
def list_globals(
    ctx: click.Context, routine: str | None, fmt: str, limit: int
) -> None:
    """List globals across the corpus, aggregated by name + ref_count."""
    cfg: Config = ctx.obj["config"]
    cms = CodeModelStore(cfg.code_model_dir)
    if routine is not None:
        # Single-routine globals: easy direct read
        candidates = cms.globals_for(routine)
        rows = [
            {
                "global_name": g.get("global_name", ""),
                "ref_count": _i(g.get("ref_count")),
                "routines": 1,
            }
            for g in candidates
            if g.get("global_name")
        ]
    else:
        # Aggregate across the whole routine-globals.tsv
        ref_counts: dict[str, int] = {}
        routine_counts: dict[str, int] = {}
        for g in cms._load("routine-globals.tsv"):
            name = g.get("global_name", "")
            if not name:
                continue
            ref_counts[name] = ref_counts.get(name, 0) + _i(g.get("ref_count"))
            routine_counts[name] = routine_counts.get(name, 0) + 1
        rows = [
            {
                "global_name": name,
                "ref_count": ref_counts[name],
                "routines": routine_counts[name],
            }
            for name in ref_counts
        ]
    rows.sort(
        key=lambda r: (-int(r["ref_count"]), str(r["global_name"]))  # type: ignore[call-overload]
    )
    rows = rows[:limit]
    _emit(
        ctx,
        rows,
        fmt,
        columns=("global_name", "ref_count", "routines"),
        md_title=f"Globals{' touched by ' + routine if routine else ''}",
        md_row=lambda r: (
            f"- `^{r['global_name']}`  "
            f"{r['ref_count']} refs across {r['routines']} routines"
        ),
    )


# ── output dispatch ───────────────────────────────────────────────


def _emit(
    ctx: click.Context,
    rows: list[dict[str, Any]],
    fmt: str,
    *,
    columns: tuple[str, ...],
    md_title: str,
    md_row,
) -> None:
    if fmt == "json":
        click.echo(json_out.render_list(rows))
    elif fmt == "tsv":
        click.echo(tsv_out.render_rows(rows, columns), nl=False)
    else:
        click.echo(f"# {md_title}")
        click.echo()
        click.echo(f"{len(rows)} entries.")
        click.echo()
        for r in rows:
            click.echo(md_row(r))


def _i(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
