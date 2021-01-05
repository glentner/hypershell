# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""
Submit tasks to the database.

Example:
    >>> from hypershell.submit import submit_from
    >>> with open('some-file', mode='r') as source:
    ...     submit_from(source, buffersize=10)



Embed a `SubmitThread` in your application directly as the `ServerThread` does.
Call `terminate()` to stop early.

Example:
    >>> import sys
    >>> from hypershell.submit import SubmitThread
    >>> thread = SubmitThread(sys.stdin, buffersize=10)
    >>> thread.start()

    >>> thread.terminate()

Note:
    In order for the `SubmitThread` to actively monitor the state set by `terminate` and
    halt execution (a requirement because of how CPython does threading), the implementation
    uses a finite state machine. *You should not instantiate this machine directly*.

Warning:
    Because the `SubmitThread` checks state actively to decide whether to halt, if your
    `source` is blocking (e.g., `sys.stdin`) it will not be able to halt. If your main program
    exits however, the thread will be stopped regardless because it runs as a `daemon`.
"""


# type annotations
from __future__ import annotations
from typing import Iterable

# standard libs
import sys
import logging
from threading import Thread

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface

# internal libs
from hypershell.core.config import config
from hypershell.submit.lib import Machine as _Machine, DEFAULT_BUFFERSIZE, submit_tasks


# module level logger
log = logging.getLogger(__name__)


def submit_from(source: Iterable[str], buffersize: int = DEFAULT_BUFFERSIZE) -> int:
    """
    Buffer command lines from `source` and submit them to the database.

    Args:
        source (Iterable[str]):
            Command lines to submit.
        buffersize (int):
            Number of lines to buffer before submitting. (default: :data:`DEFAULT_BUFFERSIZE`)

    Returns:
        count (int):
            Total number of submitted tasks.
    """
    machine = _Machine(source, buffersize=buffersize)
    machine.run()
    return machine.count


class SubmitThread(Thread):
    """
    Submit tasks from within a thread.

    Example:
        >>> thread = SubmitThread('/some/taskfile', batchsize=10)
        >>> thread.start()
        >>> thread.join()
    """

    _machine: _Machine

    def __init__(self, source: Iterable[str], buffersize: int = DEFAULT_BUFFERSIZE) -> None:
        """Initialize thread."""
        super().__init__(name='hypershell-submit', daemon=True)
        self._machine = _Machine(source, buffersize=buffersize)

    def run(self) -> None:
        """Read from file and submit tasks to database."""
        self._machine.run()

    def terminate(self) -> None:
        """Signal to thread that is should terminate."""
        self._machine.is_running = False

    @classmethod
    def new(cls, *args, **kwargs) -> SubmitThread:
        """Initialize and start the thread."""
        thread = cls(*args, **kwargs)
        thread.start()
        return thread


_program_name = 'hypershell submit'
_program_usage = f"""\
usage: {_program_name} [-h] FILE [--batchsize NUM]
Submit command lines to the database.\
"""

_program_help = f"""\
{_program_usage}

arguments:
FILE                   Path to task file.

options:
-b, --buffersize  NUM  Number of lines to buffer.
-h, --help             Show this message and exit.\
"""


class SubmitApp(Application):
    """Submit tasks to the database."""

    interface = Interface(_program_name, _program_usage, _program_help)

    filepath: str = None
    interface.add_argument('filepath')

    buffersize: int = DEFAULT_BUFFERSIZE
    interface.add_argument('-b', '--buffersize', type=int, default=buffersize)

    def run(self) -> None:
        """Run submit thread."""
        self.check_config()
        self.submit(self.filepath, self.buffersize)

    @staticmethod
    def submit(filepath: str, buffersize: int) -> None:
        """Submit tasks from `filepath`."""
        if filepath == '-':
            count = submit_from(sys.stdin, buffersize=buffersize)
        else:
            with open(filepath, mode='r') as source:
                count = submit_from(source, buffersize=buffersize)
        log.info(f'Submitted {count} tasks from {filepath}')

    @staticmethod
    def check_config():
        """Emit warning for particular configuration."""
        if config.database.provider in ('', ':memory:'):
            log.warning('Submitting tasks to in-memory database as no effect')
