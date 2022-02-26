# SPDX-FileCopyrightText: 2022 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""
Schedule and update bundles of tasks from the database.

The server can submit tasks for you so no need to directly submit before
invoking the server (see `hypershell.submit`).

Example:
    >>> from hypershell.server import serve_from
    >>> serve_from(['echo AA', 'echo BB', 'echo CC'])

To run a server process indefinitely (maybe as a service), invoke `server_forever()`.
Other programs can submit tasks at a later point.

Example:
    >>> from hypershell.server import serve_forever
    >>> serve_forever(bundlesize=10, max_retries=1)

Embed a `ServerThread` in your application directly. Call `stop()` to stop early.
Clients cannot connect from a remote machine unless you set the `bind` address
to 0.0.0.0 (as opposed to localhost which is the default).

Example:
    >>> import sys
    >>> from hypershell.server import ServerThread
    >>> server_thread = ServerThread.new(source=sys.stdin, bind=('0.0.0.0', 8080))

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
from enum import Enum
from datetime import datetime, timedelta
from functools import cached_property
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
from hypershell.core.heartbeat import Heartbeat, ClientState
from hypershell.database.model import Task
from hypershell.database import DATABASE_ENABLED
from hypershell.submit import SubmitThread, LiveSubmitThread, DEFAULT_BUNDLEWAIT

# public interface
__all__ = ['serve_from', 'serve_file', 'serve_forever', 'ServerThread', 'ServerApp',
           'DEFAULT_BUNDLESIZE', 'DEFAULT_ATTEMPTS', ]


log: Logger = logging.getLogger(__name__)


class SchedulerState(State, Enum):
    """Finite states of the scheduler."""
    START = 0
    LOAD = 1
    PACK = 2
    POST = 3
    FINAL = 4
    HALT = 5


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
    restart_mode: bool

    state = SchedulerState.START
    states = SchedulerState

    startup_phase: bool = True

    def __init__(self, queue: QueueServer, bundlesize: int = DEFAULT_BUNDLESIZE,
                 attempts: int = DEFAULT_ATTEMPTS, eager: bool = DEFAULT_EAGER_MODE,
                 forever_mode: bool = False, restart_mode: bool = False) -> None:
        """Initialize queue and parameters."""
        self.queue = queue
        self.bundle = []
        self.bundlesize = bundlesize
        self.attempts = attempts
        self.eager = eager
        self.forever_mode = forever_mode
        self.restart_mode = restart_mode
        if self.restart_mode:
            # NOTE: Halt if everything in the database is already finished
            self.startup_phase = False

    @cached_property
    def actions(self) -> Dict[SchedulerState, Callable[[], SchedulerState]]:
        return {
            SchedulerState.START: self.start,
            SchedulerState.LOAD: self.load_bundle,
            SchedulerState.PACK: self.pack_bundle,
            SchedulerState.POST: self.post_bundle,
            SchedulerState.FINAL: self.finalize,
        }

    def start(self) -> SchedulerState:
        """Initial setup then jump to LOAD state."""
        log.debug('Started (scheduler)')
        if self.forever_mode:
            log.info('Scheduler will run forever')
        task_count = Task.count()
        tasks_remaining = Task.count_remaining()
        if task_count > 0:
            log.warning(f'Database exists ({task_count} previous tasks)')
            if tasks_remaining == 0:
                log.warning(f'All tasks completed - did you mean to use the same database?')
            else:
                tasks_interrupted = Task.count_interrupted()
                log.info(f'Found {tasks_remaining} unfinished task(s)')
                Task.revert_interrupted()
                log.info(f'Reverted {tasks_interrupted} previously interrupted task(s)')
        return SchedulerState.LOAD

    def load_bundle(self) -> SchedulerState:
        """Load the next task bundle from the database."""
        self.tasks = Task.next(limit=self.bundlesize, attempts=self.attempts, eager=self.eager)
        if self.tasks:
            self.startup_phase = False
            return SchedulerState.PACK
        # An empty database must wait for at least one task
        elif not self.forever_mode and Task.count() > 0 and Task.count_remaining() == 0 and not self.startup_phase:
            return SchedulerState.FINAL
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

    @staticmethod
    def finalize() -> SchedulerState:
        """Stop scheduler."""
        log.debug('Done (scheduler)')
        return SchedulerState.HALT


