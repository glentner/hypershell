# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Task based operations."""


# type annotations
from __future__ import annotations
from typing import List, Dict, Callable, IO, Tuple, Any

# standard libs
import os
import re
import sys
import csv
import json
import time
import functools
from dataclasses import dataclass
from shutil import copyfileobj

# external libs
import yaml
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from cmdkit.config import ConfigurationError
from cmdkit.app import Application, ApplicationGroup, exit_status
from cmdkit.cli import Interface, ArgumentError
from sqlalchemy import Column
from sqlalchemy.exc import StatementError, OperationalError
from sqlalchemy.orm import Query
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.sql.elements import BinaryExpression

# internal libs
from hypershell.core.ansi import colorize_usage
from hypershell.core.platform import default_path
from hypershell.core.config import config
from hypershell.core.exceptions import handle_exception
from hypershell.core.logging import Logger, HOSTNAME
from hypershell.core.remote import SSHConnection
from hypershell.core.types import smart_coerce
from hypershell.database.model import Task, to_json_type
from hypershell.database import initdb, checkdb, DatabaseUninitialized

# public interface
__all__ = ['TaskGroupApp', ]

# initialize logger
log = Logger.with_name(__name__)


SUBMIT_PROGRAM = 'hyper-shell task submit'
SUBMIT_USAGE = f"""\
Usage:
{SUBMIT_PROGRAM} [-h] ARGS...

Submit individual task to database.\
"""

SUBMIT_HELP = f"""\
{SUBMIT_USAGE}

Arguments:
  ARGS...                Command-line arguments.

Options:
  -h, --help             Show this message and exit.\
"""


class TaskSubmitApp(Application):
    """Submit task to database."""

    interface = Interface(SUBMIT_PROGRAM,
                          colorize_usage(SUBMIT_USAGE),
                          colorize_usage(SUBMIT_HELP))

    argv: List[str] = []
    interface.add_argument('argv', nargs='+')

    def run(self) -> None:
        """Submit task to database."""
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


INFO_PROGRAM = 'hyper-shell task info'
INFO_USAGE = f"""\
Usage: 
{INFO_PROGRAM} [-h] ID [--json | --stdout | --stderr | -x FIELD]

Get metadata and/or task outputs.\
"""

INFO_HELP = f"""\
{INFO_USAGE}

Arguments:
  ID                    Unique task UUID.

Options:
      --json            Format as JSON.
  -x, --extract  FIELD  Print this field only.
      --stdout          Fetch <stdout> from task.
      --stderr          Fetch <stderr> from task.
  -h, --help            Show this message and exit.\
"""


class TaskInfoApp(Application):
    """Get metadata/status/outputs of task."""

    interface = Interface(INFO_PROGRAM,
                          colorize_usage(INFO_USAGE),
                          colorize_usage(INFO_HELP))

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
        RuntimeError: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        **Application.exceptions,
    }

    def run(self) -> None:
        """Get metadata/status/outputs of task."""
        check_uuid(self.uuid)
        if self.extract_field and (self.print_stdout or self.print_stderr or self.format_json):
            raise ArgumentError('Cannot use -x/--extract with other output formats')
        if self.extract_field:
            print(json.dumps(getattr(self.task, self.extract_field)).strip('"'))
        elif not (self.print_stdout or self.print_stderr):
            self.write(self.task.to_json())
        elif self.print_stdout:
            if self.task.outpath:
                self.write_file(self.outpath, sys.stdout)
            else:
                raise RuntimeError(f'No <stdout> for task ({self.uuid})')
        elif self.print_stderr:
            if self.task.errpath:
                self.write_file(self.errpath, sys.stderr)
            else:
                raise RuntimeError(f'No <stderr> file for task ({self.uuid})')

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


WAIT_PROGRAM = 'hyper-shell task wait'
WAIT_USAGE = f"""\
Usage: 
{WAIT_PROGRAM} [-h] ID [-n SEC] [--info [--json] | --status]

Wait for task to complete.\
"""

