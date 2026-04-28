"""vista context REF / vista ask Q — AI-ready markdown bundles.

Per planning doc §7.5: emits a markdown packet the user pastes into
an LLM chat. `ask` is `context --question Q`; both share the bundle.
"""

from __future__ import annotations

from pathlib import Path

import click

from vista_cli.canonical import resolve_package
from vista_cli.commands.routine import _build_info
from vista_cli.config import Config
from vista_cli.format import markdown
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.doc_model import DocModelStore

_DEFAULT_BUDGET = 200_000


def _bundle(
    cfg: Config,
    *,
    routine: str | None,
    package: str | None,
    question: str | None,
    with_source: bool,
    bytes_budget: int,
) -> str:
    parts: list[str] = []
    if question:
        parts.append(f"# Question\n\n{question}\n")

    if routine:
        info = _build_info(routine, cfg, with_docs=True, latest_only=True)
        if info is not None:
            parts.append(markdown.render_routine(info))
            parts.append(_doc_sections_for_routine(cfg, routine))
            if with_source:
                parts.append(_source_block(cfg, info.get("source_path", "")))

    if package:
        pkg_id = resolve_package(package)
        if pkg_id is not None:
            parts.append(_package_summary(cfg, pkg_id))

    bundle = "\n".join(p for p in parts if p)
    encoded = bundle.encode("utf-8")
    if len(encoded) > bytes_budget:
        bundle = encoded[:bytes_budget].decode("utf-8", errors="ignore")
        bundle += "\n\n_…truncated to fit byte budget._\n"
    return bundle


def _doc_sections_for_routine(cfg: Config, routine: str) -> str:
    if not cfg.doc_db.exists():
        return ""
    dms = DocModelStore(cfg.doc_db)
    try:
        sections = dms.sections_mentioning_routine(routine)
        if not sections:
            return ""
        out = ["## Documentation sections", ""]
        for s in sections:
            heading = s.get("heading") or "?"
            doc_title = s.get("doc_title") or ""
            anchor = s.get("anchor") or ""
            rel = s.get("rel_path") or ""
            out.append(f"### {doc_title} — {heading}")
            if rel:
                ref = f"{rel}#{anchor}" if anchor else rel
                out.append(f"`{ref}`")
            body = _section_body(dms, s.get("section_id"))
            if body:
                out.append("")
                out.append(body.strip())
            out.append("")
        return "\n".join(out)
    finally:
        dms.close()


def _section_body(dms: DocModelStore, section_id: int | None) -> str:
    if section_id is None:
        return ""
    cur = dms._conn_().execute(
        "SELECT body FROM doc_sections WHERE section_id = ?", (section_id,)
    )
    row = cur.fetchone()
    return (row[0] or "") if row else ""


def _package_summary(cfg: Config, pkg_id) -> str:  # type: ignore[no-untyped-def]
    cms = CodeModelStore(cfg.code_model_dir)
    routines = cms.routines_by_package(pkg_id.directory)
    out = [f"## Package {pkg_id.directory} (ns={pkg_id.ns}, app={pkg_id.app_code})", ""]
    out.append(f"{len(routines)} routines.")
    out.append("")
    return "\n".join(out)


def _source_block(cfg: Config, container_path: str) -> str:
    if not container_path:
        return ""
    prefix = "/opt/VistA-M/"
    rel = (
        container_path[len(prefix) :]
        if container_path.startswith(prefix)
        else container_path.lstrip("/")
    )
    host = cfg.vista_m_host / rel
    if not host.exists():
        return ""
    text = Path(host).read_text(encoding="utf-8", errors="replace")
    return f"## Source\n\n```mumps\n{text}```\n"


@click.command()
@click.argument("ref")
@click.option("--with-source", is_flag=True, help="Include the routine's full source.")
@click.option("--bytes", "bytes_budget", default=_DEFAULT_BUDGET, show_default=True)
@click.pass_context
def context(
    ctx: click.Context,
    ref: str,
    with_source: bool,
    bytes_budget: int,
) -> None:
    """Emit a markdown bundle of code + docs for a routine or package."""
    cfg: Config = ctx.obj["config"]
    pkg_id = resolve_package(ref)
    if pkg_id is not None:
        bundle = _bundle(
            cfg,
            routine=None,
            package=ref,
            question=None,
            with_source=with_source,
            bytes_budget=bytes_budget,
        )
    else:
        bundle = _bundle(
            cfg,
            routine=ref,
            package=None,
            question=None,
            with_source=with_source,
            bytes_budget=bytes_budget,
        )
    if not bundle.strip():
        click.echo(f"Reference '{ref}' not found.", err=True)
        ctx.exit(1)
        return
    click.echo(bundle, nl=False)


@click.command()
@click.argument("question")
@click.option("--routine", "routine", default=None)
@click.option("--pkg", "package", default=None)
@click.option("--with-source", is_flag=True)
@click.option("--bytes", "bytes_budget", default=_DEFAULT_BUDGET, show_default=True)
@click.pass_context
def ask(
    ctx: click.Context,
    question: str,
    routine: str | None,
    package: str | None,
    with_source: bool,
    bytes_budget: int,
) -> None:
    """Same as `context`, but prepends a question header for an LLM chat."""
    cfg: Config = ctx.obj["config"]
    bundle = _bundle(
        cfg,
        routine=routine,
        package=package,
        question=question,
        with_source=with_source,
        bytes_budget=bytes_budget,
    )
    click.echo(bundle, nl=False)
