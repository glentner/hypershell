# SPDX-FileCopyrightText: 2023 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""Task based operations."""


# type annotations
from __future__ import annotations
from typing import List, Dict, Callable, IO, Tuple, Any, Optional, Type

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
from cmdkit.app import Application, ApplicationGroup, exit_status
from cmdkit.cli import Interface, ArgumentError
from sqlalchemy import Column
from sqlalchemy.exc import StatementError
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
from hypershell.core.exceptions import get_shared_exception_mapping
from hypershell.database.model import Task, to_json_type
from hypershell.database import ensuredb

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

    exceptions = {
        **get_shared_exception_mapping(__name__)
    }

    def run(self: TaskSubmitApp) -> None:
        """Submit task to database."""
        ensuredb()
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
{INFO_PROGRAM} [-h] ID [--yaml | --json | --stdout | --stderr | -x FIELD]

Get metadata and/or task outputs.\
"""

INFO_HELP = f"""\
{INFO_USAGE}

Arguments:
  ID                    Unique task UUID.

Options:
      --yaml            Format task metadata as YAML.
      --json            Format task metadata as JSON.
  -x, --extract  FIELD  Print single field.
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

    print_stdout: bool = False
    print_stderr: bool = False
    extract_field: str = None
    output_format: str = 'normal'
    output_formats: List[str] = ['normal', 'json', 'yaml']
    output_interface = interface.add_mutually_exclusive_group()
    output_interface.add_argument('--format', default=output_format, dest='output_format', choices=output_formats)
    output_interface.add_argument('--json', action='store_const', const='json', dest='output_format')
    output_interface.add_argument('--yaml', action='store_const', const='yaml', dest='output_format')
    output_interface.add_argument('--stdout', action='store_true', dest='print_stdout')
    output_interface.add_argument('--stderr', action='store_true', dest='print_stderr')
    output_interface.add_argument('-x', '--extract', default=None, choices=Task.columns, dest='extract_field')

    exceptions = {
        Task.NotFound: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        **get_shared_exception_mapping(__name__)
    }

    def run(self: TaskInfoApp) -> None:
        """Get metadata/status/outputs of task."""
        ensuredb()
        check_uuid(self.uuid)
        if self.extract_field:
            self.print_field()
        elif self.print_stdout:
            self.print_file(self.outpath, self.task.outpath, sys.stdout)
        elif self.print_stderr:
            self.print_file(self.errpath, self.task.errpath, sys.stderr)
        elif self.output_format == 'normal':
            print_normal(self.task)
        else:
            self.print_formatted()

    def print_field(self: TaskInfoApp) -> None:
        """Print single field."""
        print(json.dumps(self.task.to_json().get(self.extract_field)).strip('"'))

    def print_formatted(self: TaskInfoApp) -> None:
        """Format and print task metadata to console."""
        formatter = self.format_method[self.output_format]
        output = formatter(self.task.to_json())  # NOTE: to_json() just means dict with converted value types
        if sys.stdout.isatty():
            output = Syntax(output, self.output_format, word_wrap=True,
                            theme = config.console.theme, background_color = 'default')
            Console().print(output)
        else:
            print(output, file=sys.stdout, flush=True)

    def print_file(self: TaskInfoApp, local_path: str, task_path: Optional[str], out_stream: IO) -> None:
        """Print file contents, fetch from client if necessary."""
        if task_path is None:
            raise RuntimeError(f'No {out_stream.name} for task ({self.uuid})')
        if not os.path.exists(local_path) and self.task.client_host != HOSTNAME:
            self.copy_remote_files()
        with open(local_path, mode='r') as in_stream:
            copyfileobj(in_stream, out_stream)

    @functools.cached_property
    def format_method(self: TaskInfoApp) -> Dict[str, Callable[[dict], str]]:
        """Format data method."""
        return {
            'yaml': functools.partial(yaml.dump, indent=4, sort_keys=False),
            'json': functools.partial(json.dumps, indent=4),
        }

    def copy_remote_files(self: TaskInfoApp) -> None:
        """Copy output and error files and to local host."""
        log.debug(f'Fetching remote files ({self.task.client_host})')
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
        **get_shared_exception_mapping(__name__)
    }

    def run(self: TaskWaitApp) -> None:
        """Wait for task to complete."""
        ensuredb()
        check_uuid(self.uuid)
        self.wait_task()
        if self.print_info or self.format_json:
            TaskInfoApp(uuid=self.uuid, format_json=self.format_json).run()
        elif self.print_status:
            TaskInfoApp(uuid=self.uuid, extract_field='exit_status').run()

    def wait_task(self: TaskWaitApp):
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

    exceptions = {
        **get_shared_exception_mapping(__name__)
    }

    def run(self: TaskRunApp) -> None:
        """Submit task and wait for completion."""
        ensuredb()
        task = Task.new(args=' '.join(self.argv))
        Task.add(task)
        TaskWaitApp(uuid=task.id, interval=self.interval).run()
        TaskInfoApp(uuid=task.id, print_stdout=True).run()
        TaskInfoApp(uuid=task.id, print_stderr=True).run()