WAIT_HELP = f"""\
{WAIT_USAGE}

Arguments:
  ID                    Unique UUID.

Options:
  -n, --interval  SEC   Time to wait between polling (default: {DEFAULT_INTERVAL}).
      --info            Print info on task.
      --json            Format info as JSON.
      --status          Print exit status for task.
  -h, --help            Show this message and exit.\
"""


class TaskWaitApp(Application):
    """Wait for task to complete."""

    interface = Interface(WAIT_PROGRAM,
                          colorize_usage(WAIT_USAGE),
                          colorize_usage(WAIT_HELP))

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
        """Wait for task to complete."""
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


RUN_PROGRAM = 'hyper-shell task run'
RUN_USAGE = f"""\
Usage: 
{RUN_PROGRAM} [-h] [-n SEC] ARGS... 

Submit individual task and wait for completion.\
"""

RUN_HELP = f"""\
{RUN_USAGE}

Arguments:
  ARGS                  Command-line arguments.

Options:
  -n, --interval  SEC   Time to wait between polling (default: {DEFAULT_INTERVAL}).
  -h, --help            Show this message and exit.\
"""


class TaskRunApp(Application):
    """Submit task and wait for completion."""

    interface = Interface(RUN_PROGRAM,
                          colorize_usage(RUN_USAGE),
                          colorize_usage(RUN_HELP))

    argv: List[str] = []
    interface.add_argument('argv', nargs='+')

    interval: int = DEFAULT_INTERVAL
    interface.add_argument('-n', '--interval', type=int, default=interval)

    def run(self) -> None:
        """Submit task and wait for completion."""
        task = Task.new(args=' '.join(self.argv))
        Task.add(task)
        TaskWaitApp(uuid=task.id, interval=self.interval).run()
        TaskInfoApp(uuid=task.id, print_stdout=True).run()
        TaskInfoApp(uuid=task.id, print_stderr=True).run()


SEARCH_PROGRAM = 'hyper-shell task search'
SEARCH_USAGE = f"""\
Usage:
hyper-shell task search [-h] [FIELD [FIELD ...]] [--where COND [COND ...]] 
                        [--order-by FIELD [--desc]] [-x | --json | --csv] 
                        [--count | --limit NUM]

Search for tasks in the database.\
"""

SEARCH_HELP = f"""\
{SEARCH_USAGE}

Arguments:
  FIELD                     Select specific named fields.

Options:
  -w, --where     COND...   List of conditional statements.
  -s, --order-by  FIELD     Order output by field.
  -x, --extract             Disable formatting for single column output.
      --json                Format output as JSON.
      --csv                 Format output as CSV.
  -l, --limit     NUM       Limit the number of rows.
  -c, --count               Show count of results.
  -h, --help                Show this message and exit.\
"""


