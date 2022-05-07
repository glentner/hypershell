# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Database interface, models, and methods."""


# standard libs
import sys
import logging

# external libs
from cmdkit.app import Application, exit_status
from cmdkit.cli import Interface
from sqlalchemy import inspect

# internal libs
from hypershell.core.logging import Logger
from hypershell.core.exceptions import write_traceback
from hypershell.database.core import engine, in_memory
from hypershell.database.model import Model

# public interface
__all__ = ['InitDBApp', 'initdb', 'checkdb', 'DatabaseUninitialized', 'DATABASE_ENABLED', ]

# module level logger
log: Logger = logging.getLogger(__name__)


def initdb() -> None:
    """Initialize database schema."""
    Model.metadata.create_all(engine)


def checkdb() -> None:
    """Ensure database connection and tables exist."""
    if not inspect(engine).has_table('task'):
        raise DatabaseUninitialized('Use \'initdb\' to initialize the database')


class DatabaseUninitialized(Exception):
    """The database needs to be initialized before operations."""


INITDB_PROGRAM = 'hyper-shell initdb'
INITDB_USAGE = f"""\
usage: {INITDB_PROGRAM} [-h]
{initdb.__doc__}\
"""

INITDB_HELP = f"""\
{INITDB_USAGE}

options:
-h, --help           Show this message and exit.\
"""


class InitDBApp(Application):
    """Application class for database initializer."""

    interface = Interface(INITDB_PROGRAM, INITDB_USAGE, INITDB_HELP)
    ALLOW_NOARGS = True

    def run(self) -> None:
        """Business logic for `initdb`."""
        initdb()


try:
    if not in_memory:
        DATABASE_ENABLED = True
    else:
        DATABASE_ENABLED = False
except Exception as error:
    write_traceback(error, module=__name__)
    sys.exit(exit_status.bad_config)