class SchedulerThread(Thread):
    """Run scheduler within dedicated thread."""

    def __init__(self, queue: QueueServer, bundlesize: int = DEFAULT_BUNDLESIZE,
                 attempts: int = DEFAULT_ATTEMPTS, eager: bool = DEFAULT_EAGER_MODE,
                 forever_mode: bool = False, restart_mode: bool = False) -> None:
        """Initialize machine."""
        super().__init__(name='hypershell-scheduler')
        self.machine = Scheduler(queue=queue, bundlesize=bundlesize, attempts=attempts, eager=eager,
                                 forever_mode=forever_mode, restart_mode=restart_mode)

    def run_with_exceptions(self) -> None:
        """Run machine."""
        self.machine.run()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop machine."""
        log.warning('Stopping (scheduler)')
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class ReceiverState(State, Enum):
    """Finite states for receiver."""
    START = 0
    UNLOAD = 1
    UNPACK = 2
    UPDATE = 3
    FINAL = 4
    HALT = 5


class Receiver(StateMachine):
    """Collect incoming finished task bundles and update database."""

    tasks: List[Task]
    queue: QueueServer
    bundle: List[bytes]

    live: bool
    redirect_failures: IO

    state = ReceiverState.START
    states = ReceiverState

    def __init__(self, queue: QueueServer, live: bool = False, redirect_failures: IO = None) -> None:
        """Initialize receiver."""
        self.queue = queue
        self.bundle = []
        self.live = live
        self.redirect_failures = redirect_failures

    @cached_property
    def actions(self) -> Dict[ReceiverState, Callable[[], ReceiverState]]:
        return {
            ReceiverState.START: self.start,
            ReceiverState.UNLOAD: self.unload_bundle,
            ReceiverState.UNPACK: self.unpack_bundle,
            ReceiverState.UPDATE: self.update_tasks,
            ReceiverState.FINAL: self.finalize,
        }

    @staticmethod
    def start() -> ReceiverState:
        """Jump to UNLOAD state."""
        log.debug('Started (receiver)')
        return ReceiverState.UNLOAD

    def unload_bundle(self) -> ReceiverState:
        """Get the next bundle from the completed task queue."""
        try:
            self.bundle = self.queue.completed.get(timeout=1)
            self.queue.completed.task_done()
            return ReceiverState.UNPACK if self.bundle else ReceiverState.FINAL
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
                if self.redirect_failures:
                    print(task.args, file=self.redirect_failures)
        return ReceiverState.UNLOAD

    @staticmethod
    def finalize() -> ReceiverState:
        """Return HALT."""
        log.debug('Done (receiver)')
        return ReceiverState.HALT


class ReceiverThread(Thread):
    """Run receiver within dedicated thread."""

    def __init__(self, queue: QueueServer, live: bool = False, redirect_failures: IO = None) -> None:
        """Initialize machine."""
        super().__init__(name='hypershell-receiver')
        self.machine = Receiver(queue=queue, live=live, redirect_failures=redirect_failures)

    def run_with_exceptions(self) -> None:
        """Run machine."""
        self.machine.run()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop machine."""
        log.warning('Stopping (receiver)')
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class HeartbeatState(State, Enum):
    """Finite states of the terminator machine."""
    START = 0
    NEXT = 1
    UPDATE = 2
    SWITCH = 3
    CHECK = 4
    SIGNAL = 5
    FINAL = 6
    HALT = 7


DEFAULT_EVICT: int = default.server.evict


