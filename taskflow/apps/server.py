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
from multiprocessing import JoinableQueue

# internal libs
from ..core.logging import logger
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
usage: {PROGRAM} FILE [--debug] [--host ADDR] [--port PORT] [--authkey KEY]
       {PADDING} [--maxsize SIZE] [--timeout SEC]
       {PADDING} [--help]

{__doc__}\
"""

HELP = f"""\
{USAGE}

arguments:
FILE                 Path to command list.

options:
-d, --debug          Show debugging messages.
-H, --host     ADDR  Hostname of server (default: {ADDRESS[0]}).
-p, --port     PORT  Port number for clients (default: {ADDRESS[1]}).
-k, --authkey  KEY   Cryptographic authkey for connection (default: {AUTHKEY}).
-s, --maxsize  SIZE  Maximum items allowed in the queue (default: {MAXSIZE}).
-x, --timeout  SEC   Timeout period if reading from <stdin>.
-h, --help           Show this message and exit.
"""


# initialize module level logger
log = logger.with_name(NAME)


class Server(Application):

    interface = Interface(PROGRAM, USAGE, HELP)

    infile: str = '-'
    interface.add_argument('infile')

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

    _server: QueueServer = None
    _source: IO = None

    def run(self) -> None:
        """Run the taskflow server."""
        
        if self.debug:
            for handler in log.handlers:
                handler.level = log.levels[0]

        # publish all commands to the queue
        log.debug(f'reading from {self.infile}')
        for task_id, task_line in enumerate(map(str.strip, self.source)):
            log.info(f'queued task_id={task_id}')
            log.debug(f'queued task_id={task_id}: {task_line}')
            self.tasks.put((task_id, task_line))
        
        # wait for clients to take last command
        log.info('waiting for clients to finish')
        while not self.tasks.empty():
            time.sleep(1)
        
        # attempt to send shutdown signal to all subscribed clients
        # they put their hostname on the 'connected' queue when first connecting
        # and then on the disconnected queue after receiving the sentinel value
        try:
            count = 0
            for client in iter(functools.partial(self.connected.get, timeout=1), None):
                self.tasks.put(SENTINEL)
                log.debug(f'sent disconnect to {client}')
                count += 1
                self.connected.task_done()
        except Empty:
            pass

        # FIXME: if a client died this will fail
        for i, client in enumerate(iter(self.disconnected.get, None)):
            log.debug(f'received disconnect from {client}')
            self.disconnected.task_done()
            if i + 1 == count:
                break
        
        # write all commands that failed to <stdout>
        if not self.failed.empty():
            log.info(f'some commands exited with non-zero status')
            try:
                for task_line in iter(functools.partial(self.failed.get, timeout=1), None):
                    print(task_line)
                    self.failed.task_done()
            except Empty:
                pass

    @property
    def server(self) -> QueueServer:
        """Lazy-initialize the QueueServer."""
        if self._server is None:
            self._server = QueueServer((self.host, self.port), authkey=self.authkey).__enter__()
            log.info(f'started server {self.host}:{self.port}')
        return self._server
    
    @property
    def source(self) -> IO:
        """Access to either <stdin> or file handle."""
        if self._source is None:
            if self.infile == '-':
                self._source = sys.stdin
            else:
                self._source = open(self.infile, mode='r')
        return self._source

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

    def __enter__(self) -> Server:
        """Initialize resource."""
        return self
    
    def __exit__(self, *exc) -> None:
        """Release resource."""
        if self._server is not None:
            self._server.__exit__()
            log.info(f'stopped server')
        if self._source is not None and self._source is not sys.stdin:
            self._source.close()


# inherit docstring from module
Server.__doc__ = __doc__
