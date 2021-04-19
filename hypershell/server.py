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
Schedule and collect bundles tasks from the database.

Example:
    >>> from hypershell.server import serve_forever
    >>> serve_from(source=['echo a', 'echo b'], bind=('0.0.0.0', 8080), bundlesize=10)

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
from typing import List, Tuple, Iterable, IO, Optional

# standard libs
import sys
import time
import logging
import functools
from queue import Queue, Empty

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface, ArgumentError

# internal libs
from hypershell.core.fsm import State, StateMachine, HALT
from hypershell.core.thread import Thread
from hypershell.core.queue import QueueServer, DEFAULT_BIND, DEFAULT_PORT, DEFAULT_AUTH, SENTINEL
from hypershell.database.model import Task
from hypershell.submit import SubmitThread, DEFAULT_BUFFERTIME

# public interface
__all__ = ['serve_from', 'serve_file', 'serve_forever', 'ServerThread', 'ServerApp', ]


# module level logger
log = logging.getLogger(__name__)


class __SchedulerStart(State):
    def run(self, machine: SchedulerImpl) -> State:
        """Initial state for scheduler."""
        log.debug('Starting scheduler')
        return SCHEDULER_GET


# pause between queries to not over burden the database
DEFAULT_QUERY_PAUSE = 5


class __SchedulerGet(State):
    def run(self, machine: SchedulerImpl) -> State:
        """Get the next task bundle from the database."""
        machine.tasks = Task.next(limit=machine.bundlesize, attempts=machine.attempts, eager=machine.eager)
        if machine.tasks:
            return SCHEDULER_PUT
        # NOTE: an empty database must wait for at least one task
        elif Task.count_remaining() == 0 and not machine.forever_mode and Task.count() > 0:
            return HALT
        else:
            time.sleep(DEFAULT_QUERY_PAUSE)
            return SCHEDULER_GET


class __SchedulerPut(State):
    def run(self, machine: SchedulerImpl) -> State:
        """Enqueue loaded task bundle."""
        machine.queue.put([task.to_json() for task in machine.tasks])
        for task in machine.tasks:
            log.debug(f'Scheduled task ({task.id})')
        return SCHEDULER_GET


SCHEDULER_START = __SchedulerStart()
SCHEDULER_GET = __SchedulerGet()
SCHEDULER_PUT = __SchedulerPut()


# Note: unless specified otherwise for larger problems, a bundle of size one allows
# for greater concurrency on smaller workloads.
DEFAULT_BUNDLESIZE: int = 1
DEFAULT_ATTEMPTS: int = 1
DEFAULT_EAGER_MODE: bool = False


class SchedulerImpl(StateMachine):
    """Enqueue tasks from database."""

    tasks: List[Task]
    queue: Queue[Optional[List[str]]]
    bundlesize: int
    attempts: int
    eager: bool
    forever_mode: bool

    def __init__(self, queue: Queue[Optional[List[str]]], bundlesize: int = DEFAULT_BUNDLESIZE,
                 attempts: int = DEFAULT_ATTEMPTS, eager: bool = DEFAULT_EAGER_MODE,
                 forever_mode: bool = False) -> None:
        """Initialize queue and parameters."""
        self.queue = queue
        self.bundlesize = bundlesize
        self.attempts = attempts
        self.eager = eager
        self.forever_mode = forever_mode
        super().__init__(start=SCHEDULER_START)


class SchedulerThread(Thread):
    """Run scheduler within dedicated thread."""

    def __init__(self, queue: Queue[Optional[List[str]]], bundlesize: int = DEFAULT_BUNDLESIZE,
                 attempts: int = DEFAULT_ATTEMPTS, eager: bool = DEFAULT_EAGER_MODE,
                 forever_mode: bool = False) -> None:
        super().__init__(name='hypershell-server')
        self.machine = SchedulerImpl(queue=queue, bundlesize=bundlesize, attempts=attempts, eager=eager,
                                     forever_mode=forever_mode)

    def run(self) -> None:
        self.machine.run()
        log.debug('Stopping scheduler')

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class __ReceiverStart(State):
    def run(self, machine: ReceiverImpl) -> State:
        """Initial state for receiver."""
        log.debug('Started receiver')
        return RECEIVER_GET


class __ReceiverGet(State):
    def run(self, machine: ReceiverImpl) -> State:
        """Get the next task bundle from the incoming queue."""
        try:
            bundle = machine.queue.get(timeout=1)
            if bundle is not None:
                machine.tasks = [Task.from_json(data) for data in bundle]
                return RECEIVER_UPDATE
            else:
                return HALT
        except Empty:
            return RECEIVER_GET


