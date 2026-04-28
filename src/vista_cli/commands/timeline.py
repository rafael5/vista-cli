"""vista timeline REF | --pkg PKG — chronological patch + doc history."""

from __future__ import annotations

from typing import Any

import click

from vista_cli.canonical import resolve_package
from vista_cli.config import Config
from vista_cli.format import json_out
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.doc_model import DocModelStore


@click.command()
@click.argument("ref", required=False)
@click.option(
    "--pkg",
    "package",
    default=None,
    help="Package directory, ns, or app_code.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["md", "json"]),
    default="md",
)
@click.pass_context
def timeline(
    ctx: click.Context,
    ref: str | None,
    package: str | None,
    fmt: str,
) -> None:
    """Show patch + doc events for a routine or package."""
    if not ref and not package:
        click.echo("Provide either REF (routine) or --pkg.", err=True)
        ctx.exit(64)
        return

    cfg: Config = ctx.obj["config"]
    cms = CodeModelStore(cfg.code_model_dir)
    dms = DocModelStore(cfg.doc_db) if cfg.doc_db.exists() else None

    try:
        if ref:
            scope = ref
            events = _events_for_routine(cms, dms, ref)
        else:
            assert package is not None
            pkg_id = resolve_package(package)
            scope = pkg_id.directory if pkg_id else package
            events = _events_for_package(
                cms, dms, pkg_id.directory if pkg_id else package
            )
    finally:
        if dms is not None:
            dms.close()

    info = {"scope": scope, "events": events}

    if fmt == "json":
        click.echo(json_out.render(info))
    else:
        click.echo(_render_md(info), nl=False)


def _events_for_routine(
    cms: CodeModelStore, dms: DocModelStore | None, routine: str
) -> list[dict[str, Any]]:
    patches = cms.patches_for_routine(routine)
    events: list[dict[str, Any]] = []
    for pid in patches:
        ev: dict[str, Any] = {
            "kind": "patch",
            "patch_id": pid,
            "routine": routine,
            "date": None,
        }
        if dms is not None:
            docs = dms.docs_by_patch(pid)
            if docs:
                ev["docs"] = [d.get("title", "") for d in docs]
                ev["date"] = docs[0].get("pub_date")
        events.append(ev)
    return _sort_events(events)


def _events_for_package(
    cms: CodeModelStore, dms: DocModelStore | None, directory: str
) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for r in cms.routines_by_package(directory):
        for pid in cms.patches_for_routine(r.get("routine_name", "")):
            cur = seen.setdefault(
                pid,
                {
                    "kind": "patch",
                    "patch_id": pid,
                    "routines": set(),
                    "date": None,
                },
            )
            cur["routines"].add(r.get("routine_name", ""))
    if dms is not None:
        for pid, ev in seen.items():
            docs = dms.docs_by_patch(pid)
            if docs:
                ev["docs"] = [d.get("title", "") for d in docs]
                ev["date"] = docs[0].get("pub_date")
    out = []
    for ev in seen.values():
        ev["routines"] = sorted(ev["routines"])
        out.append(ev)
    return _sort_events(out)


def _sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(e: dict[str, Any]) -> tuple[str, int]:
        # Order primarily by date asc; fall back to numeric patch sequence
        date = e.get("date") or "0000-00-00"
        pid = e.get("patch_id") or ""
        try:
            num = int(pid.rsplit("*", 1)[-1])
        except ValueError:
            num = 0
        return (date, num)

    return sorted(events, key=key)


def _render_md(info: dict[str, Any]) -> str:
    lines = [f"# timeline: {info['scope']}", ""]
    events = info.get("events") or []
    if not events:
        lines.append("_No patch or doc events found._")
        lines.append("")
        return "\n".join(lines)
    for e in events:
        date = e.get("date") or "????-??-??"
        pid = e.get("patch_id", "?")
        rs = e.get("routines") or ([e.get("routine")] if e.get("routine") else [])
        rs = [r for r in rs if r]
        rs_text = ", ".join(rs)
        docs = e.get("docs") or []
        doc_text = f" · docs: {', '.join(docs)}" if docs else ""
        lines.append(f"- {date}  `{pid}`  {rs_text}{doc_text}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
