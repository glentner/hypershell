# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""
Connect to server and run tasks.

TODO: examples and notes
"""


# type annotations
from __future__ import annotations
from typing import List, Tuple, Optional, Callable, Dict

# standard libs
import os
import sys
import logging
import functools
from enum import Enum
from datetime import datetime
from queue import Queue, Empty as QueueEmpty, Full as QueueFull
from subprocess import Popen, TimeoutExpired

# external libs
from cmdkit.app import Application, exit_status
from cmdkit.cli import Interface

# internal libs
from hypershell.core.fsm import State, StateMachine
from hypershell.core.thread import Thread
from hypershell.core.queue import QueueClient, QueueConfig
from hypershell.core.logging import HOSTNAME
from hypershell.core.exceptions import handle_exception
from hypershell.database.model import Task
from hypershell.server import DEFAULT_BUNDLESIZE

# public interface
__all__ = ['run_client', 'ClientThread', 'ClientApp', 'DEFAULT_TEMPLATE', ]


# module level logger
log = logging.getLogger(__name__)


class SchedulerState(State, Enum):
    """Finite states for scheduler."""
    START = 0
    GET_REMOTE = 1
    POP_TASK = 2
    PUT_LOCAL = 3
    HALT = 4


class ClientScheduler(StateMachine):
    """Receive task bundles from server and schedule locally."""

    queue: QueueClient
    local: Queue[Optional[bytes]]
    bundle: List[bytes]
    task_data: bytes

    state = SchedulerState.START
    states = SchedulerState

    def __init__(self, queue: QueueClient, local: Queue[Optional[bytes]]) -> None:
        """Initialize IO `stream` to read tasks and submit to database."""
        self.queue = queue
        self.local = local
        self.bundle = []
        self.task_data = b''

    @functools.cached_property
    def actions(self) -> Dict[SchedulerState, Callable[[], SchedulerState]]:
        return {
            SchedulerState.START: self.start,
            SchedulerState.GET_REMOTE: self.get_remote,
            SchedulerState.POP_TASK: self.pop_task,
            SchedulerState.PUT_LOCAL: self.put_local,
        }

    @staticmethod
    def start() -> SchedulerState:
        """Jump to GET_REMOTE state."""
        log.debug('Started scheduler')
        return SchedulerState.GET_REMOTE

    def get_remote(self) -> SchedulerState:
        """Get the next task bundle from the server."""
        try:
            self.bundle = self.queue.scheduled.get(timeout=2)
            if self.bundle is not None:
                log.debug(f'Received {len(self.bundle)} tasks from server')
                return SchedulerState.POP_TASK
            else:
                log.debug('Received disconnect')
                return SchedulerState.HALT
        except QueueEmpty:
            return SchedulerState.GET_REMOTE

    def pop_task(self) -> SchedulerState:
        """Pop next task off current bundle."""
        try:
            self.task_data = self.bundle.pop(0)
            return SchedulerState.PUT_LOCAL
        except IndexError:
            return SchedulerState.GET_REMOTE

    def put_local(self) -> SchedulerState:
        """Pop task data and put on local queue."""
        try:
            self.local.put(self.task_data, timeout=2)
            return SchedulerState.POP_TASK
        except QueueFull:
            return SchedulerState.PUT_LOCAL


class ClientSchedulerThread(Thread):
    """Run client scheduler in dedicated thread."""

    def __init__(self, queue: QueueClient, local: Queue[Optional[bytes]]) -> None:
        """Initialize machine."""
        super().__init__(name='hypershell-client-scheduler')
        self.machine = ClientScheduler(queue=queue, local=local)

    def run(self) -> None:
        """Run machine."""
        self.machine.run()
        self.stop()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop machine."""
        self.machine.halt()
        log.debug('Stopping scheduler')
        super().stop(wait=wait, timeout=timeout)


class CollectorState(State, Enum):
    """Finite states of collector."""
    START = 0
    GET_LOCAL = 1
    PUT_REMOTE = 2
    FINALIZE = 3
    HALT = 4


