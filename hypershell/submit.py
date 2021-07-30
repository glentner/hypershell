# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""
Submit tasks to the database.

Example:
    >>> from hypershell.submit import submit_from
    >>> with open('some-file', mode='r') as source:
    ...     submit_from(source, bundlesize=10)



Embed a `SubmitThread` in your application directly as the `ServerThread` does.
Call `stop()` to stop early.

Example:
    >>> import sys
    >>> from hypershell.submit import SubmitThread
    >>> thread = SubmitThread.new(sys.stdin, bundlesize=10)

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

import functools
from typing import List, Iterable, Iterator, IO, Optional, Dict, Callable

# standard libs
import sys
import logging
from datetime import datetime
from queue import Queue, Empty as QueueEmpty, Full as QueueFull
from enum import Enum

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface, ArgumentError

# internal libs
from hypershell.core.logging import Logger
from hypershell.core.config import config, default
from hypershell.core.fsm import State, StateMachine
from hypershell.core.queue import QueueClient, QueueConfig
from hypershell.core.thread import Thread
from hypershell.database.model import Task

# public interface
__all__ = ['submit_from', 'submit_file', 'SubmitThread', 'LiveSubmitThread',
           'SubmitApp', 'DEFAULT_BUNDLESIZE', 'DEFAULT_BUNDLEWAIT']


# module level logger
log: Logger = logging.getLogger(__name__)


class LoaderState(State, Enum):
    """Finite states of loader machine."""
    START = 0
    GET = 1
    PUT = 2
    HALT = 3


class Loader(StateMachine):
    """Enqueue tasks from source."""

    task: Task
    source: Iterator[str]
    queue: Queue[Optional[Task]]

    state = LoaderState.START
    states = LoaderState

    def __init__(self, source: Iterable[str], queue: Queue[Optional[Task]]) -> None:
        """Initialize source to read tasks and submit to database."""
        self.source = iter(source)
        self.queue = queue

    @functools.cached_property
    def actions(self) -> Dict[LoaderState, Callable[[], LoaderState]]:
        return {
            LoaderState.START: self.start,
            LoaderState.GET: self.get_task,
            LoaderState.PUT: self.put_task,
        }

    @staticmethod
    def start() -> LoaderState:
        """Jump to GET state."""
        log.debug('Starting loader')
        return LoaderState.GET

    def get_task(self) -> LoaderState:
        """Get the next task from the source."""
        try:
            self.task = Task.new(args=str(next(self.source)).strip())
            log.trace(f'Loaded task ({self.task.args})')
            return LoaderState.PUT
        except StopIteration:
            return LoaderState.HALT

    def put_task(self) -> LoaderState:
        """Enqueue loaded task."""
        try:
            self.queue.put(self.task, timeout=2)
            return LoaderState.GET
        except QueueFull:
            return LoaderState.PUT


