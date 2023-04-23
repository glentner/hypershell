# SPDX-FileCopyrightText: 2023 Geoffrey Lentner
# SPDX-License-Identifier: Apache-2.0

"""
Run full cluster with server and clients.
"""


# type annotations
from __future__ import annotations
from typing import IO, Optional, Iterable, List, Dict, Callable, Tuple, Type
from types import TracebackType

# standard libs
import os
import re
import sys
import time
import secrets
from subprocess import Popen
from functools import cached_property

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface, ArgumentError
from cmdkit.config import ConfigurationError, Namespace

# internal libs
from hypershell.core.ansi import colorize_usage
from hypershell.core.config import config, load_task_env, blame
from hypershell.core.queue import QueueConfig
from hypershell.core.thread import Thread
from hypershell.core.logging import Logger, HOSTNAME
from hypershell.core.template import DEFAULT_TEMPLATE
from hypershell.core.exceptions import get_shared_exception_mapping
from hypershell.data import initdb, checkdb
from hypershell.client import ClientThread, DEFAULT_NUM_TASKS, DEFAULT_DELAY
from hypershell.server import ServerThread, DEFAULT_BUNDLESIZE, DEFAULT_ATTEMPTS
from hypershell.submit import DEFAULT_BUNDLEWAIT

# public interface
__all__ = ['run_local', 'run_cluster', 'run_ssh',
           'LocalCluster', 'RemoteCluster', 'SSHCluster', 'ClusterApp', ]

# initialize logger
log = Logger.with_name(__name__)


