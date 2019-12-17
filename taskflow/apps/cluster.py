# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Run taskflow cluster, server and clients."""

# type annotations
from __future__ import annotations
from typing import IO, Tuple

# standard libs
import os
import sys
import time
import secrets
import psutil
import functools
import subprocess

# internal libs
from ..__meta__ import __appname__, __copyright__, __contact__, __website__
from ..core.logging import logger, Logger
from ..core.queue import ADDRESS, AUTHKEY, MAXSIZE, SENTINEL
from ..core.exceptions import print_and_exit
from .client import Client, TEMPLATE
from .server import Server

# external libs
from cmdkit.app import Application, exit_status
from cmdkit.cli import Interface, ArgumentError


# program name is constructed from module file name
NAME = 'cluster'
PROGRAM = f'{__appname__} {NAME}'
PADDING = ' ' * len(PROGRAM)

USAGE = f"""\
usage: {PROGRAM} FILE [--failures PATH] [--port NUM] [--maxsize SIZE]
       {PADDING} [--local [--num-cores NUM] | --mpi [--nodefile PATH] | --parsl [--profile NAME]]
       {PADDING} [--debug] [--help]

{__doc__}\
"""

HELP = f"""\
{USAGE}

arguments:
FILE                  Path to file for command list.

options:
-f, --failures  PATH  Path to file to write failed commands.
-p, --port      PORT  Port number for server (default: {ADDRESS[1]}).
-s, --maxsize   SIZE  Maximum items allowed in the queue (default: {MAXSIZE}).
-t, --template  CMD   Template command (default: "{TEMPLATE}").

    --local           Run cluster locally (uses --num-cores).
    --mpi             Run distributed cluster with MPI (uses --nodefile).
    --parsl           Run cluster using Parsl (uses --profile).

-N, --num-cores NUM   Number of cores to use (see --local).
    --nodefile  PATH  Path to node file (see --mpi).
    --profile   NAME  Name of parsl config to use.

-d, --debug           Show debugging messages.
-h, --help            Show this message and exit.
"""


# initialize module level logger
log = logger.with_name(NAME)


class Cluster(Application):

    interface = Interface(PROGRAM, USAGE, HELP)

    taskfile: str = '-'
    interface.add_argument('taskfile')

    port: int = ADDRESS[1]
    interface.add_argument('-p', '--port', default=port, type=int)

    maxsize: int = MAXSIZE
    interface.add_argument('-s', '--maxsize', default=maxsize, type=int)

    failures: str = None
    interface.add_argument('-f', '--failures', default=None)

    template: str = TEMPLATE
    interface.add_argument('-t', '--template', default=template)

    # clustering method
    cluster_mode: str = 'local'
    cluster_modes: Tuple[str] = ('local', 'mpi', 'parsl')
    cluster_mode_interface = interface.add_mutually_exclusive_group()
    cluster_mode_interface.add_argument('--local', action='store_true', dest='use_local')
    cluster_mode_interface.add_argument('--mpi', action='store_true', dest='use_mpi')
    cluster_mode_interface.add_argument('--parsl', action='store_true', dest='use_parsl')

    nodefile: str = None
    num_cores: int = None
    profile: str = 'local'  # name of parsl config to use (from config file)
    parallelism_interface = interface.add_mutually_exclusive_group()
    parallelism_interface.add_argument('--nodefile', default=None)
    parallelism_interface.add_argument('-N', '--num-cores', default=None, type=int)
    parallelism_interface.add_argument('--profile', default=profile)

    debug: bool = False
    interface.add_argument('-d', '--debug', action='store_true')

    exceptions = {
        RuntimeError: functools.partial(print_and_exit, logger=log.critical,
                                        status=exit_status.runtime_error)
    }

    def run(self) -> None:
        """Run the taskflow cluster."""

        for mode in self.cluster_modes:
            if hasattr(self, f'use_{mode}') and getattr(self, f'use_{mode}') is True:
                self.cluster_mode = mode

        method = getattr(self, f'run_{self.cluster_mode}')
        method()

    def run_local(self) -> None:
        """Run the cluster in 'local' mode."""

        stdin = None if self.taskfile != '-' else sys.stdin
        debug = '-d' if self.debug is True else ''
        authkey = secrets.token_hex(nbytes=16)
        failures = '' if self.failures is None else f'-o {self.failures}'

        server_invocation = (f'taskflow server {self.taskfile} {failures} -p {self.port} '
                             f'-k {authkey} -s {self.maxsize} {debug}')

        log.debug(f'starting server: "{server_invocation}"')
        server_process = subprocess.Popen(server_invocation, shell=True, stdin=stdin, stderr=sys.stderr)

        client_invocation = (f'taskflow client -p {self.port} -k {authkey} {debug} '
                             f'-t "{self.template}"')
        num_cores = self.num_cores if self.num_cores is not None else psutil.cpu_count()

        log.debug(f'starting {num_cores} clients: "{client_invocation}"')
        time.sleep(2)

        client_processes = []
        for _ in range(num_cores):
            client = subprocess.Popen(client_invocation, shell=True, stdout=sys.stdout, stderr=sys.stderr)
            client_processes.append(client)

        for client in client_processes:
            client.wait()

        server_process.wait()

    def run_mpi(self) -> None:
        """Run the cluster in 'mpi' mode."""

        if self.nodefile is None:
            raise ArgumentError(f'No nodefile given')

        stdin = None if self.taskfile != '-' else sys.stdin
        debug = '-d' if self.debug is True else ''
        authkey = secrets.token_hex(nbytes=16)
        failures = '' if self.failures is None else f'-o {self.failures}'
        server_invocation = (f'taskflow server {self.taskfile} {failures} -p {self.port} '
                             f'-k {authkey} -s {self.maxsize} {debug}')

        log.debug(f'starting server: "{server_invocation}"')
        server_process = subprocess.Popen(server_invocation, shell=True, stdin=stdin, stderr=sys.stderr)

        client_invocation = (f'taskflow client -p {self.port} -k {authkey} {debug} '
                             f'-t "{self.template}"')

        log.debug(f'starting clients: "{client_invocation}"')
        time.sleep(2)

        mpi_invocation = f'mpiexec -machinefile {self.nodefile} {client_invocation}'
        mpi_process = subprocess.Popen(mpi_invocation, shell=True, stdout=sys.stdout, stderr=sys.stderr)

        mpi_process.wait()
        server_process.wait()

    def run_parsl(self) -> None:
        """Run the cluster in 'parsl' mode."""
        raise ArgumentError(f'"parsl" mode is not currently implemented')


    def __enter__(self) -> Cluster:
        """Initialize resources."""

        if self.debug:
            for handler in log.handlers:
                handler.level = log.levels[0]

        return self

    def __exit__(self, *exc) -> None:
        """Release resources."""


# inherit docstring from module
Cluster.__doc__ = __doc__
