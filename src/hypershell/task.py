# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Task based operations."""


# standard libs
import logging

# external libs
from cmdkit.app import Application, ApplicationGroup, exit_status
from cmdkit.cli import Interface

# internal libs

# public interface
__all__ = ['TaskGroupApp', ]


# initialize application logger
log = logging.getLogger('hypershell')


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
    }
