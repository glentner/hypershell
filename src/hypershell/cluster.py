# SPDX-FileCopyrightText: 2021 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""
Run full cluster with server and clients.

TODO: examples and notes
"""


# type annotations
from __future__ import annotations
from typing import IO, Optional, Iterable, List, Dict, Callable, Tuple

# standard libs
import os
import sys
import time
import logging
import secrets
from subprocess import Popen
from functools import cached_property

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface, ArgumentError

# internal libs
from hypershell.core.config import config, load_task_env
from hypershell.core.queue import QueueConfig
from hypershell.core.thread import Thread
from hypershell.core.logging import Logger, HOSTNAME
from hypershell.client import ClientThread, DEFAULT_TEMPLATE
from hypershell.server import ServerThread, DEFAULT_BUNDLESIZE, DEFAULT_ATTEMPTS
from hypershell.submit import DEFAULT_BUNDLEWAIT

# public interface
__all__ = ['run_local', 'run_cluster', 'LocalCluster', 'RemoteCluster', 'ClusterApp', ]


# module level logger
log: Logger = logging.getLogger(__name__)


class LocalCluster(Thread):
    """Run server with single local client."""

    server: ServerThread
    client: ClientThread

    def __init__(self,
                 source: Iterable[str] = None, template: str = DEFAULT_TEMPLATE,
                 forever_mode: bool = False, restart_mode: bool = False,
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
                 max_retries: int = DEFAULT_ATTEMPTS, eager: bool = False, live: bool = False,
                 num_tasks: int = 1, redirect_failures: IO = None,
                 redirect_output: IO = None, redirect_errors: IO = None) -> None:
        """Initialize server and client threads."""
        auth = secrets.token_hex(64)
        self.server = ServerThread(source=source, auth=auth, live=live, bundlesize=bundlesize, bundlewait=bundlewait,
                                   max_retries=max_retries, eager=eager, forever_mode=forever_mode,
                                   restart_mode=restart_mode, redirect_failures=redirect_failures)
        self.client = ClientThread(num_tasks=num_tasks, template=template, auth=auth,
                                   bundlesize=bundlesize, bundlewait=bundlewait,
                                   redirect_output=redirect_output, redirect_errors=redirect_errors)
        super().__init__(name='hypershell-cluster')

    def run_with_exceptions(self) -> None:
        """Start child threads, wait."""
        self.server.start()
        time.sleep(2)  # NOTE: give the server a chance to start
        self.client.start()
        self.client.join()
        self.server.join()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.server.stop(wait=wait, timeout=timeout)
        self.client.stop(wait=wait, timeout=timeout)
        super().stop(wait=wait, timeout=timeout)


class RemoteCluster(Thread):
    """Run server with single local client."""

    server: ServerThread
    clients: Popen
    client_argv: str

    def __init__(self,
                 source: Iterable[str] = None, template: str = DEFAULT_TEMPLATE,
                 forever_mode: bool = False, restart_mode: bool = False,
                 launcher: str = 'mpirun', launcher_args: List[str] = None,
                 bind: Tuple[str, int] = ('0.0.0.0', QueueConfig.port),
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
                 max_retries: int = DEFAULT_ATTEMPTS, eager: bool = False, live: bool = False,
                 num_tasks: int = 1, remote_exe: str = 'hyper-shell', redirect_failures: IO = None) -> None:
        """Initialize server and client threads."""
        auth = secrets.token_hex(64)
        self.server = ServerThread(source=source, auth=auth, live=live, bundlesize=bundlesize,
                                   bundlewait=bundlewait, max_retries=max_retries, eager=eager, address=bind,
                                   forever_mode=forever_mode, restart_mode=restart_mode,
                                   redirect_failures=redirect_failures)
        launcher_args = '' if launcher_args is None else ' '.join(launcher_args)
        self.client_argv = (f'{launcher} {launcher_args} {remote_exe} client -H {HOSTNAME} -p {bind[1]} '
                            f'-N {num_tasks} -b {bundlesize} -w {bundlewait} -t "{template}" -k {auth}')
        super().__init__(name='hypershell-cluster')

    def run_with_exceptions(self) -> None:
        """Start child threads, wait."""
        self.server.start()
        time.sleep(2)  # NOTE: give the server a chance to start
        log.debug(f'Launching clients: {self.client_argv}')
        self.clients = Popen(self.client_argv, shell=True, stdout=sys.stdout, stderr=sys.stderr,
                             env={**os.environ, **load_task_env()})
        self.clients.wait()
        self.server.join()

    def stop(self, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.server.stop(wait=wait, timeout=timeout)
        self.clients.terminate()
        super().stop(wait=wait, timeout=timeout)


def run_local(**options) -> None:
    """Run local cluster until completion."""
    thread = LocalCluster.new(**options)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


def run_cluster(**options) -> None:
    """Run remote cluster until completion."""
    thread = RemoteCluster.new(**options)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


APP_NAME = 'hyper-shell cluster'
APP_USAGE = f"""\
usage: hyper-shell cluster [-h] [FILE | --restart | --forever] [--no-db] [-N NUM] [-t CMD] 
                           [-b SIZE] [-w SEC] [-o PATH] [-e PATH] [-f PATH] [-r NUM [--eager]] 
                           [--ssh HOST... | --mpi | --launcher=ARGS...]\
