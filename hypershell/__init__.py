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
import os
import sys
import logging
import datetime
import traceback

# external libs
from cmdkit.app import Application, ApplicationGroup, exit_status
from cmdkit.cli import Interface

# internal libs
from hypershell.core.config import config, get_site, init_paths
from hypershell.core.logging import initialize_logging
from hypershell.__meta__ import (__appname__, __version__, __authors__, __description__,
                                 __contact__, __license__, __copyright__, __keywords__, __website__)

# commands
from hypershell.submit import SubmitApp
from hypershell.server import ServerApp

# public interface
__all__ = ['HyperShellApp', 'main', ]


# initialize application logger
log = logging.getLogger('hypershell')


# inject logger setup into command-line framework
Application.log_critical = log.critical
Application.log_exception = log.exception


APP_NAME = 'hypershell'
APP_USAGE = f"""\
usage: {APP_NAME} [-h] [-v] <command> [<args>...]
{__description__}\
"""

APP_HELP = f"""\
{APP_USAGE}

commands:
submit                 {SubmitApp.__doc__}

options:
-h, --help             Show this message and exit.
-v, --version          Show the version and exit.

Use the -h/--help flag with the above commands to
learn more about their usage.

Documentation and issue tracking at:
{__website__}\
"""


# NOTE: catching base Exception avoids the 'raise' in Application.main
def uncaught_exception(exc: Exception) -> int:
    """Write exception to file and return exit code."""
    time = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    path = os.path.join(get_site()['log'], f'exception-{time}.log')
    with open(path, mode='w') as stream:
        print(traceback.format_exc(), file=stream)
    msg = str(exc).replace('\n', ' - ')
    log.critical(f'{exc.__class__.__name__}: {msg}')
    log.critical(f'Exception traceback written to {path}')
    return exit_status.uncaught_exception


Application.exceptions = {
    Exception: uncaught_exception,
}


class HyperShellApp(ApplicationGroup):
    """Top-level application class for console application."""

    interface = Interface(APP_NAME, APP_USAGE, APP_HELP)
    interface.add_argument('-v', '--version', action='version', version=__version__)
    interface.add_argument('command')

    command = None
    commands = {
        'submit': SubmitApp,
    }


def main() -> int:
    """Entry-point for console application."""
    init_paths()
    initialize_logging()
    return HyperShellApp.main(sys.argv[1:])

