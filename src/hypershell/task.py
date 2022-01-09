# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Task based operations."""


# type annotations
from __future__ import annotations
from typing import List, Dict, Callable, IO

# standard libs
import os
import re
import sys
import json
import time
import logging
import functools
from shutil import copyfileobj

# external libs
import yaml
from rich.console import Console
from rich.syntax import Syntax
from cmdkit.config import ConfigurationError
from cmdkit.app import Application, ApplicationGroup, exit_status
from cmdkit.cli import Interface, ArgumentError
from sqlalchemy.exc import StatementError

# internal libs
from hypershell.core.platform import default_path
from hypershell.core.config import config
from hypershell.core.exceptions import handle_exception
from hypershell.core.logging import Logger, HOSTNAME
from hypershell.core.remote import SSHConnection
from hypershell.database.model import Task

# public interface
__all__ = ['TaskGroupApp', ]


log: Logger = logging.getLogger(__name__)


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


def check_uuid(value: str) -> None:
    """Check for valid UUID."""
    if not UUID_PATTERN.match(value):
        raise ArgumentError(f'Bad UUID: \'{value}\'')


TASK_INFO_NAME = 'hyper-shell task info'
TASK_INFO_USAGE = f"""\
usage: {TASK_INFO_NAME} [-h] ID [--json | --stdout | --stderr | -x FIELD]
Get info on individual task.\
"""
TASK_INFO_HELP = f"""\
{TASK_INFO_USAGE}

arguments:
ID                   Unique UUID.

options:
    --json           Format output as JSON.
-x, --extract FIELD  Print this field only.
    --stdout         Fetch <stdout> from task.
    --stderr         Fetch <stderr> from task.
-h, --help           Show this message and exit.\
"""


class TaskInfoApp(Application):
    """Lookup information on task."""

    interface = Interface(TASK_INFO_NAME, TASK_INFO_USAGE, TASK_INFO_HELP)

    uuid: str
    interface.add_argument('uuid')

    format_json: bool = False
    print_stdout: bool = False
    print_stderr: bool = False
    print_interface = interface.add_mutually_exclusive_group()
    print_interface.add_argument('--json', action='store_true', dest='format_json')
    print_interface.add_argument('--stdout', action='store_true', dest='print_stdout')
    print_interface.add_argument('--stderr', action='store_true', dest='print_stderr')

    extract_field: str = None
    interface.add_argument('-x', '--extract', default=None, choices=Task.columns, dest='extract_field')

    exceptions = {
        Task.NotFound: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        StatementError: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        FileNotFoundError: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        **Application.exceptions,
    }

    def run(self) -> None:
        """Run submit thread."""
        check_uuid(self.uuid)
        check_database_available()
        if self.extract_field and (self.print_stdout or self.print_stderr or self.format_json):
            raise ArgumentError('Cannot use -x/--extract with other output formats')
        if self.extract_field:
            print(json.dumps(getattr(self.task, self.extract_field)))
        elif not (self.print_stdout or self.print_stderr):
            self.write(self.task.to_json())
        elif self.print_stdout:
            self.write_file(self.outpath, sys.stdout)
        elif self.print_stderr:
            self.write_file(self.errpath, sys.stderr)

    def write_file(self: TaskInfoApp, path: str, dest: IO) -> None:
        """Write content from `path` to other `dest` stream."""
        if not os.path.exists(path) and self.task.client_host != HOSTNAME:
            log.debug(f'Fetching remote files ({self.task.client_host})')
            self.copy_remote_files()
        with open(path, mode='r') as stream:
            copyfileobj(stream, dest)

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

    def copy_remote_files(self: TaskInfoApp) -> None:
        """Copy output and error files and write to local streams."""
        with SSHConnection(self.task.client_host) as remote:
            remote.get_file(self.task.outpath, self.outpath)
            remote.get_file(self.task.errpath, self.errpath)

    @functools.cached_property
    def task(self: TaskInfoApp) -> Task:
        """Look up the task from the database."""
        return Task.from_id(self.uuid)

    @functools.cached_property
    def outpath(self: TaskInfoApp) -> str:
        """Local task output file path."""
        return os.path.join(default_path.lib, 'task', f'{self.task.id}.out')

    @functools.cached_property
    def errpath(self: TaskInfoApp) -> str:
        """Local task error file path."""
        return os.path.join(default_path.lib, 'task', f'{self.task.id}.err')


# Time to wait between database queries
DEFAULT_INTERVAL = 5


TASK_WAIT_NAME = 'hyper-shell task wait'
TASK_WAIT_USAGE = f"""\
usage: {TASK_WAIT_NAME} [-h] ID [-f] [-n SEC] [--info | --json | --status]
Wait for task to complete.\
"""
TASK_WAIT_HELP = f"""\
{TASK_WAIT_USAGE}

arguments:
ID                    Unique UUID.

options:
-n, --interval  SEC   Time to wait between polling (default: {DEFAULT_INTERVAL}).
    --info            Print info on task.
    --json            Format info as JSON.
    --status          Print exit status for task.
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
    print_status: bool = False
    output_interface = interface.add_mutually_exclusive_group()
    output_interface.add_argument('--info', action='store_true', dest='print_info')
    output_interface.add_argument('--json', action='store_true', dest='format_json')
    output_interface.add_argument('--status', action='store_true', dest='print_status')

    exceptions = {
        Task.NotFound: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        StatementError: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        **Application.exceptions,
    }

    def run(self) -> None:
        """Run submit thread."""
        check_database_available()
        check_uuid(self.uuid)
        self.wait_task()
        if self.print_info or self.format_json:
            TaskInfoApp(uuid=self.uuid, format_json=self.format_json).run()
        elif self.print_status:
            TaskInfoApp(uuid=self.uuid, extract_field='exit_status').run()

    def wait_task(self):
        """Wait for the task to complete."""
        log.info(f'Waiting on task ({self.uuid})')
        while True:
            task = Task.from_id(self.uuid, caching=False)
            if task.exit_status is None:
                log.trace(f'Waiting ({self.uuid})')
                time.sleep(self.interval)
                continue
            if task.exit_status != 0:
                log.warning(f'Non-zero exit status ({task.exit_status}) for task ({task.id})')
            log.info(f'Task completed ({task.completion_time})')
            break


TASK_RUN_NAME = 'hyper-shell task run'
TASK_RUN_USAGE = f"""\
usage: {TASK_RUN_NAME} [-h] [-n SEC] ARGS... 
Submit command and wait for completion.\
"""
TASK_RUN_HELP = f"""\
{TASK_RUN_USAGE}

arguments:
ARGS                  Command-line arguments.

options:
-n, --interval  SEC   Time to wait between polling (default: {DEFAULT_INTERVAL}).
-h, --help            Show this message and exit.\
"""


class TaskRunApp(Application):
    """Submit command and wait for completion."""

    interface = Interface(TASK_RUN_NAME, TASK_RUN_USAGE, TASK_RUN_HELP)

    argv: List[str] = []
    interface.add_argument('argv', nargs='+')

    interval: int = DEFAULT_INTERVAL
    interface.add_argument('-n', '--interval', type=int, default=interval)

    def run(self) -> None:
        """Run submit thread."""
        task = Task.new(args=' '.join(self.argv))
        Task.add(task)
        TaskWaitApp(uuid=task.id, interval=self.interval).run()
        TaskInfoApp(uuid=task.id, print_stdout=True).run()
        TaskInfoApp(uuid=task.id, print_stderr=True).run()


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
run                    {TaskRunApp.__doc__}

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
        'run': TaskRunApp,
    }
