# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Task based operations."""


# type annotations
from __future__ import annotations
from typing import List, Dict, Callable

# standard libs
import re
import sys
import json
import time
import logging
import functools

# external libs
import yaml
from rich.console import Console
from rich.syntax import Syntax
from cmdkit.config import ConfigurationError
from cmdkit.app import Application, ApplicationGroup, exit_status
from cmdkit.cli import Interface, ArgumentError
from sqlalchemy.exc import StatementError

# internal libs
from hypershell.core.config import config
from hypershell.core.exceptions import handle_exception
from hypershell.core.logging import Logger
from hypershell.database.model import Task

# public interface
__all__ = ['TaskGroupApp', ]


# initialize application logger
log: Logger = logging.getLogger('hypershell')


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


# Catch bad UUID before we touch the database
UUID_PATTERN: re.Pattern = re.compile(
    r'^[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12}$'
)


TASK_INFO_NAME = 'hyper-shell task info'
TASK_INFO_USAGE = f"""\
usage: {TASK_INFO_NAME} [-h] ID [--json | --stdout | --stderr]
Get info on individual task.\
"""
TASK_INFO_HELP = f"""\
{TASK_INFO_USAGE}

arguments:
ID                  Unique UUID.

options:
    --stdout        Fetch <stdout> from task.
    --stderr        Fetch <stderr> from task.
-h, --help          Show this message and exit.\
"""


class TaskInfoApp(Application):
    """Lookup information on task."""

    interface = Interface(TASK_INFO_NAME, TASK_INFO_USAGE, TASK_INFO_HELP)

    uuid: str
    interface.add_argument('uuid')

    format_json: bool = False
    interface.add_argument('--json', action='store_true', dest='format_json')

    exceptions = {
        Task.NotFound: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        StatementError: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        **Application.exceptions,
    }

    def run(self) -> None:
        """Run submit thread."""
        check_database_available()
        self.check_uuid()
        self.write(Task.from_id(self.uuid).to_json())

    def check_uuid(self) -> None:
        """Check for valid UUID."""
        if not UUID_PATTERN.match(self.uuid):
            raise ArgumentError(f'Bad UUID: \'{self.uuid}\'')

    def write(self, data: dict) -> None:
        """Format and print `data` to console."""
        formatter = self.format_method[self.format_name]
        output = formatter(data)
        if sys.stdout.isatty():
            output = Syntax(output, self.format_name, word_wrap=True,
                            theme = config.console.theme, background_color = 'default')
            Console().print(output)
        else:
            print(output, file=sys.stdout, flush=True)

    @functools.cached_property
    def format_name(self) -> str:
        """Either 'json' or 'yaml'."""
        return 'yaml' if not self.format_json else 'json'

    @functools.cached_property
    def format_method(self) -> Dict[str, Callable[[dict], str]]:
        """Format data method."""
        return {
            'yaml': functools.partial(yaml.dump, indent=4, sort_keys=False),
            'json': functools.partial(json.dumps, indent=4),
        }


# Time to wait between database queries
DEFAULT_INTERVAL = 5


TASK_WAIT_NAME = 'hyper-shell task wait'
TASK_WAIT_USAGE = f"""\
usage: {TASK_WAIT_NAME} [-h] ID [-n SEC] [--info [--json]]
Wait for task to complete.\
"""
TASK_WAIT_HELP = f"""\
{TASK_WAIT_USAGE}

arguments:
ID                    Unique UUID.

options:
-n, --interval  SEC   Time to wait between polling (default: {DEFAULT_INTERVAL}).
    --info            Print information on task.
    --json            Format output as JSON.
-h, --help            Show this message and exit.\
"""


class TaskWaitApp(Application):
    """Wait for task to complete."""

    interface = Interface(TASK_WAIT_NAME, TASK_WAIT_USAGE, TASK_WAIT_HELP)

    uuid: str
    interface.add_argument('uuid')

    interval: int = DEFAULT_INTERVAL
    interface.add_argument('-n', '--interval', type=int, default=interval)

    print_info: bool = False
    format_json: bool = False
    interface.add_argument('--info', action='store_true', dest='print_info')
    interface.add_argument('--json', action='store_true', dest='format_json')

    exceptions = {
        Task.NotFound: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        StatementError: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        **Application.exceptions,
    }

    def run(self) -> None:
        """Run submit thread."""
        check_database_available()
        self.check_uuid()
        self.wait_task()
        if self.print_info or self.format_json:
            with TaskInfoApp(uuid=self.uuid, format_json=self.format_json) as app:
                app.run()

    def wait_task(self):
        """Wait for the task to complete."""
        while True:
            task = Task.from_id(self.uuid, caching=False)
            if task.exit_status is None:
                log.trace(f'Waiting')
                time.sleep(self.interval)
            else:
                log.trace(f'Task completed ({task.completion_time})')
                break

    def check_uuid(self) -> None:
        """Check for valid UUID."""
        if not UUID_PATTERN.match(self.uuid):
            raise ArgumentError(f'Bad UUID: \'{self.uuid}\'')


TASK_GROUP_NAME = 'hyper-shell task'
TASK_GROUP_USAGE = f"""\
usage: {TASK_GROUP_NAME} [-h] <command> [<args>...]
Search, submit, track, and manage individual tasks.\
"""

TASK_GROUP_HELP = f"""\
{TASK_GROUP_USAGE}

commands:
submit                 {TaskSubmitApp.__doc__}
info                   {TaskInfoApp.__doc__}
wait                   {TaskWaitApp.__doc__}

options:
-h, --help             Show this message and exit.\
"""


class TaskGroupApp(ApplicationGroup):
    """Search, submit, track, and manage individual tasks."""

    interface = Interface(TASK_GROUP_NAME, TASK_GROUP_USAGE, TASK_GROUP_HELP)
    interface.add_argument('command')

    command = None
    commands = {
        'submit': TaskSubmitApp,
        'info': TaskInfoApp,
        'wait': TaskWaitApp,
    }
