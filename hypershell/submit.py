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
Call `stop()` to stop early.

Example:
    >>> import sys
    >>> from hypershell.submit import SubmitThread
    >>> thread = SubmitThread.new(sys.stdin, buffersize=10)

Note:
    In order for the `SubmitThread` to actively monitor the state set by `stop` and
    halt execution (a requirement because of how CPython does threading), the implementation
    uses a finite state machine. *You should not instantiate this machine directly*.

Warning:
    Because the `SubmitThread` checks state actively to decide whether to halt, if your
    `source` is blocking (e.g., `sys.stdin`) it will not be able to halt immediately. If
    your main program exits however, the thread will be stopped regardless because it
    runs as a `daemon`.
"""


# type annotations
from __future__ import annotations
from typing import List, Iterable, Iterator, IO, Optional

# standard libs
import sys
import logging
from datetime import datetime
from queue import Queue, Empty

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface

# internal libs
from hypershell.core.config import config
from hypershell.core.fsm import State, StateMachine, HALT
from hypershell.core.thread import Thread
from hypershell.database.model import Task

# public interface
__all__ = ['submit_from', 'submit_file', 'SubmitThread',
           'SubmitApp', 'DEFAULT_BUFFERSIZE', 'DEFAULT_BUFFERTIME']


# module level logger
log = logging.getLogger(__name__)


class __LoaderStart(State):
    def run(self, machine: LoaderImpl) -> State:
        """Initial state for loader."""
        return LOADER_GET


class __LoaderGet(State):
    def run(self, machine: LoaderImpl) -> State:
        """Get the next task from the source."""
        try:
            machine.task = Task.new(args=str(next(machine.source)).strip())
            log.debug(f'Loaded task ({machine.task.args})')
            return LOADER_PUT
        except StopIteration:
            return HALT


class __LoaderPut(State):
    def run(self, machine: LoaderImpl) -> State:
        """Enqueue loaded task."""
        machine.queue.put(machine.task)
        return LOADER_GET


LOADER_START = __LoaderStart()
LOADER_GET = __LoaderGet()
LOADER_PUT = __LoaderPut()


class LoaderImpl(StateMachine):
    """Enqueue tasks from source."""

    task: Task
    source: Iterator[str]
    queue: Queue[Optional[Task]]

    def __init__(self, source: Iterable[str], queue: Queue[Optional[Task]]) -> None:
        """Initialize IO `stream` to read tasks and submit to database."""
        self.source = iter(source)
        self.queue = queue
        super().__init__(start=LOADER_START)


class LoaderThread(Thread):
    """Run loader within dedicated thread."""

    def __init__(self, source: Iterable[str], queue: Queue[Optional[Task]]) -> None:
        super().__init__(name='hypershell-submit')
        self.machine = LoaderImpl(source=source, queue=queue)

    def run(self) -> None:
        self.machine.run()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class __QueueStart(State):
    def run(self, machine: QueueImpl) -> State:
        """Initial state for queue."""
        machine.previous_submit = datetime.now()
        return QUEUE_GET


class __QueueGet(State):
    def run(self, machine: QueueImpl) -> State:
        """Pull tasks from queue and check buffer."""
        try:
            task = machine.queue.get(timeout=1)
        except Empty:
            return QUEUE_GET
        if task is not None:
            machine.tasks.append(task)
            since_last = (datetime.now() - machine.previous_submit).total_seconds()
            if len(machine.tasks) >= machine.buffersize or since_last >= machine.buffertime:
                return QUEUE_SUBMIT
            else:
                return QUEUE_GET
        else:
            return QUEUE_FINALIZE


class __QueueSubmit(State):
    def run(self, machine: QueueImpl) -> State:
        """Commit tasks to database."""
        if machine.tasks:
            Task.add_all(machine.tasks)
            log.debug(f'Submitted {len(machine.tasks)} tasks')
            machine.tasks.clear()
            machine.previous_submit = datetime.now()
        return QUEUE_GET


class __QueueFinalize(State):
    def run(self, machine: QueueImpl) -> State:
        """Force final commit of tasks and halt."""
        QUEUE_SUBMIT.run(machine)
        return HALT


QUEUE_START = __QueueStart()
QUEUE_GET = __QueueGet()
QUEUE_SUBMIT = __QueueSubmit()
QUEUE_FINALIZE = __QueueFinalize()


DEFAULT_BUFFERSIZE: int = 10
DEFAULT_BUFFERTIME: int = 1


class QueueImpl(StateMachine):
    """Submit tasks from queue to database."""

    queue: Queue[Optional[Task]]
    tasks: List[Task]
    buffersize: int
    buffertime: int
    previous_submit: datetime

    def __init__(self, queue: Queue[Optional[Task]], buffersize: int = DEFAULT_BUFFERSIZE,
                 buffertime: int = DEFAULT_BUFFERTIME) -> None:
        """Assign member."""
        self.queue = queue
        self.tasks = []
        self.buffersize = buffersize
        self.buffertime = buffertime
        super().__init__(start=QUEUE_START)


class QueueThread(Thread):
    """Run queue submitter within dedicated thread."""

    def __init__(self, queue: Queue[Optional[Task]], buffersize: int = DEFAULT_BUFFERSIZE,
                 buffertime: int = DEFAULT_BUFFERTIME) -> None:
        super().__init__(name='hypershell-submit')
        self.machine = QueueImpl(queue=queue, buffersize=buffersize, buffertime=buffertime)

    def run(self) -> None:
        self.machine.run()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class SubmitThread(Thread):
    """Manage asynchronous task queueing and submission workload."""

    queue: Queue[Optional[Task]]
    loader_thread: LoaderThread
    queue_thread: QueueThread

    def __init__(self, source: Iterable[str], buffersize: int = DEFAULT_BUFFERSIZE,
                 buffertime: int = DEFAULT_BUFFERTIME) -> None:
        """Initialize queue and child threads."""
        self.queue = Queue(maxsize=buffersize)
        self.loader_thread = LoaderThread(source=source, queue=self.queue)
        self.queue_thread = QueueThread(queue=self.queue, buffersize=buffersize, buffertime=buffertime)
        super().__init__(name='hypershell-submit')

    def run(self) -> None:
        """Start child threads, wait."""
        self.loader_thread.start()
        self.queue_thread.start()
        self.loader_thread.join()
        self.queue.put(None)
        self.queue_thread.join()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.loader_thread.stop(wait=wait, timeout=timeout)
        self.queue.put(None)
        self.queue_thread.stop(wait=wait, timeout=timeout)
        super().stop(wait=wait, timeout=timeout)


def submit_from(source: Iterable[str], buffersize: int = DEFAULT_BUFFERSIZE,
                buffertime: int = DEFAULT_BUFFERTIME) -> None:
    """Submit all task arguments from `source`."""
    thread = SubmitThread.new(source=source, buffersize=buffersize, buffertime=buffertime)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


def submit_file(path: str, buffersize: int = DEFAULT_BUFFERSIZE,
                buffertime: int = DEFAULT_BUFFERTIME, **options) -> None:
    """Submit tasks by reading argument lines from local file `path`."""
    with open(path, mode='r', **options) as stream:
        submit_from(stream, buffersize=buffersize, buffertime=buffertime)


APP_NAME = 'hypershell submit'
APP_USAGE = f"""\
usage: {APP_NAME} [-h] FILE [--buffersize NUM] [--buffertime SEC]
Submit command lines to the database.\
"""

APP_HELP = f"""\
{APP_USAGE}

