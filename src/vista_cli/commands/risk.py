"""vista risk RTN — composite 0–100 risk score for a routine.

Combines: in-degree (blast radius), patch count (churn), XINDEX
findings (debt), PIKS class of touched globals (P-class doubles
weight), cross-package outbound coupling, and doc coverage.
"""

from __future__ import annotations

from typing import Any

import click

from vista_cli.config import Config
from vista_cli.format import json_out
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.data_model import DataModelStore
from vista_cli.stores.doc_model import DocModelStore
from vista_cli.stores.joined import file_for_global


@click.command()
@click.argument("name")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json"]),
    default="md",
)
@click.pass_context
def risk(ctx: click.Context, name: str, fmt: str) -> None:
    """Score the risk of touching a routine."""
    cfg: Config = ctx.obj["config"]
    cms = CodeModelStore(cfg.code_model_dir)
    dms_data = DataModelStore(cfg.data_model_dir)
    dms = DocModelStore(cfg.doc_db) if cfg.doc_db.exists() else None

    row = cms.routine(name)
    if row is None:
        click.echo(f"Routine '{name}' not found.", err=True)
        ctx.exit(1)
        return

    info = _score(cms, dms_data, dms, row)
    if dms is not None:
        dms.close()

    if fmt == "json":
        click.echo(json_out.render(info))
    else:
        click.echo(_render_md(info), nl=False)


def _score(
    cms: CodeModelStore,
    dms_data: DataModelStore,
    dms: DocModelStore | None,
    row: dict[str, Any],
) -> dict[str, Any]:
    name = row.get("routine_name", "")
    package = row.get("package", "")

    in_degree = _i(row.get("in_degree"))
    patch_count = len(cms.patches_for_routine(name))
    xindex_findings = len(cms.xindex_errors(name))

    callees = cms.callees(name)
    cross_package = sum(
        1 for c in callees if c.get("kind") and _is_cross_pkg(cms, c, package)
    )

    globals_touched = cms.globals_for(name)
    p_class_files = 0
    piks_summary: list[str] = []
    for g in globals_touched:
        gname = g.get("global_name", "")
        f = file_for_global(dms_data, gname)
        if f is None:
            continue
        piks = (f.get("piks") or "").upper()
        if piks:
            piks_summary.append(f"{gname}={piks}")
        if piks == "P":
            p_class_files += 1

    documented = False
    if dms is not None:
        documented = bool(dms.docs_by_routine(name, latest_only=True))

    components = {
        "in_degree": _component(in_degree, scale=200, weight=20),
        "patch_count": _component(patch_count, scale=20, weight=15),
        "xindex_findings": _component(xindex_findings, scale=10, weight=15),
        "p_class_globals": _component(p_class_files, scale=3, weight=20),
        "cross_package_callees": _component(cross_package, scale=10, weight=15),
        "undocumented": 15 if not documented else 0,
    }
    score = min(100, sum(components.values()))

    return {
        "routine": name,
        "package": package,
        "score": score,
        "components": components,
        "facts": {
            "in_degree": in_degree,
            "patch_count": patch_count,
            "xindex_findings": xindex_findings,
            "p_class_globals": p_class_files,
            "cross_package_callees": cross_package,
            "documented": documented,
            "piks": piks_summary,
        },
    }


def _is_cross_pkg(cms: CodeModelStore, callee: dict, my_pkg: str) -> bool:
    """True if callee_routine is in a different package than `my_pkg`."""
    target = callee.get("callee_routine", "")
    if not target:
        return False
    row = cms.routine(target)
    if row is None:
        return False
    return (row.get("package", "") or "") != my_pkg


def _component(value: int, *, scale: int, weight: int) -> int:
    """Map a raw value to 0..weight using a saturating linear scale."""
    if scale <= 0:
        return 0
    fraction = min(1.0, value / scale)
    return int(round(fraction * weight))


def _render_md(info: dict[str, Any]) -> str:
    score = info["score"]
    bucket = (
        "low" if score < 25 else "moderate" if score < 60 else "high"
    )
    lines = [
        f"# risk: `{info['routine']}` — {score}/100 ({bucket})",
        "",
        f"_package: {info['package']}_",
        "",
        "## Components",
        "",
    ]
    for k, v in info["components"].items():
        lines.append(f"- {k:<24} +{v}")
    lines.append("")
    lines.append("## Facts")
    lines.append("")
    facts = info["facts"]
    lines.append(f"- in-degree:            {facts['in_degree']}")
    lines.append(f"- patches:              {facts['patch_count']}")
    lines.append(f"- XINDEX findings:      {facts['xindex_findings']}")
    lines.append(f"- P-class globals:      {facts['p_class_globals']}")
    lines.append(f"- cross-pkg callees:    {facts['cross_package_callees']}")
    lines.append(f"- documented:           {'yes' if facts['documented'] else 'no'}")
    if facts["piks"]:
        lines.append(f"- PIKS:                 {', '.join(facts['piks'])}")
    return "\n".join(lines).rstrip() + "\n"


def _i(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
