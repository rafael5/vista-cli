"""vista matrix — N×N cross-package call-volume matrix.

The off-diagonal cells are the package boundaries. The heaviest
non-diagonal entries are the de-facto APIs between packages.
"""

from __future__ import annotations

from typing import Any

import click

from vista_cli.config import Config
from vista_cli.format import json_out, tsv_out
from vista_cli.stores.code_model import CodeModelStore


@click.command()
@click.option(
    "--kind",
    type=click.Choice(["package"]),
    default="package",
    show_default=True,
    help="Currently only --kind package is supported.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json", "tsv"]),
    default="md",
)
@click.option(
    "--top",
    "top_n",
    default=20,
    show_default=True,
    help="Cap the off-diagonal listing in markdown.",
)
@click.pass_context
def matrix(
    ctx: click.Context, kind: str, fmt: str, top_n: int
) -> None:
    """Compute caller_pkg → callee_pkg call volumes."""
    cfg: Config = ctx.obj["config"]
    cms = CodeModelStore(cfg.code_model_dir)
    info = _build_matrix(cms)

    flat = [
        {"caller_pkg": k[0], "callee_pkg": k[1], "ref_count": v}
        for k, v in info["counts"].items()
    ]
    flat.sort(key=lambda r: (r["caller_pkg"], r["callee_pkg"]))

    if fmt == "json":
        click.echo(
            json_out.render({"packages": info["packages"], "edges": flat})
        )
    elif fmt == "tsv":
        click.echo(
            tsv_out.render_rows(flat, ["caller_pkg", "callee_pkg", "ref_count"]),
            nl=False,
        )
    else:
        click.echo(_render_md(info, top_n=top_n), nl=False)


def _build_matrix(cms: CodeModelStore) -> dict[str, Any]:
    counts: dict[tuple[str, str], int] = {}
    rows = cms._load("routine-calls.tsv")
    routine_to_pkg: dict[str, str] = {}
    for r in cms.all_routines():
        n = r.get("routine_name", "")
        if n:
            routine_to_pkg[n] = r.get("package", "")

    for c in rows:
        caller_pkg = c.get("caller_package", "") or routine_to_pkg.get(
            c.get("caller_name", ""), ""
        )
        callee = c.get("callee_routine", "")
        callee_pkg = routine_to_pkg.get(callee, "")
        if not caller_pkg or not callee_pkg:
            continue
        ref = _i(c.get("ref_count", "0"))
        key = (caller_pkg, callee_pkg)
        counts[key] = counts.get(key, 0) + ref

    return {
        "counts": {k: v for k, v in counts.items()},
        "packages": sorted({k[0] for k in counts} | {k[1] for k in counts}),
    }


def _render_md(info: dict[str, Any], *, top_n: int) -> str:
    counts = info["counts"]
    cross = sorted(
        ((k[0], k[1], v) for k, v in counts.items() if k[0] != k[1]),
        key=lambda t: -t[2],
    )
    intra = sorted(
        ((k[0], v) for k, v in counts.items() if k[0] == k[1]),
        key=lambda t: -t[1],
    )
    lines = [f"# package call matrix — {len(info['packages'])} packages", ""]
    lines.append("## Cross-package edges (top by call volume)")
    lines.append("")
    if not cross:
        lines.append("_No cross-package calls in this corpus._")
    else:
        for caller, callee, n in cross[:top_n]:
            lines.append(f"- `{caller}` → `{callee}` ×{n:,}")
    lines.append("")
    lines.append("## Intra-package totals")
    lines.append("")
    for pkg, n in intra[:top_n]:
        lines.append(f"- `{pkg}` ×{n:,}")
    return "\n".join(lines).rstrip() + "\n"


def _i(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
