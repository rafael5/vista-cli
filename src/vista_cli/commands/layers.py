"""vista layers --pkg PKG — topological sort of intra-package calls.

Layer 0: routines that call no other routine inside the same package
(leaves). Layer N: routines whose intra-package callees are all in
layers < N. Cycles are reported as a separate "cyclic" group at the
end so the rest of the sort is still useful.
"""

from __future__ import annotations

from typing import Any

import click

from vista_cli.canonical import resolve_package
from vista_cli.config import Config
from vista_cli.format import json_out
from vista_cli.stores.code_model import CodeModelStore


@click.command()
@click.option(
    "--pkg",
    "package",
    required=True,
    help="Package directory, ns, or app_code.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json"]),
    default="md",
)
@click.pass_context
def layers(ctx: click.Context, package: str, fmt: str) -> None:
    """Show a package's natural reading order via topological sort."""
    cfg: Config = ctx.obj["config"]
    pkg_id = resolve_package(package)
    directory = pkg_id.directory if pkg_id else package
    cms = CodeModelStore(cfg.code_model_dir)
    routines = cms.routines_by_package(directory)
    if not routines:
        click.echo(f"No routines in package '{package}'.", err=True)
        ctx.exit(1)
        return

    info = _layer_sort(cms, directory, routines)

    if fmt == "json":
        click.echo(json_out.render(info))
    else:
        click.echo(_render_md(info), nl=False)


def _layer_sort(
    cms: CodeModelStore,
    directory: str,
    routines: list[dict[str, Any]],
) -> dict[str, Any]:
    members = {r.get("routine_name", "") for r in routines}
    members.discard("")

    deps: dict[str, set[str]] = {m: set() for m in members}
    for caller in members:
        for c in cms.callees(caller):
            target = c.get("callee_routine", "")
            if target and target in members and target != caller:
                deps[caller].add(target)

    levels: dict[str, int] = {}
    remaining = dict(deps)
    layer = 0
    while remaining:
        leaves = {n for n, d in remaining.items() if not (d - levels.keys())}
        if not leaves:
            break
        for n in leaves:
            levels[n] = layer
        for n in leaves:
            remaining.pop(n, None)
        layer += 1

    grouped: list[list[str]] = [[] for _ in range(layer)]
    for n, lv in levels.items():
        grouped[lv].append(n)
    for g in grouped:
        g.sort()

    cyclic = sorted(remaining.keys())
    return {
        "package": directory,
        "layers": [
            {"layer": i, "routines": g} for i, g in enumerate(grouped) if g
        ],
        "cyclic": cyclic,
    }


def _render_md(info: dict[str, Any]) -> str:
    lines = [f"# layers: {info['package']}", ""]
    for entry in info.get("layers", []):
        i = entry["layer"]
        rs = entry["routines"]
        lines.append(f"## Layer {i} ({len(rs)})")
        lines.append("")
        for r in rs:
            lines.append(f"- `{r}`")
        lines.append("")
    cyclic = info.get("cyclic") or []
    if cyclic:
        lines.append("## Cyclic")
        lines.append("")
        lines.append(
            "_The routines below participate in a call cycle and could "
            "not be linearised._"
        )
        lines.append("")
        for r in cyclic:
            lines.append(f"- `{r}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
