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
from hypershell.core.exceptions import write_traceback, handle_exception
from hypershell.core.logging import initialize_logging
from hypershell.submit import SubmitApp
from hypershell.server import ServerApp
from hypershell.client import ClientApp
from hypershell.cluster import ClusterApp
from hypershell.task import TaskGroupApp
from hypershell.config import ConfigApp
from hypershell.database import InitDBApp, DatabaseUninitialized

# public interface
__all__ = ['HyperShellApp', 'main', '__version__', '__license__']

# project metadata
__version__     = '2.0.2'
__authors__     = 'Geoffrey Lentner'
__contact__     = 'glentner@purdue.edu'
__license__     = 'Apache Software License'
__copyright__   = '2019-2022. All Rights Reserved.'
__website__     = 'https://github.com/glentner/hyper-shell'
__keywords__    = 'distributed-computing command-line-tool shell-scripting high-performance-computing'
__description__ = 'Process shell commands over a distributed, asynchronous queue.'
__citation__    = """\
@inproceedings{lentner_2022,
    author = {Lentner, Geoffrey and Gorenstein, Lev},
    title = {HyperShell v2: Distributed Task Execution for HPC},
    year = {2022},
    isbn = {9781450391610},
    publisher = {Association for Computing Machinery},
    url = {https://doi.org/10.1145/3491418.3535138},
    doi = {10.1145/3491418.3535138},
    booktitle = {Practice and Experience in Advanced Research Computing},
    articleno = {80},
    numpages = {3},
    series = {PEARC '22}
}\
"""

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
initdb                 {InitDBApp.__doc__}

options:
-h, --help             Show this message and exit.
-v, --version          Show the version and exit.
    --citation         Show citation info and exit.

Issue tracking at:
{__website__}

Copyright {__copyright__}
{__authors__} <{__contact__}>.

If this software has helped in your research please consider
citing us (see `hyper-shell --citation`).\
"""


# Globally defined exception cases for all applications
Application.exceptions = {
    ConfigurationError: functools.partial(handle_exception, logger=log, status=exit_status.bad_config),
    DatabaseUninitialized: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
    Exception: functools.partial(write_traceback, logger=log, status=exit_status.runtime_error),
}


class HyperShellApp(ApplicationGroup):
    """Top-level application class for console application."""

    interface = Interface(APP_NAME, APP_USAGE, APP_HELP)
    interface.add_argument('-v', '--version', action='version', version=__version__)
    interface.add_argument('--citation', action='version', version=__citation__)
    interface.add_argument('command')

    command = None
    commands = {
        'submit': SubmitApp,
        'server': ServerApp,
        'client': ClientApp,
        'cluster': ClusterApp,
        'task': TaskGroupApp,
        'config': ConfigApp,
        'initdb': InitDBApp,
    }


def main() -> int:
    """Entry-point for console application."""
    initialize_logging()
    return HyperShellApp.main(sys.argv[1:])