class ClientCollector(StateMachine):
    """Collect finished tasks and bundle for outgoing queue."""

    tasks: List[bytes]
    queue: QueueClient
    local: Queue[Optional[bytes]]

    state = CollectorState.START
    states = CollectorState

    def __init__(self, queue: QueueClient, local: Queue[Optional[bytes]]) -> None:
        """Initialize IO `stream` to read tasks and submit to database."""
        self.tasks = []
        self.local = local
        self.queue = queue

    @functools.cached_property
    def actions(self) -> Dict[CollectorState, Callable[[], CollectorState]]:
        return {
            CollectorState.START: self.start,
            CollectorState.GET_LOCAL: self.get_local,
            CollectorState.PUT_REMOTE: self.put_remote,
            CollectorState.FINALIZE: self.finalize,
        }

    @staticmethod
    def start() -> CollectorState:
        """Jump to GET_LOCAL state."""
        log.debug('Started collector')
        return CollectorState.GET_LOCAL

    def get_local(self) -> CollectorState:
        """Get the next task from the local completed task queue."""
        try:
            task = self.local.get(timeout=1)
            if task is not None:
                self.tasks.append(task)
                if len(self.tasks) >= DEFAULT_BUNDLESIZE:
                    return CollectorState.PUT_REMOTE
                else:
                    return CollectorState.GET_LOCAL
            else:
                return CollectorState.FINALIZE
        except QueueEmpty:
            return CollectorState.GET_LOCAL

    def put_remote(self) -> CollectorState:
        """Push out bundle of completed tasks."""
        if self.tasks:
            self.queue.completed.put(self.tasks)
            self.tasks.clear()
        return CollectorState.GET_LOCAL

    def finalize(self) -> CollectorState:
        """Push out any remaining tasks and halt."""
        self.put_remote()
        log.debug('Stopping collector')
        return CollectorState.HALT


class ClientCollectorThread(Thread):
    """Run client collector within dedicated thread."""

    def __init__(self, queue: QueueClient, local: Queue[Optional[bytes]]) -> None:
        """Initialize machine."""
        super().__init__(name='hypershell-client-collector')
        self.machine = ClientCollector(queue=queue, local=local)

    def run(self) -> None:
        """Run machine."""
        self.machine.run()
        self.stop()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop machine."""
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


DEFAULT_TEMPLATE = '{}'


class TaskState(State, Enum):
    """Finite states for task executor."""
    START = 0
    GET_LOCAL = 1
    START_TASK = 2
    WAIT_TASK = 3
    PUT_LOCAL = 4
    FINALIZE = 5
    HALT = 6


class TaskExecutor(StateMachine):
    """Run tasks locally."""

    id: int
    task: Task
    process: Popen
    template: str
    inbound: Queue[Optional[bytes]]
    outbound: Queue[Optional[bytes]]
    task_data: bytes

    state = TaskState.START
    states = TaskState

    def __init__(self, id: int, inbound: Queue[Optional[bytes]], outbound: Queue[Optional[bytes]],
                 template: str = DEFAULT_TEMPLATE) -> None:
        """Initialize task executor."""
        self.id = id
        self.template = template
        self.inbound = inbound
        self.outbound = outbound

    @functools.cached_property
    def actions(self) -> Dict[TaskState, Callable[[], TaskState]]:
        return {
            TaskState.START: self.start,
            TaskState.GET_LOCAL: self.get_local,
            TaskState.START_TASK: self.start_task,
            TaskState.WAIT_TASK: self.wait_task,
            TaskState.PUT_LOCAL: self.put_local,
            TaskState.FINALIZE: self.finalize,
        }

    def start(self) -> TaskState:
        """Jump to GET_LOCAL state."""
        log.debug(f'Started executor ({self.id})')
        return TaskState.GET_LOCAL

    def get_local(self) -> TaskState:
        """Get the next task from the local inbound queue."""
        try:
            data = self.inbound.get(timeout=1)
            if data is not None:
                self.task = Task.unpack(data)
                return TaskState.START_TASK
            else:
                return TaskState.FINALIZE
        except QueueEmpty:
            return TaskState.GET_LOCAL

    def start_task(self) -> TaskState:
        """Start current task locally."""
        self.task.command = self.template.replace('{}', self.task.args)
        self.task.start_time = datetime.now().astimezone()
        self.task.client_host = HOSTNAME
        log.debug(f'Running task ({self.task.id})')
        self.process = Popen(self.task.command, shell=True, stdout=sys.stdout, stderr=sys.stderr,
                             env={**os.environ, 'TASK_ID': self.task.id, 'TASK_ARGS': self.task.args})
        return TaskState.WAIT_TASK

    def wait_task(self) -> TaskState:
        """Wait for current task to complete."""
        try:
            self.task.exit_status = self.process.wait(timeout=2)
            self.task.completion_time = datetime.now().astimezone()
            log.debug(f'Completed task ({self.task.id})')
            self.task_data = self.task.pack()
            return TaskState.PUT_LOCAL
        except TimeoutExpired:
            return TaskState.WAIT_TASK

    def put_local(self) -> TaskState:
        """Put completed task on outbound queue."""
        try:
            self.outbound.put(self.task_data, timeout=2)
            return TaskState.GET_LOCAL
        except QueueFull:
            return TaskState.PUT_LOCAL

    def finalize(self) -> TaskState:
        """Push out any remaining tasks and halt."""
        log.debug(f'Stopping executor ({self.id})')
        return TaskState.HALT


class TaskThread(Thread):
    """Run task executor within dedicated thread."""

    def __init__(self, id: int,
                 inbound: Queue[Optional[str]], outbound: Queue[Optional[str]],
                 template: str = DEFAULT_TEMPLATE) -> None:
        """Initialize task executor."""
        super().__init__(name=f'hypershell-executor-{id}')
        self.machine = TaskExecutor(id=id, inbound=inbound, outbound=outbound, template=template)

    def run(self) -> None:
        """Run machine."""
        self.machine.run()
        self.stop()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop machine."""
        self.machine.halt()
        super().stop(wait=wait, timeout=timeout)


