"""Click entry point — wires subcommands together.

`vista` is the top-level group; subcommands live in vista_cli.commands.*.
"""

from __future__ import annotations

import click

from vista_cli import __version__
from vista_cli.commands.build_cache import build_cache
from vista_cli.commands.context import ask, context
from vista_cli.commands.coverage import coverage
from vista_cli.commands.doc import doc
from vista_cli.commands.doctor import doctor
from vista_cli.commands.fetch import fetch
from vista_cli.commands.file import file as file_cmd
from vista_cli.commands.global_ import global_cmd
from vista_cli.commands.init import init_cmd
from vista_cli.commands.layers import layers
from vista_cli.commands.links import links
from vista_cli.commands.matrix import matrix
from vista_cli.commands.neighbors import neighbors
from vista_cli.commands.option import option
from vista_cli.commands.package import package
from vista_cli.commands.patch import patch
from vista_cli.commands.risk import risk
from vista_cli.commands.routine import routine
from vista_cli.commands.rpc import rpc
from vista_cli.commands.search import search
from vista_cli.commands.snapshot import snapshot
from vista_cli.commands.timeline import timeline
from vista_cli.commands.where import where
from vista_cli.config import Config


@click.group()
@click.version_option(__version__, prog_name="vista")
@click.option(
    "--no-cache",
    is_flag=True,
    help="Bypass the joined cache; read directly from TSVs / SQLite.",
)
@click.pass_context
def main(ctx: click.Context, no_cache: bool) -> None:
    """vista — joined VistA code + documentation queries."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.from_env()
    ctx.obj["allow_cache"] = not no_cache


main.add_command(ask)
main.add_command(build_cache)
main.add_command(context)
main.add_command(coverage)
main.add_command(doc)
main.add_command(doctor)
main.add_command(fetch)
main.add_command(file_cmd, name="file")
main.add_command(global_cmd)
main.add_command(init_cmd, name="init")
main.add_command(layers)
main.add_command(links)
main.add_command(matrix)
main.add_command(neighbors)
main.add_command(option)
main.add_command(package)
main.add_command(patch)
main.add_command(risk)
main.add_command(routine)
main.add_command(rpc)
main.add_command(search)
main.add_command(snapshot)
main.add_command(timeline)
main.add_command(where)


if __name__ == "__main__":
    main()