class __ReceiverUpdate(State):
    def run(self, machine: ReceiverImpl) -> State:
        """Update tasks in database with run details."""
        Task.update_all([task.to_dict() for task in machine.tasks])
        for task in machine.tasks:
            log.debug(f'Completed task ({task.id})')
            if task.exit_status != 0:
                log.warning(f'Non-zero exit status ({task.exit_status}) for task ({task.id})')
                if machine.print_on_failure:
                    print(task.args)
        return RECEIVER_GET


RECEIVER_START = __ReceiverStart()
RECEIVER_GET = __ReceiverGet()
RECEIVER_UPDATE = __ReceiverUpdate()


class ReceiverImpl(StateMachine):
    """Collect incoming finished tasks and update database."""

    tasks: List[Task]
    queue: Queue[Optional[List[str]]]
    print_on_failure: bool

    def __init__(self, queue: Queue[Optional[List[str]]], print_on_failure: bool = False) -> None:
        """Initialize IO `stream` to read tasks and submit to database."""
        self.queue = queue
        self.print_on_failure = print_on_failure
        super().__init__(start=RECEIVER_START)


class ReceiverThread(Thread):
    """Run receiver within dedicated thread."""

    def __init__(self, queue: Queue[Optional[List[str]]]) -> None:
        super().__init__(name='hypershell-server')
        self.machine = ReceiverImpl(queue=queue)

    def run(self) -> None:
        self.machine.run()
        log.debug('Stopping receiver')

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class ServerThread(Thread):
    """Manage asynchronous task bundle scheduling and receiving."""

    server: QueueServer
    submitter: SubmitThread
    scheduler: SchedulerThread
    receiver: ReceiverThread

    def __init__(self, source: Iterable[str] = None, bundlesize: int = DEFAULT_BUNDLESIZE,
                 bind: Tuple[str, int] = (DEFAULT_BIND, DEFAULT_PORT), auth: bytes = DEFAULT_AUTH,
                 buffertime: int = DEFAULT_BUFFERTIME, forever_mode: bool = False,
                 max_retries: int = DEFAULT_ATTEMPTS - 1, eager: bool = False) -> None:
        """Initialize queue manager and child threads."""
        self.server = QueueServer(address=bind, authkey=auth, maxsize=1)
        self.submitter = None if not source else SubmitThread(source, buffersize=bundlesize, buffertime=buffertime)
        self.scheduler = SchedulerThread(queue=self.server.scheduled, bundlesize=bundlesize,
                                         attempts=max_retries + 1, eager=eager, forever_mode=forever_mode)
        self.receiver = ReceiverThread(queue=self.server.completed)
        super().__init__(name='hypershell-server')

    def run(self) -> None:
        """Start child threads, wait."""
        log.debug('Starting server')
        with self.server:
            self.start_threads()
            self.wait_submitter()
            self.wait_scheduler()
            self.wait_clients()

    def start_threads(self) -> None:
        """Start child threads."""
        if self.submitter is not None:
            self.submitter.start()
        self.scheduler.start()
        self.receiver.start()

    def wait_submitter(self) -> None:
        """Wait on task submission to complete."""
        if self.submitter is not None:
            self.submitter.join()

    def wait_scheduler(self) -> None:
        """Wait for all tasks to be completed."""
        self.scheduler.join()

    def wait_clients(self) -> None:
        """Send disconnect signal to each clients."""
        try:
            log.debug('Sending disconnect request to clients')
            for hostname in iter(functools.partial(self.server.connected.get, timeout=1), None):
                self.server.scheduled.put(SENTINEL)  # NOTE: one for each
                self.server.connected.task_done()
                log.debug(f'Disconnect request sent ({hostname})')
        except Empty:
            pass

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        if self.submitter is not None:
            self.submitter.stop(wait=wait, timeout=timeout)
        self.scheduler.stop(wait=wait, timeout=timeout)
        self.server.completed.put(None)
        self.receiver.stop(wait=wait, timeout=timeout)
        super().stop(wait=wait, timeout=timeout)


def serve_from(source: Iterable[str], bundlesize: int = DEFAULT_BUNDLESIZE, buffertime: int = DEFAULT_BUFFERTIME,
               bind: Tuple[str, int] = (DEFAULT_BIND, DEFAULT_PORT), auth: bytes = DEFAULT_AUTH,
               max_retries: int = DEFAULT_ATTEMPTS - 1, eager: bool = DEFAULT_EAGER_MODE) -> None:
    """Run server with the given task `source`, run until complete."""
    thread = ServerThread(source=source, buffertime=buffertime, bundlesize=bundlesize,
                          bind=bind, auth=auth, max_retries=max_retries, eager=eager)
    try:
        thread.start()
        thread.join()
    except Exception:
        thread.stop()
        raise


