# SPDX-FileCopyrightText: 2023 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Database interface, models, and methods."""


# type annotations
from __future__ import annotations

# standard libs
import sys
import functools

# external libs
from cmdkit.app import Application, exit_status
from cmdkit.cli import Interface
from cmdkit.config import ConfigurationError
from cmdkit.ansi import colorize_usage
from sqlalchemy import inspect
from sqlalchemy.orm import close_all_sessions
from sqlalchemy.exc import OperationalError

# internal libs
from hypershell.core.logging import Logger
from hypershell.core.config import config
from hypershell.core.exceptions import (write_traceback, handle_exception, DatabaseUninitialized,
                                        get_shared_exception_mapping)
from hypershell.data.core import engine, in_memory, schema
from hypershell.data.model import Entity, Task

# public interface
__all__ = ['InitDBApp', 'initdb', 'truncatedb', 'checkdb', 'ensuredb', 'DATABASE_ENABLED', ]

# initialize logger
log = Logger.with_name(__name__)


try:
    if not in_memory:
        DATABASE_ENABLED = True
    else:
        DATABASE_ENABLED = False
except Exception as error:
    write_traceback(error, module=__name__)
    sys.exit(exit_status.bad_config)


def initdb() -> None:
    """Initialize database tables."""
    Entity.metadata.create_all(engine)


def truncatedb() -> None:
    """Truncate database tables."""
    # NOTE: We still might hang here if other sessions exist outside this app instance
    close_all_sessions()
    log.trace('Dropping all tables')
    Entity.metadata.drop_all(engine)
    log.trace('Creating all tables')
    Entity.metadata.create_all(engine)
    log.warning(f'Truncated database')


def checkdb() -> None:
    """Ensure database connection and tables exist."""
    if not inspect(engine).has_table('task', schema=schema):
        raise DatabaseUninitialized('Use \'initdb\' to initialize the database')


def ensuredb(auto_init: bool = False) -> None:
    """Ensure database configuration before applying any operations."""
    db = config.database.get('file', None) or config.database.get('database', None)
    if config.database.provider == 'sqlite' and db in ('', ':memory:', None):
        raise ConfigurationError('Missing database configuration')
    if config.database.provider == 'sqlite' or auto_init is True:
        initdb()
    else:
        checkdb()


INITDB_PROGRAM = 'hyper-shell initdb'
INITDB_USAGE = f"""\
Usage:
{INITDB_PROGRAM} [-h] [--truncate [--yes]]

Initialize database (not needed for SQLite).
Use --truncate to zero out the task metadata.\
"""

INITDB_HELP = f"""\
{INITDB_USAGE}

Options:
  -t, --truncate       Truncate database (task metadata will be lost).
  -y, --yes            Auto-confirm truncation (default will prompt).
  -h, --help           Show this message and exit.\
"""


class InitDBApp(Application):
    """Initialize database (not needed for SQLite)."""

    interface = Interface(INITDB_PROGRAM,
                          colorize_usage(INITDB_USAGE),
                          colorize_usage(INITDB_HELP))

    ALLOW_NOARGS = True

    truncate: bool = False
    interface.add_argument('-t', '--truncate', action='store_true')

    auto_confirm: bool = False
    interface.add_argument('-y', '--yes', action='store_true', dest='auto_confirm')

    exceptions = {
        OperationalError: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        **get_shared_exception_mapping(__name__),
    }

    def run(self: InitDBApp) -> None:
        """Business logic for `initdb`."""
        if not DATABASE_ENABLED:
            raise ConfigurationError('No database configured')
        elif not self.truncate:
            initdb()
        elif self.auto_confirm:
            truncatedb()
        elif not sys.stdout.isatty():
            raise RuntimeError('Non-interactive prompt cannot confirm --truncate (see --yes).')
        else:
            if config.database.provider == 'sqlite':
                site = config.database.file
            else:
                site = config.database.get('host', 'localhost')
            print(f'Connected to: {config.database.provider} ({site})')
            response = input(f'Truncate database ({Task.count()} tasks)? [Y]es/no: ').strip()
            if response.lower() in ['', 'y', 'yes']:
                truncatedb()
            elif response.lower() in ['n', 'no']:
                print('Stopping')
            else:
                raise RuntimeError(f'Stopping (invalid response: "{response}")')