class TaskSearchApp(Application):
    """Search for tasks in database."""

    interface = Interface(SEARCH_PROGRAM,
                          colorize_usage(SEARCH_USAGE),
                          colorize_usage(SEARCH_HELP))

    field_names: List[str] = list(Task.columns)
    interface.add_argument('field_names', nargs='*', default=field_names)

    where_clauses: List[str] = None
    interface.add_argument('-w', '--where', nargs='*', default=None, dest='where_clauses')

    order_by: str = None
    order_desc: bool = False
    interface.add_argument('-s', '--order-by', default=None, choices=field_names)
    interface.add_argument('--desc', action='store_true', dest='order_desc')

    limit: int = None
    interface.add_argument('-l', '--limit', type=int, default=None)

    count: bool = False
    interface.add_argument('-c', '--count', action='store_true')

    output_format: str = 'table'
    output_formats: List[str] = ['table', 'json', 'csv', ]
    output_interface = interface.add_mutually_exclusive_group()
    output_interface.add_argument('--format', default=output_format, dest='output_format', choices=output_formats)
    output_interface.add_argument('--json', action='store_const', const='json', dest='output_format')
    output_interface.add_argument('--csv', action='store_const', const='csv', dest='output_format')
    output_interface.add_argument('-x', '--extract', action='store_const', const='extract', dest='output_format')

    def run(self) -> None:
        """Search for tasks in database."""
        self.check_field_names()
        if self.count:
            print(self.build_query().count())
        else:
            self.print_output(self.build_query().all())

    def build_query(self) -> Query:
        """Build original query interface."""
        query = Task.query(*self.fields)
        if self.order_by:
            field = getattr(Task, self.order_by)
            if self.order_desc:
                field = field.desc()
            query = query.order_by(field)
        for where_clause in self.build_filters():
            query = query.filter(where_clause.compile())
        if self.limit:
            query = query.limit(self.limit)
        return query

    def build_filters(self) -> List[WhereClause]:
        """Create list of field selectors from command-line arguments."""
        if not self.where_clauses:
            return []
        else:
            return [WhereClause.from_cmdline(arg) for arg in self.where_clauses]

    @functools.cached_property
    def fields(self) -> List[Column]:
        """Field instances to query against."""
        return [getattr(Task, name) for name in self.field_names]

    @functools.cached_property
    def print_output(self) -> Callable[[List[Tuple]], None]:
        """The requested output formatter."""
        return getattr(self, f'print_{self.output_format}')

    def print_extract(self, results: List[Tuple]) -> None:
        """Basic output from single column."""
        if len(self.field_names) == 1:
            for (value, ) in results:
                print(json.dumps(to_json_type(value)).strip('"'), file=sys.stdout)
        else:
            raise ArgumentError(f'Cannot use -x/--extract for more than a single field')

    def print_table(self, results: List[Tuple]) -> None:
        """Print in table format from simple instances of ModelInterface."""
        table = Table(title=None)
        for name in self.field_names:
            table.add_column(name)
        for record in results:
            table.add_row(*[json.dumps(to_json_type(value)).strip('"') for value in record])
        Console().print(table)

    def print_json(self, results: List[Tuple]) -> None:
        """Print in JSON format from simple instances of ModelInterface."""
        data = [{field: to_json_type(value) for field, value in zip(self.field_names, record)}
                for record in results]
        if sys.stdout.isatty():
            Console().print(Syntax(json.dumps(data, indent=4, sort_keys=False), 'json',
                                   word_wrap=True, theme=config.console.theme,
                                   background_color='default'))
        else:
            print(json.dumps(data, indent=4, sort_keys=False), file=sys.stdout, flush=True)

    def print_csv(self, results: List[Tuple]) -> None:
        """Print in CVS format from simple instances of ModelInterface."""
        writer = csv.writer(sys.stdout)
        writer.writerow(self.field_names)
        for record in results:
            data = [to_json_type(value) for value in record]
            data = [value if isinstance(value, str) else json.dumps(value) for value in data]
            writer.writerow(data)

    def check_field_names(self) -> None:
        """Check field names are valid."""
        for name in self.field_names:
            if name not in Task.columns:
                raise ArgumentError(f'Invalid field name \'{name}\'')


UPDATE_PROGRAM = 'hyper-shell task update'
UPDATE_USAGE = f"""\
Usage: 
{UPDATE_PROGRAM} [-h] ID FIELD VALUE 

Update individual task metadata.\
"""

UPDATE_HELP = f"""\
{UPDATE_USAGE}

Arguments:
  ID                    Unique UUID.
  FIELD                 Task metadata field name.
  VALUE                 New value.

Options:
  -h, --help            Show this message and exit.\
"""


