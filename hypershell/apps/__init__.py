# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""The main entry-point for hyper-shell."""

# standard libs
import sys

# internal libs
from ..core.logging import logger
from ..__meta__ import (__appname__, __version__, __description__,
                        __copyright__, __contact__, __website__)

# external libs
from cmdkit.app import Application, exit_status
from cmdkit.cli import Interface, ArgumentError

# commands
from .server import Server
from .client import Client
from .cluster import Cluster


COMMANDS = {
    'server': Server,
    'client': Client,
    'cluster': Cluster
}

PROGRAM = __appname__

USAGE = f"""\
usage: {__appname__} <command> [<args>...]
       {__appname__} [--help] [--version]

{__description__}\
"""

EPILOG = f"""\
Documentation and issue tracking at:
{__website__}

{__copyright__}
Email: <{__contact__}>.\
"""

HELP = f"""\
{USAGE}

commands:
server                 {Server.__doc__}
client                 {Client.__doc__}
cluster                {Cluster.__doc__}

options:
-h, --help             Show this message and exit.
-v, --version          Show the version and exit.

Use the -h/--help flag with the above commands to
learn more about their usage.

{EPILOG}\
"""


# initialize module level logger
log = logger.with_name(__appname__)


class CompletedCommand(Exception):
    """Lift exit_status of sub-commands `main` method."""


class HyperShell(Application):
    """Entry-point for hyper-shell console-app."""

    interface = Interface(PROGRAM, USAGE, HELP)
    interface.add_argument('-v', '--version', version=__version__, action='version')

    command: str = None
    interface.add_argument('command')

    exceptions = {
        # extract exit status from exception arguments
        CompletedCommand: (lambda exc: int(exc.args[0])),
    }

    def run(self) -> None:
        """Show usage/help/version or defer to subcommand."""
        try:
            status = COMMANDS[self.command].main(sys.argv[2:])
            raise CompletedCommand(status)

        except KeyError as error:
            cmd, = error.args
            raise ArgumentError(f'"{cmd}" is not an available command.')
