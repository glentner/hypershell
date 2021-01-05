# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Package initialization and entry-point for console application."""


# standard libs
import sys
import logging

# external libs
from cmdkit.app import Application, ApplicationGroup
from cmdkit.cli import Interface

# internal libs
from hypershell.core.config import config
from hypershell.core.logging import initialize_logging
from hypershell.__meta__ import (__appname__, __version__, __authors__, __description__,
                                 __contact__, __license__, __copyright__, __keywords__, __website__)

# commands
from hypershell.submit import SubmitApp

# render uncaught exceptions with highlighting
if sys.stdout.isatty():
    from rich.traceback import install
    install()


# initialize application logger
log = logging.getLogger('hypershell')


# inject logger setup into command-line framework
Application.log_critical = log.critical
Application.log_exception = log.exception


_main_name = 'hypershell'
_main_usage = f"""\
usage: {_main_name} [-h] [-v] <command> [<args>...]
{__description__}\
"""

_main_help = f"""\
{_main_usage}

commands:
database               ...
config                 ...
submit                 {SubmitApp.__doc__}

options:
-h, --help             Show this message and exit.
-v, --version          Show the version and exit.

Use the -h/--help flag with the above commands to
learn more about their usage.

Documentation and issue tracking at:
{__website__}

Copyright {__copyright__}
{__authors__} <{__contact__}>\
"""


class HyperShellApp(ApplicationGroup):
    """Top-level application class for console application."""

    interface = Interface(_main_name, _main_usage, _main_help)

    interface.add_argument('-v', '--version', action='version', version=__version__)
    interface.add_argument('command')

    command = None
    commands = {
        'submit': SubmitApp,
    }


def main() -> int:
    """Entry-point for console application."""
    initialize_logging()
    return HyperShellApp.main(sys.argv[1:])

