# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Run the taskflow client."""

# annotations
from __future__ import annotations
from typing import IO

# standard libs
import os
import sys
from queue import Empty
from functools import partial
from subprocess import Popen, PIPE
from multiprocessing import JoinableQueue

# internal libs
from ..core.logging import logger, HOST
from ..core.queue import QueueClient, ADDRESS, AUTHKEY, SENTINEL
from ..__meta__ import __appname__, __copyright__, __contact__, __website__

# external libs
from cmdkit.app import Application, exit_status
from cmdkit.cli import Interface


# default command template
TEMPLATE = '{}'

# program name is constructed from module file name
NAME = 'client'
PROGRAM = f'{__appname__} {NAME}'
PADDING = ' ' * len(PROGRAM)

USAGE = f"""\
usage: {PROGRAM} [--template CMD] [--debug] [--host ADDR] [--port PORT] [--authkey KEY]
       {PADDING} [--timeout SEC]
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
-d, --debug          Show debugging messages.
-h, --help           Show this message and exit.
"""


# initialize module level logger
log = logger.with_name(NAME)


def received_eof(exc) -> int:
    """The server shutdown and caused an EOFError."""
    log.critical(f'server disconnected')
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

    timeout: int = 600
    interface.add_argument('-w', '--timeout', default=timeout, type=int)

    debug: bool = False
    interface.add_argument('-d', '--debug', action='store_true')

    exceptions = {
        EOFError: received_eof
    }

    server: QueueClient = None
    output: IO = None

    def run(self) -> None:
        """Run the taskflow client."""
        
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
            log.debug(f'timeout reached, shutting down')

    def __enter__(self) -> Client:
        """Initialize resources."""

        if self.debug:
            for handler in log.handlers:
                handler.level = log.levels[0]
                
        self.server = QueueClient((self.host, self.port), authkey=self.authkey).__enter__()
        self.server.connected.put(HOST)
        log.debug(f'connected to {self.host}:{self.port}')

        self.output = sys.stdout if self.outfile == '-' else open(self.outfile, 'w')
        log.debug(f'writing failures to {"<stdout>" if self.outfile == "-" else self.outfile}')

        return self
    
    def __exit__(self, *exc) -> None:
        """Release resources."""

        if self.server is not None:
            self.server.__exit__()
            log.debug(f'disconnected from server')

        if self.output is not sys.stdout:
            self.output.close()


# inherit docstring from module
Client.__doc__ = __doc__