class HeartMonitor(StateMachine):
    """Await final task signals."""

    queue: QueueServer
    beats: Dict[str, Heartbeat]
    last_check: datetime
    wait_check: timedelta
    evict_after: timedelta

    startup_phase: bool = True  # should not halt until at least one client
    scheduler_done: bool = False  # set by parent thread when scheduling is over
    should_signal: bool = False  # set by parent thread to signal clients
    latest_heartbeat: Heartbeat = None

    state = HeartbeatState.START
    states = HeartbeatState

    def __init__(self, queue: QueueServer, evict_after: int = DEFAULT_EVICT) -> None:
        """Initialize with queue server."""
        self.queue = queue
        self.last_check = datetime.now()
        self.beats = {}
        if evict_after >= 10:
            self.wait_check = timedelta(seconds=int(evict_after / 10))
            self.evict_after = timedelta(seconds=evict_after)
        else:
            raise RuntimeError(f'Evict period must be greater than 10 seconds: given {evict_after}')

    @cached_property
    def actions(self) -> Dict[HeartbeatState, Callable[[], HeartbeatState]]:
        return {
            HeartbeatState.START: self.start,
            HeartbeatState.NEXT: self.get_next,
            HeartbeatState.UPDATE: self.update_client,
            HeartbeatState.SWITCH: self.switch_mode,
            HeartbeatState.CHECK: self.check_clients,
            HeartbeatState.SIGNAL: self.signal_clients,
            HeartbeatState.FINAL: self.finalize,
        }

    @staticmethod
    def start() -> HeartbeatState:
        """Jump to WAIT_INITIAL state."""
        log.debug('Started (heartbeat)')
        return HeartbeatState.NEXT

    def get_next(self) -> HeartbeatState:
        """Get and stash heartbeat from clients."""
        try:
            hb_data = self.queue.heartbeat.get(timeout=1)
            self.queue.heartbeat.task_done()
            self.startup_phase = False
            if not hb_data:
                return HeartbeatState.FINAL
            else:
                self.latest_heartbeat = Heartbeat.unpack(hb_data)
                return HeartbeatState.UPDATE
        except QueueEmpty:
            return HeartbeatState.SWITCH

    def update_client(self) -> HeartbeatState:
        """Update client with heartbeat or disconnect."""
        hb = self.latest_heartbeat
        if hb.state is not ClientState.FINISHED:
            if hb.uuid not in self.beats:
                log.debug(f'Registered client ({hb.host}: {hb.uuid})')
            else:
                log.trace(f'Heartbeat - running ({hb.host}: {hb.uuid})')
            self.beats[hb.uuid] = hb
            return HeartbeatState.SWITCH
        else:
            log.trace(f'Client disconnected ({hb.host}: {hb.uuid})')
            if hb.uuid in self.beats:
                self.beats.pop(hb.uuid)
            return HeartbeatState.SWITCH

    def switch_mode(self) -> HeartbeatState:
        """Decide to bail, signal, check, or get another heartbeat."""
        if self.startup_phase:
            return HeartbeatState.NEXT
        if self.should_signal:
            return HeartbeatState.SIGNAL
        if not self.beats and self.scheduler_done:
            return HeartbeatState.FINAL
        now = datetime.now()
        if (now - self.last_check) > self.wait_check:
            self.last_check = now
            return HeartbeatState.CHECK
        else:
            return HeartbeatState.NEXT

    def check_clients(self) -> HeartbeatState:
        """Check last heartbeat on all clients and evict if necessary."""
        log.debug(f'Check clients ({len(self.beats)} connected)')
        for uuid in list(self.beats):
            hb = self.beats.get(uuid)
            age = self.last_check - hb.time
            if age > self.evict_after:
                log.warning(f'Evicting client ({hb.host}: {uuid})')
                self.beats.pop(uuid)
        return HeartbeatState.SWITCH

    def signal_clients(self) -> HeartbeatState:
        """Send shutdown signal to all connected clients."""
        log.debug(f'Signaling clients ({len(self.beats)} connected)')
        for hb in self.beats.values():
            self.queue.scheduled.put(None)
            log.debug(f'Disconnect requested ({hb.host}: {hb.uuid})')
        self.should_signal = False
        return HeartbeatState.SWITCH

    @staticmethod
    def finalize() -> HeartbeatState:
        """Stop heart monitor."""
        log.debug('Done (heartbeat)')
        return HeartbeatState.HALT