class LocalCluster(Thread):
    """Run server with single local client."""

    server: ServerThread
    client: ClientThread

    def __init__(self: LocalCluster,
                 source: Iterable[str] = None, num_tasks: int = 1, template: str = DEFAULT_TEMPLATE,
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
                 in_memory: bool = False, no_confirm: bool = False,
                 forever_mode: bool = False, restart_mode: bool = False,
                 max_retries: int = DEFAULT_ATTEMPTS, eager: bool = False,
                 redirect_failures: IO = None, redirect_output: IO = None, redirect_errors: IO = None,
                 delay_start: float = DEFAULT_DELAY, capture: bool = False) -> None:
        """Initialize server and client threads."""
        auth = secrets.token_hex(64)
        self.server = ServerThread(source=source, auth=auth, in_memory=in_memory, no_confirm=no_confirm,
                                   bundlesize=bundlesize, bundlewait=bundlewait,
                                   max_retries=max_retries, eager=eager, forever_mode=forever_mode,
                                   restart_mode=restart_mode, redirect_failures=redirect_failures)
        self.client = ClientThread(num_tasks=num_tasks, template=template, auth=auth, no_confirm=no_confirm,
                                   bundlesize=bundlesize, bundlewait=bundlewait, delay_start=delay_start,
                                   redirect_output=redirect_output, redirect_errors=redirect_errors,
                                   capture=capture)
        super().__init__(name='hypershell-cluster')

    def run_with_exceptions(self: LocalCluster) -> None:
        """Start child threads, wait."""
        self.server.start()
        time.sleep(2)  # NOTE: give the server a chance to start
        self.client.start()
        self.client.join()
        self.server.join()

    def stop(self: LocalCluster, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.server.stop(wait=wait, timeout=timeout)
        self.client.stop(wait=wait, timeout=timeout)
        super().stop(wait=wait, timeout=timeout)


class RemoteCluster(Thread):
    """Run server with remote clients via external launcher (e.g., MPI)."""

    server: ServerThread
    clients: Popen
    client_argv: str

    def __init__(self: RemoteCluster,
                 source: Iterable[str] = None, num_tasks: int = 1, template: str = DEFAULT_TEMPLATE,
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
                 forever_mode: bool = False, restart_mode: bool = False,
                 bind: Tuple[str, int] = ('0.0.0.0', QueueConfig.port), delay_start: float = DEFAULT_DELAY,
                 launcher: str = 'mpirun', launcher_args: List[str] = None, remote_exe: str = 'hyper-shell',
                 max_retries: int = DEFAULT_ATTEMPTS, eager: bool = False, redirect_failures: IO = None,
                 in_memory: bool = False, no_confirm: bool = False, capture: bool = False) -> None:
        """Initialize server and client threads."""
        auth = secrets.token_hex(64)
        self.server = ServerThread(source=source, auth=auth, bundlesize=bundlesize, bundlewait=bundlewait,
                                   in_memory=in_memory, no_confirm=no_confirm, max_retries=max_retries, eager=eager,
                                   address=bind, forever_mode=forever_mode, restart_mode=restart_mode,
                                   redirect_failures=redirect_failures)
        launcher_args = '' if launcher_args is None else ' '.join(launcher_args)
        client_args = ''
        if capture is True:
            client_args += ' --capture'
        if no_confirm is True:
            client_args += ' --no-confirm'
        self.client_argv = (f'{launcher} {launcher_args} {remote_exe} client -H {HOSTNAME} -p {bind[1]} '
                            f'-N {num_tasks} -b {bundlesize} -w {bundlewait} -t "{template}" -k {auth} '
                            f'-d {delay_start} {client_args}')
        super().__init__(name='hypershell-cluster')

    def run_with_exceptions(self: RemoteCluster) -> None:
        """Start child threads, wait."""
        self.server.start()
        time.sleep(2)  # NOTE: give the server a chance to start
        log.debug(f'Launching clients: {self.client_argv}')
        self.clients = Popen(self.client_argv, shell=True, stdout=sys.stdout, stderr=sys.stderr,
                             env={**os.environ, **load_task_env()})
        self.clients.wait()
        self.server.join()

    def stop(self: RemoteCluster, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.server.stop(wait=wait, timeout=timeout)
        self.clients.terminate()
        super().stop(wait=wait, timeout=timeout)


class NodeList(list):
    """A list of hostnames."""

    group_pattern: re.Pattern = re.compile(r',(?![^[]*])')
    range_pattern: re.Pattern = re.compile(r'\[((\d+|\d+-\d+)(,(\d+|\d+-\d+))*)]')

    @classmethod
    def from_cmdline(cls: Type[NodeList], arg: str = None) -> NodeList:
        """Smart initialization via some command-line `arg`."""
        if not arg:
            return cls.from_config()
        if ',' in arg or cls.range_pattern.search(arg):
            return cls.from_pattern(arg)
        else:
            return cls([arg, ])

    @classmethod
    def from_config(cls: Type[NodeList], groupname: str = None) -> NodeList:
        """Load list of hostnames from configuration file."""

        if 'ssh' not in config:
            raise ConfigurationError('No `ssh` section found in configuration')
        if 'nodelist' not in config.ssh:
            raise ConfigurationError('No `ssh.nodelist` section found in configuration')

        label = blame(config, 'ssh', 'nodelist')
        if groupname is None:
            if isinstance(config.ssh.nodelist, list):
                return cls(config.ssh.nodelist)
            elif isinstance(config.ssh.nodelist, dict):
                raise ConfigurationError(f'SSH group unspecified but multiple groups in `ssh.nodelist` ({label})')
            else:
                raise ConfigurationError(f'Expected list for `ssh.nodelist` ({label})')

        if isinstance(config.ssh.nodelist, dict):
            if groupname not in config.ssh.nodelist:
                raise ConfigurationError(f'No list \'{groupname}\' found in `ssh.nodelist` section ({label})')
            elif not isinstance(config.ssh.nodelist.get(groupname), list):
                raise ConfigurationError(f'Expected list for `ssh.nodelist.{groupname}` ({label})')
            else:
                return cls(config.ssh.nodelist.get(groupname))
        else:
            raise ConfigurationError(f'Expected either list or section for `ssh.nodelist` ({label})')

    @classmethod
    def from_pattern(cls: Type[NodeList], pattern: str) -> NodeList:
        """Expand a `pattern` to multiple hostnames."""
        pattern = pattern.strip(',')
        if match := cls.group_pattern.search(pattern):
            idx = match.start()
            return cls(cls.from_pattern(pattern[0:idx]) + cls.from_pattern(pattern[idx+1:]))
        else:
            if match := cls.range_pattern.search(pattern):
                range_spec = match.group()
                prefix, suffix = pattern.split(range_spec)
                segments = cls.expand_pattern(range_spec)
                return cls([f'{prefix}{segment}{suffix}' for segment in segments])
            else:
                return cls([pattern, ])

    @staticmethod
    def expand_pattern(spec: str) -> List[str]:
        """Take a range spec (e.g., [4,6-8]) and expand to [4,6,7,8]."""
        spec = spec.strip('[]')
        result = []
        for group in spec.split(','):
            if '-' in group:
                start_chars, stop_chars = group.strip().split('-')
                apply_padding = str if start_chars[0] != '0' else lambda s: str(s).zfill(len(start_chars))
                start, stop = int(start_chars), int(stop_chars)
                if stop < start:
                    start, stop = stop, start
                result.extend([apply_padding(value) for value in range(start, stop + 1)])
            else:
                result.extend([group, ])
        return result


def compile_env() -> str:
    """Build environment variable argument expansion for remote client launch command."""
    return ' '.join([f'{key}="{value}"' for key, value in Namespace.from_env('HYPERSHELL').items()])


class SSHCluster(Thread):
    """Run server with external ssh clients."""

    server: ServerThread
    clients: List[Popen]
    client_argv: List[str]

    def __init__(self: SSHCluster,
                 source: Iterable[str] = None, num_tasks: int = 1, template: str = DEFAULT_TEMPLATE,
                 forever_mode: bool = False, restart_mode: bool = False,
                 bind: Tuple[str, int] = ('0.0.0.0', QueueConfig.port), remote_exe: str = 'hyper-shell',
                 launcher: str = 'ssh', launcher_args: List[str] = None, nodelist: List[str] = None,
                 bundlesize: int = DEFAULT_BUNDLESIZE, bundlewait: int = DEFAULT_BUNDLEWAIT,
                 max_retries: int = DEFAULT_ATTEMPTS, eager: bool = False, in_memory: bool = False,
                 no_confirm: bool = False, redirect_failures: IO = None, export_env: bool = False,
                 delay_start: float = DEFAULT_DELAY, capture: bool = False) -> None:
        """Initialize server and client threads."""
        if nodelist is None:
            raise AttributeError('Expected nodelist')
        auth = secrets.token_hex(64)
        self.server = ServerThread(source=source, auth=auth, bundlesize=bundlesize, bundlewait=bundlewait,
                                   max_retries=max_retries, eager=eager, address=bind,
                                   forever_mode=forever_mode, restart_mode=restart_mode,
                                   in_memory=in_memory, no_confirm=no_confirm,
                                   redirect_failures=redirect_failures)
        launcher_env = '' if not export_env else compile_env()
        if launcher_args is None:
            launcher_args = config.ssh.get('args', '')
        else:
            launcher_args = config.ssh.get('args', '') + ' ' + ' '.join(launcher_args)
        client_args = ''
        if capture is True:
            client_args += ' --capture'
        if no_confirm:
            client_args += ' --no-confirm'
        self.client_argv = [f'{launcher} {launcher_args} {host} {launcher_env} {remote_exe} '
                            f'client -H {HOSTNAME} -p {bind[1]} -N {num_tasks} -b {bundlesize} -w {bundlewait} '
                            f'-t \'"{template}"\' -k {auth} -d {delay_start} {client_args}'
                            for host in nodelist]
        super().__init__(name='hypershell-cluster')

    def run_with_exceptions(self: SSHCluster) -> None:
        """Start child threads, wait."""
        self.server.start()
        time.sleep(2)  # NOTE: give the server a chance to start
        self.clients = []
        for argv in self.client_argv:
            log.debug(f'Launching client: {argv}')
            self.clients.append(Popen(argv, shell=True, stdout=sys.stdout, stderr=sys.stderr))
        for client in self.clients:
            client.wait()
        self.server.join()

    def stop(self: SSHCluster, wait: bool = False, timeout: int = None) -> None:
        """Stop child threads before main thread."""
        self.server.stop(wait=wait, timeout=timeout)
        for client in self.clients:
            client.terminate()
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


def run_ssh(**options) -> None:
    """Run remote ssh cluster until completion."""
    thread = SSHCluster.new(**options)
    try:
        thread.join()
    except Exception:
        thread.stop()
        raise


APP_NAME = 'hyper-shell cluster'
APP_USAGE = f"""\
Usage:
hyper-shell cluster [-h] [FILE | --restart | --forever] [-N NUM] [-t CMD] [-b SIZE] [-w SEC]
                    [-p PORT] [-r NUM [--eager]] [-f PATH] [--capture | [-o PATH] [-e PATH]]
                    [--ssh [HOST... | --ssh-group NAME] [--env] | --mpi | --launcher=ARGS...]
                    [--no-db | --initdb] [--no-confirm] [--delay-start SEC]

Start cluster locally, over SSH, or with a custom launcher.\
"""

APP_HELP = f"""\
{APP_USAGE}

Arguments:
  FILE                        Path to input task file (default: <stdin>).

Modes:
  --ssh              HOST...  Launch directly with SSH host(s).
  --mpi                       Same as --launcher=mpirun.
  --launcher         ARGS...  Use specific launch interface.

Options:
  -N, --num-tasks    NUM      Number of task executors per client (default: {DEFAULT_NUM_TASKS}).
  -t, --template     CMD      Command-line template pattern (default: "{DEFAULT_TEMPLATE}").
  -p, --port         NUM      Port number (default: {QueueConfig.port}).
  -b, --bundlesize   SIZE     Size of task bundle (default: {DEFAULT_BUNDLESIZE}).
  -w, --bundlewait   SEC      Seconds to wait before flushing tasks (default: {DEFAULT_BUNDLEWAIT}).
  -r, --max-retries  NUM      Auto-retry failed tasks (default: {DEFAULT_ATTEMPTS - 1}).
      --eager                 Schedule failed tasks before new tasks.
      --no-db                 Disable database (submit directly to clients).
      --initdb                Auto-initialize database.
      --no-confirm            Disable client confirmation of task bundle received.
      --forever               Schedule forever.
      --restart               Start scheduling from last completed task.
      --ssh-args     ARGS     Command-line arguments for SSH.
      --ssh-group    NAME     SSH nodelist group in config.
  -E, --env                   Send environment variables.
  -d, --delay-start  SEC      Delay time for launching clients (default: {DEFAULT_DELAY}).
  -c, --capture               Capture individual task <stdout> and <stderr>.         
  -o, --output       PATH     File path for task outputs (default: <stdout>).
  -e, --errors       PATH     File path for task errors (default: <stderr>).
  -f, --failures     PATH     File path to write failed task args (default: <none>).
  -h, --help                  Show this message and exit.\
"""


class ClusterApp(Application):
    """Run managed cluster."""

    name = APP_NAME
    interface = Interface(APP_NAME,
                          colorize_usage(APP_USAGE),
                          colorize_usage(APP_HELP))

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

    delay_start: float = DEFAULT_DELAY
    interface.add_argument('-d', '--delay-start', type=float, default=delay_start)

    eager_mode: bool = False
    max_retries: int = DEFAULT_ATTEMPTS - 1
    interface.add_argument('-r', '--max-retries', type=int, default=max_retries)
    interface.add_argument('--eager', action='store_true', dest='eager_mode')

    in_memory: bool = False
    auto_initdb: bool = False
    db_interface = interface.add_mutually_exclusive_group()
    db_interface.add_argument('--no-db', action='store_true', dest='in_memory')
    db_interface.add_argument('--initdb', action='store_true', dest='auto_initdb')

    no_confirm: bool = False
    interface.add_argument('--no-confirm', action='store_true')

    forever_mode: bool = False
    interface.add_argument('--forever', action='store_true', dest='forever_mode')

    restart_mode: bool = False
    interface.add_argument('--restart', action='store_true', dest='restart_mode')

    ssh_mode: str = None
    mpi_mode: bool = False
    launch_mode: str = None
    mode_interface = interface.add_mutually_exclusive_group()
    mode_interface.add_argument('--ssh', nargs='?', const='<default>', default=None, dest='ssh_mode')
    mode_interface.add_argument('--mpi', action='store_true', dest='mpi_mode')
    mode_interface.add_argument('--launcher', default=None, dest='launch_mode')

    ssh_args: str = ''
    interface.add_argument('--ssh-args', default=ssh_args)

    ssh_group: str = None
    interface.add_argument('--ssh-group', default=None)

    remote_exe: str = sys.argv[0]
    interface.add_argument('--remote-exe', default=remote_exe)

    export_env: bool = False
    interface.add_argument('-E', '--env', action='store_true', dest='export_env')

    port: int = QueueConfig.port
    interface.add_argument('-p', '--port', default=port, type=int)

    capture: bool = False
    output_path: str = None
    errors_path: str = None
    interface.add_argument('-o', '--output', default=None, dest='output_path')
    interface.add_argument('-e', '--errors', default=None, dest='errors_path')
    interface.add_argument('-c', '--capture', action='store_true')

    failure_path: str = None
    interface.add_argument('-f', '--failures', default=None, dest='failure_path')

    exceptions = {
        **get_shared_exception_mapping(__name__)
    }

    def run(self: ClusterApp) -> None:
        """Run cluster."""
        launcher = self.launchers.get(self.mode)
        launcher(source=self.source, num_tasks=self.num_tasks, template=self.template,
                 bundlesize=self.bundlesize, bundlewait=self.bundlewait, max_retries=self.max_retries,
                 in_memory=self.in_memory, no_confirm=self.no_confirm, forever_mode=self.forever_mode,
                 restart_mode=self.restart_mode, redirect_failures=self.failure_stream,
                 delay_start=self.delay_start, capture=self.capture)

    def run_local(self: ClusterApp, **options) -> None:
        """Run local cluster."""
        run_local(**options, redirect_output=self.output_stream, redirect_errors=self.errors_stream)

    def run_launch(self: ClusterApp, **options) -> None:
        """Run remote cluster with custom launcher."""
        run_cluster(**options, launcher=self.launch_mode,
                    remote_exe=self.remote_exe, bind=('0.0.0.0', self.port))

    def run_mpi(self: ClusterApp, **options) -> None:
        """Run remote cluster with 'mpirun'."""
        run_cluster(**options, launcher='mpirun',
                    remote_exe=self.remote_exe, bind=('0.0.0.0', self.port))

    def run_ssh(self: ClusterApp, **options) -> None:
        """Run remote cluster with SSH."""
        if self.ssh_group:
            nodelist = NodeList.from_config(self.ssh_group)
        else:
            nodelist = NodeList.from_cmdline(self.ssh_mode if self.ssh_mode != '<default>' else None)
        run_ssh(**options, launcher='ssh', launcher_args=[self.ssh_args, ], nodelist=nodelist,
                remote_exe=self.remote_exe, bind=('0.0.0.0', self.port), export_env=self.export_env)

    @cached_property
    def launchers(self: ClusterApp) -> Dict[str, Callable]:
        """Map of launchers."""
        return {
            'local': self.run_local,
            'launch': self.run_launch,
            'mpi': self.run_mpi,
            'ssh': self.run_ssh
        }

    @cached_property
    def mode(self: ClusterApp) -> str:
        """The launch mode to run the cluster."""
        for name in ['ssh', 'mpi', 'launch']:
            if getattr(self, f'{name}_mode'):
                return name
        else:
            return 'local'

    def check_arguments(self: ClusterApp) -> None:
        """Various checks on input arguments."""
        if self.restart_mode and self.in_memory:
            raise ArgumentError('Cannot restart without database (given --no-db)')
        if self.filepath is None and not self.restart_mode:
            self.filepath = '-'  # NOTE: assume STDIN
        if self.output_path and self.mode != 'local':
            raise ArgumentError('Cannot specify -o/--output PATH with remote clients')
        if self.errors_path and self.mode != 'local':
            raise ArgumentError('Cannot specify -e/--errors PATH with remote clients')
        if self.capture and self.output_path:
            raise ArgumentError('Cannot specify -c/--capture with -o/--output')
        if self.capture and self.errors_path:
            raise ArgumentError('Cannot specify -c/--capture with -e/--error')
        if self.in_memory and self.forever_mode:
            raise ArgumentError('Using --forever with --no-db is invalid')
        if self.in_memory and self.restart_mode:
            raise ArgumentError('Using --restart with --no-db is invalid')
        if self.forever_mode and self.restart_mode:
            raise ArgumentError('Using --forever with --restart is invalid')
        if self.ssh_args and not self.ssh_mode:
            raise ArgumentError('Unexpected --ssh-args when not in --ssh mode')
        if self.ssh_group and self.ssh_mode != '<default>':
            raise ArgumentError('Cannot specify --ssh with target with --ssh-group')

    @cached_property
    def output_stream(self: ClusterApp) -> IO:
        """IO stream to write task outputs."""
        return sys.stdout if not self.output_path else open(self.output_path, mode='w')

    @cached_property
    def errors_stream(self: ClusterApp) -> IO:
        """IO stream to write task errors."""
        return sys.stderr if not self.errors_path else open(self.errors_path, mode='w')

    @cached_property
    def failure_stream(self: ClusterApp) -> Optional[IO]:
        """IO stream to write failed task args."""
        return None if not self.failure_path else open(self.failure_path, mode='w')

    @cached_property
    def input_stream(self: ClusterApp) -> Optional[IO]:
        """IO stream to read task command-line args."""
        if self.restart_mode:
            return None
        else:
            return sys.stdin if self.filepath == '-' else open(self.filepath, mode='r')

    @cached_property
    def source(self: ClusterApp) -> Iterable[str]:
        """Input source for task command-line args."""
        return [] if self.restart_mode else self.input_stream

    def __enter__(self: ClusterApp) -> ClusterApp:
        """Set up resources and attributes."""
        self.check_arguments()
        if config.database.provider == 'sqlite' or self.auto_initdb:
            initdb()  # Auto-initialize if local sqlite provider
        elif not self.in_memory:
            checkdb()
        return self

    def __exit__(self: ClusterApp,
                 exc_type: Optional[Type[Exception]],
                 exc_val: Optional[Exception],
                 exc_tb: Optional[TracebackType]) -> None:
        """Close IO streams if not standard streams."""
        if self.input_stream and self.input_stream is not sys.stdin:
            self.input_stream.close()
        if self.output_stream is not sys.stdout:
            self.output_stream.close()
        if self.errors_stream is not sys.stderr:
            self.errors_stream.close()
        if self.failure_stream:
            self.failure_stream.close()