SEARCH_PROGRAM = 'hyper-shell task search'
SEARCH_USAGE = f"""\
Usage:
hyper-shell task search [-h] [FIELD [FIELD ...]] [--where COND [COND ...]] 
                        [--order-by FIELD [--desc]] [--count | --limit NUM]
                        [--format FORMAT | --json | --csv]  [-d CHAR]
                        
Search for tasks in the database.\
"""

SEARCH_HELP = f"""\
{SEARCH_USAGE}

Arguments:
  FIELD                      Select specific named fields.

Options:
  -w, --where      COND...   List of conditional statements.
  -s, --order-by   FIELD     Order output by field.
      --failed               Alias for "exit_status != 0"
      --succeeded            Alias for "exit_status == 0"
      --finished             Alias for "exit_status != null"
      --remaining            Alias for "exit_status == null"
      --json                 Format output as JSON.
      --csv                  Format output as CSV.
      --format     FORMAT    Format output (normal, plain, table, csv, json).
  -d, --delimiter  CHAR      Field seperator for plain/csv formats.
  -l, --limit      NUM       Limit the number of results.
  -c, --count                Show count of results.
  -h, --help                 Show this message and exit.\
"""


# Listing of all field names in order (default for search)
ALL_FIELDS = list(Task.columns)


# Reasonable limit on output delimiter (typically just single char).
DELIMITER_MAX_SIZE = 100


