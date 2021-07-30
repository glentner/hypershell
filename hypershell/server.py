# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""
Schedule and collect bundles tasks from the database.

Example:
    >>> from hypershell.server import serve_forever
    >>> serve_from(source=['echo a', 'echo b'])

Embed a `ServerThread` in your application directly. Call `stop()` to stop early.

Example:
    >>> import sys
    >>> from hypershell.server import ServerThread
    >>> thread = ServerThread.new(source=sys.stdin, bind=('0.0.0.0', 8080), bundlesize=10)

Note:
    In order for the `ServerThread` to actively monitor the state set by `stop` and
    halt execution (a requirement because of how CPython does threading), the implementation
    uses a finite state machine. *You should not instantiate this machine directly*.

Warning:
    Because the `ServerThread` checks state actively to decide whether to halt, if your
    `source` is blocking (e.g., `sys.stdin`) it will not be able to halt immediately. If
    your main program exits however, the thread will be stopped regardless because it
    runs as a `daemon`.
"""


# type annotations
from __future__ import annotations
from typing import List, Dict, Tuple, Iterable, IO, Optional, Callable

# standard libs
import sys
import time
import logging
import functools
from enum import Enum
from queue import Empty as QueueEmpty, Full as QueueFull

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface, ArgumentError

# internal libs
from hypershell.core.config import config, default
from hypershell.core.logging import Logger
from hypershell.core.fsm import State, StateMachine
from hypershell.core.thread import Thread
from hypershell.core.queue import QueueServer, QueueConfig
from hypershell.database.model import Task
from hypershell.submit import SubmitThread, LiveSubmitThread, DEFAULT_BUNDLEWAIT

# public interface
__all__ = ['serve_from', 'serve_file', 'serve_forever', 'ServerThread', 'ServerApp',
           'DEFAULT_BUNDLESIZE', 'DEFAULT_ATTEMPTS', ]


# module level logger
log: Logger = logging.getLogger(__name__)


class SchedulerState(State, Enum):
    """Finite states of the scheduler."""
    START = 0
    LOAD = 1
    PACK = 2
    POST = 3
    HALT = 4


# Note: unless specified otherwise for larger problems, a bundle of size one allows
# for greater concurrency on smaller workloads.
DEFAULT_BUNDLESIZE: int = default.server.bundlesize
DEFAULT_ATTEMPTS: int = default.server.attempts
DEFAULT_EAGER_MODE: bool = default.server.eager
DEFAULT_QUERY_PAUSE: int = default.server.wait


class Scheduler(StateMachine):
    """Enqueue tasks from database."""

    tasks: List[Task]
    queue: QueueServer
    bundle: List[bytes]

    bundlesize: int
    attempts: int
    eager: bool
    forever_mode: bool

    state = SchedulerState.START
    states = SchedulerState

    def __init__(self, queue: QueueServer, bundlesize: int = DEFAULT_BUNDLESIZE,
                 attempts: int = DEFAULT_ATTEMPTS, eager: bool = DEFAULT_EAGER_MODE,
                 forever_mode: bool = False) -> None:
        """Initialize queue and parameters."""
        self.queue = queue
        self.bundle = []
        self.bundlesize = bundlesize
        self.attempts = attempts
        self.eager = eager
        self.forever_mode = forever_mode

    @functools.cached_property
    def actions(self) -> Dict[SchedulerState, Callable[[], SchedulerState]]:
        return {
            SchedulerState.START: self.start,
            SchedulerState.LOAD: self.load_bundle,
            SchedulerState.PACK: self.pack_bundle,
            SchedulerState.POST: self.post_bundle,
        }

    @staticmethod
    def start() -> SchedulerState:
        """Jump to LOAD state."""
        log.debug('Starting scheduler')
        return SchedulerState.LOAD

    def load_bundle(self) -> SchedulerState:
        """Load the next task bundle from the database."""
        self.tasks = Task.next(limit=self.bundlesize, attempts=self.attempts, eager=self.eager)
        if self.tasks:
            return SchedulerState.PACK
        # NOTE: an empty database must wait for at least one task
        elif not self.forever_mode and Task.count() > 0 and Task.count_remaining() == 0:
            return SchedulerState.HALT
        else:
            time.sleep(DEFAULT_QUERY_PAUSE)
            return SchedulerState.LOAD

    def pack_bundle(self) -> SchedulerState:
        """Pack tasks into bundle (list)."""
        self.bundle = [task.pack() for task in self.tasks]
        return SchedulerState.POST

    def post_bundle(self) -> SchedulerState:
        """Put bundle on outbound queue."""
        try:
            self.queue.scheduled.put(self.bundle, timeout=2)
            for task in self.tasks:
                log.debug(f'Scheduled task ({task.id})')
            return SchedulerState.LOAD
        except QueueFull:
            return SchedulerState.POST


class SchedulerThread(Thread):
    """Run scheduler within dedicated thread."""

    def __init__(self, queue: QueueServer, bundlesize: int = DEFAULT_BUNDLESIZE,
                 attempts: int = DEFAULT_ATTEMPTS, eager: bool = DEFAULT_EAGER_MODE,
                 forever_mode: bool = False) -> None:
        """Initialize machine."""
        super().__init__(name='hypershell-scheduler')
        self.machine = Scheduler(queue=queue, bundlesize=bundlesize, attempts=attempts, eager=eager,
                                 forever_mode=forever_mode)

    def run(self) -> None:
        """Run machine."""
        self.machine.run()
        log.debug('Stopping scheduler')

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop machine."""
        log.debug('Stopping scheduler')
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class ReceiverState(State, Enum):
    """Finite states for receiver."""
    START = 0
    UNLOAD = 1
    UNPACK = 2
    UPDATE = 3
    HALT = 4


