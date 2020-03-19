# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Run the hyper-shell client."""

# annotations
from __future__ import annotations
from typing import IO

# standard libs
import sys
from queue import Queue, Empty
from functools import partial
from subprocess import Popen


# internal libs
from ..core.logging import logger, HOST, setup as logging_setup
from ..core.queue import QueueClient, ADDRESS, AUTHKEY, SENTINEL

# external libs
from cmdkit.app import Application, exit_status
from cmdkit.cli import Interface


# default command template
TEMPLATE = '{}'

# program name is constructed from module file name
NAME = 'client'
PROGRAM = 'hyper-shell client'
PADDING = ' ' * len(PROGRAM)

USAGE = f"""\
usage: {PROGRAM} [--template CMD] [--host ADDR] [--port PORT] [--authkey KEY] [--timeout SEC]
       {PADDING} [--verbose | --debug] [--logging]
       {PADDING} [--help]

{__doc__}\
"""

HELP = f"""\
{USAGE}

options:
-t, --template CMD   Template command (default: "{TEMPLATE}").
-H, --host     ADDR  Hostname of server (default: {ADDRESS[0]}).
-p, --port     SIZE  Port number for clients (default: {ADDRESS[1]}).
-k, --authkey  KEY   Cryptographic authkey for connection (default: {AUTHKEY}).
-x, --timeout  SEC   Length of time in seconds before disconnecting (default: 600).
    --parsl          Hand-off tasks to Parsl.
    --profile  NAME  Parsl configuration (default: local).
-v, --verbose        Show info messages.
-d, --debug          Show debugging messages.
-l, --logging        Show detailed syslog style messages.
-h, --help           Show this message and exit.
"""


# initialize module level logger
log = logger.with_name('hyper-shell.client')


def received_eof(exc) -> int:
    """The server shutdown and caused an EOFError."""
    log.critical('server disconnected')
    return exit_status.runtime_error


def connection_refused(exc) -> int:
    """The client raised a ConnectionRefusedError."""
    log.critical('connection refused')
    return exit_status.runtime_error


class Client(Application):

    interface = Interface(PROGRAM, USAGE, HELP)

    outfile: str = '-'
    interface.add_argument('-o', '--output', default=outfile, dest='outfile')

    host: str = ADDRESS[0]
    interface.add_argument('-H', '--host', default=host)

    port: int = ADDRESS[1]
    interface.add_argument('-p', '--port', default=port, type=int)

    authkey: bytes = AUTHKEY
    interface.add_argument('-k', '--authkey', default=authkey, type=str.encode)

    template: str = TEMPLATE
    interface.add_argument('-t', '--template', default=template)

    timeout: int = 0
    interface.add_argument('-w', '--timeout', default=timeout, type=int)

    debug: bool = False
    verbose: bool = False
    logging_interface = interface.add_mutually_exclusive_group()
    logging_interface.add_argument('-d', '--debug', action='store_true')
    logging_interface.add_argument('-v', '--verbose', action='store_true')

    logging: bool = False
    interface.add_argument('-l', '--logging', action='store_true')

    use_parsl: bool = False
    interface.add_argument('--parsl', action='store_true', dest='use_parsl')

    profile: str = 'local'
    interface.add_argument('--profile', default=profile)

    exceptions = {
        EOFError: received_eof,
        ConnectionRefusedError: connection_refused
    }

    server: QueueClient = None
    output: IO = None

    def run(self) -> None:
        """Run the hyper-shell client."""
        if not self.use_parsl:
            self.run_local()
        else:
            self.run_parsl()

    def run_local(self) -> None:
        """Run local hyper-shell client."""

        get_task = partial(self.server.tasks.get, timeout=self.timeout)
        run_task = partial(Popen, shell=True, stdout=self.output, stderr=sys.stderr)

        try:
            for task_id, task_line in iter(get_task, SENTINEL):
                # NOTE: signalling task_done immediately allows other clients to get a task
                #       without having to wait for this one to finish
                self.server.tasks.task_done()
                log.info(f'running task_id={task_id}')
                log.debug(f'running task_id={task_id}: {task_line}')
                process = run_task(self.template.format(task_line))
                process.wait()
                log.info(f'finished task_id={task_id}, status={process.returncode}')
                self.server.finished.put((task_id, task_line, process.returncode))

            log.debug('received sentinel, shutting down')

        except Empty:
            log.debug('timeout reached, shutting down')

    def run_parsl(self) -> None:
        """Run local hyper-shell client."""

        # local import allows for optional dependency on parsl
        from ..parsl.config import load_config
        from ..parsl.client import ParslScheduler, ParslCollector

        # load parsl configuration
        load_config(name=self.profile)

        # queues for sharing task futures
        tasks = Queue()
        futures = Queue()

        # start the consumer thread that pushes tasks to parsl
        scheduler = ParslScheduler(tasks, futures, self.template)
        scheduler.start()

        # start the collector thread that waits on futures
        collector = ParslCollector(futures, self.server.finished)
        collector.start()

        # publish all tasks from server to shared queue
        get_task = partial(self.server.tasks.get, timeout=self.timeout)
        try:
            for task_id, task_line in iter(get_task, SENTINEL):
                # NOTE: signalling task_done immediately allows other clients to get a task
                #       without having to wait for this one to finish
                self.server.tasks.task_done()
                tasks.put((task_id, task_line))

            log.debug('received sentinel, shutting down')
        except Empty:
            log.debug('timeout reached, shutting down')

        # publish sentinal to parsl scheduler and wait
        tasks.put(SENTINEL)
        scheduler.join()

        # scheduler puts the SENTINEL on the futures queue
        collector.join()

    def __enter__(self) -> Client:
        """Initialize resources."""

        logging_setup(log, self.debug, self.verbose, self.logging)
        self.server = QueueClient((self.host, self.port), authkey=self.authkey).__enter__()
        self.server.connected.put(HOST)
        log.debug(f'connected to {self.host}:{self.port}')

        self.output = sys.stdout if self.outfile == '-' else open(self.outfile, 'w')
        log.debug(f'writing outputs to {"<stdout>" if self.outfile == "-" else self.outfile}')

        # timeout of zero means no timeout
        self.timeout = None if self.timeout == 0 else self.timeout
        return self

    def __exit__(self, *exc) -> None:
        """Release resources."""

        if self.server is not None:
            self.server.__exit__()
            log.debug('disconnected')

        if self.output is not sys.stdout:
            self.output.close()


# inherit docstring from module
Client.__doc__ = __doc__