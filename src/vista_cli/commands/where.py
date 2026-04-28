"""vista where REF — jump to source for any reference."""

from __future__ import annotations

from pathlib import Path

import click

from vista_cli.canonical import classify_ref
from vista_cli.config import Config
from vista_cli.stores.code_model import CodeModelStore


@click.command()
@click.argument("ref")
@click.pass_context
def where(ctx: click.Context, ref: str) -> None:
    """Print path:line for the source of a reference (TAG^RTN, RTN, ^RTN)."""
    cfg: Config = ctx.obj["config"]
    kind, name, tag = classify_ref(ref)
    if kind != "routine":
        click.echo(
            f"vista where currently supports routine refs; got {kind}",
            err=True,
        )
        ctx.exit(2)
        return

    cms = CodeModelStore(cfg.code_model_dir)
    row = cms.routine(name)
    if row is None:
        click.echo(f"Routine '{name}' not found.", err=True)
        ctx.exit(1)
        return

    container_path = row.get("source_path", "")
    if not container_path:
        click.echo(f"{name}\t(no source_path in TSV)")
        return
    host_path = _container_to_host(container_path, cfg.vista_m_host)

    line = _find_tag_line(host_path, tag) if tag else 1
    click.echo(f"{host_path}:{line}")


def _container_to_host(container_path: str, vista_m_host: Path) -> Path:
    """Map /opt/VistA-M/Packages/.../X.m → <vista_m_host>/Packages/.../X.m."""
    prefix = "/opt/VistA-M/"
    rel = (
        container_path[len(prefix) :]
        if container_path.startswith(prefix)
        else container_path.lstrip("/")
    )
    return vista_m_host / rel


def _find_tag_line(path: Path, tag: str) -> int:
    """Scan the file for column-0 occurrence of `tag`. Return 1 if not found."""
    if not path.exists():
        return 1
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 1
    for i, ln in enumerate(text.split("\n"), start=1):
        if i == 1:
            continue
        if not ln:
            continue
        first = ln[0]
        if first in (" ", "\t", ";"):
            continue
        # column-0 label up to whitespace, paren, or comment
        token = ""
        for ch in ln:
            if ch.isalnum() or ch in "%":
                token += ch
            else:
                break
        if token == tag:
            return i
    return 1
