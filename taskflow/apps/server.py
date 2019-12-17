# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Run the taskflow server."""

# allow for return annotations
from __future__ import annotations

# standard libs
import os
import sys
import time
import functools
from queue import Empty
from multiprocessing import Process, JoinableQueue, Value

# internal libs
from ..core.logging import logger, Logger
from ..core.queue import QueueServer, ADDRESS, AUTHKEY, MAXSIZE, SENTINEL
from ..core.exceptions import print_and_exit
from ..__meta__ import __appname__, __copyright__, __contact__, __website__

# external libs
from cmdkit.app import Application, exit_status
from cmdkit.cli import Interface

# type annotations
from typing import IO


# program name is constructed from module file name
NAME = 'server'
PROGRAM = f'{__appname__} {NAME}'
PADDING = ' ' * len(PROGRAM)

USAGE = f"""\
usage: {PROGRAM} FILE [--output FILE] [--maxsize SIZE]
       {PADDING} [--host ADDR] [--port PORT] [--authkey KEY]
       {PADDING} [--debug] [--help]

{__doc__}\
"""

HELP = f"""\
{USAGE}

arguments:
FILE                 Path to file for command list.

options:
-o, --output   FILE  Path to file for failed commands (default: <stdout>).
-s, --maxsize  SIZE  Maximum items allowed in the queue (default: {MAXSIZE}).
-H, --host     ADDR  Bind address for server (default: {ADDRESS[0]}).
-p, --port     PORT  Port number for server (default: {ADDRESS[1]}).
-k, --authkey  KEY   Cryptographic key for connection (default: {AUTHKEY}).
-d, --debug          Show debugging messages.
-h, --help           Show this message and exit.
"""


# initialize module level logger
log = logger.with_name(NAME)


def queue_tasks(filepath: str, tasks: JoinableQueue, tasks_queued: Value) -> None:
    """Read lines from `filepath` and publish to `tasks` queue."""

    from ..core.logging import logger
    log = logger.with_name(NAME)

    source = sys.stdin if filepath == '-' else open(filepath, 'r')

    try:
        for i, task_line in enumerate(map(str.strip, source)):
            task_id = i + 1
            tasks.put((task_id, task_line))
            log.info(f'queued task_id={task_id}')
            log.debug(f'queued task_id={task_id}: {task_line}')
            with tasks_queued.get_lock():
                tasks_queued.value += 1

    except KeyboardInterrupt:
        pass

    finally:
        if source is not sys.stdin:
            source.close()


def record_results(filepath: str, finished: JoinableQueue, tasks_finished: Value) -> None:
    """Get lines from `finished` queue and write failures back to `filepath`."""

    from ..core.logging import logger
    log = logger.with_name(NAME)

    output = sys.stdout if filepath == '-' else open(filepath, 'w')

    try:
        for task_id, task_line, task_exit in iter(finished.get, SENTINEL):
            if task_exit == 0:
                log.info(f'finished task_id={task_id}')
            else:
                log.warning(f'task_id={task_id} exited status={task_exit}')
                output.write(f'{task_line}\n')
            finished.task_done()
            with tasks_finished.get_lock():
                tasks_finished.value += 1

    except KeyboardInterrupt:
        pass

    finally:
        if output is not sys.stdout:
            output.close()


class Server(Application):

    interface = Interface(PROGRAM, USAGE, HELP)

    taskfile: str = '-'
    interface.add_argument('taskfile')

    outfile: str = '-'
    interface.add_argument('-o', '--output', default=outfile, dest='outfile')

    host: str = ADDRESS[0]
    interface.add_argument('-H', '--host', default=host)

    port: int = ADDRESS[1]
    interface.add_argument('-p', '--port', default=port, type=int)

    authkey: bytes = AUTHKEY
    interface.add_argument('-k', '--authkey', default=authkey, type=str.encode)

    debug: bool = False
    interface.add_argument('-d', '--debug', action='store_true')

    maxsize: int = MAXSIZE
    interface.add_argument('-s', '--maxsize', default=maxsize, type=int)

    exceptions = {
        RuntimeError: functools.partial(print_and_exit, logger=log.critical,
                                        status=exit_status.runtime_error)
    }

    server: QueueServer = None

    def run(self) -> None:
        """Run the taskflow server."""

         # count of all tasks published
        tasks_queued = Value('i', 0)
        tasks_finished = Value('i', 0)

        # publish all commands to the task queue
        log.debug(f'reading from {"<stdin>" if self.taskfile == "-" else self.taskfile}')
        queueing_process = Process(name='taskflowd', target=queue_tasks,
                                   args=(self.taskfile, self.server.tasks, tasks_queued))
        queueing_process.start()

        # wait for finished tasks and log failures
        log.debug(f'writing failures to {"<stdout>" if self.outfile == "-" else self.outfile}')
        results_process = Process(name='taskflowd', target=record_results,
                                  args=(self.outfile, self.server.finished, tasks_finished))
        results_process.start()

        # wait for all tasks to be published
        queueing_process.join()

        # wait for all tasks to finish
        log.debug('waiting for clients to finish')
        while tasks_finished.value < tasks_queued.value:
            time.sleep(1)

        # send shutdown signal to all subscribed clients
        # they put their hostname on the 'connected' queue when first connecting
        try:
            log.debug('sending disconnect request to clients')
            for client in iter(functools.partial(self.server.connected.get, timeout=2), None):
                self.server.tasks.put(SENTINEL)
                self.server.connected.task_done()
                log.debug(f'disconnect request sent [{client}]')

        except Empty:
            pass

        # shutdown results process
        self.server.finished.put(SENTINEL)
        results_process.join()

    def __enter__(self) -> Server:
        """Initialize resources."""

        if self.debug:
            for handler in log.handlers:
                handler.level = log.levels[0]

        self.server = QueueServer((self.host, self.port), authkey=self.authkey,
                                  max_tasks=self.maxsize).__enter__()
        log.debug(f'server started')
        return self

    def __exit__(self, *exc) -> None:
        """Release resources."""

        if self.server is not None:
            self.server.__exit__()
            log.debug(f'server stopped')


# inherit docstring from module
Server.__doc__ = __doc__