arguments:
FILE                   Path to task file ("-" for <stdin>).

options:
-b, --buffersize  NUM  Number of lines to buffer.
-t, --buffertime  SEC  Seconds to wait before flushing tasks.
-h, --help             Show this message and exit.\
"""


class SubmitApp(Application):
    """Submit tasks to the database."""

    name = APP_NAME
    interface = Interface(APP_NAME, APP_USAGE, APP_HELP)

    source: IO
    filepath: str
    interface.add_argument('filepath')

    buffersize: int = DEFAULT_BUFFERSIZE
    interface.add_argument('-b', '--buffersize', type=int, default=buffersize)

    buffertime: int = DEFAULT_BUFFERTIME
    interface.add_argument('-t', '--buffertime', type=int, default=buffertime)

    count: int

    def run(self) -> None:
        """Run submit thread."""
        self.check_config()
        self.submit_all()

    def submit_all(self) -> None:
        """Submit all tasks from source."""
        submit_from(self.enumerated(self.source), buffersize=self.buffersize, buffertime=self.buffertime)
        log.info(f'Submitted {self.count} tasks from {self.filepath}')

    def enumerated(self, source: IO) -> Iterable[str]:
        """Yield lines from `source` and update counter."""
        for count, line in enumerate(source):
            self.count = count + 1
            yield line

    @staticmethod
    def check_config():
        """Emit warning for particular configuration."""
        db = config.database.get('file', None) or config.database.get('database', None)
        if config.database.provider == 'sqlite' and db in ('', ':memory:', None):
            log.warning('Submitting tasks to in-memory database has no effect')

    def __enter__(self) -> SubmitApp:
        """Open file if not stdin."""
        self.source = sys.stdin if self.filepath == '-' else open(self.filepath, mode='r')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close file if not stdin."""
        if self.source is not sys.stdin:
            self.source.close()
