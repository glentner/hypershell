# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Task based operations."""


# type annotations
from __future__ import annotations
from typing import List

# standard libs
import logging

# external libs
from cmdkit.config import ConfigurationError
from cmdkit.app import Application, ApplicationGroup
from cmdkit.cli import Interface

# internal libs
from hypershell.core.config import config
from hypershell.submit import submit_from

# public interface
__all__ = ['TaskGroupApp', ]


# initialize application logger
log = logging.getLogger('hypershell')


def check_database_available():
    """Emit warning for particular configuration."""
    db = config.database.get('file', None) or config.database.get('database', None)
    if config.database.provider == 'sqlite' and db in ('', ':memory:', None):
        raise ConfigurationError('No database configured')


TASK_SUBMIT_USAGE = f"""\
usage: hyper-shell task submit [-h] ARGS...
Submit individual command line to database.\
"""
TASK_SUBMIT_HELP = f"""\
{TASK_SUBMIT_USAGE}

arguments:
ARGS                   Command-line arguments.

options:
-h, --help             Show this message and exit.\
"""


class TaskSubmitApp(Application):
    """Submit individual command-line task to database."""
    interface = Interface('hyper-shell task submit', TASK_SUBMIT_USAGE, TASK_SUBMIT_HELP)

    argv: List[str] = []
    interface.add_argument('argv', nargs='+')

    def run(self) -> None:
        """Run submit thread."""
        check_database_available()
        task = Task.new(args=' '.join(self.argv))
        Task.add(task)
        print(task.id)



TASK_GROUP_USAGE = f"""\
usage: hyper-shell task [-h] <command> [<args>...]
Search, submit, track, and manage individual tasks.\
"""

TASK_GROUP_HELP = f"""\
{TASK_GROUP_USAGE}

commands:

options:
-h, --help             Show this message and exit.\
"""


class TaskGroupApp(ApplicationGroup):
    """Search, submit, track, and manage individual tasks."""

    interface = Interface('hyper-shell task', TASK_GROUP_USAGE, TASK_GROUP_HELP)
    interface.add_argument('command')

    command = None
    commands = {
        'submit': TaskSubmitApp,
    }