class Receiver(StateMachine):
    """Collect incoming finished task bundles and update database."""

    tasks: List[Task]
    queue: QueueServer
    bundle: List[bytes]

    live: bool
    print_on_failure: bool

    state = ReceiverState.START
    states = ReceiverState

    def __init__(self, queue: QueueServer, live: bool = False, print_on_failure: bool = False) -> None:
        """Initialize receiver."""
        self.queue = queue
        self.bundle = []
        self.live = live
        self.print_on_failure = print_on_failure

    @functools.cached_property
    def actions(self) -> Dict[ReceiverState, Callable[[], ReceiverState]]:
        return {
            ReceiverState.START: self.start,
            ReceiverState.UNLOAD: self.unload_bundle,
            ReceiverState.UNPACK: self.unpack_bundle,
            ReceiverState.UPDATE: self.update_tasks,
        }

    @staticmethod
    def start() -> ReceiverState:
        """Jump to UNLOAD state."""
        log.debug('Starting receiver')
        return ReceiverState.UNLOAD

    def unload_bundle(self) -> ReceiverState:
        """Get the next bundle from the completed task queue."""
        try:
            self.bundle = self.queue.completed.get(timeout=2)
            if self.bundle is not None:
                return ReceiverState.UNPACK
            else:
                log.debug('Stopping receiver')
                return ReceiverState.HALT
        except QueueEmpty:
            return ReceiverState.UNLOAD

    def unpack_bundle(self) -> ReceiverState:
        """Unpack previous bundle into list of tasks."""
        self.tasks = [Task.unpack(data) for data in self.bundle]
        return ReceiverState.UPDATE

    def update_tasks(self) -> ReceiverState:
        """Update tasks in database with run details."""
        if not self.live:
            Task.update_all([task.to_dict() for task in self.tasks])
        for task in self.tasks:
            log.debug(f'Completed task ({task.id})')
            if task.exit_status != 0:
                log.warning(f'Non-zero exit status ({task.exit_status}) for task ({task.id})')
                if self.print_on_failure:
                    print(task.args)
        return ReceiverState.UNLOAD