class LoaderThread(Thread):
    """Run loader within dedicated thread."""

    def __init__(self, source: Iterable[str], queue: Queue[Optional[Task]]) -> None:
        """Initialize machine."""
        super().__init__(name='hypershell-submit')
        self.machine = Loader(source=source, queue=queue)

    def run(self) -> None:
        """Run machine."""
        self.machine.run()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop machine."""
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class DatabaseCommitterState(State, Enum):
    """Finite states for database submitter."""
    START = 0
    GET = 1
    COMMIT = 2
    FINAL = 3
    HALT = 4


DEFAULT_BUNDLESIZE: int = default.submit.bundlesize
DEFAULT_BUNDLEWAIT: int = default.submit.bundlewait


class DatabaseCommitter(StateMachine):
    """Commit tasks from local queue to database."""

    queue: Queue[Optional[Task]]
    tasks: List[Task]
    bundlesize: int
    bundlewait: int
    previous_submit: datetime

    state = DatabaseCommitterState.START
    states = DatabaseCommitterState

    def __init__(self,
                 queue: Queue[Optional[Task]],
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT) -> None:
        """Initialize with task queue and buffering parameters."""
        self.queue = queue
        self.tasks = []
        self.bundlesize = bundlesize
        self.bundlewait = bundlewait

    @functools.cached_property
    def actions(self) -> Dict[DatabaseCommitterState, Callable[[], DatabaseCommitterState]]:
        return {
            DatabaseCommitterState.START: self.start,
            DatabaseCommitterState.GET: self.get_task,
            DatabaseCommitterState.COMMIT: self.commit,
            DatabaseCommitterState.FINAL: self.finalize,
        }

    def start(self) -> DatabaseCommitterState:
        """Jump to GET state."""
        log.debug('Starting committer (database)')
        self.previous_submit = datetime.now()
        return DatabaseCommitterState.GET

    def get_task(self) -> DatabaseCommitterState:
        """Get tasks from local queue and check buffer."""
        try:
            task = self.queue.get(timeout=2)
        except QueueEmpty:
            return DatabaseCommitterState.GET
        if task is not None:
            self.tasks.append(task)
            since_last = (datetime.now() - self.previous_submit).total_seconds()
            if len(self.tasks) >= self.bundlesize or since_last >= self.bundlewait:
                return DatabaseCommitterState.COMMIT
            else:
                return DatabaseCommitterState.GET
        else:
            return DatabaseCommitterState.FINAL

    def commit(self) -> DatabaseCommitterState:
        """Commit tasks to database."""
        if self.tasks:
            Task.add_all(self.tasks)
            log.debug(f'Submitted {len(self.tasks)} tasks')
            self.tasks.clear()
            self.previous_submit = datetime.now()
        return DatabaseCommitterState.GET

    def finalize(self) -> DatabaseCommitterState:
        """Force final commit of tasks and halt."""
        self.commit()
        return DatabaseCommitterState.HALT


class DatabaseCommitterThread(Thread):
    """Run committer within dedicated thread."""

    def __init__(self, queue: Queue[Optional[Task]],
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT) -> None:
        """Initialize machine."""
        super().__init__(name='hypershell-submit-committer')
        self.machine = DatabaseCommitter(queue=queue, bundlesize=bundlesize, bundlewait=bundlewait)

    def run(self) -> None:
        """Run machine."""
        self.machine.run()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop machine."""
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class SubmitThread(Thread):
    """Manage asynchronous task queueing and submission workload."""

    queue: Queue[Optional[Task]]
    loader: LoaderThread
    committer: DatabaseCommitterThread

    def __init__(self, source: Iterable[str], bundlesize: int = DEFAULT_BUNDLESIZE,
                 bundlewait: int = DEFAULT_BUNDLEWAIT) -> None:
        """Initialize queue and child threads."""
        self.queue = Queue(maxsize=bundlesize)
        self.loader = LoaderThread(source=source, queue=self.queue)
        self.committer = DatabaseCommitterThread(queue=self.queue, bundlesize=bundlesize, bundlewait=bundlewait)
        super().__init__(name='hypershell-submit')

    def run(self) -> None:
        """Start child threads, wait."""
        log.debug('Starting submitter')
        self.loader.start()
        self.committer.start()
        self.loader.join()
        self.queue.put(None)
        self.committer.join()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.loader.stop(wait=wait, timeout=timeout)
        self.queue.put(None)
        self.committer.stop(wait=wait, timeout=timeout)
        super().stop(wait=wait, timeout=timeout)


class QueueCommitterState(State, Enum):
    """Finite states for queue submitter."""
    START = 0
    GET = 1
    PACK = 2
    COMMIT = 3
    FINAL = 4
    HALT = 5


class QueueCommitter(StateMachine):
    """Commit tasks from local queue directly to remote server queue."""

    local: Queue[Optional[Task]]
    client: QueueClient

    tasks: List[Task]
    bundle: List[bytes]

    bundlesize: int
    bundlewait: int
    previous_submit: datetime

    state = QueueCommitterState.START
    states = QueueCommitterState

    def __init__(self, local: Queue[Optional[Task]], client: QueueClient,
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT) -> None:
        """Initialize with queue handles and buffering parameters."""
        self.local = local
        self.client = client
        self.tasks = []
        self.bundle = []
        self.bundlesize = bundlesize
        self.bundlewait = bundlewait

    @functools.cached_property
    def actions(self) -> Dict[QueueCommitterState, Callable[[], QueueCommitterState]]:
        return {
            QueueCommitterState.START: self.start,
            QueueCommitterState.GET: self.get_task,
            QueueCommitterState.PACK: self.pack_bundle,
            QueueCommitterState.COMMIT: self.commit,
            QueueCommitterState.FINAL: self.finalize,
        }

    def start(self) -> QueueCommitterState:
        """Jump to GET state."""
        log.debug('Starting committer (no database, direct to server)')
        self.previous_submit = datetime.now()
        return QueueCommitterState.GET

    def get_task(self) -> QueueCommitterState:
        """Get tasks from local queue and check buffer."""
        try:
            task = self.local.get(timeout=2)
        except QueueEmpty:
            return QueueCommitterState.GET
        if task is not None:
            self.tasks.append(task)
            since_last = (datetime.now() - self.previous_submit).total_seconds()
            if len(self.tasks) >= self.bundlesize or since_last >= self.bundlewait:
                return QueueCommitterState.PACK
            else:
                return QueueCommitterState.GET
        else:
            return QueueCommitterState.FINAL

    def pack_bundle(self) -> QueueCommitterState:
        """Pack tasks into bundle for remote queue."""
        self.bundle = [task.pack() for task in self.tasks]
        return QueueCommitterState.COMMIT

    def commit(self) -> QueueCommitterState:
        """Commit tasks to server scheduling queue."""
        try:
            if self.tasks:
                self.client.scheduled.put(self.bundle, timeout=2)
                for task in self.tasks:
                    log.trace(f'Scheduled task ({task.id})')
                self.tasks = []
                self.bundle = []
                self.previous_submit = datetime.now()
            return QueueCommitterState.GET
        except QueueFull:
            return QueueCommitterState.COMMIT

    def finalize(self) -> QueueCommitterState:
        """Force final commit of tasks and halt."""
        self.commit()
        return QueueCommitterState.HALT