def serve_file(path: str, bundlesize: int = DEFAULT_BUNDLESIZE, buffertime: int = DEFAULT_BUFFERTIME,
               bind: Tuple[str, int] = (DEFAULT_BIND, DEFAULT_PORT), auth: bytes = DEFAULT_AUTH,
               max_retries: int = DEFAULT_ATTEMPTS - 1, eager: bool = DEFAULT_EAGER_MODE, **file_options) -> None:
    """Run server with tasks from a local file `path`, run until complete."""
    with open(path, mode='r', **file_options) as stream:
        serve_from(stream, bundlesize=bundlesize, buffertime=buffertime, bind=bind, auth=auth,
                   max_retries=max_retries, eager=eager)


def serve_forever(bundlesize: int = DEFAULT_BUNDLESIZE,
                  bind: Tuple[str, int] = (DEFAULT_BIND, DEFAULT_PORT), auth: bytes = DEFAULT_AUTH,
                  max_retries: int = DEFAULT_ATTEMPTS - 1, eager: bool = DEFAULT_EAGER_MODE) -> None:
    """Run server forever."""
    thread = ServerThread(source=None, bundlesize=bundlesize, bind=bind, auth=auth,
                          forever_mode=True, max_retries=max_retries, eager=eager)
    try:
        thread.start()
        thread.join()
    except Exception:
        thread.stop()
        raise


APP_NAME = 'hypershell server'
APP_USAGE = f"""\
usage: {APP_NAME} [-h] [FILE | --server-forever] [--bundle-size NUM] [--max-retries NUM [--eager]]
Run server.\
"""

APP_HELP = f"""\
{APP_USAGE}

The server includes a scheduler component that pulls tasks from the database and offers
them up on a distributed queue to clients. It also has a receiver that collects the results
of finished tasks. Optionally, the server can submit tasks (FILE). When submitting tasks,
the -t/--buffertime options are the same as for 'hypershell submit' and the -b/--bundlesize
are used for -b/--buffersize.

With --max-retries greater than zero, the scheduler will check for a non-zero exit status
for tasks and re-submit them if their previous number of attempts is less.

Tasks are bundled and clients pull them in these bundles. However, by default the bundle size 
is one, meaning that at small scales there is greater responsiveness.

arguments:
FILE                        Path to task file ("-" for <stdin>).

options:
    --server-forever        Do no halt even if all tasks finished.
-b, --bundlesize      NUM   Number of lines to buffer (default: {DEFAULT_BUNDLESIZE}).
-t, --buffertime      SEC   Seconds to wait before flushing tasks (with FILE, default: {DEFAULT_BUFFERTIME}).
-r, --max-retries     NUM   Resubmit failed tasks (default: {DEFAULT_ATTEMPTS - 1}).
    --eager                 Schedule failed tasks before new tasks.
-h, --help                  Show this message and exit.\
"""


class ServerApp(Application):
    """Run server."""

    name = APP_NAME
    interface = Interface(APP_NAME, APP_USAGE, APP_HELP)

    source: Optional[IO]
    filepath: str
    interface.add_argument('filepath', nargs='?', default=None)

    bundlesize: int = DEFAULT_BUNDLESIZE
    interface.add_argument('-b', '--bundlesize', type=int, default=bundlesize)

    buffertime: int = DEFAULT_BUFFERTIME
    interface.add_argument('-t', '--buffertime', type=int, default=buffertime)

    max_retires: int = DEFAULT_ATTEMPTS - 1
    eager_mode: bool = False
    interface.add_argument('-r', '--max-retries', type=int, default=max_retires)
    interface.add_argument('--eager', action='store_true')

    serve_forever_mode: bool = False
    interface.add_argument('--serve-forever', action='store_true')

    bind_address: str = DEFAULT_BIND
    interface.add_argument('--bind', default=bind_address)

    port_number: int = DEFAULT_PORT
    interface.add_argument('--port', type=int, default=port_number)

    authkey: bytes = DEFAULT_AUTH
    interface.add_argument('--auth', type=str.encode, default=authkey)

    thread: ServerThread

    def run(self) -> None:
        """Run server."""
        self.check_args()
        if self.serve_forever_mode:
            serve_forever(bundlesize=self.bundlesize, bind=(self.bind_address, self.port_number), auth=self.authkey)
        else:
            serve_from(source=self.source, bundlesize=self.bundlesize, buffertime=self.buffertime,
                       bind=(self.bind_address, self.port_number), auth=self.authkey)

    def check_args(self):
        """Fail particular argument combinations."""
        if self.filepath is None and not self.serve_forever_mode:
            raise ArgumentError('Missing either FILE or --serve-forever')
        if self.filepath and self.serve_forever_mode:
            raise ArgumentError('Cannot specify both FILE and --serve-forever')

    def __enter__(self) -> ServerApp:
        """Open file if not stdin."""
        self.source = None
        if self.filepath is not None:
            self.source = sys.stdin if self.filepath == '-' else open(self.filepath, mode='r')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close file if not stdin."""
        if self.source is not None and self.source is not sys.stdin:
            self.source.close()
