# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Run the hyper-shell server."""

# type annotations
from __future__ import annotations

# standard libs
import sys
import time
import functools
from queue import Empty
from multiprocessing import Process, JoinableQueue, Value

# internal libs
from ..core.logging import logger, setup as logging_setup
from ..core.queue import QueueServer, ADDRESS, AUTHKEY, MAXSIZE, SENTINEL
from ..core.exceptions import print_and_exit

# external libs
from cmdkit.app import Application, exit_status
from cmdkit.cli import Interface


# program name is constructed from module file name
NAME = 'server'
PROGRAM = 'hyper-shell server'
PADDING = ' ' * len(PROGRAM)

USAGE = f"""\
usage: {PROGRAM} FILE [--output FILE] [--maxsize SIZE]
       {PADDING} [--host ADDR] [--port PORT] [--authkey KEY]
       {PADDING} [--verbose | --debug] [--logging]
       {PADDING} [--help]

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
-v, --verbose        Show info messages.
-d, --debug          Show debug messages.
-l, --logging        Show detailed syslog style messages.
-h, --help           Show this message and exit.
"""


# initialize module level logger
log = logger.with_name('hyper-shell.server')


def queue_tasks(filepath: str, tasks: JoinableQueue, tasks_queued: Value,
                debug: bool = False, verbose: bool = False, logging: bool = False) -> None:
    """Read lines from `filepath` and publish to `tasks` queue."""

    logging_setup(log, debug, verbose, logging)
    # NOTE: Python has unfortunate behavior of setting stdin=/dev/null with
    #       Process creation. Work around: stackoverflow.com #30134297
    sys.stdin = open(0)
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


def record_results(filepath: str, finished: JoinableQueue, tasks_finished: Value,
                   debug: bool = False, verbose: bool = False, logging: bool = False) -> None:
    """Get lines from `finished` queue and write failures back to `filepath`."""

    logging_setup(log, debug, verbose, logging)
    output = sys.stdout if filepath == '-' else open(filepath, 'w')

    try:
        for task_id, task_line, task_exit in iter(finished.get, SENTINEL):
            if task_exit == 0:
                log.info(f'finished task_id={task_id}')
            else:
                log.warning(f'task_id={task_id} returned status={task_exit}')
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

    maxsize: int = MAXSIZE
    interface.add_argument('-s', '--maxsize', default=maxsize, type=int)

    debug: bool = False
    verbose: bool = False
    logging_interface = interface.add_mutually_exclusive_group()
    logging_interface.add_argument('-d', '--debug', action='store_true')
    logging_interface.add_argument('-v', '--verbose', action='store_true')

    logging: bool = False
    interface.add_argument('-l', '--logging', action='store_true')

    exceptions = {
        RuntimeError: functools.partial(print_and_exit, logger=log.critical,
                                        status=exit_status.runtime_error)
    }

    server: QueueServer = None

    def run(self) -> None:
        """Run the hyper-shell server."""

        # count of all tasks published
        tasks_queued = Value('i', 0)
        tasks_finished = Value('i', 0)

        # publish all commands to the task queue
        log.debug(f'reading from {"<stdin>" if self.taskfile == "-" else self.taskfile}')
        queueing_process = Process(name='hypershelld', target=queue_tasks,
                                   args=(self.taskfile, self.server.tasks, tasks_queued,
                                         self.debug, self.verbose, self.logging))
        queueing_process.start()

        # wait for finished tasks and log failures
        log.debug(f'writing failures to {"<stdout>" if self.outfile == "-" else self.outfile}')
        results_process = Process(name='hypershelld', target=record_results,
                                  args=(self.outfile, self.server.finished, tasks_finished,
                                        self.debug, self.verbose, self.logging))
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
        logging_setup(log, self.debug, self.verbose, self.logging)
        self.server = QueueServer((self.host, self.port), authkey=self.authkey,
                                  max_tasks=self.maxsize).__enter__()
        log.debug('started')
        return self

    def __exit__(self, *exc) -> None:
        """Release resources."""
        if self.server is not None:
            self.server.__exit__()
            log.debug('stopped')


# inherit docstring from module
Server.__doc__ = __doc__