class ReceiverThread(Thread):
    """Run receiver within dedicated thread."""

    def __init__(self, queue: QueueServer, live: bool = False, print_on_failure: bool = False) -> None:
        """Initialize machine."""
        super().__init__(name='hypershell-receiver')
        self.machine = Receiver(queue=queue, live=live, print_on_failure=print_on_failure)

    def run(self) -> None:
        """Run machine."""
        self.machine.run()
        self.stop()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop machine."""
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class ServerThread(Thread):
    """Manage asynchronous task bundle scheduling and receiving."""

    queue: QueueServer
    submitter: Optional[SubmitThread]
    scheduler: Optional[SchedulerThread]
    receiver: ReceiverThread

    def __init__(self,
                 source: Iterable[str] = None, live: bool = False, forever_mode: bool = False,
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
                 address: Tuple[str, int] = (QueueConfig.host, QueueConfig.port), auth: str = QueueConfig.auth,
                 max_retries: int = DEFAULT_ATTEMPTS - 1, eager: bool = False,
                 print_on_failure: bool = False) -> None:
        """Initialize queue manager and child threads."""
        queue_config = QueueConfig(host=address[0], port=address[1], auth=auth)
        self.queue = QueueServer(config=queue_config)
        if live:
            log.info('Running live (no scheduler)')
            self.scheduler = None
            self.submitter = None if not source else LiveSubmitThread(
                source, queue_config=queue_config, buffersize=bundlesize, buffertime=buffertime)
        else:
            self.submitter = None if not source else SubmitThread(source, buffersize=bundlesize, buffertime=buffertime)
            self.scheduler = SchedulerThread(queue=self.queue, bundlesize=bundlesize, attempts=max_retries + 1,
                                             eager=eager, forever_mode=forever_mode)
        self.receiver = ReceiverThread(queue=self.queue, live=live, print_on_failure=print_on_failure)
        super().__init__(name='hypershell-server')

    def run(self) -> None:
        """Start child threads, wait."""
        log.debug('Starting server')
        with self.queue:
            self.start_threads()
            self.wait_submitter()
            self.wait_scheduler()
            self.wait_clients()

    def start_threads(self) -> None:
        """Start child threads."""
        if self.submitter is not None:
            self.submitter.start()
        if self.scheduler is not None:
            self.scheduler.start()
        self.receiver.start()

    def wait_submitter(self) -> None:
        """Wait on task submission to complete."""
        if self.submitter is not None:
            self.submitter.join()

    def wait_scheduler(self) -> None:
        """Wait for all tasks to be completed."""
        if self.scheduler is not None:
            self.scheduler.join()

    def wait_clients(self) -> None:
        """Send disconnect signal to each clients."""
        try:
            log.info('Sending disconnect request to clients')
            for hostname in iter(functools.partial(self.queue.connected.get, timeout=2), None):
                self.queue.scheduled.put(None)  # NOTE: one for each
                self.queue.connected.task_done()
                log.trace(f'Disconnect request sent ({hostname.decode()})')
        except QueueEmpty:
            pass

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        if self.submitter is not None:
            self.submitter.stop(wait=wait, timeout=timeout)
        if self.scheduler is not None:
            self.scheduler.stop(wait=wait, timeout=timeout)
        self.queue.completed.put(None)
        self.receiver.stop(wait=wait, timeout=timeout)
        super().stop(wait=wait, timeout=timeout)


def serve_from(source: Iterable[str], live: bool = False, print_on_failure: bool = False,
               bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
               address: Tuple[str, int] = (QueueConfig.host, QueueConfig.port), auth: str = QueueConfig.auth,
               max_retries: int = DEFAULT_ATTEMPTS - 1, eager: bool = DEFAULT_EAGER_MODE) -> None:
    """Run server with the given task `source`, run until complete."""
    thread = ServerThread.new(source=source, live=live, print_on_failure=print_on_failure,
                              bundlesize=bundlesize, bundlewait=bundlewait,
                              address=address, auth=auth, max_retries=max_retries, eager=eager)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


def serve_file(path: str, live: bool = False, print_on_failure: bool = False,
               bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
               address: Tuple[str, int] = (QueueConfig.host, QueueConfig.port), auth: str = QueueConfig.auth,
               max_retries: int = DEFAULT_ATTEMPTS - 1, eager: bool = DEFAULT_EAGER_MODE, **file_options) -> None:
    """Run server with tasks from a local file `path`, run until complete."""
    with open(path, mode='r', **file_options) as stream:
        serve_from(stream, live=live, print_on_failure=print_on_failure,
                   bundlesize=bundlesize, bundlewait=bundlewait, address=address, auth=auth,
                   max_retries=max_retries, eager=eager)


def serve_forever(bundlesize: int = DEFAULT_BUNDLESIZE, live: bool = False, print_on_failure: bool = False,
                  address: Tuple[str, int] = (QueueConfig.host, QueueConfig.port), auth: str = QueueConfig.auth,
                  max_retries: int = DEFAULT_ATTEMPTS - 1, eager: bool = DEFAULT_EAGER_MODE) -> None:
    """Run server forever."""
    thread = ServerThread.new(source=None, live=live, print_on_failure=print_on_failure,
                              bundlesize=bundlesize, address=address, auth=auth,
                              forever_mode=True, max_retries=max_retries, eager=eager)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


APP_NAME = 'hypershell server'
APP_USAGE = f"""\
usage: {APP_NAME} [-h] [FILE | --server-forever] [-b NUM] [-w SEC] [--max-retries NUM [--eager]]
                       [-H ADDR] [-p NUM] [--auth KEY] [--live] [--print]