class HeartMonitorThread(Thread):
    """Run heart monitor within dedicated thread."""

    def __init__(self, queue: QueueServer, evict_after: int = DEFAULT_EVICT) -> None:
        """Initialize machine."""
        super().__init__(name='hypershell-server-heartbeat')
        self.machine = HeartMonitor(queue=queue, evict_after=evict_after)

    def run_with_exceptions(self) -> None:
        """Run machine."""
        self.machine.run()

    def signal_clients(self) -> None:
        """Set signal flag to post sentinel for each connected clients."""
        self.machine.should_signal = True

    def signal_scheduler_done(self) -> None:
        """Set flag to tell heart monitor that scheduler is done."""
        self.machine.scheduler_done = True

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop machine."""
        log.warning('Stopping (heartbeat)')
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class ServerThread(Thread):
    """Manage asynchronous task bundle scheduling and receiving."""

    queue: QueueServer
    submitter: Optional[SubmitThread]
    scheduler: Optional[SchedulerThread]
    receiver: ReceiverThread
    heartmonitor: HeartMonitorThread
    live_mode: bool

    def __init__(self,
                 source: Iterable[str] = None,
                 live: bool = False, forever_mode: bool = False, restart_mode: bool = False,
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
                 address: Tuple[str, int] = (QueueConfig.host, QueueConfig.port), auth: str = QueueConfig.auth,
                 max_retries: int = DEFAULT_ATTEMPTS - 1, eager: bool = False,
                 redirect_failures: IO = None, evict_after: int = DEFAULT_EVICT) -> None:
        """Initialize queue manager and child threads."""
        self.live_mode = live
        if not self.live_mode and not DATABASE_ENABLED:
            log.warning('No database configured - automatically disabled')
            self.live_mode = True
        if self.live_mode and max_retries > 0:
            log.warning('Retries disabled in live mode')
        queue_config = QueueConfig(host=address[0], port=address[1], auth=auth)
        self.queue = QueueServer(config=queue_config)
        if self.live_mode:
            self.scheduler = None
            self.submitter = None if not source else LiveSubmitThread(
                source, queue_config=queue_config, bundlesize=bundlesize, bundlewait=bundlewait)
        else:
            self.submitter = None if not source else SubmitThread(source, bundlesize=bundlesize, bundlewait=bundlewait)
            self.scheduler = SchedulerThread(queue=self.queue, bundlesize=bundlesize, attempts=max_retries + 1,
                                             eager=eager, forever_mode=forever_mode, restart_mode=restart_mode)
        self.receiver = ReceiverThread(queue=self.queue, live=self.live_mode, redirect_failures=redirect_failures)
        self.heartmonitor = HeartMonitorThread(queue=self.queue, evict_after=evict_after)
        super().__init__(name='hypershell-server')

    def run_with_exceptions(self) -> None:
        """Start child threads, wait."""
        log.debug('Started')
        with self.queue:
            self.start_threads()
            self.wait_submitter()
            self.wait_scheduler()
            self.wait_heartbeat()
            self.wait_receiver()
        log.debug('Done')

    def start_threads(self) -> None:
        """Start child threads."""
        if self.submitter is not None:
            self.submitter.start()
        if self.scheduler is not None:
            self.scheduler.start()
        self.heartmonitor.start()
        self.receiver.start()

    def wait_submitter(self) -> None:
        """Wait on task submission to complete."""
        if self.submitter is not None:
            log.trace('Waiting (submitter)')
            self.submitter.join()

    def wait_scheduler(self) -> None:
        """Wait scheduling until complete."""
        if self.scheduler is not None:
            log.trace('Waiting (scheduler)')
            self.scheduler.join()

    def wait_heartbeat(self) -> None:
        """Wait for heartmonitor to stop."""
        log.trace('Waiting (heartbeat)')
        self.heartmonitor.signal_scheduler_done()
        self.heartmonitor.signal_clients()
        self.heartmonitor.join()

    def wait_receiver(self) -> None:
        """Wait for receiver to stop."""
        log.trace('Waiting (receiver)')
        self.queue.completed.put(None)
        self.receiver.join()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        log.warning('Stopping')
        if self.submitter is not None:
            self.submitter.stop(wait=wait, timeout=timeout)
        if self.scheduler is not None:
            self.scheduler.stop(wait=wait, timeout=timeout)
        self.heartmonitor.stop(wait=wait, timeout=timeout)
        self.queue.completed.put(None)
        self.receiver.stop(wait=wait, timeout=timeout)
        super().stop(wait=wait, timeout=timeout)


def serve_from(source: Iterable[str], live: bool = False, redirect_failures: IO = None,
               bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
               address: Tuple[str, int] = (QueueConfig.host, QueueConfig.port), auth: str = QueueConfig.auth,
               max_retries: int = DEFAULT_ATTEMPTS - 1, eager: bool = DEFAULT_EAGER_MODE,
               restart_mode: bool = False, evict_after: int = DEFAULT_EVICT) -> None:
    """Run server with the given task `source`, run until complete."""
    thread = ServerThread.new(source=source, live=live, redirect_failures=redirect_failures,
                              bundlesize=bundlesize, bundlewait=bundlewait, address=address, auth=auth,
                              max_retries=max_retries, eager=eager, restart_mode=restart_mode,
                              evict_after=evict_after)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


def serve_file(path: str, live: bool = False, redirect_failures: IO = None,
               bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
               address: Tuple[str, int] = (QueueConfig.host, QueueConfig.port), auth: str = QueueConfig.auth,
               max_retries: int = DEFAULT_ATTEMPTS - 1, eager: bool = DEFAULT_EAGER_MODE,
               evict_after: int = DEFAULT_EVICT, **file_options) -> None:
    """Run server with tasks from a local file `path`, run until complete."""
    with open(path, mode='r', **file_options) as stream:
        serve_from(stream, live=live, redirect_failures=redirect_failures,
                   bundlesize=bundlesize, bundlewait=bundlewait, address=address, auth=auth,
                   max_retries=max_retries, eager=eager, evict_after=evict_after)


def serve_forever(bundlesize: int = DEFAULT_BUNDLESIZE, live: bool = False, redirect_failures: IO = None,
                  address: Tuple[str, int] = (QueueConfig.host, QueueConfig.port), auth: str = QueueConfig.auth,
                  max_retries: int = DEFAULT_ATTEMPTS - 1, eager: bool = DEFAULT_EAGER_MODE,
                  evict_after: int = DEFAULT_EVICT) -> None:
    """Run server forever."""
    thread = ServerThread.new(source=None, live=live, redirect_failures=redirect_failures,
                              bundlesize=bundlesize, address=address, auth=auth,
                              forever_mode=True, max_retries=max_retries, eager=eager, evict_after=evict_after)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


APP_NAME = 'hyper-shell server'
APP_USAGE = f"""\
usage: hyper-shell server [-h] [FILE | --forever | --restart] [-b NUM] [-w SEC] [-r NUM [--eager]]
                          [-H ADDR] [-p PORT] [-k KEY] [--no-db] [--print | -f PATH]\
