"""Click entry point — wires subcommands together.

`vista` is the top-level group; subcommands live in vista_cli.commands.*.
"""

from __future__ import annotations

import click

from vista_cli import __version__
from vista_cli.commands.doctor import doctor
from vista_cli.commands.routine import routine
from vista_cli.commands.where import where
from vista_cli.config import Config


@click.group()
@click.version_option(__version__, prog_name="vista")
@click.pass_context
def main(ctx: click.Context) -> None:
    """vista — joined VistA code + documentation queries."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.from_env()


main.add_command(doctor)
main.add_command(routine)
main.add_command(where)


if __name__ == "__main__":
    main()
