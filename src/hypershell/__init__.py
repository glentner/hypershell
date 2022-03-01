# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Initialization and entry-point for console application."""


# standard libs
import sys
import logging
import functools

# external libs
from cmdkit.app import Application, ApplicationGroup, exit_status
from cmdkit.cli import Interface
from cmdkit.config import ConfigurationError

# internal libs
from hypershell.__meta__ import __version__, __authors__, __description__, __contact__, __copyright__, __website__
from hypershell.core.exceptions import write_traceback, handle_exception
from hypershell.core.config import config
from hypershell.core.logging import initialize_logging
from hypershell.submit import submit_from, submit_file, SubmitThread, SubmitApp
from hypershell.server import serve_from, serve_file, serve_forever, ServerThread, ServerApp
from hypershell.client import run_client, ClientThread, ClientApp
from hypershell.cluster import ClusterApp
from hypershell.task import TaskGroupApp
from hypershell.config import ConfigApp

# public interface
__all__ = ['config',
           'submit_from', 'submit_file', 'SubmitThread', 'SubmitApp',
           'serve_from', 'serve_file', 'serve_forever', 'ServerThread', 'ServerApp',
           'run_client', 'ClientThread', 'ClientApp', 'ClusterApp',
           'HyperShellApp', 'main', ]


# initialize application logger
log = logging.getLogger('hypershell')


# inject logger setup into command-line framework
Application.log_critical = log.critical
Application.log_exception = log.exception


APP_NAME = 'hyper-shell'
APP_USAGE = f"""\
usage: {APP_NAME} [-h] [-v] <command> [<args>...]
{__description__}\
"""

APP_HELP = f"""\
{APP_USAGE}

commands:
config                 {ConfigApp.__doc__}
submit                 {SubmitApp.__doc__}
server                 {ServerApp.__doc__}
client                 {ClientApp.__doc__}
cluster                {ClusterApp.__doc__} (recommended)
task                   {TaskGroupApp.__doc__}

options:
-h, --help             Show this message and exit.
-v, --version          Show the version and exit.

Documentation and issue tracking at:
{__website__}

Copyright {__copyright__}
{__authors__} <{__contact__}>.\
"""

Application.exceptions = {
    Exception: functools.partial(write_traceback, logger=log, status=exit_status.runtime_error),
    ConfigurationError: functools.partial(handle_exception, logger=log, status=exit_status.bad_config),
}


class HyperShellApp(ApplicationGroup):
    """Top-level application class for console application."""

    interface = Interface(APP_NAME, APP_USAGE, APP_HELP)
    interface.add_argument('-v', '--version', action='version', version=__version__)
    interface.add_argument('command')

    command = None
    commands = {
        'submit': SubmitApp,
        'server': ServerApp,
        'client': ClientApp,
        'cluster': ClusterApp,
        'task': TaskGroupApp,
        'config': ConfigApp,
    }


def main() -> int:
    """Entry-point for console application."""
    initialize_logging()
    return HyperShellApp.main(sys.argv[1:])