class TaskUpdateApp(Application):
    """Update individual task attribute directly."""

    interface = Interface(UPDATE_PROGRAM,
                          colorize_usage(UPDATE_USAGE),
                          colorize_usage(UPDATE_HELP))

    uuid: str
    interface.add_argument('uuid')

    field: str
    interface.add_argument('field', choices=list(Task.columns)[1:])  # NOTE: not ID!

    value: str
    interface.add_argument('value', type=smart_coerce)

    def run(self) -> None:
        """Update individual task attribute directly."""
        check_uuid(self.uuid)
        try:
            Task.update(self.uuid, **{self.field: self.value, })
        except StaleDataError as err:
            raise Task.NotFound(str(err)) from err


TASK_PROGRAM = 'hyper-shell task'
TASK_USAGE = f"""\
Usage: 
{TASK_PROGRAM} [-h] <command> [<args>...]

Search, submit, track, and manage individual tasks.\
"""

TASK_HELP = f"""\
{TASK_USAGE}

Commands:
  submit                 {TaskSubmitApp.__doc__}
  info                   {TaskInfoApp.__doc__}
  wait                   {TaskWaitApp.__doc__}
  run                    {TaskRunApp.__doc__}
  search                 {TaskSearchApp.__doc__}
  update                 {TaskUpdateApp.__doc__}

Options:
  -h, --help             Show this message and exit.\
"""


class TaskGroupApp(ApplicationGroup):
    """Search, submit, track, and manage individual tasks."""

    interface = Interface(TASK_PROGRAM,
                          colorize_usage(TASK_USAGE),
                          colorize_usage(TASK_HELP))

    interface.add_argument('command')

    command = None
    commands = {
        'submit': TaskSubmitApp,
        'info': TaskInfoApp,
        'wait': TaskWaitApp,
        'run': TaskRunApp,
        'search': TaskSearchApp,
        'update': TaskUpdateApp,
    }

    # NOTE: ApplicationGroup only defines the CompletedCommand mechanism.
    #       Extending this allows for a shared exception for all task commands
    exceptions = {
        ConfigurationError: functools.partial(handle_exception, logger=log, status=exit_status.bad_config),
        DatabaseUninitialized: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        OperationalError: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        **ApplicationGroup.exceptions
    }

    def __enter__(self: TaskGroupApp) -> TaskGroupApp:
        """Resource initialization."""
        db = config.database.get('file', None) or config.database.get('database', None)
        if config.database.provider == 'sqlite' and db in ('', ':memory:', None):
            raise ConfigurationError('Missing database configuration')
        if config.database.provider == 'sqlite':
            initdb()  # Auto-initialize if local sqlite provider
        else:
            checkdb()
        return self


@dataclass
class WhereClause:
    """Parse and prepare query filters based on command-line argument."""

    field: str
    value: Any
    operand: str

    pattern = re.compile(r'^([a-z_]+)\s*(==|!=|>|>=|<|<=|~)\s*(.*)$')
    op_call = {
        '==': lambda lhs, rhs: lhs == rhs,
        '!=': lambda lhs, rhs: lhs != rhs,
        '>=': lambda lhs, rhs: lhs >= rhs,
        '<=': lambda lhs, rhs: lhs <= rhs,
        '>':  lambda lhs, rhs: lhs > rhs,
        '<':  lambda lhs, rhs: lhs < rhs,
        '~':  lambda lhs, rhs: lhs.regexp_match(rhs),
    }

    def compile(self) -> BinaryExpression:
        """Build binary expression object out of elements."""
        op_call = self.op_call.get(self.operand)
        return op_call(getattr(Task, self.field), self.value)

    @classmethod
    def from_cmdline(cls, argument: str) -> WhereClause:
        """
        Construct from command-line `argument`.

        Example:
            >>> WhereClause.from_cmdline('exit_status != 0')
            WhereClause(field='exit_status', value=0, operand='!=')
        """
        match = cls.pattern.match(argument)
        if match:
            field, operand, value = match.groups()
            return WhereClause(field=field, value=smart_coerce(value), operand=operand)
        else:
            raise ArgumentError(f'Where clause not understood ({argument})')