class ClientThread(Thread):
    """Manage asynchronous task bundle scheduling and receiving."""

    client: QueueClient
    inbound: Queue[Optional[bytes]]
    outbound: Queue[Optional[bytes]]
    scheduler: ClientSchedulerThread
    collector: ClientCollectorThread
    executors: List[TaskThread]

    def __init__(self, ntasks: int = 1, address: Tuple[str, int] = (QueueConfig.host, QueueConfig.port),
                 auth: str = QueueConfig.auth, template: str = DEFAULT_TEMPLATE) -> None:
        """Initialize queue manager and child threads."""
        super().__init__(name='hypershell-client')
        self.client = QueueClient(config=QueueConfig(host=address[0], port=address[1], auth=auth))
        self.inbound = Queue(maxsize=DEFAULT_BUNDLESIZE)
        self.outbound = Queue(maxsize=DEFAULT_BUNDLESIZE)
        self.scheduler = ClientSchedulerThread(queue=self.client, local=self.inbound)
        self.collector = ClientCollectorThread(queue=self.client, local=self.outbound)
        self.executors = [TaskThread(id=count+1, inbound=self.inbound, outbound=self.outbound, template=template)
                          for count in range(ntasks)]

    def run(self) -> None:
        """Start child threads, wait."""
        log.debug('Starting client')
        with self.client:
            self.start_threads()
            self.wait_scheduler()
            self.wait_tasks()
            self.wait_collector()

    def start_threads(self) -> None:
        """Start child threads."""
        self.scheduler.start()
        self.collector.start()
        for task_thread in self.executors:
            task_thread.start()

    def wait_scheduler(self) -> None:
        """Wait for all tasks to be completed."""
        self.scheduler.join()

    def wait_tasks(self) -> None:
        """Send disconnect signal to each clients."""
        for _ in self.executors:
            self.inbound.put(None)  # signal executors to shutdown
        for thread in self.executors:
            thread.join()

    def wait_collector(self) -> None:
        """Signal collector to halt."""
        self.outbound.put(None)
        self.collector.join()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        log.debug('Stopping client')
        self.scheduler.stop(wait=wait, timeout=timeout)
        self.collector.stop(wait=wait, timeout=timeout)
        super().stop(wait=wait, timeout=timeout)


def run_client(address: Tuple[str, int] = (QueueConfig.host, QueueConfig.port), auth: str = QueueConfig.auth,
               template: str = DEFAULT_TEMPLATE, ntasks: int = 1) -> None:
    """Run client until disconnect signal received."""
    thread = ClientThread.new(ntasks=ntasks, address=address, auth=auth, template=template)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


APP_NAME = 'hypershell client'
APP_USAGE = f"""\
usage: {APP_NAME} [-h] [-n INT] [-H HOST] [-p PORT] [-t TEMPLATE]
Run client.\
"""

APP_HELP = f"""\
{APP_USAGE}

options:
-n, --ntasks         NUM        Number of tasks to run in parallel.
-t, --template       TEMPLATE   Command line template pattern.
-H, --host           ADDRESS    Hostname for server.
-p, --port           NUM        Port number for server.
-h, --help                      Show this message and exit.\
"""


class ClientApp(Application):
    """Run client."""

    name = APP_NAME
    interface = Interface(APP_NAME, APP_USAGE, APP_HELP)

    ntasks: int = 1
    interface.add_argument('-n', '--ntasks', type=int, default=ntasks)

    host: str = QueueConfig.host
    interface.add_argument('-H', '--host', default=host)

    port: int = QueueConfig.port
    interface.add_argument('-p', '--port', type=int, default=port)

    authkey: str = QueueConfig.auth
    interface.add_argument('--auth', default=authkey)

    template: str = DEFAULT_TEMPLATE
    interface.add_argument('-t', '--template', default=template)

    exceptions = {
        ConnectionRefusedError: functools.partial(handle_exception, logger=log, status=exit_status.runtime_error),
        **Application.exceptions,
    }

    def run(self) -> None:
        """Run client."""
        run_client(ntasks=self.ntasks, address=(self.host, self.port),
                   auth=self.authkey, template=self.template)