Run hypershell server.\
"""

APP_HELP = f"""\
{APP_USAGE}

The server includes a scheduler component that pulls tasks from the database and offers
them up on a distributed queue to clients. It also has a receiver that collects the results
of finished tasks. Optionally, the server can submit tasks (FILE). When submitting tasks,
the -w/--bundlewait options are the same as for 'hypershell submit' and the -b/--bundlesize
are used for -b/--bundlesize.

With --max-retries greater than zero, the scheduler will check for a non-zero exit status
for tasks and re-submit them if their previous number of attempts is less.

Tasks are bundled and clients pull them in these bundles. However, by default the bundle size 
is one, meaning that at small scales there is greater responsiveness.

arguments:
FILE                        Path to task file ("-" for <stdin>).

options:
-H, --bind            ADDR  Bind address (default: localhost)
-p, --port            NUM   Port number.
    --auth            KEY   Cryptography key to secure server.
    --serve-forever         Do not halt even if all tasks finished.
-b, --bundlesize      NUM   Size of task bundle (default: {DEFAULT_BUNDLESIZE}).
-t, --bundlewait      SEC   Seconds to wait before flushing tasks (with FILE, default: {DEFAULT_BUNDLEWAIT}).
-r, --max-retries     NUM   Auto-retry failed tasks (default: {DEFAULT_ATTEMPTS - 1}).
    --eager                 Schedule failed tasks before new tasks.
    --live                  Run server without database.
    --print                 Print failed command args to STDOUT.
-h, --help                  Show this message and exit.\
"""


class ServerApp(Application):
    """Run server."""

    name = APP_NAME
    interface = Interface(APP_NAME, APP_USAGE, APP_HELP)

    filepath: str
    source: Optional[IO] = None
    interface.add_argument('filepath', nargs='?', default=None)

    bundlesize: int = config.server.bundlesize
    interface.add_argument('-b', '--bundlesize', type=int, default=bundlesize)

    bundlewait: int = config.submit.bundlewait
    interface.add_argument('-w', '--bundlewait', type=int, default=bundlewait)

    eager_mode: bool = False
    max_retries: int = DEFAULT_ATTEMPTS - 1
    interface.add_argument('-r', '--max-retries', type=int, default=max_retries)
    interface.add_argument('--eager', action='store_true')

    serve_forever_mode: bool = False
    interface.add_argument('--serve-forever', action='store_true', dest='serve_forever_mode')

    host: str = QueueConfig.host
    interface.add_argument('-H', '--bind', default=host, dest='host')

    port: int = QueueConfig.port
    interface.add_argument('-p', '--port', type=int, default=port)

    auth: str = QueueConfig.auth
    interface.add_argument('--auth', default=auth)

    live_mode: bool = False
    interface.add_argument('--live', action='store_true', dest='live_mode')

    print_on_failure: bool = False
    interface.add_argument('--print', action='store_true')

    def run(self) -> None:
        """Run server."""
        if self.serve_forever_mode:
            serve_forever(bundlesize=self.bundlesize, address=(self.host, self.port), auth=self.auth,
                          live=self.live_mode, print_on_failure=self.print_on_failure, max_retries=self.max_retries)
        else:
            serve_from(source=self.source, bundlesize=self.bundlesize, bundlewait=self.bundlewait,
                       address=(self.host, self.port), auth=self.auth, max_retries=self.max_retries,
                       live=self.live_mode, print_on_failure=self.print_on_failure)

    def check_args(self):
        """Fail particular argument combinations."""
        if self.filepath and self.serve_forever_mode:
            raise ArgumentError('Cannot specify both FILE and --serve-forever')
        if self.filepath is None and not self.serve_forever_mode:
            self.filepath = '-'  # NOTE: assume STDIN

    def __enter__(self) -> ServerApp:
        """Open file if not stdin."""
        self.check_args()
        if self.filepath is not None:
            self.source = sys.stdin if self.filepath == '-' else open(self.filepath, mode='r')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close file if not stdin."""
        if self.source is not None and self.source is not sys.stdin:
            self.source.close()