"""
APP_HELP = f"""\
{APP_USAGE}

Start cluster locally, over SSH, or with a custom launcher.

arguments:
FILE                     Path to input task file (default: <stdin>).

modes:
--ssh          HOST...   Launch directly with SSH host(s).
--mpi                    Same as '--launcher=mpirun'
--launcher     ARGS...   Use specific launch interface.

options:
-N, --num-tasks    NUM   Number of task executors per client.
-t, --template     CMD   Command-line template pattern.
-p, --port         NUM   Port number (default: {QueueConfig.port}).
-b, --bundlesize   SIZE  Size of task bundle (default: {DEFAULT_BUNDLESIZE}).
-w, --bundlewait   SEC   Seconds to wait before flushing tasks (default: {DEFAULT_BUNDLEWAIT}).
-r, --max-retries  NUM   Auto-retry failed tasks (default: {DEFAULT_ATTEMPTS - 1}).
    --eager              Schedule failed tasks before new tasks.
    --no-db              Disable database (submit directly to clients).
    --forever            Schedule forever.
    --restart            Start scheduling from last completed task.
-o, --output       PATH  File path for task outputs (default: <stdout>).
-e, --errors       PATH  File path for task errors (default: <stderr>).
-f, --failures     PATH  File path to write failed task args (default: <none>).
-h, --help               Show this message and exit.\
"""


class ClusterApp(Application):
    """Cluster application."""

    name = APP_NAME
    interface = Interface(APP_NAME, APP_USAGE, APP_HELP)

    filepath: str
    source: Optional[IO] = None
    interface.add_argument('filepath', nargs='?', default=None)

    num_tasks: int = 1
    interface.add_argument('-N', '--num-tasks', type=int, default=num_tasks)

    template: str = DEFAULT_TEMPLATE
    interface.add_argument('-t', '--template', default=template)

    bundlesize: int = config.server.bundlesize
    interface.add_argument('-b', '--bundlesize', type=int, default=bundlesize)

    bundlewait: int = config.submit.bundlewait
    interface.add_argument('-w', '--bundlewait', type=int, default=bundlewait)

    eager_mode: bool = False
    max_retries: int = DEFAULT_ATTEMPTS - 1
    interface.add_argument('-r', '--max-retries', type=int, default=max_retries)
    interface.add_argument('--eager', action='store_true', dest='eager_mode')

    live_mode: bool = False
    interface.add_argument('--no-db', action='store_true', dest='live_mode')

    forever_mode: bool = False
    interface.add_argument('--forever', action='store_true', dest='forever_mode')

    restart_mode: bool = False
    interface.add_argument('--restart', action='store_true', dest='restart_mode')

    ssh_mode: List[str] = None
    mpi_mode: bool = False
    launch_mode: str = None
    mode_interface = interface.add_mutually_exclusive_group()
    mode_interface.add_argument('--ssh', nargs='+', default=None, dest='ssh_mode')
    mode_interface.add_argument('--mpi', action='store_true', dest='mpi_mode')
    mode_interface.add_argument('--launcher', default=None, dest='launch_mode')

    remote_exe: str = 'hyper-shell'
    interface.add_argument('--remote-exe', default=remote_exe)

    port: int = QueueConfig.port
    interface.add_argument('-p', '--port', default=port, type=int)

    output_path: str = None
    errors_path: str = None
    interface.add_argument('-o', '--output', default=None, dest='output_path')
    interface.add_argument('-e', '--errors', default=None, dest='errors_path')

    failure_path: str = None
    interface.add_argument('-f', '--failures', default=None, dest='failure_path')

    def run(self) -> None:
        """Run cluster."""
        log.info(f'Reading tasks from {self.filename}')
        if self.live_mode and self.forever_mode:
            raise ArgumentError('Using --forever with --no-db is invalid')
        if self.live_mode and self.restart_mode:
            raise ArgumentError('Using --restart with --no-db is invalid')
        if self.forever_mode and self.restart_mode:
            raise ArgumentError('Using --forever with --restart is invalid')
        launcher = self.launchers.get(self.mode)
        launcher(source=self.source, num_tasks=self.num_tasks, template=self.template,
                 bundlesize=self.bundlesize, bundlewait=self.bundlewait,
                 max_retries=self.max_retries, live=self.live_mode,
                 forever_mode=self.forever_mode, restart_mode=self.restart_mode,
                 redirect_failures=self.failure_stream)

    def run_local(self, **options) -> None:
        """Run local cluster."""
        run_local(**options, redirect_output=self.output_stream, redirect_errors=self.errors_stream)

    def run_launch(self, **options) -> None:
        """Run remote cluster with custom launcher."""
        run_cluster(**options, launcher=self.launch_mode,
                    remote_exe=self.remote_exe, bind=('0.0.0.0', self.port))

    def run_mpi(self, **options) -> None:
        """Run remote cluster with 'mpirun'."""
        run_cluster(**options, launcher='mpirun',
                    remote_exe=self.remote_exe, bind=('0.0.0.0', self.port))

    @staticmethod
    def run_ssh(**options) -> None:
        """Run remote cluster with SSH."""
        log.critical('SSH-mode not implemented')

    @cached_property
    def launchers(self) -> Dict[str, Callable]:
        """Map of launchers."""
        return {
            'local': self.run_local,
            'launch': self.run_launch,
            'mpi': self.run_mpi,
            'ssh': self.run_ssh
        }

    @cached_property
    def mode(self) -> str:
        """The launch mode to run the cluster."""
        for name in ['ssh', 'mpi', 'launch']:
            if getattr(self, f'{name}_mode'):
                return name
        else:
            return 'local'

    def check_arguments(self) -> None:
        """Various checks on input arguments."""
        if self.restart_mode and self.live_mode:
            raise ArgumentError('Cannot restart without database (given --no-db)')
        if self.filepath is None and not self.restart_mode:
            self.filepath = '-'  # NOTE: assume STDIN
        if self.output_path and self.mode != 'local':
            raise ArgumentError('Cannot specify -o/--output PATH with remote clients')
        if self.errors_path and self.mode != 'local':
            raise ArgumentError('Cannot specify -e/--errors PATH with remote clients')

    @cached_property
    def filename(self) -> str:
        """The basename of the file."""
        if self.restart_mode:
            return '<none>'
        else:
            return '<stdin>' if self.filepath == '-' else os.path.basename(self.filepath)

    @cached_property
    def output_stream(self) -> IO:
        """IO stream to write task outputs."""
        return sys.stdout if not self.output_path else open(self.output_path, mode='w')

    @cached_property
    def errors_stream(self) -> IO:
        """IO stream to write task errors."""
        return sys.stderr if not self.errors_path else open(self.errors_path, mode='w')

    @cached_property
    def failure_stream(self) -> IO:
        """IO stream to write failed task args."""
        return os.devnull if not self.failure_path else open(self.failure_path, mode='w')

    @cached_property
    def input_stream(self) -> Optional[IO]:
        """IO stream to read task command-line args."""
        if self.restart_mode:
            return None
        else:
            return sys.stdin if self.filepath == '-' else open(self.filepath, mode='r')

    @cached_property
    def source(self) -> Iterable[str]:
        """Input source for task command-line args."""
        return [] if self.restart_mode else self.input_stream

    def __enter__(self) -> ClusterApp:
        """Set up resources and attributes."""
        self.check_arguments()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close IO streams if not standard streams."""
        if self.input_stream is not None and self.input_stream is not sys.stdin:
            self.input_stream.close()
        if self.output_stream is not sys.stdout:
            self.output_stream.close()
        if self.errors_stream is not sys.stderr:
            self.errors_stream.close()
        if self.failure_stream is not os.devnull:
            self.failure_stream.close()
