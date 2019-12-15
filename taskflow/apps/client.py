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

# allow for return annotations
from __future__ import annotations

# standard libs
import os
import sys
from queue import Empty
from functools import partial
from subprocess import Popen, PIPE
from multiprocessing import JoinableQueue

# internal libs
from ..core.logging import logger, HOST
from ..core.queue import QueueClient, ADDRESS, AUTHKEY, MAXSIZE
from ..__meta__ import __appname__, __copyright__, __contact__, __website__

# external libs
from cmdkit.app import Application
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
-x, --timeout  SEC   Length of time in seconds before disconnecting (default: 60).
-d, --debug          Show debugging messages.
-h, --help           Show this message and exit.
"""


# initialize module level logger
log = logger.with_name(NAME)


class Client(Application):

    interface = Interface(PROGRAM, USAGE, HELP)

    host: str = ADDRESS[0]
    interface.add_argument('-H', '--host', default=host)

    port: int = ADDRESS[1]
    interface.add_argument('-p', '--port', default=port, type=int)

    authkey: bytes = AUTHKEY
    interface.add_argument('-k', '--authkey', default=authkey, type=str.encode)

    template: str = TEMPLATE
    interface.add_argument('-t', '--template', default=template)

    timeout: float = 60
    interface.add_argument('-x', '--timeout', default=timeout, type=float)

    debug: bool = False
    interface.add_argument('-d', '--debug', action='store_true')

    _server: QueueClient = None

    def run(self) -> None:
        """Run the taskflow client."""
        
        if self.debug:
            for handler in log.handlers:
                handler.level = log.levels[0]
        
        get_task = partial(self.tasks.get, timeout=self.timeout)
        run_task = partial(Popen, shell=True, stdout=sys.stdout, stderr=sys.stderr)
        try:
            for task_id, task_line in iter(get_task, None):
                log.info(f'running task_id={task_id}')
                log.debug(f'running task_id={task_id}: {task_line}')
                process = run_task(self.template.format(task_line))
                process.wait()
                log.debug(f'finished task_id={task_id}, status={process.returncode}')
                if process.returncode != 0:
                    self.failed.put(task_line)
                self.tasks.task_done()

            log.debug('received sentinel, shutting down')
        except Empty:
            log.debug(f'timeout reached, shutting down')
        finally:
            self.disconnected.put(HOST)

    @property
    def server(self) -> QueueClient:
        """Lazy-initialize the QueueClient."""
        if self._server is None:
            self._server = QueueClient((self.host, self.port), authkey=self.authkey).__enter__()
            log.info(f'connected to {self.host}:{self.port}')
            self._server.connected.put(HOST)
        return self._server

    @property
    def tasks(self) -> JoinableQueue:
        """Access to QueueServer's `tasks` queue."""
        return self.server.tasks

    @property
    def failed(self) -> JoinableQueue:
        """Access to QueueServer's `failed` queue."""
        return self.server.failed

    @property
    def connected(self) -> JoinableQueue:
        """Access to QueueServer's `connected` queue."""
        return self.server.connected

    @property
    def disconnected(self) -> JoinableQueue:
        """Access to QueueServer's `disconnected` queue."""
        return self.server.disconnected

    def __enter__(self) -> Client:
        """Initialize resource."""
        return self
    
    def __exit__(self, *exc) -> None:
        """Release resource."""
        if self._server is not None:
            self._server.__exit__()
            log.info(f'disconnected')


# inherit docstring from module
Client.__doc__ = __doc__