"""

APP_HELP = f"""\
{APP_USAGE}

Launch server, schedule directly or asynchronously from database.

The server includes a scheduler component that pulls tasks from the database and offers
them up on a distributed queue to clients. It also has a receiver that collects the results
of finished tasks. Optionally, the server can submit tasks (FILE). When submitting tasks,
the -w/--bundlewait and -b/bundlesize options are the same as for 'hypershell submit'.

With --max-retries greater than zero, the scheduler will check for a non-zero exit status
for tasks and re-submit them if their previous number of attempts is less.

Tasks are bundled and clients pull them in these bundles. However, by default the bundle size 
is one, meaning that at small scales there is greater responsiveness.

arguments:
FILE                        Path to task file ("-" for <stdin>).

options:
-H, --bind            ADDR  Bind address (default: {QueueConfig.host}).
-p, --port            NUM   Port number (default: {QueueConfig.port}).
-k, --auth            KEY   Cryptographic key to secure server.
    --forever               Do not halt even if all tasks finished.
    --restart               Restart scheduling from last completed task.
-b, --bundlesize      NUM   Size of task bundle (default: {DEFAULT_BUNDLESIZE}).
-t, --bundlewait      SEC   Seconds to wait before flushing tasks (with FILE, default: {DEFAULT_BUNDLEWAIT}).
-r, --max-retries     NUM   Auto-retry failed tasks (default: {DEFAULT_ATTEMPTS - 1}).
    --eager                 Schedule failed tasks before new tasks.
    --no-db                 Run server without database.
    --restart               Include previously failed or interrupted tasks.
    --print                 Print failed task args to <stdout>.