class TaskSearchApp(Application):
    """Search for tasks in database."""

    interface = Interface(SEARCH_PROGRAM,
                          colorize_usage(SEARCH_USAGE),
                          colorize_usage(SEARCH_HELP))

    field_names: List[str] = ALL_FIELDS
    interface.add_argument('field_names', nargs='*', default=field_names)

    where_clauses: List[str] = None
    interface.add_argument('-w', '--where', nargs='*', default=[], dest='where_clauses')

    order_by: str = None
    order_desc: bool = False
    interface.add_argument('-s', '--order-by', default=None, choices=field_names)
    interface.add_argument('--desc', action='store_true', dest='order_desc')

    limit: int = None
    interface.add_argument('-l', '--limit', type=int, default=None)

    show_count: bool = False
    interface.add_argument('-c', '--count', action='store_true', dest='show_count')

    show_failed: bool = False
    show_finished: bool = False
    show_succeeded: bool = False
    show_remaining: bool = False
    search_alias_interface = interface.add_mutually_exclusive_group()
    search_alias_interface.add_argument('--failed', action='store_true', dest='show_failed')
    search_alias_interface.add_argument('--finished', action='store_true', dest='show_finished')
    search_alias_interface.add_argument('--remaining', action='store_true', dest='show_remaining')
    search_alias_interface.add_argument('--succeeded', action='store_true', dest='show_succeeded')

    output_format: str = '<default>'  # 'plain' if field_names else 'normal'
    output_formats: List[str] = ['normal', 'plain', 'table', 'json', 'csv']
    output_interface = interface.add_mutually_exclusive_group()
    output_interface.add_argument('--format', default=output_format, dest='output_format', choices=output_formats)
    output_interface.add_argument('--json', action='store_const', const='json', dest='output_format')
    output_interface.add_argument('--csv', action='store_const', const='csv', dest='output_format')

    output_delimiter: str = '<default>'  # <space> if plain, ',' if --csv, else not valid
    interface.add_argument('-d', '--delimiter', default=output_delimiter, dest='output_delimiter')

    exceptions = {
        StatementError: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        **get_shared_exception_mapping(__name__)
    }

    def run(self: TaskSearchApp) -> None:
        """Search for tasks in database."""
        ensuredb()
        self.check_field_names()
        self.check_output_format()
        if self.show_count:
            print(self.build_query().count())
        else:
            self.print_output(self.build_query().all())

    def build_query(self: TaskSearchApp) -> Query:
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

    def build_filters(self: TaskSearchApp) -> List[WhereClause]:
        """Create list of field selectors from command-line arguments."""
        if self.show_failed:
            self.where_clauses.append('exit_status != 0')
        if self.show_succeeded:
            self.where_clauses.append('exit_status == 0')
        if self.show_finished:
            self.where_clauses.append('exit_status != null')
        if self.show_remaining:
            self.where_clauses.append('exit_status == null')
        if not self.where_clauses:
            return []
        else:
            return [WhereClause.from_cmdline(arg) for arg in self.where_clauses]

    @functools.cached_property
    def fields(self: TaskSearchApp) -> List[Column]:
        """Field instances to query against."""
        return [getattr(Task, name) for name in self.field_names]

    @functools.cached_property
    def print_output(self: TaskSearchApp) -> Callable[[List[Tuple]], None]:
        """The requested output formatter."""
        return getattr(self, f'print_{self.output_format}')

    def print_table(self: TaskSearchApp, results: List[Tuple]) -> None:
        """Print in table format."""
        table = Table(title=None)
        for name in self.field_names:
            table.add_column(name)
        for record in results:
            table.add_row(*[json.dumps(to_json_type(value)).strip('"') for value in record])
        Console().print(table)

    @staticmethod
    def print_normal(results: List[Tuple]) -> None:
        """Print semi-structured output with all field names."""
        for record in results:
            print('---')
            print_normal(Task.from_dict(dict(zip(Task.columns, record))))

    def print_plain(self: TaskSearchApp, results: List[Tuple]) -> None:
        """Print plain text output with given field names, one task per line."""
        for record in results:
            data = [json.dumps(to_json_type(value)).strip('"') for value in record]
            print(self.output_delimiter.join(map(str, data)))

    def print_json(self: TaskSearchApp, results: List[Tuple]) -> None:
        """Print in output in JSON format."""
        data = [{field: to_json_type(value) for field, value in zip(self.field_names, record)}
                for record in results]
        if sys.stdout.isatty():
            Console().print(Syntax(json.dumps(data, indent=4, sort_keys=False), 'json',
                                   word_wrap=True, theme=config.console.theme,
                                   background_color='default'))
        else:
            print(json.dumps(data, indent=4, sort_keys=False), file=sys.stdout, flush=True)

    def print_csv(self: TaskSearchApp, results: List[Tuple]) -> None:
        """Print output in CVS format."""
        writer = csv.writer(sys.stdout, delimiter=self.output_delimiter)
        writer.writerow(self.field_names)
        for record in results:
            data = [to_json_type(value) for value in record]
            data = [value if isinstance(value, str) else json.dumps(value) for value in data]
            writer.writerow(data)

    def check_field_names(self: TaskSearchApp) -> None:
        """Check field names are valid."""
        for name in self.field_names:
            if name not in Task.columns:
                raise ArgumentError(f'Invalid field name \'{name}\'')

    def check_output_format(self: TaskSearchApp) -> None:
        """Check given output format is valid."""
        if self.field_names == ALL_FIELDS:
            if self.output_format == '<default>':
                self.output_format = 'normal'
        else:
            if self.output_format == '<default>':
                self.output_format = 'plain'
            elif self.output_format == 'normal':
                raise ArgumentError('Cannot use --format=normal with subset of field names')
        if self.output_delimiter != '<default>' and self.output_format not in ['plain', 'csv']:
            raise ArgumentError(f'Unused --delimiter for --format={self.output_format}')
        if len(self.output_delimiter) > DELIMITER_MAX_SIZE:
            raise ArgumentError(f'Output delimiter exceeds max size ({len(self.output_delimiter)} '
                                f'> {DELIMITER_MAX_SIZE})')
        if self.output_delimiter == '<default>':
            if self.output_format == 'csv':
                self.output_delimiter = ','
            else:
                self.output_delimiter = '\t'
        elif self.output_format == 'csv' and len(self.output_delimiter) != 1:
            # NOTE: csv module demands single-char delimiter
            raise ArgumentError(f'Valid --csv output must use single-char delimiter')


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

    exceptions = {
        Task.NotFound: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        **get_shared_exception_mapping(__name__)
    }

    def run(self: TaskUpdateApp) -> None:
        """Update individual task attribute directly."""
        ensuredb()
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

    def compile(self: WhereClause) -> BinaryExpression:
        """Build binary expression object out of elements."""
        op_call = self.op_call.get(self.operand)
        return op_call(getattr(Task, self.field), self.value)

    @classmethod
    def from_cmdline(cls: Type[WhereClause], argument: str) -> WhereClause:
        """
        Construct from command-line `argument`.

        Example:
            >>> WhereClause.from_cmdline('exit_status != 0')
            WhereClause(field='exit_status', value=0, operand='!=')
        """
        match = cls.pattern.match(argument)
        if match:
            field, operand, value = match.groups()
            if Task.columns.get(field) is str:
                # We want to coerce the value (e.g., as an int or None)
                # But also allow for, e.g., args==1 which expects type str.
                value = None if value.lower() in {'none', 'null'} else value
            else:
                value = smart_coerce(value)
            return WhereClause(field=field, value=value, operand=operand)
        else:
            raise ArgumentError(f'Where clause not understood ({argument})')


def print_normal(task: Task) -> None:
    """Print semi-structured task metadata with all field names."""
    task_data = {k: json.dumps(to_json_type(v)).strip('"') for k, v in task.to_dict().items()}
    print(f'          id: {task_data["id"]}')
    print(f'     command: {task_data["command"]} ({task_data["args"]})')
    print(f' exit_status: {task_data["exit_status"]}')
    print(f'   submitted: {task_data["submit_time"]}')
    print(f'   scheduled: {task_data["schedule_time"]}')
    print(f'     started: {task_data["start_time"]}')
    print(f'   completed: {task_data["completion_time"]}')
    print(f' submit_host: {task_data["submit_host"]} ({task_data["submit_id"]})')
    print(f' server_host: {task_data["server_host"]} ({task_data["server_id"]})')
    print(f' client_host: {task_data["client_host"]} ({task_data["client_id"]})')
    print(f'     attempt: {task_data["attempt"]}')
    print(f'     retried: {task_data["retried"]}')
    print(f'     outpath: {task_data["outpath"]}')
    print(f'     errpath: {task_data["errpath"]}')
    print(f' previous_id: {task_data["previous_id"]}')
    print(f'     next_id: {task_data["next_id"]}')