class QueueCommitterThread(Thread):
    """Run queue committer within dedicated thread."""

    def __init__(self, local: Queue[Optional[Task]], client: QueueClient,
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT) -> None:
        """Initialize machine."""
        super().__init__(name='hypershell-submit')
        self.machine = QueueCommitter(local=local, client=client, buffersize=buffersize, buffertime=buffertime)

    def run(self) -> None:
        """Run machine."""
        self.machine.run()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop machine."""
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class LiveSubmitThread(Thread):
    """Manage asynchronous task queueing and submission workload."""

    local: Queue[Optional[Task]]
    client: QueueClient
    loader: LoaderThread
    committer: QueueCommitterThread

    def __init__(self, source: Iterable[str], queue_config: QueueConfig,
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT) -> None:
        """Initialize queue and child threads."""
        self.local = Queue(maxsize=bundlesize)
        self.loader = LoaderThread(source=source, queue=self.local)
        self.client = QueueClient(config=queue_config)
        self.committer = QueueCommitterThread(local=self.local, client=self.client,
                                              bundlesize=bundlesize, bundlewait=bundlewait)
        super().__init__(name='hypershell-submit')

    def run(self) -> None:
        """Start child threads, wait."""
        log.debug('Starting submitter (live)')
        with self.client:
            self.loader.start()
            self.committer.start()
            self.loader.join()
            self.local.put(None)
            self.committer.join()
            log.trace(f'Registering final task ({self.committer.final_task_id})')
            self.client.terminator.put(self.committer.final_task_id.encode())

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.loader.stop(wait=wait, timeout=timeout)
        self.local.put(None)
        self.committer.stop(wait=wait, timeout=timeout)
        super().stop(wait=wait, timeout=timeout)


def submit_from(source: Iterable[str], queue_config: QueueConfig = None,
                bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT) -> None:
    """Submit all task arguments from `source`."""
    if queue_config:
        thread = LiveSubmitThread.new(source=source, queue_config=queue_config,
                                      bundlesize=bundlesize, bundlewait=bundlewait)
    else:
        thread = SubmitThread.new(source=source, bundlesize=bundlesize, bundlewait=bundlewait)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


def submit_file(path: str, queue_config: QueueConfig = None,
                bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT, **options) -> None:
    """Submit tasks by reading argument lines from local file `path`."""
    with open(path, mode='r', **options) as stream:
        submit_from(stream, queue_config=queue_config, bundlesize=bundlesize, bundlewait=bundlewait)


APP_NAME = 'hypershell submit'
APP_USAGE = f"""\
usage: {APP_NAME} [-h] [FILE] [-b NUM] [-w SEC]
Submit command lines to the database.\
"""

APP_HELP = f"""\
{APP_USAGE}

arguments:
FILE                   Path to task file ("-" for <stdin>).

options:
-b, --bundlesize  NUM  Number of lines to buffer (default: {DEFAULT_BUNDLESIZE}).
-w, --bundlewait  SEC  Seconds to wait before flushing tasks (default: {DEFAULT_BUNDLEWAIT}).
-h, --help             Show this message and exit.\
"""


class SubmitApp(Application):
    """Submit tasks to the database."""

    name = APP_NAME
    interface = Interface(APP_NAME, APP_USAGE, APP_HELP)

    source: IO
    filepath: str
    interface.add_argument('filepath', nargs='?', default='-')

    bundlesize: int = config.submit.bundlesize
    interface.add_argument('-b', '--bundlesize', type=int, default=bundlesize)

    bundlewait: int = config.submit.bundlewait
    interface.add_argument('-w', '--bundlewait', type=int, default=bundlewait)

    count: int

    def run(self) -> None:
        """Run submit thread."""
        self.check_config()
        self.submit_all()

    def submit_all(self) -> None:
        """Submit all tasks from source."""
        submit_from(self.enumerated(self.source),
                    bundlesize=self.bundlesize, bundlewait=self.bundlewait)
        log.info(f'Submitted {self.count} tasks from {self.filename}')

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

    @property
    def filename(self) -> str:
        """The basename of the file."""
        return '<stdin>' if self.filepath == '-' else os.path.basename(self.filepath)

    def __enter__(self) -> SubmitApp:
        """Open file if not stdin."""
        self.source = sys.stdin if self.filepath == '-' else open(self.filepath, mode='r')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close file if not stdin."""
        if self.source is not sys.stdin:
            self.source.close()