-f, --failures        PATH  File path to redirect failed task args.
-h, --help                  Show this message and exit.\
"""


class ServerApp(Application):
    """Run server in stand-alone mode."""

    name = APP_NAME
    interface = Interface(APP_NAME, APP_USAGE, APP_HELP)

    filepath: str
    interface.add_argument('filepath', nargs='?', default=None)

    bundlesize: int = config.server.bundlesize
    interface.add_argument('-b', '--bundlesize', type=int, default=bundlesize)

    bundlewait: int = config.submit.bundlewait
    interface.add_argument('-w', '--bundlewait', type=int, default=bundlewait)

    eager_mode: bool = False
    max_retries: int = DEFAULT_ATTEMPTS - 1
    interface.add_argument('-r', '--max-retries', type=int, default=max_retries)
    interface.add_argument('--eager', action='store_true')

    forever_mode: bool = False
    interface.add_argument('--forever', action='store_true', dest='forever_mode')

    restart_mode: bool = False
    interface.add_argument('--restart', action='store_true', dest='restart_mode')

    host: str = QueueConfig.host
    interface.add_argument('-H', '--bind', default=host, dest='host')

    port: int = QueueConfig.port
    interface.add_argument('-p', '--port', type=int, default=port)

    auth: str = QueueConfig.auth
    interface.add_argument('-k', '--auth', default=auth)

    live_mode: bool = False
    interface.add_argument('--no-db', action='store_true', dest='live_mode')

    print_mode: bool = False
    failure_path: str = None
    output_interface = interface.add_mutually_exclusive_group()
    output_interface.add_argument('--print', action='store_true', dest='print_mode')
    output_interface.add_argument('-f', '--failures', default=None, dest='failure_path')

    def run(self) -> None:
        """Run server."""
        if self.forever_mode:
            serve_forever(bundlesize=self.bundlesize, address=(self.host, self.port), auth=self.auth,
                          live=self.live_mode, redirect_failures=self.failure_stream,
                          max_retries=self.max_retries, evict_after=config.server.evict)
        else:
            serve_from(source=self.input_stream, bundlesize=self.bundlesize, bundlewait=self.bundlewait,
                       address=(self.host, self.port), auth=self.auth, max_retries=self.max_retries,
                       live=self.live_mode, redirect_failures=self.failure_stream,
                       restart_mode=self.restart_mode, evict_after=config.server.evict)

    def check_args(self):
        """Fail particular argument combinations."""
        if self.filepath and self.forever_mode:
            raise ArgumentError('Cannot specify both FILE and --forever')
        if self.filepath is None and not self.forever_mode:
            self.filepath = '-'  # NOTE: assume STDIN
        if self.restart_mode and self.forever_mode:
            raise ArgumentError('Using --forever with --restart is invalid')

    @cached_property
    def input_stream(self) -> Optional[IO]:
        """Input IO stream for task args."""
        if self.forever_mode or self.restart_mode:
            return None
        else:
            return sys.stdin if self.filepath == '-' else open(self.filepath, mode='r')

    @cached_property
    def failure_stream(self) -> Optional[IO]:
        """IO stream for failed task args."""
        if self.print_mode:
            return sys.stdout
        elif self.failure_path:
            return sys.stdout if self.failure_path == '-' else open(self.failure_path, mode='w')
        else:
            return None

    def __enter__(self) -> ServerApp:
        """Open file if not stdin."""
        self.check_args()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up IO if necessary."""
        if self.input_stream is not None and self.input_stream is not sys.stdin:
            self.input_stream.close()
        if self.failure_stream is not None and self.failure_path is not sys.stdout:
            self.failure_stream.close()
